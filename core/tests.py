import json
import threading
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from core import clock, turn_context
from core.logging import LogCategory, log_event

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
        self.assertEqual(json.loads(record.getMessage()), record.event)

    def test_nivel_por_categoria(self):
        with self.assertLogs('emporio.events', 'INFO') as logs:
            log_event('fallback_reply', LogCategory.DEGRADATION)
            log_event('tool_failed', LogCategory.SILENT_FAILURE, error=ValueError('x'))
            log_event('llm_call', LogCategory.LLM_CALL)
        self.assertEqual([r.levelname for r in logs.records], ['WARNING', 'WARNING', 'INFO'])
        self.assertIsNone(logs.records[2].event['turn_id'])
