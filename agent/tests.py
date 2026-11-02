import json
import os
from datetime import datetime
from types import SimpleNamespace
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from langgraph.checkpoint.memory import InMemorySaver

from agent import clock
from agent.graph import FALLBACK_REPLY, MAX_TOOL_ROUNDS, trim_history
from agent.policies import KNOWLEDGE_DIR, TOPICS, consultar_politicas
from agent.service import AgentReply, StoreAgent
from agent.tools import execute_tool, get_tools
from llm import ChatResponse, LLMConfig, LLMError, ToolCall
from store.hours import store_status

TZ = ZoneInfo('America/Campo_Grande')


class ToolsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_data', stdout=StringIO())

    def test_definicoes_validas_e_serializaveis(self):
        tools = get_tools()
        self.assertEqual(
            {t.name for t in tools},
            {'buscar_produtos', 'detalhes_produto', 'listar_promocoes', 'condicoes_pagamento', 'consultar_pedido',
             'consultar_politicas'},
        )
        for tool in tools:
            definition = tool.definition()
            self.assertEqual(definition['function']['parameters']['type'], 'object')
            json.dumps(definition)
        categories = tools[0].parameters['properties']['categoria']['enum']
        self.assertIn('Violões', categories)

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
                result = execute_tool(name, args)
                self.assertNotIn('erro', result)
                json.dumps(result, ensure_ascii=False)

    def test_promocoes_ativas(self):
        result = execute_tool('listar_promocoes', {})
        self.assertEqual({p['id'] for p in result['promocoes_ativas']}, {90, 94, 121, 127})

    def test_condicoes_com_item_em_promocao(self):
        result = execute_tool('condicoes_pagamento', {'itens': [
            {'produto': 'Crafter HT-100', 'quantidade': 1},  # em promoção (18%)
            {'produto': 'Takamine GD20', 'quantidade': 1},
        ]})
        self.assertEqual(result['total'], 'R$ 4.166,18')
        self.assertEqual(result['pix']['valor'], 'R$ 4.056,23')  # 5% só sobre o Takamine

    def test_condicoes_rejeita_produto_indisponivel(self):
        result = execute_tool('condicoes_pagamento', {'itens': [{'produto': '96'}]})
        self.assertIn('erro', result)

    def test_detalhes_ambiguo(self):
        result = execute_tool('detalhes_produto', {'produto': 'Taylor'})
        self.assertTrue(result['ambiguo'])

    def test_pedido_sem_verificacao_nao_vaza_dados(self):
        result = execute_tool('consultar_pedido', {'numero_pedido': '4', 'email_ou_telefone': 'x@y.com'})
        self.assertEqual(set(result), {'erro'})

    def test_erros_viram_dict(self):
        self.assertIn('erro', execute_tool('inexistente', {}))
        self.assertIn('erro', execute_tool('detalhes_produto', {'nome_errado': 'x'}))


class StoreHoursTests(SimpleTestCase):
    def test_aberta_e_fechada(self):
        cases = [
            # (momento, aberta, próxima abertura esperada)
            (datetime(2026, 11, 2, 10, 0, tzinfo=TZ), True, None),  # segunda 10h
            (datetime(2026, 11, 2, 18, 0, tzinfo=TZ), False, 'terça-feira, 03/11 às 09:00'),  # fecha às 18h
            (datetime(2026, 11, 7, 12, 59, tzinfo=TZ), True, None),  # sábado antes das 13h
            (datetime(2026, 11, 7, 13, 30, tzinfo=TZ), False, 'segunda-feira, 09/11 às 09:00'),  # sábado à tarde
            (datetime(2026, 11, 8, 11, 0, tzinfo=TZ), False, 'segunda-feira, 09/11 às 09:00'),  # domingo
            (datetime(2026, 11, 2, 2, 0, tzinfo=TZ), False, 'segunda-feira, 02/11 às 09:00'),  # madrugada
        ]
        for now, is_open, next_opening in cases:
            with self.subTest(now=now):
                status = store_status(now)
                self.assertEqual(status['aberta'], is_open)
                self.assertEqual(status.get('proxima_abertura'), next_opening)


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
        now = datetime(2026, 11, 8, 11, 0, tzinfo=TZ)
        with clock.frozen(now):
            result = consultar_politicas(topicos=['horario'])
        self.assertFalse(result['situacao_agora']['aberta'])

    def test_inconsistencias_resolvidas_no_texto(self):
        contact = consultar_politicas(topicos=['loja'])['secoes']['loja']
        self.assertIn('contato@emporiodamusica.com.br', contact)
        self.assertNotIn('empório', contact.split('E-mail:')[1].splitlines()[0])
        self.assertIn('(67) 3341-4444', contact)
        self.assertNotIn('3321-4500', contact)

    def test_topico_invalido(self):
        self.assertIn('erro', consultar_politicas(topicos=['inexistente']))
        self.assertIn('erro', consultar_politicas(topicos=[]))


