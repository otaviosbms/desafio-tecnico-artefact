import json

from django.test import SimpleTestCase

from conversation.management.commands.eval_router import DEFAULT_DATASET, load_cases, score
from llm import ChatResponse, LLMConfig, LLMError, LLMService
from router.intents import INTENT_TOOLS, Intent, tools_for
from router.prompts import build_messages
from core.text import is_small_talk
from router.service import IntentRouter
from tools.handlers import TOOLS



class ScriptedClient:
    def __init__(self, *results):
        self.config = LLMConfig(model='roteador-falso', api_key='x')
        self.results = list(results)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({'messages': messages, **kwargs})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return ChatResponse(content=result if isinstance(result, str) else json.dumps(result))


def router(*results, mode='enforce', **kwargs):
    client = ScriptedClient(*results)
    return IntentRouter(LLMService(client), mode=mode, **kwargs), client


class IntentsTests(SimpleTestCase):
    def test_toda_intencao_tem_ferramentas_validas(self):
        names = {tool.name for tool in TOOLS}
        self.assertEqual(set(INTENT_TOOLS), set(Intent))
        for intent, tools in INTENT_TOOLS.items():
            self.assertLessEqual(set(tools), names, intent)

    def test_uniao_sem_repeticao(self):
        self.assertEqual(tools_for([Intent.PEDIDO, Intent.POLITICAS]), ['consultar_pedido', 'consultar_politicas'])
        self.assertEqual(tools_for([Intent.SAUDACAO_CONVERSA]), [])
        self.assertEqual(len(tools_for(list(Intent))), len(TOOLS))  # todas juntas cobrem todas as ferramentas

    def test_atalho_de_conversa(self):
        for text in ['oi', 'Olá!', 'bom dia', 'Muito obrigado!', 'valeu, tchau', 'e aí, tudo bem?']:
            self.assertTrue(is_small_talk(text), text)
        for text in ['ok', 'sim', 'oi, quanto custa o violão?', 'bom dia, cadê meu pedido?', '', '???']:
            self.assertFalse(is_small_talk(text), text)


class IntentRouterTests(SimpleTestCase):
    def classify(self, router_, message='quero devolver o pedido 4', last=None):
        with self.assertLogs('emporio.events', 'INFO') as logs:
            decision = router_.classify(message, last)
        return decision, [r.event for r in logs.records]

    def test_enforce_libera_so_as_ferramentas_das_intencoes(self):
        r, client = router({'intents': ['pedido', 'politicas'], 'confidence': 0.9, 'reasoning': 'devolução'})
        decision, events = self.classify(r)

        self.assertEqual(decision.allowed_tools, ['consultar_pedido', 'consultar_politicas'])
        self.assertEqual(decision.source, 'llm')
        self.assertEqual(client.calls[0]['response_format']['type'], 'json_schema')
        decided = events[-1]
        self.assertEqual((decided['category'], decided['event']), ('DECISION', 'intent_classified'))
        self.assertEqual(decided['intencoes'], ['pedido', 'politicas'])

    def test_shadow_classifica_mas_nao_restringe(self):
        r, _ = router({'intents': ['politicas'], 'confidence': 0.95, 'reasoning': 'x'}, mode='shadow')
        decision, _ = self.classify(r)
        self.assertIsNone(decision.allowed_tools)
        self.assertEqual(decision.proposed_tools, ['consultar_politicas'])

    def test_off_nao_chama_o_llm(self):
        r, client = router(mode='off')
        decision, _ = self.classify(r)
        self.assertIsNone(decision.allowed_tools)
        self.assertEqual(client.calls, [])

    def test_atalho_sem_llm(self):
        r, client = router()
        decision, _ = self.classify(r, 'Boa tarde!')
        self.assertEqual(decision.source, 'shortcut')
        self.assertEqual(decision.allowed_tools, [])
        self.assertEqual(client.calls, [])

    def test_falha_do_llm_libera_tudo(self):
        r, _ = router(LLMError('timeout'))
        decision, events = self.classify(r)
        self.assertIsNone(decision.allowed_tools)
        self.assertEqual(decision.source, 'fallback')
        self.assertEqual(len(decision.llm_calls), 1)
        self.assertIn(('DEGRADATION', 'router_fail_open'), {(e['category'], e['event']) for e in events})

    def test_saida_invalida_libera_tudo(self):
        r, _ = router({'intents': ['nao_existe'], 'confidence': 0.9, 'reasoning': 'x'})
        decision, _ = self.classify(r)
        self.assertIsNone(decision.allowed_tools)
        self.assertEqual(decision.source, 'fallback')

    def test_confianca_baixa_libera_tudo(self):
        r, _ = router({'intents': ['catalogo'], 'confidence': 0.3, 'reasoning': 'x'})
        decision, events = self.classify(r)
        self.assertIsNone(decision.allowed_tools)
        self.assertEqual(decision.proposed_tools, ['buscar_produtos', 'detalhes_produto', 'listar_promocoes'])
        self.assertIn('low_confidence', [e.get('reason') for e in events])

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            router(mode='talvez')



class EvalRouterTests(SimpleTestCase):
    def test_dataset_valido_e_cobre_todas_as_intencoes(self):
        cases = load_cases(DEFAULT_DATASET)
        self.assertGreaterEqual(len(cases), 30)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        self.assertEqual({i for c in cases for i in c['intencoes']}, set(Intent))

    def test_pontuacao(self):
        case = {'intencoes': ['pedido', 'politicas'], 'alternativas': [['pedido']]}
        self.assertEqual(score(case, ['politicas', 'pedido']), {'acerto': True, 'cobertura': True})
        self.assertEqual(score(case, ['pedido']), {'acerto': True, 'cobertura': True})  # alternativa aceita
        self.assertEqual(score(case, ['pedido', 'catalogo']), {'acerto': False, 'cobertura': True})
        self.assertEqual(score(case, ['politicas']), {'acerto': False, 'cobertura': False})

class RouterPromptTests(SimpleTestCase):
    def test_contexto_e_delimitadores(self):
        messages = build_messages('  e no PIX?  ', 'O Takamine GD20 custa R$ 2.199,00. Quer saber no PIX?')
        self.assertIn('<cliente>\ne no PIX?\n</cliente>', messages[1]['content'])
        self.assertIn('Quer saber no PIX?', messages[1]['content'])
        self.assertIn('(início da conversa)', build_messages('oi')[1]['content'])
        long = 'x' * 1000 + 'PERGUNTA FINAL'
        self.assertIn('PERGUNTA FINAL', build_messages('sim', long)[1]['content'])  # guarda o fim da resposta

