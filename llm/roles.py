"""Modelo por papel: cada camada de IA da aplicação pode usar um modelo, e até um provedor, diferente.

O agente que redige a resposta precisa do melhor modelo; o roteador de intenção e os
guardrails só classificam, então um modelo menor e mais rápido costuma bastar.

Para cada papel, no .env:
    LLM_MODEL_<PAPEL>             "modelo" (mesmo provedor do LLM_PROVIDER) ou "provedor:modelo"
                                  (outro preset, com a chave dele, ex.: groq:llama-3.3-70b-versatile).
                                  Vazio = LLM_MODEL.
    LLM_REASONING_EFFORT_<PAPEL>  só quando o papel usa outro modelo (o LLM_REASONING_EFFORT vale
                                  para o LLM_MODEL).
"""

import os

from .config import LLMConfig

ROLES = {
    'agent': 'AGENT',  # conversa: o agente que responde ao cliente
    'router': 'ROUTER',  # roteador de intenção
    'guardrails': 'GUARDRAILS',  # portão de entrada
}


def _suffix(role: str) -> str:
    if role not in ROLES:
        raise ValueError(f'Papel desconhecido: {role!r}. Use um de {sorted(ROLES)}.')
    return ROLES[role]


def model_ref(role: str) -> str | None:
    """O que o .env define para o papel (`LLM_MODEL_<PAPEL>`), ou None."""
    return (os.getenv(f'LLM_MODEL_{_suffix(role)}') or '').strip() or None


def model_for(role: str, default: str) -> str:
    return model_ref(role) or default


def config_for(role: str, base: LLMConfig, override: str | None = None,
               temperature: float | None = None) -> LLMConfig:
    """Configuração do papel: `override` (ex.: escolhido na UI) > LLM_MODEL_<PAPEL> > `base`."""
    suffix = _suffix(role)
    ref = (override or '').strip() or model_ref(role)
    config = base
    if ref and ref != base.model:
        config = base.with_model(ref, reasoning_effort=os.getenv(f'LLM_REASONING_EFFORT_{suffix}') or None)
    if temperature is not None:
        config = config.with_temperature(temperature)
    return config


def describe(base: LLMConfig) -> dict[str, dict]:
    """Provedor e modelo de cada papel, para mostrar na UI.

    `ref` é o valor como no .env ("modelo" ou "provedor:modelo"): é o que a UI compara e envia.
    """
    result = {}
    for role in ROLES:
        config = config_for(role, base)
        result[role] = {'provedor': config.provider, 'modelo': config.model, 'ref': model_ref(role) or base.model,
                        'temperatura': config.temperature}
    return result
