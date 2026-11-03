"""Eventos estruturados por categoria.

Cada evento é um registro no logger `emporio.events`: a mensagem é o nome do evento e os campos
vão em `record.event`, sempre com `turn_id` e `thread_id` do turno atual. O centralizador
(core/observability) junta esses campos ao JSON de saída, igual para todos os sinks.
"""

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
    HTTP = 'HTTP'  # requisições HTTP (status e duração)
    TOOL = 'TOOL'  # execução de cada ferramenta (duração, resultado)
    AUDIT = 'AUDIT'  # acesso a dados pessoais (consulta de pedido), sem gravar o dado em si
    SYSTEM = 'SYSTEM'  # subida e configuração dos componentes, carga de dados, comandos


LEVELS = {
    LogCategory.DEGRADATION: logging.WARNING,
    LogCategory.SILENT_FAILURE: logging.WARNING,
}


def log_event(name: str, category: LogCategory, *, level: int | None = None, **fields) -> dict:
    """`level` sobrescreve o nível padrão da categoria (ex.: um evento de AUDIT que merece WARNING)."""
    context = turn_context.current()
    event = {
        'event': name,
        'category': str(category),
        'turn_id': context.turn_id if context else None,
        'thread_id': context.thread_id if context else None,
        **fields,
    }
    logger.log(level or LEVELS.get(category, logging.INFO), name, extra={'event': event})
    return event
