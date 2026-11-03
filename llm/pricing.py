"""Custo estimado das chamadas, a partir dos tokens informados pelo provedor.

Preços em US$ por 1 milhão de tokens (entrada, saída) dos modelos da OpenAI da família GPT-5 em
diante, pela tabela pública em 29/10/2026 (fonte: benchlm.ai/openai/api-pricing, conferida com o
LiteLLM para o GPT-6). Confira antes de usar: é uma estimativa para acompanhar o custo por turno,
não faturamento. Simplificações:
- todo token de entrada usa o preço normal (sem o desconto de entrada em cache);
- o preço é o de contexto curto (até 272 mil tokens; acima disso, o GPT-6 cobra mais).

Modelos `:free` (OpenRouter) custam 0; um modelo fora da tabela (inclusive de outro provedor ou
local) custa 0 e gera um aviso (uma vez por modelo).
"""

import logging
import re
from decimal import Decimal

logger = logging.getLogger(__name__)

PRICES: dict[str, tuple[Decimal, Decimal]] = {
    # GPT-6
    'gpt-6-astra': (Decimal('10.00'), Decimal('50.00')),
    'gpt-6.1-sol': (Decimal('2.00'), Decimal('10.00')),
    'gpt-6-sol': (Decimal('2.00'), Decimal('10.00')),
    'gpt-6.1-terra': (Decimal('1.00'), Decimal('5.00')),
    'gpt-6-luna': (Decimal('0.10'), Decimal('0.50')),
    # GPT-5.6
    'gpt-5.6-sol': (Decimal('4.00'), Decimal('20.00')),
    'gpt-5.6-terra': (Decimal('2.00'), Decimal('12.00')),
    'gpt-5.6-luna': (Decimal('0.20'), Decimal('1.20')),
    # GPT-5.5
    'gpt-5.5-pro': (Decimal('30.00'), Decimal('180.00')),
    'gpt-5.5': (Decimal('5.00'), Decimal('30.00')),
    # GPT-5.4
    'gpt-5.4-pro': (Decimal('30.00'), Decimal('180.00')),
    'gpt-5.4': (Decimal('2.50'), Decimal('15.00')),
    'gpt-5.4-mini': (Decimal('0.75'), Decimal('4.50')),
    'gpt-5.4-nano': (Decimal('0.20'), Decimal('1.25')),
    # GPT-5.2, 5.1 e 5
    'gpt-5.2': (Decimal('1.75'), Decimal('14.00')),
    'gpt-5.1': (Decimal('1.25'), Decimal('10.00')),
    'gpt-5': (Decimal('1.25'), Decimal('10.00')),
    'gpt-5-mini': (Decimal('0.25'), Decimal('2.00')),
    'gpt-5-nano': (Decimal('0.05'), Decimal('0.40')),
}

MILLION = Decimal(1_000_000)
DATED = re.compile(r'-\d{4}-\d{2}-\d{2}$')  # versão fixa: "gpt-5.4-mini-2026-03-05"
_warned: set[str] = set()


def _price(model: str) -> tuple[Decimal, Decimal] | None:
    if model.endswith(':free'):
        return Decimal(0), Decimal(0)
    # OpenRouter prefixa o fornecedor ("openai/gpt-6-luna"); versões fixas terminam com a data.
    name = DATED.sub('', model.rsplit('/', 1)[-1])
    return PRICES.get(name)


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
