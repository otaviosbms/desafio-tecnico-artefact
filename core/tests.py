import json
import logging
import sys
import threading
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import clock, turn_context
from core.logging import LogCategory, log_event
from core.observability import CentralHandler, ContextFilter, JsonFormatter, bind_request, register_sink
from core.observability import sinks as sinks_module
from core.observability.middleware import RequestLogMiddleware

TZ = ZoneInfo('America/Campo_Grande')


class ClockTests(SimpleTestCase):
    def test_frozen_e_parse(self):
        moment = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)
        with clock.frozen(moment):
            self.assertEqual(clock.now(), moment)
            self.assertEqual(clock.today(), moment.date())
        self.assertNotEqual(clock.now(), moment)
        self.assertEqual(clock.parse('2026-11-02T10:00'), moment)
        self.assertIsNone(clock.parse(''))


class TurnContextTests(SimpleTestCase):
    def test_fora_de_um_turno(self):
        self.assertIsNone(turn_context.current())
        turn_context.add_llm_usage({'total_tokens': 10})  # não quebra sem turno aberto

    def test_soma_uso_de_llm(self):
        with turn_context.start_turn('t1') as turn:
            turn_context.add_llm_usage({'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120})
            turn_context.add_llm_usage({'prompt_tokens': 50, 'completion_tokens': None}, Decimal('0.01'))
            turn_context.add_llm_usage({})
        self.assertEqual(turn.llm_calls, 3)
        self.assertEqual(turn.tokens, {'prompt_tokens': 150, 'completion_tokens': 20, 'total_tokens': 120})
        self.assertEqual(turn.cost_usd, Decimal('0.01'))
        self.assertEqual(turn.summary()['cost_usd'], '0.01')

    def test_turnos_isolados(self):
        with turn_context.start_turn('t1') as first:
            turn_context.add_llm_usage({'total_tokens': 5})
        with turn_context.start_turn('t1') as second:
            self.assertIs(turn_context.current(), second)
        self.assertIsNone(turn_context.current())
        self.assertNotEqual(first.turn_id, second.turn_id)
        self.assertEqual(second.llm_calls, 0)

    def test_turnos_em_threads_diferentes_nao_se_misturam(self):
        seen = {}

        def run(name):
            with turn_context.start_turn(name):
                turn_context.add_llm_usage({'total_tokens': 1})
                seen[name] = turn_context.current().thread_id

        threads = [threading.Thread(target=run, args=(f't{i}',)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(seen, {'t0': 't0', 't1': 't1', 't2': 't2'})


class LogEventTests(SimpleTestCase):
    def test_evento_leva_o_turno_atual(self):
        with self.assertLogs('emporio.events', 'INFO') as logs:
            with turn_context.start_turn('t1') as turn:
                log_event('turn_started', LogCategory.LIFECYCLE, extra='x')
        record = logs.records[0]
        self.assertEqual(record.event, {
            'event': 'turn_started', 'category': 'LIFECYCLE', 'turn_id': turn.turn_id, 'thread_id': 't1', 'extra': 'x',
        })
        self.assertEqual(record.getMessage(), 'turn_started')

    def test_nivel_por_categoria(self):
        with self.assertLogs('emporio.events', 'INFO') as logs:
            log_event('fallback_reply', LogCategory.DEGRADATION)
            log_event('tool_failed', LogCategory.SILENT_FAILURE, error=ValueError('x'))
            log_event('llm_call', LogCategory.LLM_CALL)
        self.assertEqual([r.levelname for r in logs.records], ['WARNING', 'WARNING', 'INFO'])
        self.assertIsNone(logs.records[2].event['turn_id'])


class MemorySink(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(self.format(record)))


class ObservabilityTests(SimpleTestCase):
    def record(self, msg='oi', **extra):
        record = logging.LogRecord('teste', logging.INFO, __file__, 1, msg, None, None)
        record.__dict__.update(extra)
        return record

    def test_formato_unico_com_contexto_e_evento(self):
        with bind_request('req-1'), turn_context.start_turn('t1') as turn:
            record = self.record()
            ContextFilter().filter(record)
        record.event = {'event': 'llm_call', 'category': 'LLM_CALL', 'tokens': {'total_tokens': 5}}
        data = json.loads(JsonFormatter().format(record))
        self.assertEqual((data['request_id'], data['turn_id'], data['thread_id']), ('req-1', turn.turn_id, 't1'))
        self.assertEqual((data['event'], data['tokens'], data['level'], data['logger']),
                         ('llm_call', {'total_tokens': 5}, 'INFO', 'teste'))
        self.assertIn('service', data)
        self.assertTrue(data['timestamp'].endswith('+00:00'))

    def test_excecao_vira_campo(self):
        try:
            raise ValueError('falhou')
        except ValueError:
            record = logging.LogRecord('teste', logging.ERROR, __file__, 1, 'erro', None, sys.exc_info())
        self.assertIn('ValueError: falhou', json.loads(JsonFormatter().format(record))['exception'])

    def test_handler_central_entrega_a_todos_os_sinks(self):
        memory = MemorySink()
        register_sink('memoria')(lambda: memory)
        self.addCleanup(sinks_module.SINKS.pop, 'memoria')
        handler = CentralHandler('memoria, inexistente')  # sink desconhecido é ignorado
        logger = logging.getLogger('teste.central')
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)  # nos testes, o root fica em ERROR
        self.addCleanup(logger.removeHandler, handler)
        with bind_request('req-2'):
            logger.warning('estoque %s', 'baixo', extra={'event': {'event': 'x', 'category': 'DECISION'}})
        handler.close()  # esvazia a fila
        self.assertEqual(len(memory.lines), 1)
        line = memory.lines[0]
        self.assertEqual((line['message'], line['request_id'], line['event']), ('estoque baixo', 'req-2', 'x'))

    def test_middleware_marca_a_requisicao(self):
        middleware = RequestLogMiddleware(lambda request: HttpResponse('ok'))
        with self.assertLogs('emporio.events', 'INFO') as logs:
            response = middleware(RequestFactory().get('/api/contexto/', HTTP_X_REQUEST_ID='abc-123'))
        self.assertEqual(response['X-Request-ID'], 'abc-123')
        event = logs.records[0].event
        self.assertEqual((event['event'], event['category'], event['status'], event['path']),
                         ('http_request', 'HTTP', 200, '/api/contexto/'))
        generated = middleware(RequestFactory().get('/static/x.css', HTTP_X_REQUEST_ID='<script>'))
        self.assertRegex(generated['X-Request-ID'], r'^[0-9a-f]{16}$')  # id inválido é trocado

    def test_log_do_django_depois_do_middleware_leva_o_id(self):
        request = RequestFactory().get('/x')
        request.request_id = 'req-9'
        record = self.record(request=request)
        ContextFilter().filter(record)
        self.assertEqual(record.request_id, 'req-9')
