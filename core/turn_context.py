"""Contexto de um turno (uma mensagem do cliente e tudo que ela dispara).

Fica num `ContextVar`, então qualquer camada (grafo, LLM, ferramentas) lê o turno atual
sem recebê-lo por parâmetro. Os logs estruturados usam o `turn_id` para agrupar os eventos.
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

TOKEN_KEYS = ('prompt_tokens', 'completion_tokens', 'total_tokens')


@dataclass
class TurnContext:
    thread_id: str
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: datetime = field(default_factory=timezone.now)
    llm_calls: int = 0
    tokens: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TOKEN_KEYS, 0))
    cost_usd: Decimal = Decimal(0)
    _start: float = field(default_factory=time.perf_counter, repr=False)

    def elapsed_ms(self) -> int:
        return round((time.perf_counter() - self._start) * 1000)

    def summary(self) -> dict:
        return {
            'duration_ms': self.elapsed_ms(),
            'llm_calls': self.llm_calls,
            'tokens': dict(self.tokens),
            'cost_usd': str(self.cost_usd),
        }


_current: ContextVar[TurnContext | None] = ContextVar('turn_context', default=None)


def current() -> TurnContext | None:
    return _current.get()


@contextmanager
def start_turn(thread_id: str) -> Iterator[TurnContext]:
    """Abre um turno novo para `thread_id` dentro do bloco."""
    context = TurnContext(thread_id=thread_id)
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def add_llm_usage(usage: dict | None, cost: Decimal = Decimal(0)) -> None:
    """Soma uma chamada ao LLM no turno atual (sem turno aberto, não faz nada)."""
    context = current()
    if context is None:
        return
    context.llm_calls += 1
    for key in TOKEN_KEYS:
        context.tokens[key] += (usage or {}).get(key) or 0
    context.cost_usd += cost
