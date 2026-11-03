"""Consulta de pedidos com verificação de identidade e prazos do manual (seções 4 e 8)."""

import logging
import re
from datetime import date, timedelta

from core.logging import LogCategory, log_event

from .models import Order
from .pricing import brl, payment_method_label

RETURN_DAYS = 7  # arrependimento (4.1), contado do recebimento
PREFERENCE_EXCHANGE_DAYS = 7  # troca por preferência (4.3); suposição: contado do recebimento
DEFECT_EXCHANGE_DAYS = 30  # troca por defeito (4.2), contado da compra
LEGAL_WARRANTY_DAYS = 90  # garantia legal (8.1), contada do recebimento

STATUS_NEXT_STEP = {
    Order.Status.PENDING: 'Aguardando a confirmação do pagamento.',
    Order.Status.CONFIRMED: 'Pagamento confirmado; o pedido está sendo preparado para envio.',
    Order.Status.SHIPPED: 'Pedido a caminho. O rastreio pode ser consultado no site dos Correios ou da Jadlog.',
    Order.Status.DELIVERED: 'Pedido entregue.',
    Order.Status.CANCELLED: 'Pedido cancelado.',
}


def _digits(value: str) -> str:
    return re.sub(r'\D', '', value or '')


def matches_customer(order: Order, contact: str) -> bool:
    """Confere o e-mail ou o telefone informado com o cadastro do cliente do pedido."""
    contact = (contact or '').strip().lower()
    if '@' in contact:
        return contact == order.customer.email.lower()
    digits, phone = _digits(contact), _digits(order.customer.phone)
    # Aceita com ou sem DDD (mínimo de 8 dígitos para não aceitar trechos curtos).
    return len(digits) >= 8 and phone.endswith(digits)


def find_order(number, contact: str) -> Order | None:
    """Retorna o pedido só se o contato bater com o cliente (LGPD).

    Pedido inexistente e contato errado dão o mesmo resultado, para não revelar
    quais números de pedido existem.
    """
    if not str(number).strip().lstrip('#').isdigit():
        log_event('order_lookup', LogCategory.AUDIT, order=str(number)[:20], outcome='invalid_number')
        return None
    order = (
        Order.objects.select_related('customer')
        .prefetch_related('items__product')
        .filter(pk=int(str(number).strip().lstrip('#')))
        .first()
    )
    verified = bool(order and matches_customer(order, contact))
    # Auditoria (LGPD): quem tentou ver qual pedido e o resultado. O contato não vai para o log; um
    # contato que não confere fica em WARNING, porque várias tentativas podem ser alguém testando dados.
    outcome = 'granted' if verified else ('contact_mismatch' if order else 'not_found')
    log_event('order_lookup', LogCategory.AUDIT, level=None if verified else logging.WARNING,
              order=str(number).strip().lstrip('#'), outcome=outcome,
              contact_type='email' if '@' in contact else 'phone')
    return order if verified else None


def _window(start: date, days: int, today: date) -> dict:
    deadline = start + timedelta(days=days)
    remaining = (deadline - today).days
    return {
        'prazo_ate': deadline.isoformat(),
        'dentro_do_prazo': remaining >= 0,
        'dias_restantes': max(remaining, 0),
    }


def return_windows(order: Order, today: date) -> dict:
    """Prazos de devolução, troca e garantia aplicáveis ao pedido."""
    if order.status == Order.Status.CANCELLED:
        return {'observacao': 'Pedido cancelado: não há prazos de troca ou devolução.'}
    if order.status != Order.Status.DELIVERED:
        return {
            'observacao': 'O pedido ainda não foi entregue. Os prazos de arrependimento, '
                          'troca por preferência e garantia contam a partir do recebimento.',
            'troca_por_defeito': _window(order.order_date, DEFECT_EXCHANGE_DAYS, today),
        }

    # Suposição: não há data real de entrega nos dados; usamos a previsão de
    # entrega dos pedidos entregues como data de recebimento.
    received = order.estimated_delivery or order.order_date
    windows = {
        'data_recebimento_considerada': received.isoformat(),
        'arrependimento': _window(received, RETURN_DAYS, today),
        'troca_por_preferencia': _window(received, PREFERENCE_EXCHANGE_DAYS, today),
        'troca_por_defeito': _window(order.order_date, DEFECT_EXCHANGE_DAYS, today),
        'garantia_legal': _window(received, LEGAL_WARRANTY_DAYS, today),
    }
    if not windows['troca_por_defeito']['dentro_do_prazo']:
        windows['observacao'] = (
            'Fora do prazo de troca na loja: defeitos devem ser tratados pela garantia do '
            'fabricante (de 6 meses a 2 anos, conforme o certificado). A loja pode intermediar.'
        )
    return windows


def order_details(order: Order, today: date) -> dict:
    data = {
        'numero': order.pk,
        'cliente': order.customer.name,
        'data_pedido': order.order_date.isoformat(),
        'status': order.get_status_display(),
        'situacao': STATUS_NEXT_STEP[order.status],
        'itens': [
            {'produto': item.product.name, 'quantidade': item.quantity}
            for item in order.items.all()
        ],
        'total_pago': brl(order.total_brl),
        'forma_pagamento': payment_method_label(order.payment_method),
    }
    if order.tracking_code:
        data['codigo_rastreio'] = order.tracking_code
    if order.estimated_delivery:
        data['previsao_entrega'] = order.estimated_delivery.isoformat()
    if order.notes:
        data['observacoes'] = order.notes
    data['prazos'] = return_windows(order, today)
    return data
