"""Logs estruturados por categoria.

Cada evento é uma linha JSON no logger `emporio.events`, sempre com `turn_id` e
`thread_id` do turno atual. Os campos também vão em `record.event`, para testes e
handlers que queiram o dict sem reparsear o JSON.
"""

import json
import logging
from enum import StrEnum

from . import turn_context

logger = logging.getLogger('emporio.events')


class LogCategory(StrEnum):
    LIFECYCLE = 'LIFECYCLE'  # início e fim do turno
    LLM_CALL = 'LLM_CALL'  # cada chamada ao LLM
    DECISION = 'DECISION'  # decisões do pipeline (guardrails, intenção, ferramentas liberadas)
    DEGRADATION = 'DEGRADATION'  # um estágio usou fallback
    SILENT_FAILURE = 'SILENT_FAILURE'  # erro que não interrompe o turno


LEVELS = {
    LogCategory.DEGRADATION: logging.WARNING,
    LogCategory.SILENT_FAILURE: logging.WARNING,
}


def log_event(name: str, category: LogCategory, **fields) -> dict:
    context = turn_context.current()
    event = {
        'event': name,
        'category': str(category),
        'turn_id': context.turn_id if context else None,
        'thread_id': context.thread_id if context else None,
        **fields,
    }
    logger.log(
        LEVELS.get(category, logging.INFO),
        json.dumps(event, ensure_ascii=False, default=str),
        extra={'event': event},
    )
    return event
