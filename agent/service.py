"""Ponto de entrada do agente para a UI e o CLI.

Cada conversa é uma `thread_id`. O histórico fica no checkpointer do LangGraph:
Postgres quando o banco do projeto é Postgres (persiste entre reinícios), e memória
no fallback com SQLite.
"""

import atexit
import json
from dataclasses import dataclass, field
from functools import cache

from django.db import connection
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from llm import LLMClient

from .graph import build_graph
from .tools import Tool, get_tools


@dataclass
class AgentReply:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # [{'nome': ..., 'argumentos': {...}}]


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


def default_checkpointer() -> BaseCheckpointSaver:
    return postgres_checkpointer() if connection.vendor == 'postgresql' else InMemorySaver()


class StoreAgent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        tools: list[Tool] | None = None,
        **graph_kwargs,
    ):
        self.graph = build_graph(llm or LLMClient(), tools or get_tools(), **graph_kwargs).compile(
            checkpointer=checkpointer or default_checkpointer()
        )

    def _config(self, thread_id: str) -> dict:
        return {'configurable': {'thread_id': thread_id}}

    def _messages(self, thread_id: str) -> list[dict]:
        state = self.graph.get_state(self._config(thread_id))
        return state.values.get('messages', []) if state.values else []

    def reply(self, thread_id: str, text: str) -> AgentReply:
        before = len(self._messages(thread_id))
        result = self.graph.invoke(
            {'messages': [{'role': 'user', 'content': text}], 'tool_rounds': 0},
            self._config(thread_id),
        )
        new_messages = result['messages'][before:]
        tool_calls = [
            {'nome': call['function']['name'], 'argumentos': _parse_arguments(call['function']['arguments'])}
            for message in new_messages
            for call in message.get('tool_calls') or []
        ]
        return AgentReply(text=result['messages'][-1]['content'], tool_calls=tool_calls)

    def history(self, thread_id: str) -> list[dict]:
        """Mensagens visíveis da conversa (cliente e assistente, sem as ferramentas)."""
        return [
            {'role': m['role'], 'content': m['content']}
            for m in self._messages(thread_id)
            if m['role'] in ('user', 'assistant') and m.get('content')
        ]


@cache
def get_agent() -> StoreAgent:
    """Instância única por processo (reaproveita o pool de conexões e os schemas)."""
    return StoreAgent()
