# 9. Observabilidade e testes

## Eventos estruturados por turno

Cada `run_turn` abre um `TurnContext` (`core/turn_context.py`), guardado num `ContextVar`. Qualquer
camada (grafo, estágios, ferramentas, `LLMService`) lê o turno atual sem recebê-lo por parâmetro, e
o `LLMService` soma nele as chamadas, os tokens e o custo.

`core.logging.log_event` grava uma linha JSON no logger `emporio.events`, sempre com `turn_id` e
`thread_id`, em cinco categorias:

| Categoria | Eventos | Nível |
|---|---|---|
| `LIFECYCLE` | `turn_started`, `turn_finished` (sucesso, duração, nº de chamadas, tokens, custo) | INFO |
| `LLM_CALL` | `llm_call` (caller, papel, modelo, duração, tokens, custo, sucesso, nível de saída estruturada) | INFO |
| `DECISION` | `guardrails_evaluated`, `intent_classified`, `human_handoff` | INFO |
| `DEGRADATION` | `fallback_reply`, `llm_degraded`, `structured_output_downgraded`, `guardrails_fail_open`, `router_fail_open` | WARNING |
| `SILENT_FAILURE` | `tool_not_found`, `tool_arguments_invalid`, `tool_failed` | WARNING |

Exemplo de um turno (console do `runserver`):

```
INFO {"event": "turn_started", "category": "LIFECYCLE", "turn_id": "e64d99251fa8", "thread_id": "web-…"}
INFO {"event": "guardrails_evaluated", "category": "DECISION", "turn_id": "e64d99251fa8", "origem": "llm", …}
INFO {"event": "llm_call", "category": "LLM_CALL", "turn_id": "e64d99251fa8", "caller": "agent.respond", …}
INFO {"event": "turn_finished", "category": "LIFECYCLE", "turn_id": "e64d99251fa8", "success": true,
      "duration_ms": 21450, "llm_calls": 4, "tokens": {…}, "cost_usd": "0"}
```

- `LOG_LEVEL` no `.env` controla o nível (padrão INFO; WARNING mostra só degradações e falhas).
- Nos testes só aparecem erros. O CLI `chat` esconde os eventos INFO, a menos que receba `--logs`.
- O rastro da UI (`trace` no estado do grafo) é separado: ele é por conversa e vai para o inspetor;
  os eventos são por processo e vão para o log.

## Testes automatizados

```bash
python manage.py test                                   # Postgres (DATABASE_URL do .env)
DATABASE_URL=sqlite:///test.sqlite3 python manage.py test   # os mesmos testes em SQLite
```

172 testes, todos sem rede: o LLM é substituído por clientes falsos com respostas roteirizadas.

| Pacote | Cobre |
|---|---|
| `store` | Carga dos CSVs, busca aproximada, preços, PIX, parcelamento, frete, prazos de pedido, horário |
| `knowledge` | Tópicos e conteúdo das políticas |
| `tools` | Contrato, schemas, validação de argumentos, executor (erros, ferramentas não liberadas) |
| `llm` | Cliente, cada nível de saída estruturada, memória do nível por modelo, custo, modelo por papel |
| `core` | Relógio, `TurnContext`, logs, atalho de conversa |
| `guardrails` | Regras do detector, gate LLM, modos, bloqueios em série, fail-open; nenhum caso normal do dataset é bloqueado pelo detector |
| `router` | Mapa de intenções, atalho, confiança mínima, modos, fail-open |
| `conversation` | Grafo, limite de rodadas, histórico, orquestrador, views e API, estágios por mensagem, comandos |
| `tests/` | Snapshots e regra de camadas (abaixo) |

### Snapshots

`conversation/snapshots.py` lista o texto exato que vai ao LLM: system prompt do agente (3
variantes: loja aberta, fechada e com orientação + escopo), prompts do roteador e dos guardrails e
os schemas das ferramentas. `tests/test_snapshots.py` compara com os arquivos versionados: qualquer
mudança quebra o teste e aparece como diff no git. Para aceitar uma mudança feita de propósito:

```bash
python manage.py update_snapshots
```

### Regra de camadas

`tests/test_architecture.py` lê os imports de cada pacote (com `ast`) e falha se algum importar uma
camada acima:

| Pacote | Pode importar |
|---|---|
| `core` | nada do projeto |
| `llm`, `store` | `core` |
| `knowledge` | `core`, `store` |
| `router`, `guardrails` | `core`, `llm` |
| `tools` | `core`, `llm`, `store`, `knowledge` |
| `conversation` | todos os anteriores |

Testes e comandos de gerenciamento ficam de fora (podem montar o sistema inteiro).

## Avaliações com o LLM real (`evals/`)

Os testes provam que o código faz o que deve com um LLM previsível. As avaliações medem o que o
modelo real faz. Todos os comandos aceitam `--limit`, `--ids` e `--report` (grava um Markdown em
`evals/reports/`):

| Comando | Dataset | Mede | Meta |
|---|---|---|---|
| `eval_router` | `router.jsonl` (35 casos: as mensagens dos exemplos e variações) | Acerto das intenções (iguais às esperadas ou a uma alternativa aceita) e cobertura (nenhuma ferramenta necessária ficou de fora) | 85% de acerto para usar `enforce` |
| `eval_guardrails` | `guardrails.jsonl` (22 casos: 12 normais, 10 problemáticos) | Falsos bloqueios, detecção, severidade | Zero falsos bloqueios |
| `eval_agent` | `agent.jsonl` (12 conversas) | Ponta a ponta: ferramentas chamadas e proibidas, trechos que a resposta deve ou não ter (ex.: "2.199,00") | Todos passam |

O `eval_agent` roda o pipeline completo com histórico em memória (não mexe nas conversas salvas),
aceita `--router-mode` e `--guardrails-mode` e usa data simulada quando o caso precisa (ex.: prazo
de devolução do pedido 4).

---

Anterior: [8. Ambiente de testes](08-ambiente-de-testes.md) · [Índice](README.md) · Próximo: [10. Decisões e limitações](10-decisoes-e-limitacoes.md)
