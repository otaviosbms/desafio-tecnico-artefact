"""Modelo por papel: cada estágio de IA pode usar um modelo diferente.

O agente que redige a resposta precisa do melhor modelo; o roteador de intenção e
os guardrails só classificam, então um modelo menor e mais rápido costuma bastar.
Sem a variável do papel, vale o LLM_MODEL (mesmo provedor e chave para todos).
"""

import os

ROLES = {
    'agent': 'LLM_MODEL_AGENT',
    'router': 'LLM_MODEL_ROUTER',
    'guardrails': 'LLM_MODEL_GUARDRAILS',
}


def model_for(role: str, default: str) -> str:
    if role not in ROLES:
        raise ValueError(f'Papel desconhecido: {role!r}. Use um de {sorted(ROLES)}.')
    return os.getenv(ROLES[role]) or default
