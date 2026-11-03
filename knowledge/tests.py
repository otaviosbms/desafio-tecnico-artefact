from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from core import clock
from knowledge.policies import KNOWLEDGE_DIR, TOPICS, consultar_politicas

TZ = ZoneInfo('America/Campo_Grande')


class PoliciesTests(SimpleTestCase):
    def test_todo_topico_tem_arquivo_e_vice_versa(self):
        files = {p.stem for p in KNOWLEDGE_DIR.glob('*.md')}
        self.assertEqual(files, set(TOPICS))

    def test_consulta_varios_topicos(self):
        result = consultar_politicas(topicos=['pagamento', 'trocas_e_devolucoes'])
        self.assertEqual(set(result['secoes']), {'pagamento', 'trocas_e_devolucoes'})
        self.assertIn('7 dias corridos', result['secoes']['trocas_e_devolucoes'])
        self.assertNotIn('situacao_agora', result)

    def test_horario_inclui_situacao_atual(self):
        now = datetime(2026, 11, 8, 11, 0, tzinfo=TZ)  # domingo
        self.assertFalse(consultar_politicas(topicos=['horario'], now=now)['situacao_agora']['aberta'])
        with clock.frozen(now):  # sem `now`, usa o relógio (que pode estar simulado)
            self.assertFalse(consultar_politicas(topicos=['horario'])['situacao_agora']['aberta'])

    def test_inconsistencias_resolvidas_no_texto(self):
        contact = consultar_politicas(topicos=['loja'])['secoes']['loja']
        self.assertIn('contato@emporiodamusica.com.br', contact)
        self.assertNotIn('empório', contact.split('E-mail:')[1].splitlines()[0])
        self.assertIn('(67) 3341-4444', contact)
        self.assertNotIn('3321-4500', contact)

    def test_topico_invalido(self):
        self.assertIn('erro', consultar_politicas(topicos=['inexistente']))
        self.assertIn('erro', consultar_politicas(topicos=[]))
