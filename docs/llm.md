# Módulo `llm/`

Integração genérica com qualquer LLM cujo provedor siga o padrão de **Chat Completions** do
SDK da OpenAI. O provedor e o modelo são escolhidos apenas pelo `.env`.

## Configuração

| Variável | Descrição |
|---|---|
| `LLM_PROVIDER` | Preset: `openai` (padrão), `anthropic`, `gemini`, `groq`, `openrouter`, `deepseek`, `ollama`, `lmstudio` ou `custom` |
| `LLM_MODEL` | Nome do modelo no provedor (obrigatório) |
| `LLM_BASE_URL` | Sobrescreve a URL do preset (obrigatório para `custom`) |
| `LLM_API_KEY` | Sobrescreve a chave; sem ela, usa a variável do provedor (`OPENAI_API_KEY`, `GROQ_API_KEY`, ...) |
| `LLM_TEMPERATURE` | Opcional; se ausente, não é enviada (alguns modelos de raciocínio a rejeitam) |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | Padrão: 60 s e 2 tentativas |

Exemplos:

```env
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...

# Local, sem custo (precisa do Ollama rodando)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b

# Qualquer outro endpoint compatível
LLM_PROVIDER=custom
LLM_BASE_URL=https://meu-provedor/v1
LLM_API_KEY=...
LLM_MODEL=...
```

Para function calling, o modelo escolhido precisa suportar ferramentas.

## Uso

```python
from llm import LLMClient, function_tool, tool_result_message

client = LLMClient()  # lê o .env; ou LLMClient(LLMConfig(...))

tools = [function_tool('buscar_produtos', 'Busca no catálogo', {
    'type': 'object',
    'properties': {'termo': {'type': 'string'}},
    'required': ['termo'],
})]

messages = [{'role': 'user', 'content': 'Tem violão Yamaha?'}]
resp = client.chat(messages, tools=tools)
messages.append(resp.to_message())          # guarda a resposta no histórico
for call in resp.tool_calls:                 # call.arguments já vem como dict
    result = {'erro': call.arguments_error} if call.arguments_error else executar(call)
    messages.append(tool_result_message(call.id, result))
resp = client.chat(messages, tools=tools)   # resposta final em resp.content

for trecho in client.stream(messages):       # streaming de texto
    print(trecho, end='')
```

Erros do provedor (rede, autenticação, rate limit) viram `LLMError`. Problemas de
configuração geram `LLMConfigError`.

## Testes

`python manage.py test llm` (ou `python -m unittest llm.tests`): usa um cliente falso, sem rede.
