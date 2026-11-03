"""Grafo do turno (LangGraph): guardrails, roteador de intenção, agente <-> ferramentas.

    START -> guardrails --(bloqueio duro?)--> respond_blocked ----------------------> finalize -> END
                 |                                                                      ^
                 v                                                                      |
              router -> agent --(pediu ferramentas?)--> tools -> agent ... --(resposta)-+

O guardrails pode barrar a mensagem ou mandar uma orientação ao agente (ver guardrails/); o
roteador decide quais ferramentas o agente recebe nesta mensagem (ver router/); o finalize
registra a decisão final do turno (transferência para a equipe e uso de LLM).

As mensagens ficam no formato da API de Chat Completions. O system prompt não é salvo: é
montado a cada chamada, com a data/hora do momento. Os modos dos estágios e a data simulada
podem vir na config da execução (`configurable`), por mensagem.
"""

import logging
import operator
import time
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from core import clock
from core import turn_context
from core.logging import LogCategory, log_event
from guardrails.responses import TOO_MANY_BLOCKS_REPLY, blocked_reply
from guardrails.service import Guardrails
from llm import LLMCall, LLMService, Message, tool_result_message
from router.service import IntentRouter
from tools import registry
from tools.contracts import ToolContext
from tools.executor import ToolExecutor

from .prompts import build_system_prompt

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
    # Decisões do turno (guardrails, roteador, transferência, final), com o nº do turno.
    decisions: Annotated[list[dict], operator.add]
    # Ferramentas liberadas pelo roteador para a mensagem atual (None = todas).
    allowed_tools: list[str] | None
    # Intenções que restringiram as ferramentas nesta mensagem (só em enforce), para o prompt.
    intents: list[str] | None
    # Orientação do guardrails para o agente nesta mensagem (bloqueio leve / caso para a equipe).
    guidance: str | None
    # Esta mensagem vai para o respond_blocked (bloqueio duro ou bloqueios demais em série)?
    blocked: bool
    # Bloqueios seguidos nesta conversa (persiste entre mensagens; zera quando uma passa).
    consecutive_blocks: int


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


def _llm_event(turn: int, call: LLMCall, **fields) -> dict:
    event = {
        'turno': turn, 'tipo': 'llm', 'caller': call.caller, 'modelo': call.model,
        'duracao_ms': call.duration_ms, 'custo_usd': str(call.cost_usd), **fields,
    }
    if call.ok:
        event.update(tokens=call.response.usage, finish_reason=call.response.finish_reason)
    if call.error:
        event['erro'] = call.error
    return event


def _option(config: RunnableConfig, name: str):
    return (config or {}).get('configurable', {}).get(name)


def _last_assistant_text(messages: list[Message]) -> str | None:
    """Última resposta do assistente antes da mensagem atual do cliente."""
    return next((m['content'] for m in reversed(messages[:-1]) if m['role'] == 'assistant' and m.get('content')),
                None)


