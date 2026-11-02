"""Regras de preço e pagamento do manual de políticas (seções 3, 5 e 6).

Ficam em Python (e não no prompt) para o LLM nunca precisar fazer conta.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PIX_DISCOUNT_PERCENT = Decimal('5')
# (máximo de parcelas da faixa, parcela mínima). Suposição para "até 3x":
# o texto diz "sem valor mínimo (exceto abaixo de R$ 50,00)", lido como mínimo de R$ 50.
INSTALLMENT_RULES = [(3, Decimal('50')), (6, Decimal('80')), (12, Decimal('100'))]
COMBINED_PAYMENT_MIN = Decimal('2000')
FREE_SHIPPING_MIN = Decimal('500')
LOCAL_SHIPPING_FEE = Decimal('35')

PAYMENT_METHOD_LABELS = {
    'pix': 'PIX',
    'debit': 'Cartão de débito',
    'boleto': 'Boleto bancário',
}


def money(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def brl(value) -> str:
    """Formata no padrão brasileiro: R$ 2.199,00."""
    formatted = f'{money(value):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {formatted}'


def payment_method_label(code: str) -> str:
    if code.startswith('credit_'):
        return f'Cartão de crédito em {code.removeprefix("credit_")}'
    return PAYMENT_METHOD_LABELS.get(code, code)


@dataclass
class PriceInfo:
    original: Decimal
    final: Decimal
    discount_percent: int = 0
    promotion: str | None = None

    @property
    def on_sale(self) -> bool:
        return self.discount_percent > 0

    def as_dict(self) -> dict:
        data = {'preco': brl(self.final)}
        if self.on_sale:
            # Política 6.2: preço promocional sempre junto do original e do percentual.
            data.update({
                'preco_original': brl(self.original),
                'desconto': f'{self.discount_percent}%',
                'promocao': self.promotion,
            })
        return data


def price_info(price, discount_percent: int | None = None, promotion: str | None = None) -> PriceInfo:
    original = money(price)
    if not discount_percent:
        return PriceInfo(original, original)
    final = money(original * (100 - Decimal(discount_percent)) / 100)
    return PriceInfo(original, final, int(discount_percent), promotion)


def _min_installment(n: int) -> Decimal:
    return next(minimum for max_n, minimum in INSTALLMENT_RULES if n <= max_n)


def max_installments(total) -> int:
    """Maior número de parcelas sem juros permitido para o valor."""
    total = Decimal(total)
    max_n = INSTALLMENT_RULES[-1][0]
    return next((n for n in range(max_n, 1, -1) if total / n >= _min_installment(n)), 1)


def payment_conditions(total, promo_total=0) -> dict:
    """Condições de pagamento para um valor.

    `promo_total` é a parte do valor que já está em promoção: o desconto do PIX
    não vale sobre ela (promoções não são cumulativas).
    """
    total, promo_total = money(total), money(promo_total)
    pix_discount = money((total - promo_total) * PIX_DISCOUNT_PERCENT / 100)
    installments = max_installments(total)

    pix = {'valor': brl(total - pix_discount)}
    if pix_discount:
        pix['desconto'] = f'{PIX_DISCOUNT_PERCENT}% ({brl(pix_discount)})'
    if promo_total:
        pix['observacao'] = 'Desconto do PIX não se aplica a itens já em promoção.'

    return {
        'total': brl(total),
        'pix': pix,
        'cartao_debito': {'valor': brl(total)},
        'boleto': {'valor': brl(total), 'observacao': 'Compensação em até 3 dias úteis.'},
        'cartao_credito': {
            'parcelas_max_sem_juros': installments,
            'valor_parcela': brl(total / installments),
        },
        'pode_combinar_formas_de_pagamento': total > COMBINED_PAYMENT_MIN,
        'frete_regiao_metropolitana_campo_grande': (
            'Grátis' if total > FREE_SHIPPING_MIN else brl(LOCAL_SHIPPING_FEE)
        ),
    }
