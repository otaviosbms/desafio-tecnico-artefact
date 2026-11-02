"""Ponto de entrada do agente para a UI e o CLI.

Cada conversa é uma `thread_id`. O histórico fica no checkpointer do LangGraph:
Postgres quando o banco do projeto é Postgres (persiste entre reinícios), e memória
no fallback com SQLite.
"""

import atexit
import dataclasses
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache

from django.db import connection
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from llm import LLMClient, LLMConfig

from .graph import build_graph
from .tools import Tool, get_tools


@dataclass
class AgentReply:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # [{'nome': ..., 'argumentos': {...}}]
    trace: list[dict] = field(default_factory=list)  # eventos deste turno (LLM e ferramentas)
    duration_ms: int = 0


def _parse_arguments(raw: str | None):
    try:
        return json.loads(raw or '{}')
    except ValueError:
        return raw


def postgres_checkpointer() -> BaseCheckpointSaver:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.conninfo import make_conninfo
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    db = connection.settings_dict
    conninfo = make_conninfo(
        dbname=db['NAME'], user=db['USER'], password=db['PASSWORD'],
        host=db['HOST'] or 'localhost', port=db['PORT'] or 5432,
    )
    pool = ConnectionPool(
        conninfo,
        max_size=5,
        kwargs={'autocommit': True, 'prepare_threshold': 0, 'row_factory': dict_row},
        open=True,
    )
    atexit.register(pool.close)  # fecha as conexões antes do interpretador encerrar
    saver = PostgresSaver(pool)
    saver.setup()  # cria/atualiza as tabelas de checkpoint (idempotente)
    return saver


@cache
def default_checkpointer() -> BaseCheckpointSaver:
    """Um checkpointer por processo, compartilhado por todos os agentes (modelos)."""
    return postgres_checkpointer() if connection.vendor == 'postgresql' else InMemorySaver()


class StoreAgent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        tools: list[Tool] | None = None,
        **graph_kwargs,
    ):
        self.llm = llm or LLMClient()
        self.graph = build_graph(self.llm, tools or get_tools(), **graph_kwargs).compile(
            checkpointer=checkpointer or default_checkpointer()
        )

    def _config(self, thread_id: str) -> dict:
        return {'configurable': {'thread_id': thread_id}}

    def _state(self, thread_id: str) -> dict:
        return self.graph.get_state(self._config(thread_id)).values or {}

    def _messages(self, thread_id: str) -> list[dict]:
        return self._state(thread_id).get('messages', [])

    def reply(self, thread_id: str, text: str, now: datetime | None = None) -> AgentReply:
        """Responde a mensagem. `now` simula a data/hora (padrão: relógio real)."""
        state = self._state(thread_id)
        before_messages, before_trace = len(state.get('messages', [])), len(state.get('trace', []))
        config = self._config(thread_id)
        if now:
            config['configurable']['agora'] = now.isoformat()

        start = time.perf_counter()
        result = self.graph.invoke(
            {'messages': [{'role': 'user', 'content': text}], 'tool_rounds': 0},
            config,
        )
        new_messages = result['messages'][before_messages:]
        tool_calls = [
            {'nome': call['function']['name'], 'argumentos': _parse_arguments(call['function']['arguments'])}
            for message in new_messages
            for call in message.get('tool_calls') or []
        ]
        return AgentReply(
            text=result['messages'][-1]['content'],
            tool_calls=tool_calls,
            trace=result.get('trace', [])[before_trace:],
            duration_ms=round((time.perf_counter() - start) * 1000),
        )

    def trace(self, thread_id: str) -> list[dict]:
        """Todos os eventos de execução da conversa (campo `turno` = nº da mensagem do cliente)."""
        return self._state(thread_id).get('trace', [])

    def history(self, thread_id: str) -> list[dict]:
        """Mensagens visíveis da conversa (cliente e assistente, sem as ferramentas)."""
        return [
            {'role': m['role'], 'content': m['content']}
            for m in self._messages(thread_id)
            if m['role'] in ('user', 'assistant') and m.get('content')
        ]


@cache
def get_agent(model: str | None = None, temperature: float | None = None) -> StoreAgent:
    """Um agente por (modelo, temperatura) por processo; todos compartilham o histórico.

    Sem argumentos, usa o modelo do .env. O provedor (URL e chave) é sempre o do .env:
    a UI de testes troca apenas o modelo e a temperatura.
    """
    if model is None and temperature is None:
        return StoreAgent()
    base = LLMConfig.from_env()
    config = dataclasses.replace(
        base,
        model=model or base.model,
        temperature=base.temperature if temperature is None else temperature,
    )
    return StoreAgent(llm=LLMClient(config))
