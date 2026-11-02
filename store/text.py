import re
import unicodedata


def normalize(text: str) -> str:
    """Normaliza texto para busca: sem acentos, minúsculo, só letras/números.

    Também separa letras de números ("GD20" -> "gd 20"), para que "gd20",
    "GD-20" e "gd 20" fiquem iguais.
    """
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])', ' ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return text.strip()
