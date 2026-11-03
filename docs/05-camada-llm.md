# 5. Camada de LLM (`llm/`)

Integração genérica com qualquer LLM cujo provedor siga o padrão de **Chat Completions** do
SDK da OpenAI. O provedor e o modelo são escolhidos apenas pelo `.env`.

## Por que um módulo próprio

- **Um padrão, vários provedores:** a API de Chat Completions virou o padrão de fato. OpenAI,
  Anthropic, Gemini, Groq, OpenRouter, DeepSeek, Ollama e LM Studio expõem endpoints compatíveis.
  Um módulo fino com presets permite **trocar de provedor ou modelo só pelo `.env`**, inclusive
  rodar 100% local com Ollama, sem chave paga.
- **Chat Completions, não a Responses API:** a Responses API é específica da OpenAI.
- **Respostas normalizadas** (`ChatResponse`, `ToolCall`): o resto do projeto não depende dos
  tipos do SDK, e argumentos de ferramenta com JSON inválido não derrubam o agente.
- **Alternativas descartadas:** `langchain-openai` (mais uma camada de abstração e dependência) e
  LiteLLM (bom, mas desnecessário quando o padrão OpenAI já cobre os provedores desejados).

O módulo tem duas camadas: o `LLMClient` (transporte: `chat` e `stream`) e o `LLMService` (o ponto
único de chamada do resto do projeto, com papel, logs, custo e saída estruturada).

## Modelo em uso

**OpenAI** com `gpt-6-luna`, desde as avaliações de 02/11/2026 (resultados no capítulo 9):

- **Latência:** de 1 a 4 s por chamada; um turno completo (guardrails, roteador e agente) leva
  poucos segundos.
- **Ferramentas:** no Chat Completions, o `gpt-6-luna` só aceita function calling sem raciocínio
  (`LLM_REASONING_EFFORT=none`); sem isso, a API devolve 400 em toda chamada com ferramentas.
- **Custo:** o modelo ainda não está na tabela de `llm/pricing.py`, então o custo aparece como 0
  (com um aviso no log).

Antes, o projeto usou o OpenRouter com `nvidia/nemotron-3-ultra-550b-a55b:free`: gratuito, mas com
latência de até minutos por chamada e cota diária (erro 429). Os dois funcionam só trocando o `.env`.

## Configuração

| Variável | Descrição |
|---|---|
| `LLM_PROVIDER` | Preset: `openai` (padrão), `anthropic`, `gemini`, `groq`, `openrouter`, `deepseek`, `ollama`, `lmstudio` ou `custom` |
| `LLM_MODEL` | Nome do modelo no provedor (obrigatório) |
| `LLM_BASE_URL` | Sobrescreve a URL do preset (obrigatório para `custom`) |
| `LLM_API_KEY` | Sobrescreve a chave; sem ela, usa a variável do provedor (`OPENAI_API_KEY`, `GROQ_API_KEY`, ...) |
| `LLM_TEMPERATURE` | Opcional; se ausente, não é enviada (alguns modelos de raciocínio a rejeitam) |
| `LLM_REASONING_EFFORT` | Opcional (`none`, `low`, `medium`, `high`), para modelos de raciocínio; se ausente, não é enviado |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | Padrão: 60 s e 2 tentativas |
| `LLM_MODEL_AGENT` / `LLM_MODEL_ROUTER` / `LLM_MODEL_GUARDRAILS` | Modelo de cada camada: `modelo` ou `provedor:modelo`; vazio = `LLM_MODEL` (ver abaixo) |
| `LLM_REASONING_EFFORT_AGENT` / `_ROUTER` / `_GUARDRAILS` | Reasoning da camada quando ela usa outro modelo |
| `LLM_STRUCTURED_OUTPUT` | `auto` (padrão), `json_schema`, `json_object` ou `prompt` (ver abaixo) |

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

### Modelo por camada

Cada camada de IA tem o seu modelo, e até o seu provedor, configurável no `.env`:

