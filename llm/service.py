"""Serviço único de LLM: toda chamada ao modelo passa por aqui.

Sobre o `LLMClient` (transporte), o serviço acrescenta:
- **caller e papel:** quem chamou (`agent.respond`, `router.classify`, ...) e qual modelo usar
  (ver `roles.py`: modelo e provedor por camada);
- **observabilidade:** cada chamada gera um log `LLM_CALL` e soma tokens e custo no turno atual;
- **saída estruturada portável:** `complete_json` valida a resposta com Pydantic e tem três
  níveis de fallback, porque nem todo provedor compatível com a OpenAI aceita `json_schema`;
- **fail-closed:** nenhum método lança exceção. Quem chama decide o que fazer com `None`
  (ou com `LLMCall.error`) e o serviço registra a `DEGRADATION`.
"""

import copy
import dataclasses
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from core.logging import LogCategory, log_event
from core.turn_context import add_llm_usage

from . import pricing
from .client import ChatResponse, LLMClient, LLMError, Message
from .roles import ROLES, config_for

Model = TypeVar('Model', bound=BaseModel)

# Níveis de saída estruturada, do mais ao menos rígido.
JSON_SCHEMA, JSON_OBJECT, PROMPT = 'json_schema', 'json_object', 'prompt'
STRUCTURED_MODES = (JSON_SCHEMA, JSON_OBJECT, PROMPT)


@dataclass
class LLMCall:
    """Uma chamada ao modelo, com o que for preciso para o rastro e os logs."""

    caller: str
    role: str
    model: str
    duration_ms: int = 0
    usage: dict[str, int] = dataclasses.field(default_factory=dict)
    cost_usd: Decimal = Decimal(0)
    response: ChatResponse | None = None
    error: str | None = None
    structured_mode: str | None = None
    format_rejected: bool = False  # o provedor recusou o `response_format` pedido

    @property
    def ok(self) -> bool:
        return self.response is not None


@dataclass
class StructuredCall(Generic[Model]):
    value: Model | None = None  # resposta validada (None se falhou)
    calls: list[LLMCall] = dataclasses.field(default_factory=list)  # uma por nível tentado


def _strict_schema(schema: dict) -> dict:
    """Ajusta o schema do Pydantic ao modo `strict` da OpenAI.

    No modo estrito, todo objeto precisa de `additionalProperties: false` e de todas as
    propriedades em `required`; sem isso o provedor rejeita o schema com HTTP 400.
    """
    schema = copy.deepcopy(schema)

    def visit(node):
        if isinstance(node, dict):
            if node.get('type') == 'object' and 'properties' in node:
                node['additionalProperties'] = False
                node['required'] = list(node['properties'])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema


