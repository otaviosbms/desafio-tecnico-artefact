"""Base de conhecimento das políticas da loja.

O manual em PDF (data/politicas_da_loja.pdf) foi convertido à mão em seções Markdown
(agent/knowledge/*.md), revisadas e com as inconsistências do original resolvidas
(ver docs/dados.md). Cada arquivo é um tópico que o agente consulta por ferramenta.
"""

from functools import cache
from pathlib import Path

from django.utils import timezone

from store.hours import store_status

KNOWLEDGE_DIR = Path(__file__).parent / 'knowledge'

# tópico -> quando consultar (vai para a descrição da ferramenta)
TOPICS = {
    'loja': 'endereço, telefone, WhatsApp, e-mail, o que a loja vende e não vende (acessórios)',
    'horario': 'horário de funcionamento e se a loja está aberta agora',
    'pagamento': 'formas de pagamento, desconto no PIX, regras de parcelamento',
    'trocas_e_devolucoes': 'arrependimento, devolução, troca por defeito ou preferência, itens sem troca',
    'frete_e_entrega': 'frete, prazos de entrega, transportadoras, rastreamento, avaria no transporte',
    'promocoes': 'campanhas do ano e regras de promoções',
    'garantia': 'garantia legal, do fabricante e o que não é coberto',
    'privacidade': 'uso de dados pessoais (LGPD) e exclusão de dados',
    'reclamacoes': 'como tratar reclamações e prazo de retorno da equipe',
}


@cache
def load_section(topic: str) -> str:
    return (KNOWLEDGE_DIR / f'{topic}.md').read_text(encoding='utf-8').strip()


def consultar_politicas(topicos):
    if isinstance(topicos, str):
        topicos = [topicos]
    unknown = [t for t in topicos if t not in TOPICS]
    if unknown or not topicos:
        return {'erro': f'Tópicos inválidos: {unknown}. Use: {", ".join(TOPICS)}.'}

    result = {'secoes': {topic: load_section(topic) for topic in dict.fromkeys(topicos)}}
    if 'horario' in topicos:
        result['situacao_agora'] = store_status(timezone.localtime())
    return result
