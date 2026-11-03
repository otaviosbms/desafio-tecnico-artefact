# 1. Visão geral

## O desafio

Desafio técnico de AI Engineer da Artefact: prototipar um **agente de atendimento por
mensagens de texto** para a **Empório da Música**, loja fictícia de instrumentos musicais
em Campo Grande/MS. A equipe da loja está sobrecarregada com perguntas recorrentes
(horários, status de pedido, preço e disponibilidade de produtos).

O agente deve:

- assumir uma **persona** alinhada ao tom da loja (informal, mas profissional);
- responder com base no contexto disponível;
- saber **quando consultar dados** (estoque, preço, pedidos) e **quando consultar políticas**
  (trocas, horários, pagamento);
- lidar com perguntas **fora do escopo** da loja.

Única restrição obrigatória: **Python**.

### Entregáveis

1. Repositório público no GitHub, com histórico de commits real (sem force-push).
2. `README.md` com instruções para rodar, justificativa das decisões técnicas, limitações
   conhecidas e uso de assistentes de código.
3. De 3 a 5 exemplos de conversa. Pelo menos um não trivial, consultando dados ou aplicando políticas.

Cenários sugeridos pelo enunciado: violões até R$ 1000, endereço da loja, preço do Takamine GD20 e
arrependimento e devolução de compra. Todos estão em [`examples/`](../examples/README.md).

### Material fornecido (`data/`)

- `categories.csv`, `products.csv`, `promotions.csv`, `customers.csv`, `orders.csv`, `order_items.csv`;
- `politicas_da_loja.pdf`: manual interno de atendimento (horários, pagamento, trocas, frete,
  promoções, diretrizes do WhatsApp, garantia, LGPD).

Detalhes e inconsistências no [capítulo 7](07-dados-e-regras.md).

## A solução em uma página

Cada mensagem do cliente passa por um pipeline de estágios (um grafo LangGraph):

```
mensagem ─► guardrails ─► roteador de intenção ─► agente ⇄ ferramentas ─► finalize ─► resposta
             (pode        (decide quais           (LLM redige;      (dados e regras
             bloquear)     ferramentas liberar)    não faz contas)    em Python)
```

- **Guardrails:** regras determinísticas e um gate LLM barram ou orientam mensagens problemáticas
  (manipulação, dados de terceiros) antes do agente.
- **Roteador:** classifica a intenção (catálogo, pagamento, pedido, políticas, conversa, fora de
  escopo) e define quais ferramentas o agente pode usar.
- **Agente:** o LLM decide quais ferramentas chamar e redige a resposta. Preços, promoções, PIX,
  parcelamento, prazos de devolução e horário de funcionamento são calculados em Python; o modelo
  só escreve.
- **Políticas:** o manual virou 9 seções Markdown revisadas, consultadas por tópico (sem RAG vetorial).
- **Provedor de LLM:** qualquer um compatível com a API de Chat Completions da OpenAI, escolhido
  pelo `.env`, com modelo próprio para cada papel (agente, roteador, guardrails).
- **Ambiente de testes:** uma UI web que mostra, por mensagem, o rastro das chamadas, as decisões
  dos estágios, o system prompt e os schemas, com data/hora simulada e troca de modelo.

Stack: Python 3.14, Django 6, LangGraph, SDK da OpenAI, PostgreSQL (com fallback para SQLite). Tudo
roda com `docker compose up`: aplicação, banco e pgAdmin.

## Estrutura de pastas

```
config/          projeto Django (settings lidos do .env, banco via DATABASE_URL, LOGGING)
core/            infraestrutura transversal: relógio, TurnContext, logs estruturados, texto
llm/             integração genérica com LLMs compatíveis com o SDK da OpenAI (cap. 5)
store/           dados da loja (models) e regras de negócio: catálogo, preços, pedidos, horário (cap. 7)
knowledge/       manual de políticas em seções Markdown + consulta por tópico (cap. 6)
tools/           ferramentas do agente: contrato, registry, executor e handlers (cap. 6)
guardrails/      portão de entrada: detector por regras + gate LLM (cap. 4)
router/          roteador de intenção (cap. 4)
conversation/    orquestrador, grafo, prompt do agente, UI, API e comandos (caps. 2, 3 e 8)
tests/           testes transversais: snapshots e regra de camadas (cap. 9)
evals/           datasets de avaliação com o LLM real (cap. 9)
data/            CSVs e manual de políticas fornecidos pelo desafio
docker/          configuração do pgAdmin (servidor já cadastrado)
Dockerfile, docker-compose.yml   imagem da aplicação; serviços web, db e pgadmin
docs/            esta documentação
examples/        conversas de exemplo (transcrições reais)
```

As dependências entre pacotes seguem camadas (`core` ← `llm`, `store` ← `knowledge`, `router`,
`guardrails`, `tools` ← `conversation`), verificadas por teste ([capítulo 9](09-observabilidade-e-testes.md)).

## Histórico do projeto

| Etapa | O que entrou |
|---|---|
| Base | Projeto Django, models da loja e `load_data`; módulo genérico `llm/`; Postgres local |
| Ferramentas | Regras de negócio em `store/`, ferramentas de dados, base de conhecimento das políticas, horário de funcionamento |
| Agente | Grafo LangGraph, system prompt, histórico persistido em Postgres, CLI `manage.py chat` |
| Interfaces | UI de chat web, depois transformada em ambiente de testes (configuração, inspetor, layout responsivo) |
| Exemplos | 5 conversas geradas pelo comando `generate_examples` com o LLM real |
| Reestruturação, Fase 1 | `core/`: relógio, `TurnContext`, logs estruturados por categoria |
| Fase 2 | `LLMService`: caller, modelo por papel, saída estruturada em 3 níveis, custo |
| Fase 3 | `tools/` (contrato Pydantic, registry, executor que nunca lança) e `knowledge/` |
| Fase 4 | Roteador de intenção (modos off/shadow/enforce) + `eval_router` |
| Fase 5 | Guardrails (detector + gate LLM, bloqueio leve/duro, transferência) + `eval_guardrails` |
| Fase 6 | `agent/` virou `conversation/`; `ConversationOrchestrator` e nó `finalize` |
| Fase 7 | UI com estágios por mensagem e aba Decisões |
| Fase 8 | Snapshots de prompts e schemas, teste de camadas, `eval_agent` |
| Fase 9 | Documentação em capítulos, exemplos regenerados com as decisões dos estágios, README final |

---

[Índice](README.md) · Próximo: [2. Ciclo request/response](02-ciclo-request-response.md)
