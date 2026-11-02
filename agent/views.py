import json
import logging
import uuid

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_safe

from .service import get_agent

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000

SUGGESTIONS = [
    'Quais violões disponíveis custam até R$ 1000?',
    'Quanto custa o Takamine GD20?',
    'Qual o endereço e o horário da loja?',
    'Me arrependi da compra, posso devolver meu pedido?',
]


def _thread_id(request) -> str:
    """Cada sessão do navegador tem a sua conversa."""
    if 'thread_id' not in request.session:
        request.session['thread_id'] = f'web-{uuid.uuid4().hex}'
    return request.session['thread_id']


@require_safe
def chat(request):
    thread_id = _thread_id(request)
    return render(request, 'agent/chat.html', {
        'history': get_agent().history(thread_id),
        'suggestions': SUGGESTIONS,
    })


@require_POST
def new_conversation(request):
    request.session.pop('thread_id', None)
    return redirect('agent:chat')


@require_POST
def send_message(request):
    try:
        text = (json.loads(request.body).get('texto') or '').strip()
    except (ValueError, AttributeError):
        return JsonResponse({'erro': 'Requisição inválida.'}, status=400)
    if not text:
        return JsonResponse({'erro': 'Digite uma mensagem.'}, status=400)
    if len(text) > MAX_MESSAGE_LENGTH:
        return JsonResponse({'erro': f'Mensagem muito longa (máximo de {MAX_MESSAGE_LENGTH} caracteres).'}, status=400)

    try:
        reply = get_agent().reply(_thread_id(request), text)
    except Exception:
        logger.exception('Falha ao responder a mensagem')
        return JsonResponse({'erro': 'Não consegui responder agora. Tente novamente em instantes.'}, status=500)
    return JsonResponse({'resposta': reply.text, 'ferramentas': reply.tool_calls})
