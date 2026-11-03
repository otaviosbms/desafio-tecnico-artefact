"""Configuração do provedor de LLM.

Qualquer provedor que exponha a API de Chat Completions no padrão da OpenAI
funciona: basta informar `base_url`, `api_key` e `model`. Para os provedores
mais comuns há presets, então normalmente só é preciso definir LLM_PROVIDER,
LLM_MODEL e a chave de API do provedor.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    base_url: str | None  # None = endpoint padrão do SDK (api.openai.com)
    api_key_env: str | None  # variável de ambiente com a chave do provedor
    default_api_key: str | None = None  # para servidores locais que ignoram a chave


PROVIDERS: dict[str, Provider] = {
    'openai': Provider(None, 'OPENAI_API_KEY'),
    'anthropic': Provider('https://api.anthropic.com/v1/', 'ANTHROPIC_API_KEY'),
    'gemini': Provider('https://generativelanguage.googleapis.com/v1beta/openai/', 'GEMINI_API_KEY'),
    'groq': Provider('https://api.groq.com/openai/v1', 'GROQ_API_KEY'),
    'openrouter': Provider('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY'),
    'deepseek': Provider('https://api.deepseek.com', 'DEEPSEEK_API_KEY'),
    'ollama': Provider('http://localhost:11434/v1', None, default_api_key='ollama'),
    'lmstudio': Provider('http://localhost:1234/v1', None, default_api_key='lm-studio'),
}


class LLMConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    model: str
    provider: str = 'openai'
    base_url: str | None = None
    api_key: str | None = None
    temperature: float | None = None  # None = não envia (alguns modelos não aceitam)
    reasoning_effort: str | None = None  # None = não envia (só modelos de raciocínio aceitam)
    timeout: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_env(cls, prefix: str = 'LLM_') -> 'LLMConfig':
        """Monta a configuração a partir de variáveis de ambiente.

        LLM_PROVIDER     preset (openai, ollama, groq, ...) ou 'custom'
        LLM_MODEL        nome do modelo (obrigatório)
        LLM_BASE_URL     sobrescreve a URL do preset (obrigatório para 'custom')
        LLM_API_KEY      sobrescreve a chave lida da variável do provedor
        LLM_TEMPERATURE  opcional
        LLM_REASONING_EFFORT  opcional (none, low, medium, high), para modelos de raciocínio
        LLM_TIMEOUT      segundos (padrão 60)
        LLM_MAX_RETRIES  padrão 2
        """
        def env(name, default=None):
            return os.getenv(prefix + name) or default

        provider_name = env('PROVIDER', 'openai').lower()
        model = env('MODEL')
        if not model:
            raise LLMConfigError(f'Defina {prefix}MODEL com o nome do modelo.')

        preset = PROVIDERS.get(provider_name)
        if preset is None and provider_name != 'custom':
            raise LLMConfigError(
                f'Provedor desconhecido: {provider_name!r}. Use um de '
                f'{sorted(PROVIDERS)} ou "custom" com {prefix}BASE_URL.'
            )

        base_url = env('BASE_URL') or (preset.base_url if preset else None)
        if provider_name == 'custom' and not base_url:
            raise LLMConfigError(f'Provedor "custom" exige {prefix}BASE_URL.')

        api_key = env('API_KEY')
        if not api_key and preset:
            api_key = (os.getenv(preset.api_key_env) if preset.api_key_env else None) or preset.default_api_key
        if not api_key:
            hint = preset.api_key_env if preset and preset.api_key_env else f'{prefix}API_KEY'
            raise LLMConfigError(f'Chave de API não encontrada para {provider_name!r}. Defina {hint}.')

        temperature = env('TEMPERATURE')
        return cls(
            model=model,
            provider=provider_name,
            base_url=base_url,
            api_key=api_key,
            temperature=float(temperature) if temperature is not None else None,
            reasoning_effort=env('REASONING_EFFORT'),
            timeout=float(env('TIMEOUT', 60)),
            max_retries=int(env('MAX_RETRIES', 2)),
        )
