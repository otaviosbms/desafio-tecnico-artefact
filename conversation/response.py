"""Envelope JSON da API de mensagens, montado a partir do `TurnResult`."""

from .orchestrator import TurnResult


def to_api(result: TurnResult) -> dict:
    return {
        'resposta': result.text,
        'ferramentas': result.tool_calls,
        'rastro': result.trace,
        'decisoes': result.decisions,
        'uso': result.usage,
        'transferencia': result.transfer,
        'duracao_ms': result.duration_ms,
        'modelo': result.model,
    }
