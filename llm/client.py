"""Cliente de LLM genérico sobre o SDK da OpenAI (Chat Completions).

Usa apenas a API de Chat Completions, que é o padrão suportado pela maioria
dos provedores "OpenAI-compatible". As respostas são normalizadas em
dataclasses simples, para que o resto do projeto não dependa dos tipos do SDK.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import openai

from .config import LLMConfig

Message = dict[str, Any]


class LLMError(RuntimeError):
    """Falha ao chamar o provedor (rede, autenticação, limite, etc.)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code  # HTTP do provedor, quando houver (400, 429, ...)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str
    # Alguns modelos geram JSON inválido; nesse caso `arguments` fica vazio e o
    # erro fica aqui, para o agente poder devolvê-lo ao modelo.
    arguments_error: str | None = None


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    def to_message(self) -> Message:
        """Mensagem do assistente pronta para ser anexada ao histórico."""
        message: Message = {'role': 'assistant', 'content': self.content}
        if self.tool_calls:
            message['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.name, 'arguments': tc.raw_arguments},
                }
                for tc in self.tool_calls
            ]
        return message


def function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Monta a definição de uma ferramenta no formato de function calling."""
    return {
        'type': 'function',
        'function': {'name': name, 'description': description, 'parameters': parameters},
    }


def tool_result_message(tool_call_id: str, content: Any) -> Message:
    """Mensagem com o resultado de uma ferramenta (dicts/listas viram JSON)."""
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)
    return {'role': 'tool', 'tool_call_id': tool_call_id, 'content': content}


def _parse_tool_call(tc) -> ToolCall:
    raw = tc.function.arguments or '{}'
    try:
        arguments = json.loads(raw)
        error = None if isinstance(arguments, dict) else 'Argumentos não são um objeto JSON.'
        if error:
            arguments = {}
    except json.JSONDecodeError as exc:
        arguments, error = {}, f'JSON inválido: {exc}'
    return ToolCall(id=tc.id, name=tc.function.name, arguments=arguments, raw_arguments=raw, arguments_error=error)


class LLMClient:
    def __init__(self, config: LLMConfig | None = None, client: openai.OpenAI | None = None):
        self.config = config or LLMConfig.from_env()
        self._client = client or openai.OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

    def _params(self, messages: list[Message], **kwargs) -> dict[str, Any]:
        params: dict[str, Any] = {'model': self.config.model, 'messages': messages}
        if self.config.temperature is not None:
            params['temperature'] = self.config.temperature
        if self.config.reasoning_effort:
            params['reasoning_effort'] = self.config.reasoning_effort
        params.update({k: v for k, v in kwargs.items() if v is not None})
        return params

    def chat(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Uma chamada de Chat Completions. `kwargs` extras vão direto ao provedor."""
        if not tools:
            tool_choice = None
        params = self._params(messages, tools=tools or None, tool_choice=tool_choice, **kwargs)
        try:
            completion = self._client.chat.completions.create(**params)
        except openai.APIError as exc:
            raise LLMError(f'[{self.config.provider}] {exc}', getattr(exc, 'status_code', None)) from exc

        choice = completion.choices[0]
        usage = completion.usage.model_dump(include={'prompt_tokens', 'completion_tokens', 'total_tokens'}) if completion.usage else {}
        return ChatResponse(
            content=choice.message.content,
            tool_calls=[_parse_tool_call(tc) for tc in choice.message.tool_calls or []],
            finish_reason=choice.finish_reason,
            model=completion.model,
            usage=usage,
        )

    def stream(self, messages: list[Message], **kwargs) -> Iterator[str]:
        """Gera os trechos de texto da resposta conforme chegam (sem ferramentas)."""
        try:
            for chunk in self._client.chat.completions.create(**self._params(messages, stream=True, **kwargs)):
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.APIError as exc:
            raise LLMError(f'[{self.config.provider}] {exc}', getattr(exc, 'status_code', None)) from exc
