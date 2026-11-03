"""Utilidades de texto usadas por mais de um estágio (roteador e guardrails)."""

import re
import unicodedata

# Mensagens curtas feitas só destas palavras são conversa (cumprimento, agradecimento, despedida).
# Afirmações como "ok", "sim" e "beleza" ficam de fora de propósito: costumam continuar um
# assunto ("quer o valor no PIX?" "sim").
SMALL_TALK_WORDS = {
    'oi', 'oii', 'ola', 'opa', 'eai', 'e', 'ai', 'bom', 'boa', 'dia', 'tarde', 'noite', 'tudo', 'bem',
    'obrigado', 'obrigada', 'obg', 'brigado', 'valeu', 'vlw', 'muito', 'tchau', 'ate', 'mais', 'logo',
}
MAX_SMALL_TALK_WORDS = 4


def plain(text: str) -> str:
    """Minúsculas e sem acentos ("Olá, Ação" -> "ola, acao")."""
    decomposed = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def words(text: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', plain(text))


def is_small_talk(message: str) -> bool:
    found = words(message)
    return 0 < len(found) <= MAX_SMALL_TALK_WORDS and all(w in SMALL_TALK_WORDS for w in found)
