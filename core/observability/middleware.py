"""Middleware de observabilidade das requisições HTTP."""

import re
import time

from ..logging import LogCategory, log_event
from .context import bind_request

REQUEST_ID = re.compile(r'^[\w-]{1,64}$')
QUIET_PREFIXES = ('/static/',)  # arquivos estáticos não geram evento


class RequestLogMiddleware:
    """Dá um `request_id` a cada requisição (respeita o X-Request-ID recebido, para rastrear entre
    serviços), devolve no cabeçalho da resposta e registra `http_request` com status e duração.
    Todo log feito durante a requisição (views, grafo, LLM, ferramentas) sai com o mesmo id."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get('X-Request-ID', '')
        with bind_request(incoming if REQUEST_ID.match(incoming) else None) as request_id:
            request.request_id = request_id
            start = time.perf_counter()
            response = self.get_response(request)
            response['X-Request-ID'] = request_id
            if not request.path.startswith(QUIET_PREFIXES):
                log_event(
                    'http_request', LogCategory.HTTP,
                    method=request.method, path=request.path, status=response.status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000),
                )
        return response
