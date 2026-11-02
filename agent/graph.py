"""Grafo do agente (LangGraph): nó do LLM <-> nó de ferramentas.

    START -> agent --(pediu ferramentas?)--> tools -> agent ... -> END

O estado guarda só as mensagens da conversa (formato da API de Chat Completions).
O system prompt não é salvo: é montado a cada chamada, com a data/hora do momento.
"""

import json
import logging
import operator
import time
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from llm import LLMClient, LLMError, Message, tool_result_message

from . import clock
from .prompts import build_system_prompt
from .tools import Tool, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4  # rodadas de ferramentas por mensagem do cliente
MAX_HISTORY_MESSAGES = 40  # mensagens anteriores enviadas ao LLM

FALLBACK_REPLY = (
    'Desculpa, tive um problema técnico para responder agora. Você pode tentar de novo em instantes '
    'ou falar com a nossa equipe pelo WhatsApp (67) 3341-4444.'
)


class AgentState(TypedDict):
    messages: Annotated[list[Message], operator.add]
    tool_rounds: int
    # Eventos de execução (chamadas ao LLM e às ferramentas) para o inspetor da UI.
    # Ficam fora de `messages`, então nunca são enviados ao LLM.
    trace: Annotated[list[dict], operator.add]


def trim_history(messages: list[Message], limit: int = MAX_HISTORY_MESSAGES) -> list[Message]:
    """Últimas `limit` mensagens, começando sempre numa mensagem do cliente.

    Cortar no meio de uma rodada de ferramentas deixaria mensagens `tool` sem a
    chamada correspondente, o que os provedores rejeitam.
    """
    if len(messages) <= limit:
        return messages
    recent = messages[-limit:]
    for i, message in enumerate(recent):
        if message['role'] == 'user':
            return recent[i:]
    return messages[-1:]


def _turn(state: AgentState) -> int:
    return sum(1 for m in state['messages'] if m['role'] == 'user')


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def build_graph(llm: LLMClient, tools: list[Tool], now: Callable[[], datetime] = clock.now):
    definitions = [tool.definition() for tool in tools]

    def current_time(config: RunnableConfig) -> datetime:
        # Data/hora simulada vem na config da execução (ver StoreAgent.reply).
        return clock.parse(config.get('configurable', {}).get('agora')) or now()

    def agent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        system = build_system_prompt(current_time(config))
        messages = [{'role': 'system', 'content': system}, *trim_history(state['messages'])]
        # Esgotou as rodadas: pede uma resposta final sem ferramentas.
        allow_tools = state.get('tool_rounds', 0) < MAX_TOOL_ROUNDS
        event = {'turno': _turn(state), 'tipo': 'llm', 'modelo': llm.config.model, 'com_ferramentas': allow_tools}
        start = time.perf_counter()
        try:
            response = llm.chat(messages, tools=definitions if allow_tools else None)
        except LLMError as exc:
            logger.exception('Falha ao chamar o LLM')
            event.update(duracao_ms=_ms(start), erro=str(exc))
            return {'messages': [{'role': 'assistant', 'content': FALLBACK_REPLY}], 'trace': [event]}
        event.update(
            duracao_ms=_ms(start),
            tokens=response.usage,
            finish_reason=response.finish_reason,
            pediu_ferramentas=[call.name for call in response.tool_calls],
        )
        if not response.tool_calls and not (response.content or '').strip():
            event['erro'] = 'Resposta vazia do modelo.'
            return {'messages': [{'role': 'assistant', 'content': FALLBACK_REPLY}], 'trace': [event]}
        return {'messages': [response.to_message()], 'trace': [event]}

    def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        results, events = [], []
        with clock.frozen(clock.parse(config.get('configurable', {}).get('agora'))):
            for call in state['messages'][-1]['tool_calls']:
                name, raw = call['function']['name'], call['function']['arguments']
                start = time.perf_counter()
                try:
                    arguments = json.loads(raw or '{}')
                    result = execute_tool(name, arguments, tools)
                except ValueError as exc:
                    arguments, result = raw, {'erro': f'Argumentos em JSON inválido: {exc}'}
                logger.info('Ferramenta %s(%s)', name, raw)
                results.append(tool_result_message(call['id'], result))
                events.append({
                    'turno': _turn(state), 'tipo': 'ferramenta', 'nome': name,
                    'argumentos': arguments, 'resultado': result, 'duracao_ms': _ms(start),
                })
        return {'messages': results, 'tool_rounds': state.get('tool_rounds', 0) + 1, 'trace': events}

    def route(state: AgentState) -> str:
        return 'tools' if state['messages'][-1].get('tool_calls') else END

    graph = StateGraph(AgentState)
    graph.add_node('agent', agent)
    graph.add_node('tools', run_tools)
    graph.add_edge(START, 'agent')
    graph.add_conditional_edges('agent', route, ['tools', END])
    graph.add_edge('tools', 'agent')
    return graph
