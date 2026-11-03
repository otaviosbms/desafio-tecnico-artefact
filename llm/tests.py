import os
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase, mock

import openai
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from core import turn_context
from llm import (
    ChatResponse, LLMClient, LLMConfig, LLMConfigError, LLMError, LLMService, function_tool, tool_result_message,
)
from llm import pricing
from llm.config import split_model_ref
from llm.roles import config_for, describe, model_for
from llm.service import _extract_json, _strict_schema


def _completion(message, finish_reason='stop'):
    return ChatCompletion.model_validate({
        'id': 'cmpl-1',
        'object': 'chat.completion',
        'created': 0,
        'model': 'modelo-teste',
        'choices': [{'index': 0, 'message': {'role': 'assistant', **message}, 'finish_reason': finish_reason}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
    })


class FakeOpenAI:
    """Substitui o openai.OpenAI registrando os parâmetros enviados."""

    def __init__(self, result):
        self.calls = []

        def create(**params):
            self.calls.append(params)
            if isinstance(result, Exception):
                raise result
            return result

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


CONFIG = LLMConfig(model='modelo-teste', api_key='x')


class LLMConfigFromEnvTests(TestCase):
    def from_env(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return LLMConfig.from_env()

    def test_preset_le_chave_do_provedor(self):
        config = self.from_env(LLM_PROVIDER='groq', LLM_MODEL='llama', GROQ_API_KEY='gk')
        self.assertEqual(config.base_url, 'https://api.groq.com/openai/v1')
        self.assertEqual(config.api_key, 'gk')
        self.assertIsNone(config.temperature)

    def test_openai_usa_endpoint_padrao(self):
        config = self.from_env(LLM_MODEL='gpt', OPENAI_API_KEY='sk')
        self.assertEqual(config.provider, 'openai')
        self.assertIsNone(config.base_url)

    def test_servidor_local_dispensa_chave(self):
        config = self.from_env(LLM_PROVIDER='ollama', LLM_MODEL='qwen')
        self.assertEqual(config.api_key, 'ollama')

    def test_custom_com_overrides(self):
        config = self.from_env(
            LLM_PROVIDER='custom', LLM_MODEL='m', LLM_BASE_URL='http://x/v1',
            LLM_API_KEY='k', LLM_TEMPERATURE='0.3', LLM_TIMEOUT='10',
        )
        self.assertEqual((config.base_url, config.api_key, config.temperature, config.timeout), ('http://x/v1', 'k', 0.3, 10.0))

    def test_erros_de_configuracao(self):
        cases = [
            {},  # sem modelo
            {'LLM_MODEL': 'm'},  # openai sem chave
            {'LLM_MODEL': 'm', 'LLM_PROVIDER': 'inexistente'},
            {'LLM_MODEL': 'm', 'LLM_PROVIDER': 'custom', 'LLM_API_KEY': 'k'},  # custom sem URL
        ]
        for env in cases:
            with self.subTest(env=env), self.assertRaises(LLMConfigError):
                self.from_env(**env)


class LLMClientTests(TestCase):
    def test_resposta_de_texto(self):
        fake = FakeOpenAI(_completion({'content': 'Olá!'}))
        response = LLMClient(CONFIG, client=fake).chat([{'role': 'user', 'content': 'oi'}])

        self.assertEqual(response.content, 'Olá!')
        self.assertEqual(response.tool_calls, [])
        self.assertEqual(response.usage['total_tokens'], 15)
        # Sem ferramentas/temperatura, nada disso é enviado ao provedor.
        self.assertEqual(set(fake.calls[0]), {'model', 'messages'})

    def test_tool_calls_e_historico(self):
        fake = FakeOpenAI(_completion({
            'content': None,
            'tool_calls': [
                {'id': 'c1', 'type': 'function', 'function': {'name': 'buscar', 'arguments': '{"termo": "violão"}'}},
                {'id': 'c2', 'type': 'function', 'function': {'name': 'buscar', 'arguments': '{quebrado'}},
            ],
        }, finish_reason='tool_calls'))
        tools = [function_tool('buscar', 'Busca produtos', {'type': 'object', 'properties': {}})]
        response = LLMClient(CONFIG, client=fake).chat([], tools=tools, tool_choice='auto')

        self.assertEqual(fake.calls[0]['tools'], tools)
        self.assertEqual(response.tool_calls[0].arguments, {'termo': 'violão'})
        self.assertIsNotNone(response.tool_calls[1].arguments_error)
        message = response.to_message()
        self.assertEqual(message['tool_calls'][1]['function']['arguments'], '{quebrado')

    def test_tool_choice_ignorado_sem_tools(self):
        fake = FakeOpenAI(_completion({'content': 'ok'}))
        LLMClient(CONFIG, client=fake).chat([], tool_choice='auto')
        self.assertNotIn('tool_choice', fake.calls[0])

    def test_temperatura_e_kwargs_extras(self):
        fake = FakeOpenAI(_completion({'content': 'ok'}))
        config = LLMConfig(model='m', api_key='x', temperature=0.1)
        LLMClient(config, client=fake).chat([], max_tokens=50)
        self.assertEqual((fake.calls[0]['temperature'], fake.calls[0]['max_tokens']), (0.1, 50))
        self.assertNotIn('reasoning_effort', fake.calls[0])

    def test_reasoning_effort(self):
        fake = FakeOpenAI(_completion({'content': 'ok'}))
        LLMClient(LLMConfig(model='m', api_key='x', reasoning_effort='none'), client=fake).chat([])
        self.assertEqual(fake.calls[0]['reasoning_effort'], 'none')
        with mock.patch.dict(os.environ, {'LLM_MODEL': 'm', 'LLM_API_KEY': 'k', 'LLM_REASONING_EFFORT': 'low'}):
            self.assertEqual(LLMConfig.from_env().reasoning_effort, 'low')

    def test_erro_do_provedor_vira_llm_error(self):
        fake = FakeOpenAI(openai.APIError('falhou', request=None, body=None))
        with self.assertRaises(LLMError):
            LLMClient(CONFIG, client=fake).chat([])

    def test_tool_result_message_serializa(self):
        message = tool_result_message('c1', {'preco': 10})
        self.assertEqual(message, {'role': 'tool', 'tool_call_id': 'c1', 'content': '{"preco": 10}'})


class ScriptedClient:
    """LLMClient roteirizado: devolve os resultados em ordem e registra os parâmetros."""

    def __init__(self, *results, model='modelo-teste'):
        self.config = LLMConfig(model=model, api_key='x')
        self.results = list(results)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({'messages': messages, **kwargs})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, ChatResponse) else ChatResponse(
            content=result, usage={'prompt_tokens': 1000, 'completion_tokens': 100, 'total_tokens': 1100},
        )


class Intent(BaseModel):
    intent: str
    confidence: float = 1.0


MESSAGES = [{'role': 'user', 'content': 'Quanto custa o violão?'}]
REJECTED = LLMError('response_format json_schema is not supported', status_code=400)


class LLMServiceStructuredTests(TestCase):
    def complete(self, client, **kwargs):
        service = LLMService(client, **kwargs)
        with self.assertLogs('emporio.events', 'INFO') as logs:
            result = service.complete_json(caller='router.classify', role='router', messages=MESSAGES,
                                           output_model=Intent)
        return service, result, [r.event for r in logs.records]

    def test_json_schema_estrito(self):
        client = ScriptedClient('{"intent": "catalogo", "confidence": 0.9}')
        _, result, events = self.complete(client)

        self.assertEqual(result, Intent(intent='catalogo', confidence=0.9))
        response_format = client.calls[0]['response_format']
        self.assertEqual(response_format['type'], 'json_schema')
        self.assertTrue(response_format['json_schema']['strict'])
        self.assertEqual(response_format['json_schema']['schema']['required'], ['intent', 'confidence'])
        self.assertEqual(client.calls[0]['messages'], MESSAGES)  # schema vai no response_format, não no prompt
        self.assertEqual(events[0]['caller'], 'router.classify')

    def test_provedor_recusa_schema_cai_para_json_object_e_lembra(self):
        client = ScriptedClient(REJECTED, '{"intent": "pedido"}', '{"intent": "politicas"}')
        service, result, events = self.complete(client)

        self.assertEqual(result.intent, 'pedido')
        self.assertEqual(client.calls[1]['response_format'], {'type': 'json_object'})
        self.assertIn('JSON Schema', client.calls[1]['messages'][-1]['content'])
        self.assertIn('structured_output_downgraded', [e['event'] for e in events])
        # A próxima chamada já começa no nível que funcionou.
        service.complete_json(caller='router.classify', role='router', messages=MESSAGES, output_model=Intent)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(client.calls[2]['response_format'], {'type': 'json_object'})

    def test_ultimo_nivel_extrai_json_do_texto(self):
        rejected_object = LLMError('Unsupported parameter: response_format', status_code=400)
        client = ScriptedClient(REJECTED, rejected_object, 'Claro! ```json\n{"intent": "saudacao"}\n``` pronto')
        _, result, _ = self.complete(client)

        self.assertEqual(result.intent, 'saudacao')
        self.assertNotIn('response_format', client.calls[2])

    def test_json_invalido_vira_none_e_degradacao(self):
        _, result, events = self.complete(ScriptedClient('{"confidence": "alta"}'))
        self.assertIsNone(result)
        degraded = [e for e in events if e['category'] == 'DEGRADATION']
        self.assertEqual(degraded[0]['reason'], 'invalid_output')

    def test_erro_de_rede_nao_rebaixa_o_nivel(self):
        client = ScriptedClient(LLMError('timeout'))
        service, result, events = self.complete(client)
        self.assertIsNone(result)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(events[-1]['reason'], 'llm_error')
        self.assertEqual(service._structured_level, {'modelo-teste': 0})

    def test_nivel_fixo_pela_configuracao(self):
        client = ScriptedClient('{"intent": "pedido"}')
        _, result, _ = self.complete(client, structured_output='prompt')
        self.assertEqual(result.intent, 'pedido')
        self.assertNotIn('response_format', client.calls[0])

    def test_nivel_invalido(self):
        with self.assertRaises(ValueError):
            LLMService(ScriptedClient(), structured_output='xml')


class LLMServiceTests(TestCase):
    def test_complete_text_e_uso_somado_no_turno(self):
        client = ScriptedClient('  Oi!  ', model='openai/gpt-6-luna')
        service = LLMService(client)
        with self.assertLogs('emporio.events', 'INFO') as logs, turn_context.start_turn('t1') as turn:
            text = service.complete_text(caller='teste', role='agent', messages=MESSAGES)

        self.assertEqual(text, 'Oi!')
        self.assertEqual(turn.llm_calls, 1)
        self.assertEqual(turn.tokens['total_tokens'], 1100)
        # 1000 × 0,10 + 100 × 0,50 por milhão
        self.assertEqual(turn.cost_usd, Decimal('0.00015'))
        event = logs.records[0].event
        self.assertEqual((event['category'], event['caller'], event['turn_id']), ('LLM_CALL', 'teste', turn.turn_id))

    def test_chat_nunca_lanca(self):
        service = LLMService(ScriptedClient(LLMError('caiu')))
        with self.assertLogs('emporio.events', 'INFO'), turn_context.start_turn('t1') as turn:
            call = service.chat(caller='agent.respond', role='agent', messages=MESSAGES, tools=None)
        self.assertFalse(call.ok)
        self.assertEqual(call.error, 'caiu')
        self.assertEqual(turn.llm_calls, 1)

    def test_texto_vazio_vira_none(self):
        service = LLMService(ScriptedClient('   '))
        with self.assertLogs('emporio.events', 'INFO') as logs:
            self.assertIsNone(service.complete_text(caller='teste', role='agent', messages=MESSAGES))
        self.assertEqual(logs.records[-1].event['reason'], 'empty_response')

    def test_modelo_por_papel(self):
        base = ScriptedClient(model='grande')
        with mock.patch.dict(os.environ, {'LLM_MODEL_ROUTER': 'pequeno'}):
            service = LLMService(base)
            self.assertIs(service.client_for('agent'), base)
            router = service.client_for('router')
        self.assertEqual(router.config.model, 'pequeno')
        self.assertEqual(router.config.api_key, base.config.api_key)  # mesmo provedor e chave
        self.assertIs(service.client_for('router'), router)  # em cache

    def test_cliente_fixo_por_papel(self):
        fixed = ScriptedClient(model='escolhido-na-ui')
        with mock.patch.dict(os.environ, {'LLM_MODEL_AGENT': 'do-env'}):
            service = LLMService(ScriptedClient(), role_clients={'agent': fixed})
            self.assertIs(service.client_for('agent'), fixed)

    def test_papel_desconhecido(self):
        with self.assertRaises(ValueError):
            model_for('juiz', 'm')


class ModelPerLayerTests(TestCase):
    BASE = LLMConfig(model='gpt-6-luna', provider='openai', api_key='sk-base', reasoning_effort='none')

    def test_referencia_com_e_sem_provedor(self):
        self.assertEqual(split_model_ref('groq:llama-3.3-70b'), ('groq', 'llama-3.3-70b'))
        self.assertEqual(split_model_ref('gpt-4.1-mini'), (None, 'gpt-4.1-mini'))
        # ":" do OpenRouter não é prefixo de provedor
        self.assertEqual(split_model_ref('nvidia/nemotron:free'), (None, 'nvidia/nemotron:free'))

    def test_camada_em_outro_provedor_usa_a_chave_dele(self):
        env = {'LLM_MODEL_GUARDRAILS': 'groq:llama-3.3-70b', 'GROQ_API_KEY': 'gsk-x'}
        with mock.patch.dict(os.environ, env):
            config = config_for('guardrails', self.BASE)
        self.assertEqual((config.provider, config.model, config.api_key), ('groq', 'llama-3.3-70b', 'gsk-x'))
        self.assertEqual(config.base_url, 'https://api.groq.com/openai/v1')
        self.assertIsNone(config.reasoning_effort)  # o do LLM_MODEL não vale para outro modelo

    def test_outro_modelo_do_mesmo_provedor_tem_reasoning_proprio(self):
        env = {'LLM_MODEL_ROUTER': 'gpt-4.1-mini', 'LLM_REASONING_EFFORT_ROUTER': 'low'}
        with mock.patch.dict(os.environ, env):
            config = config_for('router', self.BASE)
        self.assertEqual((config.model, config.api_key, config.reasoning_effort), ('gpt-4.1-mini', 'sk-base', 'low'))
        self.assertEqual(config_for('agent', self.BASE), self.BASE)  # sem variável: o LLM_MODEL

    def test_provedor_sem_chave(self):
        with mock.patch.dict(os.environ, {'LLM_MODEL_ROUTER': 'groq:llama', 'GROQ_API_KEY': ''}):
            with self.assertRaises(LLMConfigError):
                config_for('router', self.BASE)

    def test_escolha_da_ui_sobrepoe_o_env_e_describe(self):
        with mock.patch.dict(os.environ, {'LLM_MODEL_AGENT': 'gpt-4.1'}):
            self.assertEqual(config_for('agent', self.BASE, 'gpt-4.1-nano', temperature=0.3).model, 'gpt-4.1-nano')
            roles = describe(self.BASE)
        self.assertEqual(roles['agent']['ref'], 'gpt-4.1')
        self.assertEqual(roles['router']['ref'], 'gpt-6-luna')

    def test_servico_com_modelos_trocados(self):
        env = {'LLM_PROVIDER': 'openai', 'LLM_MODEL': 'gpt-6-luna', 'OPENAI_API_KEY': 'sk-x', 'GROQ_API_KEY': 'gsk-x'}
        with mock.patch.dict(os.environ, env):
            service = LLMService.with_overrides({'guardrails': 'groq:llama-3.3-70b', 'router': None},
                                                agent_temperature=0.2)
        self.assertEqual(service.client_for('guardrails').config.provider, 'groq')
        self.assertEqual(service.client_for('agent').config.temperature, 0.2)
        self.assertEqual(service.client_for('router').config.model, 'gpt-6-luna')


class StructuredHelpersTests(TestCase):
    def test_strict_schema_inclui_objetos_aninhados(self):
        class Inner(BaseModel):
            a: int = 0

        class Outer(BaseModel):
            inner: Inner
            note: str | None = None

        schema = _strict_schema(Outer.model_json_schema())
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['required'], ['inner', 'note'])
        self.assertEqual(schema['$defs']['Inner']['required'], ['a'])

    def test_extract_json(self):
        self.assertEqual(_extract_json('ok {"a": {"b": 1}} fim {"c": 2}'), '{"a": {"b": 1}}')
        self.assertEqual(_extract_json('{quebrado} depois {"a": 1}'), '{"a": 1}')
        self.assertIsNone(_extract_json('sem json'))
        self.assertIsNone(_extract_json(None))


class PricingTests(TestCase):
    def test_custos(self):
        usage = {'prompt_tokens': 1_000_000, 'completion_tokens': 1_000_000}
        self.assertEqual(pricing.cost('gpt-6-luna', usage), Decimal('0.60'))
        self.assertEqual(pricing.cost('openai/gpt-6-luna', usage), Decimal('0.60'))
        self.assertEqual(pricing.cost('gpt-5.4-mini-2026-03-05', usage), Decimal('5.25'))  # versão com data
        self.assertEqual(pricing.cost('gpt-5', usage), Decimal('11.25'))  # não confunde com gpt-5.x
        self.assertEqual(pricing.cost('nvidia/nemotron-3-ultra-550b-a55b:free', usage), 0)
        with self.assertLogs('llm.pricing', 'WARNING'):
            self.assertEqual(pricing.cost('modelo-sem-preco-x', usage), 0)
        with self.assertLogs('llm.pricing', 'WARNING'):
            self.assertEqual(pricing.cost('gpt-4.1-mini', usage), 0)  # só a família GPT-5 em diante