def _extract_json(text: str | None) -> str | None:
    """Primeiro objeto JSON do texto (tolera cercas ```json e texto em volta)."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    start = text.find('{')
    while start != -1:
        try:
            _, end = decoder.raw_decode(text, start)
            return text[start:end]
        except ValueError:
            start = text.find('{', start + 1)
    return None


def _schema_instruction(output_model: type[BaseModel]) -> Message:
    schema = json.dumps(output_model.model_json_schema(), ensure_ascii=False)
    return {
        'role': 'system',
        'content': 'Responda apenas com um objeto JSON válido, sem texto antes ou depois, que siga este '
                   f'JSON Schema:\n{schema}',
    }


def _rejects_response_format(exc: LLMError) -> bool:
    """O provedor recusou o `response_format` (e não falhou por rede, cota, etc.)?"""
    message = str(exc).lower()
    return exc.status_code in (400, 404, 422) or 'response_format' in message or 'unsupported' in message


class LLMService:
    def __init__(self, client: LLMClient | None = None, *, role_clients: dict[str, LLMClient] | None = None,
                 structured_output: str | None = None):
        """`client` é a base (provedor, chave, modelo padrão); `role_clients` fixa o cliente de um papel.

        `structured_output`: 'auto' (padrão, testa os níveis em ordem) ou um nível fixo.
        """
        self.client = client or LLMClient()
        self._role_clients = dict(role_clients or {})
        for role in ROLES:  # resolve já, para um .env errado falhar na subida e não no meio da conversa
            self.client_for(role)
        mode = (structured_output or os.getenv('LLM_STRUCTURED_OUTPUT') or 'auto').lower()
        if mode != 'auto' and mode not in STRUCTURED_MODES:
            raise ValueError(f'LLM_STRUCTURED_OUTPUT inválido: {mode!r}. Use auto, {", ".join(STRUCTURED_MODES)}.')
        self.structured_output = mode
        self._structured_level: dict[str, int] = {}  # modelo -> nível que funcionou

    @classmethod
    def with_overrides(cls, models: dict[str, str | None] | None = None,
                       agent_temperature: float | None = None) -> 'LLMService':
        """Serviço com o modelo de alguns papéis trocado (ex.: escolhido na UI de testes).

        `models`: papel -> "modelo" ou "provedor:modelo". Lança LLMConfigError se faltar a chave do
        provedor pedido.
        """
        base = LLMClient()
        overrides = {role: ref for role, ref in (models or {}).items() if ref}
        if agent_temperature is not None:
            overrides.setdefault('agent', None)
        role_clients = {
            role: LLMClient(config_for(role, base.config, ref, agent_temperature if role == 'agent' else None))
            for role, ref in overrides.items()
        }
        return cls(base, role_clients=role_clients)

    def client_for(self, role: str) -> LLMClient:
        if role not in self._role_clients:
            config = config_for(role, self.client.config)
            self._role_clients[role] = self.client if config == self.client.config else LLMClient(config)
        return self._role_clients[role]

    # Chamadas ----------------------------------------------------------------------------

    def chat(self, *, caller: str, role: str, messages: list[Message], tools: list[dict] | None = None,
             **kwargs) -> LLMCall:
        """Chamada com function calling. O resultado vem em `LLMCall.response` (None se falhou)."""
        return self._call(caller, role, messages, tools=tools, **kwargs)

    def complete_text(self, *, caller: str, role: str, messages: list[Message], **kwargs) -> str | None:
        call = self._call(caller, role, messages, **kwargs)
        text = (call.response.content or '').strip() if call.ok else ''
        if not text:
            self._degraded(call, 'llm_error' if call.error else 'empty_response')
            return None
        return text

    def complete_json(self, *, caller: str, role: str, messages: list[Message],
                      output_model: type[Model], **kwargs) -> Model | None:
        """Resposta validada por `output_model`, ou None (com `DEGRADATION`) se não der."""
        return self.structured(caller=caller, role=role, messages=messages, output_model=output_model, **kwargs).value

    def structured(self, *, caller: str, role: str, messages: list[Message],
                   output_model: type[Model], **kwargs) -> 'StructuredCall[Model]':
        """Como `complete_json`, mas devolve também as chamadas feitas (para o rastro)."""
        model = self.client_for(role).config.model
        if self.structured_output == 'auto':
            levels = STRUCTURED_MODES[self._structured_level.get(model, 0):]
        else:
            levels = (self.structured_output,)

        result = StructuredCall()
        for mode in levels:
            call = self._call(caller, role, self._structured_messages(messages, output_model, mode),
                              structured_mode=mode, **self._structured_params(output_model, mode), **kwargs)
            result.calls.append(call)
            if self._can_downgrade(call, mode):
                log_event('structured_output_downgraded', LogCategory.DEGRADATION,
                          caller=caller, model=model, rejected=mode, error=call.error)
                continue
            if self.structured_output == 'auto':
                self._structured_level[model] = STRUCTURED_MODES.index(mode)
            if not call.ok:
                self._degraded(call, 'llm_error')
                return result
            raw = _extract_json(call.response.content)
            try:
                result.value = output_model.model_validate_json(raw or '')
            except ValidationError as exc:
                call.error = 'Saída fora do schema.'
                self._degraded(call, 'invalid_output', detail=str(exc)[:500])
            return result
        return result

    # Internos -----------------------------------------------------------------------------

    def _structured_messages(self, messages, output_model, mode):
        if mode == JSON_SCHEMA:
            return messages
        return [*messages, _schema_instruction(output_model)]

    def _structured_params(self, output_model, mode) -> dict[str, Any]:
        if mode == JSON_SCHEMA:
            return {'response_format': {'type': 'json_schema', 'json_schema': {
                'name': output_model.__name__,
                'schema': _strict_schema(output_model.model_json_schema()),
                'strict': True,
            }}}
        if mode == JSON_OBJECT:
            return {'response_format': {'type': 'json_object'}}
        return {}

    def _can_downgrade(self, call: LLMCall, mode: str) -> bool:
        return self.structured_output == 'auto' and mode != PROMPT and call.format_rejected

    def _call(self, caller: str, role: str, messages: list[Message], *, structured_mode: str | None = None,
              **kwargs) -> LLMCall:
        client = self.client_for(role)
        call = LLMCall(caller=caller, role=role, model=client.config.model, structured_mode=structured_mode)
        start = time.perf_counter()
        try:
            call.response = client.chat(messages, **kwargs)
        except LLMError as exc:
            call.error = str(exc)
            call.format_rejected = structured_mode in (JSON_SCHEMA, JSON_OBJECT) and _rejects_response_format(exc)
        call.duration_ms = round((time.perf_counter() - start) * 1000)
        if call.ok:
            call.usage = call.response.usage or {}
            call.cost_usd = pricing.cost(call.model, call.usage)
        add_llm_usage(call.usage, call.cost_usd)
        log_event(
            'llm_call', LogCategory.LLM_CALL,
            caller=caller, role=role, model=call.model, duration_ms=call.duration_ms, tokens=call.usage,
            cost_usd=str(call.cost_usd), success=call.ok, structured_mode=structured_mode,
            **({'error': call.error} if call.error else {}),
        )
        return call

    def _degraded(self, call: LLMCall, reason: str, **fields) -> None:
        log_event('llm_degraded', LogCategory.DEGRADATION, caller=call.caller, model=call.model,
                  reason=reason, **({'error': call.error} if call.error else {}), **fields)
