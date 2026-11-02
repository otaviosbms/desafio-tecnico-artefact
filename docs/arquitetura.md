# Arquitetura

## Estrutura de pastas

```
config/          projeto Django (settings lidos do .env, banco via DATABASE_URL)
store/           app com os dados da loja
  models.py      Category, Product, Promotion, Customer, Order, OrderItem
  text.py        normalização de texto para busca
  catalog.py     busca aproximada, preço com promoção, disponibilidade, alternativas
  pricing.py     regras de pagamento (PIX, parcelamento, frete) e formatação em R$
  orders.py      consulta de pedido com verificação e prazos de troca/devolução/garantia
  hours.py       horário de funcionamento: aberta agora? próxima abertura
  management/commands/load_data.py   importa data/*.csv (idempotente)
agent/           o agente de atendimento
  tools.py       schemas das ferramentas + execute_tool (erros viram dict)
  policies.py    tópicos da base de conhecimento + consultar_politicas
  knowledge/     manual de políticas reescrito em seções Markdown (uma por tópico)
  prompts.py     system prompt (persona + regras + contexto de data/hora)
  graph.py       grafo LangGraph: agent <-> tools, limites e fallbacks
  service.py     StoreAgent.reply/history + checkpointer (Postgres ou memória)
  views.py, urls.py             UI de chat (/) e API POST /api/mensagem/
  templates/agent/chat.html, static/agent/   front (HTML + CSS + JS puro)
  management/commands/chat.py   CLI de conversa
  management/commands/generate_examples.py   gera examples/*.md com o agente real
llm/             integração genérica com LLMs compatíveis com o SDK da OpenAI
  config.py      LLMConfig + presets de provedores
  client.py      LLMClient (chat, stream) e tipos normalizados
  tests.py
data/            CSVs e manual de políticas fornecidos pelo desafio
docs/            esta documentação
examples/        conversas de exemplo (transcrições reais)
```

## Fluxo do agente

```
Usuário (CLI / UI) → StoreAgent.reply(thread_id, texto)
   └─ grafo LangGraph (checkpointer Postgres guarda o histórico por thread_id)
        agent: system prompt (data/hora/loja aberta) + histórico → LLMClient.chat(tools)
          ├─ pediu ferramentas → tools: execute_tool → resultados → volta para agent
          └─ respondeu texto → fim
```

O modelo decide quais ferramentas chamar. As ferramentas devolvem dados já tratados
(preços com promoção calculada, status traduzido, prazos calculados), e o modelo só redige.

## Comandos úteis

```bash
python manage.py migrate
python manage.py load_data
python manage.py test
python manage.py chat --show-tools
python manage.py runserver   # UI em http://localhost:8000
```
