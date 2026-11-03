"""Centralizador de logs: todo log da aplicação passa por um único caminho.

    logger (qualquer um: emporio.events, llm, django, conversation, ...)
      └─ root ─► CentralHandler (fila, não bloqueia a requisição)
                   └─ thread do QueueListener ─► sinks (console, file, ... kafka, newrelic)

- **Um formato** (`JsonFormatter`): cada log vira um objeto JSON com timestamp, nível, logger,
  serviço, ambiente e o contexto da execução (`request_id`, `turn_id`, `thread_id`), injetado pelo
  `ContextFilter` antes de entrar na fila.
- **Sinks plugáveis** (`sinks.py`): `LOG_SINKS=console,file` no .env. Um destino novo (Kafka, New
  Relic, ...) é um `logging.Handler` registrado com `register_sink`; nada mais muda.

Configurado pelo LOGGING do Django (config/settings.py).
"""

from .context import ContextFilter, bind_request, current_request_id
from .formatter import JsonFormatter
from .handler import CentralHandler
from .sinks import SINKS, build_sinks, register_sink

__all__ = [
    'SINKS',
    'CentralHandler',
    'ContextFilter',
    'JsonFormatter',
    'bind_request',
    'build_sinks',
    'current_request_id',
    'register_sink',
]
