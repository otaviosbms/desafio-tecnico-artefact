"""Handler central: fila na frente dos sinks, para nenhum destino lento travar a requisição."""

import atexit
import copy
import logging
import logging.handlers
import queue

from .context import ContextFilter
from .sinks import build_sinks


class CentralHandler(logging.handlers.QueueHandler):
    """Recebe todos os logs (fica no root) e entrega aos sinks numa thread separada.

    `sinks`: nomes registrados em `sinks.py` (ex.: ['console', 'file']).
    """

    def __init__(self, sinks: list[str] | str = ('console',)):
        if isinstance(sinks, str):
            sinks = [s.strip() for s in sinks.split(',') if s.strip()]
        super().__init__(queue.SimpleQueue())
        self.addFilter(ContextFilter())
        self.sinks = build_sinks(list(sinks))
        self.listener = logging.handlers.QueueListener(self.queue, *self.sinks, respect_handler_level=True)
        self.listener.start()
        atexit.register(self.close)  # esvazia a fila antes de o processo sair

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # O padrão do QueueHandler formata a mensagem aqui e descarta o traceback. A fila é em memória
        # (sem pickle), então basta resolver os argumentos e manter o resto para os sinks formatarem.
        record = copy.copy(record)
        record.msg, record.args = record.getMessage(), None
        return record

    def close(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        super().close()
