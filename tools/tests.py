import json
from datetime import datetime
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from tools import registry
from tools.contracts import ToolContext, ToolResult, parameters_schema
from tools.executor import ToolExecutor
from tools.handlers.condicoes_pagamento import CondicoesPagamentoInput

TZ = ZoneInfo('America/Campo_Grande')
CTX = ToolContext(now=datetime(2026, 11, 2, 10, 0, tzinfo=TZ), thread_id='t1', turn_id='abc')


def run(name, args, ctx=CTX, **kwargs):
    """Executa como o grafo faz e devolve o payload que vai ao modelo."""
    return ToolExecutor().run(name, args, ctx, **kwargs).to_model_payload()


class ToolsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_data', stdout=StringIO())

    def test_definicoes_validas_e_serializaveis(self):
        definitions = registry.definitions()
        self.assertEqual(
            [d['function']['name'] for d in definitions],
            ['buscar_produtos', 'detalhes_produto', 'listar_promocoes', 'condicoes_pagamento', 'consultar_pedido',
             'consultar_politicas'],
        )
        for definition in definitions:
            self.assertEqual(definition['function']['parameters']['type'], 'object')
            json.dumps(definition)
        categories = definitions[0]['function']['parameters']['properties']['categoria']['enum']
        self.assertIn('Violões', categories)

    def test_definicoes_filtradas(self):
        names = [d['function']['name'] for d in registry.definitions(['consultar_politicas', 'listar_promocoes'])]
        self.assertEqual(names, ['listar_promocoes', 'consultar_politicas'])

    def test_resultados_sao_serializaveis(self):
        calls = [
            ('buscar_produtos', {'categoria': 'Violões', 'preco_max': 1000}),
            ('detalhes_produto', {'produto': 'Takamine GD20'}),
            ('listar_promocoes', {}),
            ('condicoes_pagamento', {'itens': [{'produto': 'Takamine GD20'}]}),
            ('consultar_pedido', {'numero_pedido': '4', 'email_ou_telefone': 'lucas.mendes@jmail.com'}),
        ]
        for name, args in calls:
            with self.subTest(tool=name):
                result = ToolExecutor().run(name, args, CTX)
                self.assertTrue(result.ok, result.error_message)
                self.assertNotIn('erro', result.to_model_payload())
                json.dumps(result.to_model_payload(), ensure_ascii=False)

    def test_promocoes_ativas(self):
        result = run('listar_promocoes', {})
        self.assertEqual({p['id'] for p in result['promocoes_ativas']}, {90, 94, 121, 127})

    def test_condicoes_com_item_em_promocao(self):
        result = run('condicoes_pagamento', {'itens': [
            {'produto': 'Crafter HT-100', 'quantidade': 1},  # em promoção (18%)
            {'produto': 'Takamine GD20', 'quantidade': 1},
        ]})
        self.assertEqual(result['total'], 'R$ 4.166,18')
        self.assertEqual(result['pix']['valor'], 'R$ 4.056,23')  # 5% só sobre o Takamine

    def test_condicoes_rejeita_produto_indisponivel(self):
        result = ToolExecutor().run('condicoes_pagamento', {'itens': [{'produto': '96'}]}, CTX)
        self.assertEqual(result.error, 'unavailable')
        self.assertIn('erro', result.to_model_payload())

    def test_condicoes_sem_itens(self):
        self.assertEqual(run('condicoes_pagamento', {'itens': []}), {'erro': 'Informe ao menos um produto.'})

    def test_detalhes_ambiguo(self):
        result = ToolExecutor().run('detalhes_produto', {'produto': 'Taylor'}, CTX)
        self.assertEqual(result.error, 'ambiguous')
        self.assertTrue(result.to_model_payload()['ambiguo'])

    def test_busca_com_categoria_inexistente(self):
        result = ToolExecutor().run('buscar_produtos', {'categoria': 'xyzwq'}, CTX)
        self.assertEqual(result.error, 'not_found')
        self.assertEqual(result.to_model_payload()['produtos'], [])

    def test_pedido_sem_verificacao_nao_vaza_dados(self):
        result = ToolExecutor().run('consultar_pedido', {'numero_pedido': '4', 'email_ou_telefone': 'x@y.com'}, CTX)
        self.assertEqual(result.error, 'verification_failed')
        self.assertEqual(set(result.to_model_payload()), {'erro'})

    def test_pedido_sem_contato_pede_o_contato(self):
        for contact in ['', 'nao informado', '4']:
            result = ToolExecutor().run('consultar_pedido', {'numero_pedido': '4', 'email_ou_telefone': contact}, CTX)
            self.assertEqual(result.error, 'missing_contact', contact)
            self.assertIn('Peça ao cliente', result.to_model_payload()['erro'])

    def test_execucao_gera_evento_sem_os_valores_dos_argumentos(self):
        args = {'numero_pedido': '4', 'email_ou_telefone': 'lucas.mendes@jmail.com'}
        with self.assertLogs('emporio.events', 'INFO') as logs:
            ToolExecutor().run('consultar_pedido', args, CTX)
        executed = next(r.event for r in logs.records if r.event['event'] == 'tool_executed')
        self.assertEqual((executed['category'], executed['tool'], executed['success']), ('TOOL', 'consultar_pedido', True))
        self.assertEqual(executed['arguments'], ['email_ou_telefone', 'numero_pedido'])
        self.assertNotIn('lucas.mendes', str([r.event for r in logs.records]))

    def test_pedido_aceita_numero_como_inteiro(self):
        result = run('consultar_pedido', {'numero_pedido': 4, 'email_ou_telefone': 'lucas.mendes@jmail.com'})
        self.assertNotIn('erro', result)

    def test_prazos_do_pedido_usam_o_relogio_do_contexto(self):
        args = {'numero_pedido': '4', 'email_ou_telefone': 'lucas.mendes@jmail.com'}
        early = run('consultar_pedido', args, ToolContext(now=datetime(2025, 12, 24, 10, 0, tzinfo=TZ)))
        late = run('consultar_pedido', args, ToolContext(now=datetime(2027, 1, 1, 10, 0, tzinfo=TZ)))
        self.assertTrue(early['prazos']['arrependimento']['dentro_do_prazo'])
        self.assertFalse(late['prazos']['arrependimento']['dentro_do_prazo'])

    def test_politicas_pela_ferramenta(self):
        result = run('consultar_politicas', {'topicos': 'horario'})  # um tópico solto vira lista
        self.assertIn('horario', result['secoes'])
        self.assertTrue(result['situacao_agora']['aberta'])  # segunda 10h, do contexto
        self.assertIn('Tópicos inválidos', run('consultar_politicas', {'topicos': ['xyz']})['erro'])