| Camada | Variável | Papel no código |
|---|---|---|
| Conversa (o agente que responde) | `LLM_MODEL_AGENT` | `agent` |
| Roteador de intenção | `LLM_MODEL_ROUTER` | `router` |
| Guardrails | `LLM_MODEL_GUARDRAILS` | `guardrails` |

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-6-luna                          # padrão de todas as camadas
OPENAI_API_KEY=sk-...
LLM_MODEL_ROUTER=gpt-4.1-mini                 # mesmo provedor e chave
LLM_MODEL_GUARDRAILS=groq:llama-3.3-70b-versatile   # outro provedor, com a chave dele
GROQ_API_KEY=gsk-...
```

- **`provedor:modelo`:** o prefixo só conta se for um preset (`openai`, `groq`, `gemini`, ...);
  nomes do OpenRouter com `:` (`nvidia/x:free`) continuam sendo só o modelo. O provedor novo usa a
  URL e a chave do preset dele.
- **Reasoning:** `LLM_REASONING_EFFORT` vale para o `LLM_MODEL`. Uma camada com outro modelo não o
  herda (um modelo pode recusar o parâmetro); use `LLM_REASONING_EFFORT_<CAMADA>` se precisar.
- **Falha cedo:** os clientes de todas as camadas são montados quando o serviço sobe; um provedor
  sem chave gera `LLMConfigError` na subida, e não no meio de uma conversa.
- **UI de testes:** os campos de modelo (agente, roteador e guardrails) aceitam o mesmo formato, por
  mensagem; um provedor sem chave devolve um erro 400 com a variável que falta.

Tudo isso fica em `llm/` (`roles.py`, `LLMConfig.with_model`, `LLMService.with_overrides`): o resto
da aplicação só pede um papel ao `LLMService` e não monta clientes nem configurações.

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

## `LLMService`: o ponto único de chamada (`llm/service.py`)

O agente, o roteador e os guardrails não usam o `LLMClient` direto: toda
chamada passa pelo `LLMService`, que recebe sempre **quem chamou** (`caller`) e **o papel**
(`role`), e acrescenta:

- **modelo por papel** (`llm/roles.py`): `agent`, `router` e `guardrails`, cada um com o seu
  modelo e provedor (ver "Modelo por camada"). A UI de testes pode trocar o modelo de cada papel por
  mensagem;
- **logs e uso:** cada chamada gera um `LLM_CALL` (caller, papel, modelo, duração, tokens, custo,
  sucesso) e soma tokens e custo no `TurnContext` do turno;
- **custo estimado** (`llm/pricing.py`): tabela em US$ por 1M de tokens. Modelos `:free` custam 0;
  um modelo fora da tabela custa 0 e gera um aviso, uma vez por modelo;
- **nunca lança exceção:** `chat` devolve um `LLMCall` (`response` é `None` em caso de falha, com
  o motivo em `error`); `complete_text` e `complete_json` devolvem `None` e registram uma
  `DEGRADATION`. Quem chama decide o fallback.

```python
from llm import LLMService

service = LLMService()
call = service.chat(caller='agent.respond', role='agent', messages=messages, tools=tools)
if call.ok:
    resposta = call.response          # ChatResponse, como o do LLMClient
print(call.model, call.duration_ms, call.cost_usd)

class Intencao(BaseModel):
    intent: str
    confidence: float

resultado = service.complete_json(caller='router.classify', role='router',
                                  messages=messages, output_model=Intencao)  # Intencao | None
```

### Saída estruturada em três níveis

Nem todo provedor compatível com a OpenAI aceita `response_format` com `json_schema`. Em `auto`,
o `complete_json` tenta, nesta ordem:

1. **`json_schema` estrito:** o schema do Pydantic, ajustado ao modo `strict` da OpenAI
   (`additionalProperties: false` e todas as propriedades em `required`, inclusive em objetos
   aninhados);
2. **`json_object`:** se o provedor recusar o nível 1 (HTTP 400/404/422 ou mensagem citando
   `response_format`/`unsupported`), com o schema descrito numa mensagem de sistema;
3. **`prompt`:** se também recusar o nível 2, sem `response_format`; o primeiro objeto `{...}` do
   texto é extraído (tolera cercas de código e texto em volta).

- O nível que funcionou fica em memória por modelo, para não repetir as tentativas recusadas.
- Erros de rede, cota (429) ou timeout **não** rebaixam o nível: devolvem `None` direto.
- Em todos os níveis a resposta é validada com `output_model.model_validate_json`. JSON inválido
  ou fora do schema vira `None` com `DEGRADATION` (`reason='invalid_output'`).
- `LLM_STRUCTURED_OUTPUT` fixa um nível (útil quando já se sabe o que o provedor suporta).

## Testes

`python manage.py test llm`: usa clientes falsos, sem rede. Cobre cada nível de saída estruturada,
a memória do nível por modelo, JSON inválido, erro de rede, modelo por papel e custo.

---

Anterior: [4. Estágios de IA](04-estagios-de-ia.md) · [Índice](README.md) · Próximo: [6. Ferramentas e políticas](06-tools.md)
