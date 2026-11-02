"""Relógio do agente, com suporte a data/hora simulada (para testes na UI).

Tudo que depende de "agora" (horário da loja, prazos de pedidos, system prompt) lê
daqui. O ambiente de testes pode congelar o relógio numa data para simular, por
exemplo, a loja aberta ou um pedido ainda dentro do prazo de devolução.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime

from django.utils import timezone

_frozen: ContextVar[datetime | None] = ContextVar('agent_frozen_now', default=None)


def now() -> datetime:
    return _frozen.get() or timezone.localtime()


def today() -> date:
    return now().date()


@contextmanager
def frozen(moment: datetime | None):
    """Congela o relógio em `moment` dentro do bloco (None = relógio real)."""
    token = _frozen.set(moment)
    try:
        yield
    finally:
        _frozen.reset(token)


def parse(value: str | None) -> datetime | None:
    """Converte '2026-11-02T10:00' (datetime-local) em datetime no fuso da loja."""
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return timezone.make_aware(moment) if timezone.is_naive(moment) else timezone.localtime(moment)
