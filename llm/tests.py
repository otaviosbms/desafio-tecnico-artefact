import os
from types import SimpleNamespace
from unittest import TestCase, mock

import openai
from openai.types.chat import ChatCompletion

from llm import LLMClient, LLMConfig, LLMConfigError, LLMError, function_tool, tool_result_message


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

    def test_erro_do_provedor_vira_llm_error(self):
        fake = FakeOpenAI(openai.APIError('falhou', request=None, body=None))
        with self.assertRaises(LLMError):
            LLMClient(CONFIG, client=fake).chat([])

    def test_tool_result_message_serializa(self):
        message = tool_result_message('c1', {'preco': 10})
        self.assertEqual(message, {'role': 'tool', 'tool_call_id': 'c1', 'content': '{"preco": 10}'})
