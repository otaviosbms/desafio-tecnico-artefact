"""Integração genérica com LLMs compatíveis com o SDK da OpenAI.

Uso:
    from llm import LLMClient
    client = LLMClient()  # lê LLM_PROVIDER / LLM_MODEL / chave do .env
    resposta = client.chat([{'role': 'user', 'content': 'Oi!'}])
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

__all__ = [
    'PROVIDERS',
    'ChatResponse',
    'LLMClient',
    'LLMConfig',
    'LLMConfigError',
    'LLMError',
    'Message',
    'ToolCall',
    'function_tool',
    'tool_result_message',
]
