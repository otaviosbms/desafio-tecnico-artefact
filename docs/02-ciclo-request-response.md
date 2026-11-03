# 2. Ciclo request/response

Como uma mensagem entra no sistema e como a resposta sai, pela UI, pela API ou pelo CLI.

## Pontos de entrada

| Entrada | Onde | Conversa (`thread_id`) |
|---|---|---|
| UI web | `GET /` (`conversation/views.py`, template + JS) | Guardado na sessão do navegador |
| API | `POST /api/mensagem/` | O da sessão |
| CLI | `python manage.py chat` (interativo ou `-m` roteirizado) | Gerado ou passado por `--thread` |
| Comandos | `generate_examples`, `eval_agent` | Um novo por cenário |

Todos chamam o mesmo ponto: `ConversationOrchestrator.run_turn(thread_id, texto, TurnOptions)`.

## Endpoints

| Método e rota | Função |
|---|---|
| `GET /` | Página do ambiente de testes |
| `POST /api/mensagem/` | Envia uma mensagem e devolve a resposta com rastro e decisões |
| `GET /api/contexto/?agora=...` | System prompt, ferramentas e situação da loja para uma data (real ou simulada) |
| `POST /api/conversa/` | Troca a conversa da sessão por um `thread_id` existente (ex.: criado no CLI) e devolve histórico, rastro e decisões |
| `POST /nova-conversa/` | Começa uma conversa nova |

## `POST /api/mensagem/`

**Requisição** (JSON; só `texto` é obrigatório):

```json
{
  "texto": "Quanto custa o Takamine GD20?",
  "modelo": "nvidia/nemotron-3-ultra-550b-a55b:free",
  "temperatura": 0.2,
  "agora": "2025-12-24T10:00",
  "modo_guardrails": "enforce",
  "modo_roteador": "shadow",
  "modelo_guardrails": null,
  "modelo_roteador": null
}
```

A view valida tudo no backend antes de chamar o orquestrador:

- texto não vazio e com até 2.000 caracteres;
- nome de modelo em formato válido, temperatura entre 0 e 2, data ISO;
- modos em `off`, `shadow` ou `enforce` (ausente = padrão do `.env`);
- CSRF exigido.

Entrada inválida devolve `400` com `{"erro": "..."}`. Uma falha inesperada devolve `500` com uma
mensagem amigável (o erro vai para o log). Falhas do LLM **não** chegam aqui: o grafo devolve a
resposta de contingência (capítulo 3).

**Resposta** (`conversation/response.py`, a partir do `TurnResult`):

| Campo | Conteúdo |
|---|---|
| `resposta` | Texto que o cliente lê |
| `ferramentas` | Ferramentas chamadas no turno (nome, argumentos, resultado) |
| `rastro` | Eventos do turno: chamadas ao LLM, ferramentas, decisões, bloqueios |
| `decisoes` | O que cada estágio decidiu: guardrails, roteador, transferência e a decisão final |
| `uso` | Chamadas ao LLM, tokens e custo estimado do turno |
| `transferencia` | Se o caso foi encaminhado à equipe, e o motivo |
| `duracao_ms`, `modelo` | Duração do turno e modelo do agente |

## O orquestrador

`ConversationOrchestrator` (`conversation/orchestrator.py`) é o único ponto de entrada do pipeline.
`get_orchestrator(modelo, temperatura, modelo_roteador, modelo_guardrails)` guarda um por
combinação, todos com o mesmo checkpointer, então trocar de modelo no meio da conversa mantém o
histórico. Valores iguais aos do `.env` usam o orquestrador padrão.

`run_turn(thread_id, texto, TurnOptions)`:

1. abre o `TurnContext` (capítulo 9) e registra `turn_started`;
2. invoca o grafo com `configurable` = `thread_id` + opções da mensagem (`agora`, `router_mode`,
   `guardrails_mode`), zerando os campos por mensagem do estado (`allowed_tools`, `intents`,
   `guidance`, `blocked`). `consecutive_blocks` atravessa as mensagens;
3. o nó `finalize` fecha todo turno, também depois de um bloqueio (capítulo 3);
4. registra `turn_finished` e devolve o `TurnResult`: texto, ferramentas, rastro, decisões, uso,
   transferência, duração e modelo.

Também expõe `history`, `trace` e `decisions` de uma conversa, usados para reabrir uma thread na UI.

## Persistência

O histórico fica num checkpointer do LangGraph, por `thread_id`:

- **Postgres:** `PostgresSaver` no mesmo banco do projeto; sobrevive a reinícios;
- **SQLite (fallback):** `InMemorySaver`; o histórico some ao reiniciar o servidor.

O estado guarda as mensagens no formato Chat Completions (dicts), independente de provedor. O
rastro e as decisões ficam em campos separados (`trace`, `decisions`) e nunca vão para o LLM.
Campos novos são opcionais, então conversas salvas antes das mudanças continuam abrindo (há teste).

---

Anterior: [1. Visão geral](01-visao-geral.md) · [Índice](README.md) · Próximo: [3. Pipeline do turno](03-pipeline-do-turno.md)
