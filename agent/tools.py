"""Ferramentas de dados que o agente pode chamar (function calling).

Cada ferramenta tem um schema JSON (o que o LLM vê) e uma função Python que
consulta o banco e devolve um dict já pronto para o modelo redigir a resposta.
Erros viram {"erro": ...} em vez de exceções, para o modelo poder se corrigir.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils import timezone

from agent.policies import TOPICS, consultar_politicas
from llm import function_tool
from store import catalog, orders, pricing
from store.models import Category, Product, Promotion

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., dict]

    def definition(self) -> dict[str, Any]:
        return function_tool(self.name, self.description, self.parameters)


def buscar_produtos(termo=None, categoria=None, preco_min=None, preco_max=None, apenas_disponiveis=True, limite=5):
    return catalog.search(
        term=termo,
        category=categoria,
        min_price=preco_min,
        max_price=preco_max,
        only_available=apenas_disponiveis,
        limit=max(1, min(int(limite), 20)),
    )


def detalhes_produto(produto):
    product, candidates = catalog.find(produto)
    if product:
        return catalog.details(product)
    if candidates:
        return {
            'ambiguo': True,
            'mensagem': 'Mais de um produto corresponde. Pergunte ao cliente qual deles.',
            'candidatos': [catalog.summary(p) for p in candidates],
        }
    return {'erro': f'Nenhum produto encontrado para "{produto}". Tente buscar_produtos com outro termo.'}


def listar_promocoes():
    promotions = Promotion.objects.filter(is_active=True).values_list('product_id', flat=True)
    products = catalog.with_prices(Product.objects.filter(pk__in=promotions)).order_by('final_price')
    return {
        'promocoes_ativas': [catalog.summary(p) for p in products],
        'regras': 'Promoções não são cumulativas: o desconto do PIX não vale sobre preço promocional.',
    }


def condicoes_pagamento(itens):
    total = promo_total = Decimal(0)
    lines = []
    for item in itens:
        reference, quantity = item.get('produto'), int(item.get('quantidade') or 1)
        product, candidates = catalog.find(reference)
        if not product:
            names = ', '.join(p.name for p in candidates)
            hint = f' Opções: {names}.' if names else ''
            return {'erro': f'Produto "{reference}" não identificado.{hint}'}
        if not product.is_available:
            return {'erro': f'{product.name} não está disponível para venda: {catalog.availability(product)["situacao"]}'}
        price = catalog.product_price(product)
        subtotal = price.final * quantity
        total += subtotal
        if price.on_sale:
            promo_total += subtotal
        lines.append({'produto': product.name, 'quantidade': quantity, **price.as_dict(), 'subtotal': pricing.brl(subtotal)})
    if not lines:
        return {'erro': 'Informe ao menos um produto.'}
    return {'itens': lines, **pricing.payment_conditions(total, promo_total)}


def consultar_pedido(numero_pedido, email_ou_telefone):
    order = orders.find_order(numero_pedido, email_ou_telefone)
    if order is None:
        return {
            'erro': 'Não encontramos um pedido com esse número para o e-mail/telefone informado. '
                    'Peça ao cliente para conferir os dados.'
        }
    return orders.order_details(order, timezone.localdate())


def _category_names() -> list[str]:
    return list(Category.objects.order_by('name').values_list('name', flat=True))


def get_tools() -> list[Tool]:
    """Monta as ferramentas (os schemas usam as categorias do banco, por isso é uma função)."""
    return [
        Tool(
            'buscar_produtos',
            'Busca instrumentos no catálogo da loja por nome/marca/tipo, categoria e faixa de preço. '
            'Use para perguntas como "quais violões até R$ 1000?" ou "vocês têm guitarra Fender?". '
            'Retorna preço atual (já com promoção, se houver) e disponibilidade em estoque.',
            {
                'type': 'object',
                'properties': {
                    'termo': {'type': 'string', 'description': 'Nome, marca ou característica (ex.: "yamaha", "7 cordas", "elétrico").'},
                    'categoria': {'type': 'string', 'enum': _category_names()},
                    'preco_min': {'type': 'number', 'description': 'Preço mínimo em reais.'},
                    'preco_max': {'type': 'number', 'description': 'Preço máximo em reais.'},
                    'apenas_disponiveis': {'type': 'boolean', 'description': 'Padrão true: só itens à venda e em estoque.'},
                    'limite': {'type': 'integer', 'description': 'Máximo de resultados (padrão 5, máx. 20).'},
                },
            },
            buscar_produtos,
        ),
        Tool(
            'detalhes_produto',
            'Detalhes de um produto específico: preço (com promoção ativa, se houver), estoque, descrição e '
            'especificações. Se estiver indisponível, já traz alternativas semelhantes. '
            'Use quando o cliente perguntar sobre um modelo específico (ex.: "quanto custa o Takamine GD20?").',
            {
                'type': 'object',
                'properties': {'produto': {'type': 'string', 'description': 'Nome do produto ou id.'}},
                'required': ['produto'],
            },
            detalhes_produto,
        ),
        Tool(
            'listar_promocoes',
            'Lista as promoções ativas no momento, com preço original, desconto e preço final. '
            'Use quando o cliente perguntar sobre ofertas ou promoções.',
            {'type': 'object', 'properties': {}},
            listar_promocoes,
        ),
        Tool(
            'condicoes_pagamento',
            'Calcula o total e as condições de pagamento de um ou mais produtos: valor no PIX (com desconto '
            'quando aplicável), parcelamento máximo sem juros no cartão, boleto, débito e frete em Campo Grande. '
            'Use quando o cliente perguntar quanto fica no PIX, em quantas vezes pode parcelar etc.',
            {
                'type': 'object',
                'properties': {
                    'itens': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'produto': {'type': 'string', 'description': 'Nome do produto ou id.'},
                                'quantidade': {'type': 'integer', 'minimum': 1},
                            },
                            'required': ['produto'],
                        },
                    },
                },
                'required': ['itens'],
            },
            condicoes_pagamento,
        ),
        Tool(
            'consultar_pedido',
            'Consulta status, itens, rastreio e prazos de troca/devolução/garantia de um pedido. '
            'Exige o número do pedido E o e-mail ou telefone do cadastro do cliente (proteção de dados). '
            'Se o cliente não informou os dois, peça antes de chamar.',
            {
                'type': 'object',
                'properties': {
                    'numero_pedido': {'type': 'string'},
                    'email_ou_telefone': {'type': 'string'},
                },
                'required': ['numero_pedido', 'email_ou_telefone'],
            },
            consultar_pedido,
        ),
        Tool(
            'consultar_politicas',
            'Consulta o manual de políticas da loja. Use para dúvidas sobre regras e informações gerais '
            '(não para preço/estoque de produtos nem status de pedidos). Pode pedir vários tópicos de uma vez. '
            'Tópicos: ' + '; '.join(f'{name} ({desc})' for name, desc in TOPICS.items()) + '.',
            {
                'type': 'object',
                'properties': {
                    'topicos': {'type': 'array', 'items': {'type': 'string', 'enum': list(TOPICS)}, 'minItems': 1},
                },
                'required': ['topicos'],
            },
            consultar_politicas,
        ),
    ]


def execute_tool(name: str, arguments: dict[str, Any], tools: list[Tool] | None = None) -> dict:
    """Executa uma ferramenta pelo nome. Nunca levanta exceção: erros voltam como dict."""
    tool = next((t for t in tools or get_tools() if t.name == name), None)
    if tool is None:
        return {'erro': f'Ferramenta desconhecida: {name}.'}
    try:
        return tool.func(**arguments)
    except TypeError as exc:
        return {'erro': f'Argumentos inválidos para {name}: {exc}'}
    except Exception:
        logger.exception('Falha ao executar a ferramenta %s', name)
        return {'erro': f'Falha interna ao executar {name}. Tente novamente ou siga sem esse dado.'}
