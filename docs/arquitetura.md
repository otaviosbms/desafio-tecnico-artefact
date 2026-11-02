# Arquitetura

## Estrutura de pastas

```
config/          projeto Django (settings lidos do .env, banco via DATABASE_URL)
store/           app com os dados da loja
  models.py      Category, Product, Promotion, Customer, Order, OrderItem
  management/commands/load_data.py   importa data/*.csv (idempotente)
llm/             integração genérica com LLMs compatíveis com o SDK da OpenAI
  config.py      LLMConfig + presets de provedores
  client.py      LLMClient (chat, stream) e tipos normalizados
  tests.py
data/            CSVs e manual de políticas fornecidos pelo desafio
docs/            esta documentação
```

## Fluxo planejado do agente

```
Usuário (template Django) → view /chat → grafo LangGraph
   ├─ nó agente: LLMClient.chat(mensagens, tools)
   │      ⇄ nó de ferramentas: consultas ao ORM e às seções das políticas
   └─ checkpointer Postgres: histórico por thread_id (uma conversa = uma thread)
```

O modelo decide quais ferramentas chamar. As ferramentas devolvem dados já tratados
(preços com promoção calculada, status traduzido), e o modelo só redige a resposta.

## Comandos úteis

```bash
python manage.py migrate
python manage.py load_data
python manage.py test
```
