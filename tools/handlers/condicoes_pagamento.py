from decimal import Decimal

from pydantic import Field

from store import catalog, pricing

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class Item(ToolInput):
    produto: str = Field(description='Nome do produto ou id.')
    quantidade: int = Field(1, ge=1)


class CondicoesPagamentoInput(ToolInput):
    itens: list[Item]


class CondicoesPagamento(ToolHandler):
    name = 'condicoes_pagamento'
    description = (
        'Calcula o total e as condições de pagamento de um ou mais produtos: valor no PIX (com desconto '
        'quando aplicável), parcelamento máximo sem juros no cartão, boleto, débito e frete em Campo Grande. '
        'Use quando o cliente perguntar quanto fica no PIX, em quantas vezes pode parcelar etc.'
    )
    input_model = CondicoesPagamentoInput

    def execute(self, ctx: ToolContext, args: CondicoesPagamentoInput) -> ToolResult:
        if not args.itens:
            return ToolResult(error='invalid_request', error_message='Informe ao menos um produto.')
        total = promo_total = Decimal(0)
        lines = []
        for item in args.itens:
            product, candidates = catalog.find(item.produto)
            if not product:
                names = ', '.join(p.name for p in candidates)
                hint = f' Opções: {names}.' if names else ''
                return ToolResult(error='ambiguous' if candidates else 'not_found',
                                  error_message=f'Produto "{item.produto}" não identificado.{hint}')
            if not product.is_available:
                situation = catalog.availability(product)['situacao']
                return ToolResult(error='unavailable',
                                  error_message=f'{product.name} não está disponível para venda: {situation}')
            price = catalog.product_price(product)
            subtotal = price.final * item.quantidade
            total += subtotal
            if price.on_sale:
                promo_total += subtotal
            lines.append({'produto': product.name, 'quantidade': item.quantidade, **price.as_dict(),
                          'subtotal': pricing.brl(subtotal)})
        return ToolResult(data={'itens': lines, **pricing.payment_conditions(total, promo_total)})
