"""Respostas fixas do bloqueio duro. O LLM classifica; o texto ao cliente é sempre este (não inventado)."""

TEAM_CONTACT = 'WhatsApp (67) 3341-4444'

BLOCKED_REPLIES = {
    'mensagem_vazia': 'Não consegui entender sua mensagem 😅 Pode escrever de novo o que você precisa?',
    'abusivo': 'Quero te ajudar, mas preciso que a conversa siga com respeito. Se quiser, me conta o que '
               'aconteceu que eu vejo como resolver.',
}
DEFAULT_BLOCKED_REPLY = (
    'Desculpa, não consigo ajudar com isso por aqui. Posso te ajudar com instrumentos, pedidos e informações '
    'da loja.'
)
HUMAN_HANDOFF = f'Se preferir, nossa equipe atende pelo {TEAM_CONTACT}.'
HUMAN_HANDOFF_GUIDANCE = (
    f'Este caso precisa da equipe humana: além de responder, ofereça o contato da equipe ({TEAM_CONTACT}) '
    'e diga que eles retornam em até 24 horas úteis.'
)
TOO_MANY_BLOCKS_REPLY = (
    'Acho que não estou conseguindo te ajudar por aqui. Que tal falar direto com a nossa equipe pelo '
    f'{TEAM_CONTACT}? Eles vão te atender.'
)


def blocked_reply(category: str, requires_human: bool) -> str:
    reply = BLOCKED_REPLIES.get(category, DEFAULT_BLOCKED_REPLY)
    return f'{reply} {HUMAN_HANDOFF}' if requires_human else reply