def build_graph(llm: LLMService, now: Callable[[], datetime] = clock.now, executor: ToolExecutor | None = None,
                router: IntentRouter | None = None, guardrails: Guardrails | None = None):
    all_definitions = registry.definitions()
    executor = executor or ToolExecutor()
    router = router or IntentRouter(llm)
    guardrails = guardrails or Guardrails(llm)

    def current_time(config: RunnableConfig) -> datetime:
        # Data/hora simulada vem na config da execução (ver ConversationOrchestrator.run_turn).
        return clock.parse(_option(config, 'agora')) or now()

    def check_guardrails(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        turn = _turn(state)
        previous = [m for m in state['messages'][:-1] if m['role'] in ('user', 'assistant') and m.get('content')][-2:]
        decision = guardrails.evaluate(state['messages'][-1]['content'] or '', previous,
                                       mode=_option(config, 'guardrails_mode'))
        blocked = decision.applied and not decision.allowed
        blocks = state.get('consecutive_blocks', 0) + 1 if blocked else 0
        record = {'turno': turn, 'estagio': 'guardrails', **decision.as_dict(), 'bloqueios_seguidos': blocks}
        events = [_llm_event(turn, call, com_ferramentas=False) for call in decision.llm_calls]
        events.append({'tipo': 'decisao', **record})
        decisions = [record]
        if decision.applied and decision.requires_human:
            decisions.append({'turno': turn, 'estagio': 'transferencia', 'motivo': decision.category})
            log_event('human_handoff', LogCategory.DECISION, reason=decision.category)
        return {
            'guidance': decision.agent_guidance,
            'consecutive_blocks': blocks,
            'decisions': decisions,
            'trace': events,
            # Para o desvio do grafo: bloqueio duro, ou bloqueios demais em série.
            'blocked': decision.hard_block or blocks >= guardrails.max_consecutive_blocks,
        }

    def respond_blocked(state: AgentState) -> dict[str, Any]:
        turn = _turn(state)
        last = next(d for d in reversed(state['decisions']) if d['estagio'] == 'guardrails')
        too_many = state.get('consecutive_blocks', 0) >= guardrails.max_consecutive_blocks
        if too_many:
            reply = TOO_MANY_BLOCKS_REPLY
            log_event('human_handoff', LogCategory.DECISION, reason='consecutive_blocks')
        else:
            reply = blocked_reply(last['categoria'], last['requer_humano'])
        update = {
            'messages': [{'role': 'assistant', 'content': reply}],
            'trace': [{'turno': turn, 'tipo': 'bloqueio', 'motivo': 'bloqueios_seguidos' if too_many
                       else last['categoria'], 'resposta': reply}],
        }
        if too_many:
            update['consecutive_blocks'] = 0
            update['decisions'] = [{'turno': turn, 'estagio': 'transferencia', 'motivo': 'bloqueios_seguidos'}]
        return update

    def after_guardrails(state: AgentState) -> str:
        return 'respond_blocked' if state.get('blocked') else 'router'

    def route_intent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        turn = _turn(state)
        decision = router.classify(state['messages'][-1]['content'] or '', _last_assistant_text(state['messages']),
                                   mode=_option(config, 'router_mode'))
        events = [_llm_event(turn, call, com_ferramentas=False) for call in decision.llm_calls]
        events.append({'turno': turn, 'tipo': 'decisao', 'estagio': 'router', **decision.as_dict()})
        return {
            'allowed_tools': decision.allowed_tools,
            'intents': decision.intents if decision.restricted else None,
            'decisions': [{'turno': turn, 'estagio': 'router', **decision.as_dict()}],
            'trace': events,
        }

    def agent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        allowed = state.get('allowed_tools')
        system = build_system_prompt(current_time(config), guidance=state.get('guidance'),
                                     intents=state.get('intents'), allowed_tools=allowed)
        messages = [{'role': 'system', 'content': system}, *trim_history(state['messages'])]
        definitions = all_definitions if allowed is None else [
            d for d in all_definitions if d['function']['name'] in allowed
        ]
        # Esgotou as rodadas (ou o roteador não liberou nada): resposta sem ferramentas.
        allow_tools = state.get('tool_rounds', 0) < MAX_TOOL_ROUNDS and bool(definitions)
        call = llm.chat(caller='agent.respond', role='agent', messages=messages,
                        tools=definitions if allow_tools else None)
        event = _llm_event(_turn(state), call, com_ferramentas=allow_tools,
                           ferramentas_oferecidas=None if allowed is None else [d['function']['name']
                                                                                 for d in definitions])
        if not call.ok:
            logger.error('Falha ao chamar o LLM: %s', call.error)
            log_event('fallback_reply', LogCategory.DEGRADATION, stage='agent', reason='llm_error')
            return {'messages': [{'role': 'assistant', 'content': FALLBACK_REPLY}], 'trace': [event]}
        response = call.response
        event['pediu_ferramentas'] = [tool_call.name for tool_call in response.tool_calls]
        if not response.tool_calls and not (response.content or '').strip():
            event['erro'] = 'Resposta vazia do modelo.'
            log_event('fallback_reply', LogCategory.DEGRADATION, stage='agent', reason='empty_response')
            return {'messages': [{'role': 'assistant', 'content': FALLBACK_REPLY}], 'trace': [event]}
        return {'messages': [response.to_message()], 'trace': [event]}

    def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        turn = turn_context.current()
        ctx = ToolContext(
            now=current_time(config),
            thread_id=config.get('configurable', {}).get('thread_id', ''),
            turn_id=turn.turn_id if turn else '',
        )
        results, events = [], []
        for call in state['messages'][-1]['tool_calls']:
            name, raw = call['function']['name'], call['function']['arguments']
            start = time.perf_counter()
            result = executor.run(name, raw, ctx, allowed=state.get('allowed_tools'))
            payload = result.to_model_payload()
            results.append(tool_result_message(call['id'], payload))
            event = {
                'turno': _turn(state), 'tipo': 'ferramenta', 'nome': name,
                'argumentos': result.meta.get('arguments', raw), 'resultado': payload, 'duracao_ms': _ms(start),
            }
            if result.error:
                event['codigo_erro'] = result.error
            events.append(event)
        return {'messages': results, 'tool_rounds': state.get('tool_rounds', 0) + 1, 'trace': events}

    def route(state: AgentState) -> str:
        return 'tools' if state['messages'][-1].get('tool_calls') else 'finalize'

    def finalize(state: AgentState) -> dict[str, Any]:
        turn_number = _turn(state)
        this_turn = [d for d in state.get('decisions', []) if d.get('turno') == turn_number]
        transfer = next((d['motivo'] for d in this_turn if d['estagio'] == 'transferencia'), None)
        turn = turn_context.current()
        record = {
            'turno': turn_number, 'estagio': 'final', 'transferencia': transfer is not None, 'motivo': transfer,
            'bloqueada': state.get('blocked', False), 'uso': turn.summary() if turn else None,
        }
        log_event('turn_decided', LogCategory.DECISION, transfer=record['transferencia'], reason=transfer,
                  blocked=record['bloqueada'])
        return {'decisions': [record]}

    graph = StateGraph(AgentState)
    graph.add_node('guardrails', check_guardrails)
    graph.add_node('respond_blocked', respond_blocked)
    graph.add_node('router', route_intent)
    graph.add_node('agent', agent)
    graph.add_node('tools', run_tools)
    graph.add_node('finalize', finalize)
    graph.add_edge(START, 'guardrails')
    graph.add_conditional_edges('guardrails', after_guardrails, ['respond_blocked', 'router'])
    graph.add_edge('respond_blocked', 'finalize')
    graph.add_edge('router', 'agent')
    graph.add_conditional_edges('agent', route, ['tools', 'finalize'])
    graph.add_edge('finalize', END)
    graph.add_edge('tools', 'agent')
    return graph
