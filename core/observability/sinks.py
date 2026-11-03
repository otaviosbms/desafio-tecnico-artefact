"""Destinos dos logs (sinks). Cada um é um `logging.Handler` comum.

Escolhidos no .env: `LOG_SINKS=console,file`. Para um destino novo (ex.: Kafka, New Relic), basta
registrar uma fábrica que devolva um Handler, num módulo importado na subida (ex.: `apps.py`):

    @register_sink('kafka')
    def kafka_sink() -> logging.Handler:
        return KafkaLogHandler(topic=os.getenv('LOG_KAFKA_TOPIC', 'emporio-logs'))

O handler recebe registros já com o contexto e formata com `JsonFormatter` (ou usa `to_dict` para
mandar o dict). Ver docs/09-observabilidade-e-testes.md.
"""

import logging
import logging.handlers
import os
import sys
from collections.abc import Callable
from pathlib import Path

from .formatter import JsonFormatter

SinkFactory = Callable[[], logging.Handler]
SINKS: dict[str, SinkFactory] = {}


def register_sink(name: str) -> Callable[[SinkFactory], SinkFactory]:
    def decorator(factory: SinkFactory) -> SinkFactory:
        SINKS[name] = factory
        return factory
    return decorator


@register_sink('console')
def console_sink() -> logging.Handler:
    """stdout: o padrão de containers (docker compose logs, coletores como Fluent Bit e Vector)."""
    return logging.StreamHandler(sys.stdout)


@register_sink('file')
def file_sink() -> logging.Handler:
    """Arquivo JSON Lines com rotação (LOG_FILE, padrão logs/app.jsonl), para um agente de coleta."""
    path = Path(os.getenv('LOG_FILE', 'logs/app.jsonl'))
    path.parent.mkdir(parents=True, exist_ok=True)
    return logging.handlers.RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8')


def build_sinks(names: list[str]) -> list[logging.Handler]:
    """Handlers dos sinks pedidos, já com o formato JSON. Nome desconhecido vira aviso, não erro."""
    handlers = []
    for name in names:
        factory = SINKS.get(name)
        if factory is None:
            print(f'[observability] sink desconhecido ignorado: {name!r}. Disponíveis: {sorted(SINKS)}',
                  file=sys.stderr)
            continue
        handler = factory()
        if handler.formatter is None:
            handler.setFormatter(JsonFormatter())
        handlers.append(handler)
    return handlers
