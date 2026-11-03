"""Custo estimado das chamadas, a partir dos tokens informados pelo provedor.

Preços em US$ por 1 milhão de tokens (entrada, saída), da tabela pública dos provedores
(confira antes de usar). É uma estimativa para acompanhar o custo por turno, não faturamento.
Modelos `:free` (OpenRouter) custam 0; um modelo fora da tabela (inclusive local) custa 0 e
gera um aviso (uma vez por modelo).
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

PRICES: dict[str, tuple[Decimal, Decimal]] = {
    'gpt-4o': (Decimal('2.50'), Decimal('10.00')),
    'gpt-4o-mini': (Decimal('0.15'), Decimal('0.60')),
    'gpt-4.1': (Decimal('2.00'), Decimal('8.00')),
    'gpt-4.1-mini': (Decimal('0.40'), Decimal('1.60')),
    'gpt-4.1-nano': (Decimal('0.10'), Decimal('0.40')),
}

MILLION = Decimal(1_000_000)
_warned: set[str] = set()


def _price(model: str) -> tuple[Decimal, Decimal] | None:
    if model.endswith(':free'):
        return Decimal(0), Decimal(0)
    # OpenRouter prefixa o fornecedor: "openai/gpt-4o-mini".
    return PRICES.get(model) or PRICES.get(model.rsplit('/', 1)[-1])


def cost(model: str, usage: dict | None) -> Decimal:
    price = _price(model)
    if price is None:
        if model not in _warned:
            _warned.add(model)
            logger.warning('Modelo sem preço na tabela (custo considerado 0): %s', model)
        return Decimal(0)
    usage = usage or {}
    prompt, completion = usage.get('prompt_tokens') or 0, usage.get('completion_tokens') or 0
    return (prompt * price[0] + completion * price[1]) / MILLION
