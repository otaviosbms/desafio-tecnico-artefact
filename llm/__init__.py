"""Integração genérica com LLMs compatíveis com o SDK da OpenAI.

Uso:
    from llm import LLMClient
    client = LLMClient()  # lê LLM_PROVIDER / LLM_MODEL / chave do .env
    resposta = client.chat([{'role': 'user', 'content': 'Oi!'}])

    # No projeto, toda chamada passa pelo serviço (caller, modelo por papel, logs, custo):
    from llm import LLMService
    texto = LLMService().complete_text(caller='exemplo', role='agent', messages=[...])
"""

from .client import (
    ChatResponse,
    LLMClient,
    LLMError,
    Message,
    ToolCall,
    function_tool,
    tool_result_message,
)
from .config import PROVIDERS, LLMConfig, LLMConfigError
from .service import LLMCall, LLMService, StructuredCall

__all__ = [
    'PROVIDERS',
    'ChatResponse',
    'LLMClient',
    'LLMConfig',
    'LLMConfigError',
    'LLMCall',
    'LLMError',
    'LLMService',
    'StructuredCall',
    'Message',
    'ToolCall',
    'function_tool',
    'tool_result_message',
]