class ExecutorErrorsTests(SimpleTestCase):
    def run_logged(self, *args, **kwargs):
        with self.assertLogs('emporio.events', 'WARNING') as logs:
            result = ToolExecutor().run(*args, **kwargs)
        return result, logs.records[0].event

    def test_ferramenta_desconhecida(self):
        result, event = self.run_logged('inexistente', '{}', CTX)
        self.assertEqual(result.error, 'tool_not_found')
        self.assertEqual((event['category'], event['event'], event['tool']), ('SILENT_FAILURE', 'tool_not_found',
                                                                              'inexistente'))

    def test_json_invalido(self):
        result, _ = self.run_logged('detalhes_produto', '{quebrado', CTX)
        self.assertEqual(result.error, 'tool_invalid_args')
        self.assertIn('JSON inválido', result.error_message)
        self.assertEqual(result.meta['arguments'], '{quebrado')

    def test_argumentos_fora_do_schema(self):
        result, _ = self.run_logged('detalhes_produto', {'nome_errado': 'x'}, CTX)
        self.assertEqual(result.error, 'tool_invalid_args')
        self.assertIn('produto', result.error_message)  # diz qual campo faltou

    def test_ferramenta_nao_liberada(self):
        result, _ = self.run_logged('consultar_pedido', '{}', CTX, allowed=['consultar_politicas'])
        self.assertEqual(result.error, 'tool_not_allowed')

    def test_excecao_no_handler(self):
        handler = registry.get_tool('listar_promocoes')
        with mock.patch.object(handler, 'execute', side_effect=RuntimeError('banco fora')), \
                self.assertLogs('tools.executor', 'ERROR'):
            result, event = self.run_logged('listar_promocoes', '{}', CTX)
        self.assertEqual(result.error, 'tool_failed')
        self.assertIn('Falha interna', result.error_message)
        self.assertIn('banco fora', event['detail'])


class ContractsTests(SimpleTestCase):
    def test_payload_de_erro_preserva_dados(self):
        result = ToolResult(data={'produtos': []}, error='not_found', error_message='Categoria não encontrada.')
        self.assertEqual(result.to_model_payload(), {'produtos': [], 'erro': 'Categoria não encontrada.'})
        self.assertEqual(ToolResult(data={'a': 1}, meta={'x': 2}).to_model_payload(), {'a': 1})

    def test_schema_inlina_modelos_aninhados_e_tira_titulos(self):
        schema = parameters_schema(CondicoesPagamentoInput)
        self.assertNotIn('$defs', json.dumps(schema))
        self.assertNotIn('title', json.dumps(schema))
        item = schema['properties']['itens']['items']
        self.assertEqual(item['required'], ['produto'])
        self.assertEqual(item['properties']['quantidade'], {'type': 'integer', 'minimum': 1})
