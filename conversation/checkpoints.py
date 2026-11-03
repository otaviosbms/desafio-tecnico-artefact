"""Onde o histórico das conversas fica salvo (checkpointer do LangGraph).

Postgres quando o banco do projeto é Postgres (persiste entre reinícios), e memória no
fallback com SQLite.
"""

import atexit
from functools import cache

from django.db import connection
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver


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


@cache
def default_checkpointer() -> BaseCheckpointSaver:
    """Um checkpointer por processo, compartilhado por todos os orquestradores (modelos)."""
    return postgres_checkpointer() if connection.vendor == 'postgresql' else InMemorySaver()
