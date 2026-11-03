"""Contexto da execução que vai em todo log: requisição HTTP e turno da conversa."""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from .. import turn_context

_request_id: ContextVar[str | None] = ContextVar('request_id', default=None)


def current_request_id() -> str | None:
    return _request_id.get()


@contextmanager
def bind_request(request_id: str | None = None) -> Iterator[str]:
    """Marca os logs desta execução com um `request_id` (recebido no X-Request-ID ou novo)."""
    request_id = request_id or uuid.uuid4().hex[:16]
    token = _request_id.set(request_id)
    try:
        yield request_id
    finally:
        _request_id.reset(token)


class ContextFilter(logging.Filter):
    """Copia o contexto para o registro. Roda na thread de quem logou, antes da fila: depois, na
    thread do listener, os ContextVars já não existem."""

    def filter(self, record: logging.LogRecord) -> bool:
        turn = turn_context.current()
        if not hasattr(record, 'request_id'):
            # O Django registra a resposta (django.request) depois do middleware; o id fica no request.
            request = getattr(record, 'request', None)
            record.request_id = current_request_id() or getattr(request, 'request_id', None)
        if not hasattr(record, 'turn_id'):
            record.turn_id = turn.turn_id if turn else None
        if not hasattr(record, 'thread_id'):
            record.thread_id = turn.thread_id if turn else None
        return True
