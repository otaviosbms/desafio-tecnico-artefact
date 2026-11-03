"""Formato único dos logs: uma linha JSON por registro."""

import json
import logging
import os
from datetime import UTC, datetime

SERVICE = os.getenv('SERVICE_NAME', 'emporio-agente')
ENVIRONMENT = os.getenv('APP_ENV', 'local')


def to_dict(record: logging.LogRecord) -> dict:
    """O registro como dict, no formato comum a todos os sinks.

    Eventos do `log_event` (core/logging.py) trazem os campos em `record.event`; eles vão para o
    nível de cima (event, category, caller, tokens, ...).
    """
    data = {
        'timestamp': datetime.fromtimestamp(record.created, UTC).isoformat(timespec='milliseconds'),
        'level': record.levelname,
        'logger': record.name,
        'message': record.getMessage(),
        'service': SERVICE,
        'environment': ENVIRONMENT,
        'request_id': getattr(record, 'request_id', None),
        'turn_id': getattr(record, 'turn_id', None),
        'thread_id': getattr(record, 'thread_id', None),
    }
    event = getattr(record, 'event', None)
    if isinstance(event, dict):
        data.update(event)
    if record.exc_info:
        data['exception'] = logging.Formatter().formatException(record.exc_info)
    return data


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(to_dict(record), ensure_ascii=False, default=str)
