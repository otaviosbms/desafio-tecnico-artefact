"""Executa uma chamada de ferramenta pedida pelo modelo. Nunca lança exceção.

| Situação                       | `ToolResult.error`  | Log              |
|--------------------------------|---------------------|------------------|
| Ferramenta não registrada      | `tool_not_found`    | `SILENT_FAILURE` |
| Não liberada para a mensagem   | `tool_not_allowed`  | `SILENT_FAILURE` |
| JSON inválido / fora do schema | `tool_invalid_args` | `SILENT_FAILURE` |
| Exceção no handler             | `tool_failed`       | `SILENT_FAILURE` |

O erro volta ao modelo como {"erro": ...}, para ele se corrigir ou seguir sem o dado.
"""

import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from core.logging import LogCategory, log_event

from . import registry
from .contracts import ToolContext, ToolResult

logger = logging.getLogger(__name__)


def _failure(name: str, error: str, message: str, arguments: Any, **fields) -> ToolResult:
    log_event(error, LogCategory.SILENT_FAILURE, tool=name, **fields)
    return ToolResult(error=error, error_message=message, meta={'arguments': arguments})


def _validation_message(name: str, exc: ValidationError) -> str:
    fields = '; '.join(f"{'.'.join(map(str, e['loc'])) or 'argumentos'}: {e['msg']}" for e in exc.errors())
    return f'Argumentos inválidos para {name}: {fields}'


class ToolExecutor:
    def run(self, name: str, raw_args: str | dict | None, ctx: ToolContext,
            allowed: list[str] | None = None) -> ToolResult:
        """`raw_args` é o JSON que o modelo mandou (ou já um dict); `allowed`, as ferramentas liberadas."""
        arguments: Any = raw_args
        if isinstance(raw_args, str) or raw_args is None:
            try:
                arguments = json.loads(raw_args or '{}')
            except ValueError as exc:
                return _failure(name, 'tool_invalid_args', f'Argumentos em JSON inválido: {exc}', raw_args,
                                detail=str(exc))

        handler = registry.get_tool(name)
        if handler is None:
            return _failure(name, 'tool_not_found', f'Ferramenta desconhecida: {name}.', arguments)
        if allowed is not None and name not in allowed:
            return _failure(name, 'tool_not_allowed', f'A ferramenta {name} não está disponível para esta mensagem.',
                            arguments)
        try:
            args = handler.input_model.model_validate(arguments)
        except ValidationError as exc:
            return _failure(name, 'tool_invalid_args', _validation_message(name, exc), arguments,
                            detail=str(exc)[:500])

        start = time.perf_counter()
        try:
            result = handler.execute(ctx, args)
        except Exception as exc:
            logger.exception('Falha ao executar a ferramenta %s', name)
            return _failure(name, 'tool_failed',
                            f'Falha interna ao executar {name}. Tente novamente ou siga sem esse dado.',
                            arguments, detail=repr(exc))
        result.meta.setdefault('arguments', arguments)
        # Só os nomes dos argumentos: os valores podem ter dados pessoais (e-mail, telefone).
        log_event('tool_executed', LogCategory.TOOL, tool=name, duration_ms=round((time.perf_counter() - start) * 1000),
                  success=result.error is None, error=result.error, transfer_to_human=result.transfer_to_human,
                  arguments=sorted(args.model_dump(exclude_none=True)))
        return result
