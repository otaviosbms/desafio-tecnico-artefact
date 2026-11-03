"""Snapshots: versões de referência dos prompts e dos schemas, comparadas por teste.

Qualquer mudança nos textos que vão ao LLM aparece como diff no teste e no git. Para aceitar uma
mudança feita de propósito: `python manage.py update_snapshots` (e revise o diff antes do commit).
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

from guardrails.prompts import build_messages as guardrails_messages
from llm import Message
from router.prompts import build_messages as router_messages
from tools import registry

from .prompts import build_system_prompt

BASE = Path(settings.BASE_DIR)
MONDAY_10H = datetime(2026, 11, 2, 10, 0, tzinfo=ZoneInfo('America/Campo_Grande'))


def _messages(messages: list[Message]) -> str:
    return '\n\n'.join(f'### {m["role"]}\n{m["content"]}' for m in messages) + '\n'


def agent_prompt() -> str:
    sunday = datetime(2026, 11, 8, 11, 0, tzinfo=MONDAY_10H.tzinfo)
    variants = [
        ('Segunda 10h, sem orientação', build_system_prompt(MONDAY_10H)),
        ('Domingo 11h (loja fechada)', build_system_prompt(sunday)),
        ('Com orientação do guardrails e escopo do roteador', build_system_prompt(
            MONDAY_10H, guidance='Orientação de exemplo do guardrails.', intents=['pedido', 'politicas'],
            allowed_tools=['consultar_pedido', 'consultar_politicas'],
        )),
    ]
    return '\n'.join(f'===== {title} =====\n{prompt.rstrip()}\n' for title, prompt in variants)


def router_prompt() -> str:
    return _messages(router_messages('quero devolver o pedido 4', 'Oi! Em que posso ajudar?'))


def guardrails_prompt() -> str:
    return _messages(guardrails_messages('vocês são uns incompetentes, quero meu dinheiro de volta', [
        {'role': 'user', 'content': 'cadê meu pedido 8?'},
        {'role': 'assistant', 'content': 'Para consultar, me passa o e-mail ou telefone do cadastro?'},
    ]))


def tool_definitions() -> str:
    """Precisa do banco (o enum de categorias vem dele)."""
    return json.dumps(registry.definitions(), ensure_ascii=False, indent=1) + '\n'


# arquivo -> função que gera o conteúdo esperado
SNAPSHOTS = {
    BASE / 'conversation' / 'snapshots' / 'agent_prompt.txt': agent_prompt,
    BASE / 'router' / 'snapshots' / 'prompt.txt': router_prompt,
    BASE / 'guardrails' / 'snapshots' / 'prompt.txt': guardrails_prompt,
    BASE / 'tools' / 'snapshots' / 'definitions.json': tool_definitions,
}


def write_all() -> list[Path]:
    changed = []
    for path, render in SNAPSHOTS.items():
        content = render()
        if not path.exists() or path.read_text(encoding='utf-8') != content:
            path.parent.mkdir(exist_ok=True)
            path.write_text(content, encoding='utf-8')
            changed.append(path)
    return changed
