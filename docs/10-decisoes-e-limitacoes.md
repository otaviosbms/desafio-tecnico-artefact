# 10. Decisões e limitações

## Decisões técnicas

Cada decisão traz o motivo e as alternativas descartadas. Os detalhes estão nos capítulos indicados.

| Decisão | Motivo | Alternativas descartadas |
|---|---|---|
| **Django** como base | ORM, migrations, admin (útil para a equipe inspecionar dados) e templates para a UI, num só framework | FastAPI + front separado: mais peças para pouco ganho num protótipo |
| **PostgreSQL**, com fallback para SQLite | Banco de produção mais provável; `unaccent` + `pg_trgm` para a busca aproximada; guarda o histórico das conversas. Sem `DATABASE_URL`, roda com SQLite e zero configuração | Só SQLite: sem busca por trigramas nem histórico persistente |
| **Módulo de LLM próprio** sobre o SDK da OpenAI (cap. 5) | Chat Completions é o padrão de fato: trocar de provedor ou modelo é só mudar o `.env`, inclusive para rodar local com Ollama | `langchain-openai`, LiteLLM, Responses API (específica da OpenAI) |
| **LangGraph com grafo próprio** (cap. 3) | Estágios, limite de rodadas e tratamento de erros explícitos; checkpointer pronto para o histórico | `create_react_agent` (exige modelos do LangChain); loop manual (sem persistência pronta) |
| **Pipeline em estágios**: guardrails → roteador → agente (cap. 4) | Separa segurança, escolha de ferramentas e redação; cada estágio é medido sozinho e pode ser desligado | Um único prompt grande com todas as regras e ferramentas |
| **O LLM classifica, o código decide** | Ferramentas liberadas vêm de um mapa fixo; respostas de bloqueio duro são textos fixos; nada depende de o modelo "obedecer" | Deixar o modelo escolher livremente ou escrever a recusa |
| **Fail-open e modo `shadow`** nos estágios | Uma falha do roteador ou dos guardrails não derruba o atendimento; `shadow` mede antes de aplicar | Fail-closed: um 429 do classificador bloquearia clientes legítimos |
| **Saída estruturada em 3 níveis** + Pydantic (cap. 5) | Nem todo provedor aceita `json_schema`; o nível que funciona fica em cache por modelo | Exigir `json_schema` e limitar os provedores |
| **Ferramentas tipadas** em vez de text-to-SQL (cap. 6) | Previsíveis, seguras e testáveis; um `input_model` Pydantic gera o schema e valida os argumentos | Text-to-SQL: SQL gerado pelo modelo, difícil de auditar |
| **Regras de negócio em Python** (cap. 6) | O LLM nunca faz conta: promoções, PIX, parcelamento, prazos e horário chegam prontos e formatados | Passar o manual e deixar o modelo calcular |
| **Políticas em Markdown por tópico**, sem RAG vetorial (cap. 6) | Documento pequeno (~3k tokens) e tópicos claros: um `enum` é mais preciso e auditável; as inconsistências do PDF foram resolvidas no texto | Embeddings + busca vetorial; extrair o PDF automaticamente |
| **Verificação de identidade** nos pedidos (cap. 6) | LGPD: número + e-mail ou telefone; mesma mensagem para pedido inexistente e contato errado | Consultar só pelo número |
| **System prompt fora do estado** (cap. 3) | Montado a cada chamada com a data/hora e a situação da loja; o histórico não envelhece | Guardar o prompt no histórico |
| **Observabilidade estruturada** (cap. 9) | `TurnContext` + eventos JSON por categoria; rastro e decisões por mensagem na UI | Logs soltos com `print` |
| **Centralizador de logs sobre o `logging` do Python** (cap. 9) | Um JSON e um contexto (`request_id`, `turn_id`) para toda a aplicação, inclusive os logs do Django; fila para não travar a requisição; sinks plugáveis (Kafka, New Relic) sem mudar quem loga | Biblioteca de logs externa (structlog, loguru): mais uma dependência para o mesmo resultado |
| **Snapshots, teste de camadas e avaliações** (cap. 9) | Mudanças no texto enviado ao LLM aparecem no diff; a arquitetura não se degrada; o modelo real é medido | Só testes unitários com LLM falso |