class FakeLLM:
    """LLM roteirizado: devolve as respostas na ordem e registra o que recebeu."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.config = LLMConfig(model='modelo-falso', api_key='x')

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append({'messages': messages, 'tools': tools})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def text(content):
    return ChatResponse(content=content)


def calls_tool(name, arguments, call_id='c1'):
    return ChatResponse(content=None, tool_calls=[
        ToolCall(id=call_id, name=name, arguments=arguments, raw_arguments=json.dumps(arguments)),
    ])


class AgentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_data', stdout=StringIO())

    def make_agent(self, llm):
        now = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)  # segunda, 10h: loja aberta
        return StoreAgent(llm=llm, checkpointer=InMemorySaver(), now=lambda: now)

    def test_loop_de_ferramentas(self):
        llm = FakeLLM(calls_tool('detalhes_produto', {'produto': 'Takamine GD20'}), text('Custa R$ 2.199,00.'))
        reply = self.make_agent(llm).reply('t1', 'Quanto custa o Takamine GD20?')

        self.assertEqual(reply.text, 'Custa R$ 2.199,00.')
        self.assertEqual(reply.tool_calls, [{'nome': 'detalhes_produto', 'argumentos': {'produto': 'Takamine GD20'}}])
        tool_message = llm.calls[1]['messages'][-1]
        self.assertEqual(tool_message['role'], 'tool')
        self.assertIn('R$ 2.199,00', tool_message['content'])

    def test_system_prompt_com_contexto_atual(self):
        llm = FakeLLM(text('Oi!'))
        self.make_agent(llm).reply('t1', 'Oi')
        system = llm.calls[0]['messages'][0]
        self.assertEqual(system['role'], 'system')
        self.assertIn('segunda-feira, 02/11/2026, 10:00', system['content'])
        self.assertIn('A loja está aberta agora', system['content'])

    def test_historico_persiste_entre_mensagens(self):
        llm = FakeLLM(text('Oi, Ana!'), text('Claro.'))
        agent = self.make_agent(llm)
        agent.reply('t1', 'Oi, sou a Ana')
        agent.reply('t1', 'Pode me ajudar?')

        sent = [m['content'] for m in llm.calls[1]['messages'][1:]]
        self.assertEqual(sent, ['Oi, sou a Ana', 'Oi, Ana!', 'Pode me ajudar?'])
        self.assertEqual(len(agent.history('t1')), 4)
        self.assertEqual(agent.history('outra'), [])  # conversas isoladas

    def test_limite_de_rodadas_forca_resposta_sem_ferramentas(self):
        rounds = [calls_tool('listar_promocoes', {}, call_id=f'c{i}') for i in range(MAX_TOOL_ROUNDS)]
        llm = FakeLLM(*rounds, text('Resposta final.'))
        reply = self.make_agent(llm).reply('t1', 'Promoções?')

        self.assertEqual(reply.text, 'Resposta final.')
        self.assertIsNone(llm.calls[-1]['tools'])
        self.assertTrue(all(call['tools'] for call in llm.calls[:-1]))

    def test_falha_do_provedor_vira_resposta_amigavel(self):
        with self.assertLogs('agent.graph', 'ERROR'):
            reply = self.make_agent(FakeLLM(LLMError('timeout'))).reply('t1', 'Oi')
        self.assertEqual(reply.text, FALLBACK_REPLY)

    def test_resposta_vazia_vira_resposta_amigavel(self):
        reply = self.make_agent(FakeLLM(text(''))).reply('t1', 'Oi')
        self.assertEqual(reply.text, FALLBACK_REPLY)

    def test_argumentos_invalidos_voltam_como_erro_para_o_modelo(self):
        broken = ChatResponse(content=None, tool_calls=[
            ToolCall(id='c1', name='detalhes_produto', arguments={}, raw_arguments='{quebrado'),
        ])
        llm = FakeLLM(broken, text('Pode repetir?'))
        self.make_agent(llm).reply('t1', 'Oi')
        self.assertIn('erro', json.loads(llm.calls[1]['messages'][-1]['content']))


    def test_rastro_registra_llm_e_ferramentas_por_turno(self):
        llm = FakeLLM(calls_tool('detalhes_produto', {'produto': 'Takamine GD20'}), text('Custa R$ 2.199,00.'))
        agent = self.make_agent(llm)
        reply = agent.reply('t1', 'Quanto custa o Takamine GD20?')

        self.assertEqual([e['tipo'] for e in reply.trace], ['llm', 'ferramenta', 'llm'])
        self.assertEqual(reply.trace[0]['pediu_ferramentas'], ['detalhes_produto'])
        self.assertEqual(reply.trace[1]['resultado']['preco'], 'R$ 2.199,00')
        self.assertTrue(all(e['turno'] == 1 for e in reply.trace))
        self.assertEqual(agent.trace('t1'), reply.trace)
        # O rastro nunca vai para o LLM.
        self.assertNotIn('duracao_ms', json.dumps(llm.calls[-1]['messages']))

    def test_data_simulada_chega_ao_prompt_e_as_ferramentas(self):
        args = {'numero_pedido': '4', 'email_ou_telefone': 'lucas.mendes@jmail.com'}
        llm = FakeLLM(calls_tool('consultar_pedido', args), text('Está no prazo.'))
        agent = StoreAgent(llm=llm, checkpointer=InMemorySaver())  # sem `now` fixo: usa o relógio
        reply = agent.reply('t1', 'Posso devolver?', now=datetime(2025, 12, 24, 10, 0, tzinfo=TZ))

        self.assertIn('24/12/2025, 10:00', llm.calls[0]['messages'][0]['content'])
        prazos = reply.trace[1]['resultado']['prazos']
        self.assertTrue(prazos['arrependimento']['dentro_do_prazo'])


class TrimHistoryTests(SimpleTestCase):
    def test_corta_sempre_numa_mensagem_do_cliente(self):
        messages = [
            {'role': 'user', 'content': '1'},
            {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c1'}]},
            {'role': 'tool', 'tool_call_id': 'c1', 'content': '{}'},
            {'role': 'assistant', 'content': 'ok'},
            {'role': 'user', 'content': '2'},
            {'role': 'assistant', 'content': 'ok'},
        ]
        trimmed = trim_history(messages, limit=4)
        self.assertEqual(trimmed[0], {'role': 'user', 'content': '2'})
        self.assertEqual(trim_history(messages, limit=10), messages)


class FakeAgent:
    def __init__(self, fail=False):
        self.threads = {}
        self.fail = fail
        self.calls = []
        self.llm = SimpleNamespace(config=LLMConfig(model='modelo-falso', api_key='x'))

    def reply(self, thread_id, text, now=None):
        self.calls.append({'thread': thread_id, 'texto': text, 'now': now})
        if self.fail:
            raise RuntimeError('boom')
        self.threads.setdefault(thread_id, []).extend([
            {'role': 'user', 'content': text}, {'role': 'assistant', 'content': f'eco: {text}'},
        ])
        trace = [{'turno': 1, 'tipo': 'llm', 'duracao_ms': 5}]
        return AgentReply(text=f'eco: {text}', tool_calls=[{'nome': 'listar_promocoes', 'argumentos': {}}],
                          trace=trace, duration_ms=7)

    def history(self, thread_id):
        return self.threads.get(thread_id, [])

    def trace(self, thread_id):
        return []


class ChatViewTests(TestCase):
    def setUp(self):
        self.agent = FakeAgent()
        self.get_agent = mock.patch('agent.views.get_agent', return_value=self.agent).start()
        self.addCleanup(mock.patch.stopall)
        env = {'LLM_PROVIDER': 'custom', 'LLM_BASE_URL': 'http://llm/v1', 'LLM_API_KEY': 'k', 'LLM_MODEL': 'modelo-env'}
        mock.patch.dict(os.environ, env).start()

    def send(self, payload):
        return self.client.post(reverse('agent:send_message'), json.dumps(payload), content_type='application/json')

    def page_data(self):
        return self.client.get(reverse('agent:chat')).context['page_data']

    def test_pagina_inicial(self):
        response = self.client.get(reverse('agent:chat'))
        self.assertContains(response, 'Ambiente de testes do agente')
        data = response.context['page_data']
        self.assertTrue(data['thread_id'].startswith('web-'))
        self.assertEqual(data['llm']['modelo'], 'modelo-env')
        self.assertIn('Quanto custa o Takamine GD20?', data['cenarios'][1]['mensagens'])

    def test_envia_mensagem_e_mantem_a_conversa_da_sessao(self):
        response = self.send({'texto': 'Oi'})
        self.assertEqual(response.json(), {
            'resposta': 'eco: Oi',
            'ferramentas': [{'nome': 'listar_promocoes', 'argumentos': {}}],
            'rastro': [{'turno': 1, 'tipo': 'llm', 'duracao_ms': 5}],
            'duracao_ms': 7,
            'modelo': 'modelo-falso',
        })
        self.assertEqual(self.page_data()['historico'][1]['content'], 'eco: Oi')

    def test_configuracao_da_mensagem(self):
        self.send({'texto': 'Oi', 'config': {'modelo': 'outro/modelo:free', 'temperatura': 0.3, 'agora': '2026-11-08T11:00'}})
        self.get_agent.assert_called_with('outro/modelo:free', 0.3)
        now = self.agent.calls[-1]['now']
        self.assertEqual((now.weekday(), now.hour, str(now.tzinfo)), (6, 11, 'America/Campo_Grande'))

        # Modelo igual ao do .env usa o agente padrão.
        self.send({'texto': 'Oi', 'config': {'modelo': 'modelo-env'}})
        self.get_agent.assert_called_with(None, None)

    def test_configuracao_invalida(self):
        for config in [
            {'modelo': 'rm -rf /'}, {'temperatura': 3}, {'temperatura': 'quente'},
            {'agora': 'ontem'}, 'nao-e-objeto',
        ]:
            with self.subTest(config=config):
                self.assertEqual(self.send({'texto': 'Oi', 'config': config}).status_code, 400)

    def test_nova_conversa_troca_a_thread(self):
        self.send({'texto': 'Oi'})
        old = self.client.session['thread_id']
        response = self.client.post(reverse('agent:new_conversation'), HTTP_ACCEPT='application/json')
        self.assertNotEqual(response.json()['thread_id'], old)
        self.assertEqual(self.client.session['thread_id'], response.json()['thread_id'])

    def test_abrir_conversa_existente(self):
        self.agent.threads['cli-123'] = [{'role': 'user', 'content': 'Oi'}, {'role': 'assistant', 'content': 'Olá'}]
        response = self.client.post(reverse('agent:open_conversation'), json.dumps({'thread_id': 'cli-123'}),
                                    content_type='application/json')
        self.assertEqual(response.json()['historico'][1]['content'], 'Olá')
        self.assertEqual(self.client.session['thread_id'], 'cli-123')
        bad = self.client.post(reverse('agent:open_conversation'), json.dumps({'thread_id': '../x'}),
                               content_type='application/json')
        self.assertEqual(bad.status_code, 400)

    def test_contexto_com_data_simulada(self):
        response = self.client.get(reverse('agent:context'), {'agora': '2026-11-08T11:00'})
        data = response.json()
        self.assertFalse(data['situacao_loja']['aberta'])
        self.assertIn('domingo, 08/11/2026, 11:00', data['system_prompt'])
        self.assertIn('consultar_pedido', [t['name'] for t in data['ferramentas']])
        self.assertEqual(self.client.get(reverse('agent:context'), {'agora': 'x'}).status_code, 400)

    def test_dados_de_teste_so_em_debug(self):
        call_command('load_data', stdout=StringIO())
        with self.settings(DEBUG=True):
            self.assertEqual(len(self.page_data()['pedidos_teste']), 20)
        with self.settings(DEBUG=False):
            self.assertEqual(self.page_data()['pedidos_teste'], [])

    def test_validacoes(self):
        self.assertEqual(self.send({'texto': '   '}).status_code, 400)
        self.assertEqual(self.send({'texto': 'x' * 2001}).status_code, 400)
        self.assertEqual(self.send(['lista']).status_code, 400)
        bad = self.client.post(reverse('agent:send_message'), 'não é json', content_type='application/json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.get(reverse('agent:send_message')).status_code, 405)

    def test_erro_inesperado_retorna_500_com_mensagem(self):
        self.agent.fail = True
        with self.assertLogs('agent.views', 'ERROR'):
            response = self.send({'texto': 'Oi'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('erro', response.json())

    def test_csrf_exigido(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('agent:send_message'), json.dumps({'texto': 'Oi'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
