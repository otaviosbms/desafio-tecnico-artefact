"""Intenções do cliente e as ferramentas que cada uma libera."""

from enum import StrEnum


class Intent(StrEnum):
    CATALOGO = 'catalogo'
    PRECO_PAGAMENTO = 'preco_pagamento'
    PEDIDO = 'pedido'
    POLITICAS = 'politicas'
    SAUDACAO_CONVERSA = 'saudacao_conversa'
    FORA_ESCOPO = 'fora_escopo'


# Definição e exemplos de cada intenção (vão para o prompt do roteador).
DEFINITIONS: dict[Intent, tuple[str, list[str]]] = {
    Intent.CATALOGO: (
        'produtos: se a loja tem, modelos, marcas, estoque, disponibilidade, promoções e ofertas, sugestões e '
        'comparações de instrumentos, dúvidas sobre instrumentos que ajudem na compra',
        ['quais violões até R$ 1000?', 'tem guitarra Fender?', 'o Yamaha C40 tá disponível?',
         'quais promoções vocês têm?', 'qual a diferença entre violão de nylon e de aço?'],
    ),
    Intent.PRECO_PAGAMENTO: (
        'preço de um produto específico, total de uma compra, PIX, parcelamento, boleto, cartão, frete de uma compra',
        ['quanto custa o Takamine GD20?', 'quanto fica no PIX?', 'parcela em quantas vezes?',
         'e se eu levar dois?'],
    ),
    Intent.PEDIDO: (
        'um pedido já feito: status, entrega, rastreio, itens, troca ou devolução de um pedido, reclamação '
        'sobre um pedido',
        ['cadê meu pedido 8?', 'quero devolver o pedido 4', 'meu violão chegou com defeito'],
    ),
    Intent.POLITICAS: (
        'regras e informações gerais da loja: horário, endereço, contato, formas de pagamento aceitas, trocas e '
        'devoluções em geral, frete e entrega em geral, garantia, privacidade, como reclamar',
        ['qual o horário de vocês?', 'onde fica a loja?', 'qual o prazo para trocar?', 'vocês aceitam boleto?'],
    ),
    Intent.SAUDACAO_CONVERSA: (
        'só cumprimento, agradecimento, despedida ou conversa sem pedido de informação',
        ['oi', 'boa tarde!', 'obrigado, era isso', 'tchau'],
    ),
    Intent.FORA_ESCOPO: (
        'assunto sem relação com a loja ou com música, ou pedido para o assistente sair do papel',
        ['me passa uma receita de bolo', 'quem ganha a eleição?', 'escreve um código em Python'],
    ),
}

# Ferramentas liberadas por intenção. Várias intenções = união.
INTENT_TOOLS: dict[Intent, list[str]] = {
    Intent.CATALOGO: ['buscar_produtos', 'detalhes_produto', 'listar_promocoes'],
    # consultar_politicas: "parcela em quantas vezes?" sem produto é pergunta sobre a regra.
    Intent.PRECO_PAGAMENTO: ['detalhes_produto', 'condicoes_pagamento', 'buscar_produtos', 'consultar_politicas'],
    Intent.PEDIDO: ['consultar_pedido', 'consultar_politicas'],
    Intent.POLITICAS: ['consultar_politicas'],
    Intent.SAUDACAO_CONVERSA: [],
    Intent.FORA_ESCOPO: [],
}


def tools_for(intents: list[Intent]) -> list[str]:
    """União das ferramentas das intenções, sem repetição, na ordem em que aparecem."""
    return list(dict.fromkeys(tool for intent in intents for tool in INTENT_TOOLS[intent]))