## Limitações conhecidas

### Observadas nas conversas reais (`examples/`)

| Observação | Exemplo | Possível melhoria |
|---|---|---|
| Ainda oferece "fechar a compra", mesmo com a regra no prompt (o agente não vende) | 01: "Quer fechar ou precisa de mais alguma info?" | Exemplos no prompt (few-shot) ou outro modelo; um caso no `eval_agent` |
| Resposta inicial um pouco otimista antes de verificar o pedido | 03: "Sim, para compras online você tem 7 dias..." antes de saber se o pedido está no prazo | Instruir a condicionar a resposta até consultar o pedido |
| Pede o contato de novo quando o cliente manda só o número do pedido | 03: comportamento correto, mas exige uma mensagem a mais | Aceitável (verificação obrigatória) |
| O gate LLM dos guardrails roda em quase toda mensagem | 01 a 04: "passou · llm" em todas as mensagens normais | Regras de "passe livre" mais amplas, ou um modelo pequeno só para o gate |

### Técnicas

- **Latência e custo por turno:** guardrails, roteador e agente fazem de 3 a 4 chamadas ao LLM por
  mensagem, em sequência. Guardrails e roteador são independentes e poderiam rodar em paralelo; um
  modelo menor para eles (`LLM_MODEL_ROUTER`, `LLM_MODEL_GUARDRAILS`) também ajuda.
- **Modelo:** com o `gpt-6-luna` (OpenAI), uma chamada leva de 1 a 4 s. Ele exige
  `reasoning_effort=none` para usar ferramentas, e essa configuração vale para os três papéis (o
  roteador caiu de 97% para 89% numa rodada sem raciocínio, antes das correções do capítulo 9); um
  valor por papel seria a melhoria.
- **Modelo gratuito (usado antes):** `nemotron-3-ultra-550b:free` via OpenRouter tem latência muito variável (de
  ~1 s a minutos por chamada) e cota diária (erro 429 `free-models-per-day`; com US$ 10 em créditos o
  limite sobe para 1.000 requisições por dia). Sem cota, o agente responde com a mensagem de
  contingência, e o roteador e os guardrails entram em fail-open.
- **Estágios em `shadow` por padrão:** roteador e guardrails registram, mas não agem. Com o
  `gpt-6-luna` as metas foram atingidas; falta validar o agente com os dois em `enforce`.
- **Avaliações pequenas:** 35, 22 e 12 casos cobrem os cenários do desafio, não a variedade de um
  atendimento real. A verificação das respostas é por expressões regulares, não por um juiz LLM.
- **Sem streaming:** a resposta chega inteira de uma vez.
- **Feriados:** não estão nos dados, então o cálculo de "aberta agora" não os considera.
- **Data de recebimento dos pedidos:** não existe nos dados; usa-se a previsão de entrega.
- **Frete para outras cidades:** não é calculado, por falta de tabela de CEP, peso e medidas.
- **Busca:** a ordenação é feita em Python sobre os candidatos (adequado para 65 produtos). Um
  catálogo grande precisaria de índice GIN trigram e ordenação no SQL.
- **Concorrência:** a UI usa o servidor de desenvolvimento do Django (também no Docker), com
  requisições síncronas.
- **Detector de dados de terceiros:** pega "pedido da Gibson" (marca com inicial maiúscula); o
  efeito é só uma orientação extra ao agente.

## Próximos passos

1. Rodar o `eval_agent` com os dois estágios em `enforce` e, se continuar 12/12, mudar o padrão
   (as metas do roteador e dos guardrails já foram atingidas; capítulo 9).
2. Rodar guardrails e roteador em paralelo e testar modelos menores para eles.
3. Streaming (SSE) das respostas e dos eventos do LangGraph na UI.
4. Juiz LLM no `eval_agent` para avaliar tom e correção, além das expressões regulares.
5. Deploy com servidor de aplicação (gunicorn/uvicorn) e Postgres gerenciado.

---

Anterior: [9. Observabilidade e testes](09-observabilidade-e-testes.md) · [Índice](README.md)
