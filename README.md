# Empório da Música · agente de atendimento

Protótipo de um agente de atendimento por mensagens de texto para a **Empório da Música**, loja
fictícia de instrumentos musicais em Campo Grande/MS (desafio técnico de AI Engineer da Artefact).

O agente responde sobre catálogo, preços, promoções, formas de pagamento, pedidos, trocas,
horário e endereço. Consulta os dados da loja e o manual de políticas por ferramentas, verifica a
identidade antes de mostrar um pedido e recusa com educação o que está fora do escopo.

**Stack:** Python 3.14 · Django 6 · LangGraph · SDK da OpenAI (qualquer provedor compatível) · PostgreSQL · Docker Compose (com pgAdmin)

```
mensagem ─► guardrails ─► roteador de intenção ─► agente ⇄ ferramentas ─► finalize ─► resposta
```

- [Conversas de exemplo](examples/README.md): 5 transcrições reais, sem edição
- [Documentação técnica](docs/README.md): 10 capítulos

---

## Como rodar (Docker)

Pré-requisito: Docker com Compose v2.24 ou mais novo. Python e Postgres rodam nos containers.

### 1. Configurar o LLM

```bash
cp .env.example .env
```

No `.env`, escolha o provedor e o modelo. Qualquer endpoint compatível com a API de Chat
Completions da OpenAI serve, desde que o modelo suporte function calling:

```env
LLM_PROVIDER=openai          # openai, anthropic, gemini, groq, openrouter, deepseek, ollama, lmstudio, custom
LLM_MODEL=gpt-6-luna
OPENAI_API_KEY=sk-...        # ou a variável do provedor escolhido, ou LLM_API_KEY
```

Cada camada (conversa, roteador, guardrails) pode usar outro modelo, e até outro provedor:
`LLM_MODEL_AGENT`, `LLM_MODEL_ROUTER` e `LLM_MODEL_GUARDRAILS` aceitam `modelo` ou
`provedor:modelo` (ex.: `groq:llama-3.3-70b-versatile`); vazio usa o `LLM_MODEL`. Modelos de
raciocínio podem exigir `LLM_REASONING_EFFORT=none` para usar ferramentas. Todas as opções estão no
[capítulo 5](docs/05-camada-llm.md).

### 2. Subir

```bash
docker compose up -d --build
```

| Serviço | Endereço | O que é |
|---|---|---|
| `web` | http://localhost:8000 | A aplicação (ambiente de testes do agente). Na subida, aplica as migrations e carrega os CSVs de `data/` |
| `db` | `localhost:5432` | PostgreSQL 17 (usuário, senha e banco: `emporio`) |
| `pgadmin` | http://localhost:5050 | pgAdmin, já com o servidor "Empório da Música" cadastrado; na primeira conexão, a senha é `emporio` |

Se alguma porta já estiver em uso, mude no `.env` (`WEB_PORT`, `POSTGRES_PORT`, `PGADMIN_PORT`).

### 3. Usar

```bash
docker compose exec web python manage.py chat --show-tools   # conversa pelo terminal
docker compose logs -f web                                   # eventos estruturados de cada turno
docker compose down                                          # para (os dados ficam nos volumes)
```

Depois de mudar o código, rode `docker compose up -d --build` de novo.

### Testes e avaliações

```bash
docker compose exec web python manage.py test                   # 190 testes, sem rede (LLM falso)
docker compose exec web python manage.py eval_router --report   # avaliações com o LLM real
docker compose exec web python manage.py eval_guardrails --report
docker compose exec web python manage.py eval_agent --report
docker compose exec web python manage.py generate_examples      # regenera examples/
```

Os relatórios e exemplos são gravados dentro do container; para trazê-los para o repositório, use
`docker compose cp web:/app/evals/reports ./evals/`.

### Sem Docker (opcional)

Com Python 3.14: `python -m venv .venv`, `pip install -r requirements.txt` e rode
`python manage.py migrate`, `load_data` e `runserver`. Sem `DATABASE_URL`, o banco é SQLite; para um
Postgres próprio, defina `DATABASE_URL=postgres://usuario:senha@host:porta/banco` no `.env`. No Windows, se o console reclamar de emoji, defina `PYTHONIOENCODING=utf-8`.

---

## O que tem dentro

| Peça | Resumo | Detalhes |
|---|---|---|
| **Guardrails** | Regras por regex (mensagem vazia, manipulação, dados de terceiros) e um gate LLM. Bloqueio leve vira orientação ao agente; bloqueio duro tem resposta fixa; casos sensíveis vão para a equipe | [Cap. 4](docs/04-estagios-de-ia.md) |
| **Roteador de intenção** | Classifica a mensagem (catálogo, pagamento, pedido, políticas, conversa, fora de escopo) e libera só as ferramentas daquela intenção | [Cap. 4](docs/04-estagios-de-ia.md) |
| **Agente** | Grafo LangGraph: o LLM escolhe as ferramentas e redige; no máximo 4 rodadas por mensagem; falhas viram uma resposta de contingência | [Cap. 3](docs/03-pipeline-do-turno.md) |
| **Ferramentas** | 6 ferramentas tipadas com Pydantic: busca, detalhes, promoções, pagamento, pedido, políticas. Preços, PIX, parcelamento e prazos são calculados em Python | [Cap. 6](docs/06-tools.md) |
| **Políticas** | O manual em PDF virou 9 seções Markdown revisadas, consultadas por tópico | [Cap. 6](docs/06-tools.md) |
| **Camada de LLM** | Um módulo para qualquer provedor compatível com a OpenAI, modelo e provedor por camada, custo estimado, saída estruturada em 3 níveis | [Cap. 5](docs/05-camada-llm.md) |
| **Ambiente de testes** | UI com data/hora simulada e modo dos estágios por mensagem, e um inspetor com rastro, decisões, prompt e schemas | [Cap. 8](docs/08-ambiente-de-testes.md) |
| **Qualidade** | Centralizador de logs (um JSON para toda a aplicação, sinks plugáveis para Kafka e New Relic), 190 testes, snapshots dos prompts, teste da regra de camadas e 3 avaliações com o LLM real | [Cap. 9](docs/09-observabilidade-e-testes.md) |

## Decisões técnicas

Os pontos principais. A tabela completa, com as alternativas descartadas, está no
[capítulo 10](docs/10-decisoes-e-limitacoes.md).

- **Ferramentas tipadas em vez de text-to-SQL:** previsíveis, seguras e testáveis. O modelo nunca
  gera SQL nem faz contas: promoções, PIX (que não acumula com promoção), parcelamento por faixas,
  frete e prazos de devolução chegam prontos e formatados.
- **Políticas por tópico em vez de RAG vetorial:** o manual tem ~3k tokens e tópicos claros. Um
  `enum` de tópicos é mais preciso e auditável que embeddings, e as contradições do PDF foram
  resolvidas no texto revisado ([cap. 7](docs/07-dados-e-regras.md)).
- **Pipeline em estágios:** guardrails, roteador e agente têm responsabilidades
  separadas, são medidos separadamente e podem ser desligados. O LLM classifica, mas quem decide
  (ferramentas liberadas, texto de bloqueio) é o código.
- **Fail-open e modo `shadow`:** se o roteador ou os guardrails falham, o atendimento continua.
  Os dois começam em `shadow` (registram sem agir) até as avaliações justificarem o `enforce`.
- **Provedor de LLM pelo `.env`:** o padrão Chat Completions cobre OpenAI, Anthropic, Gemini,
  Groq, OpenRouter, Ollama e outros, sem LangChain nem LiteLLM.
- **Django + PostgreSQL:** ORM, migrations, admin e templates num só framework; `pg_trgm` para a
  busca aproximada ("takamine gd 20") e checkpointer do LangGraph para o histórico, no mesmo banco.
- **LGPD:** um pedido só aparece com o número + e-mail ou telefone do cadastro, e o erro é o mesmo
  para pedido inexistente e contato errado.

### Suposições sobre os dados

O manual tem contradições (dois WhatsApps, dois e-mails, regras de parcelamento diferentes) e os
dados não têm a data de recebimento dos pedidos. As escolhas feitas estão no
[capítulo 7](docs/07-dados-e-regras.md#inconsistências-encontradas-no-manual).

## Limitações conhecidas

- **Latência e custo:** um turno faz de 3 a 4 chamadas ao LLM em sequência (guardrails, roteador,
  agente).
- **Estágios em `shadow`:** o roteador e os guardrails ainda não restringem nada por padrão. Com o
  `gpt-6-luna`, as avaliações atingiram as metas: roteador com 97% de acerto, guardrails sem falsos
  bloqueios e agente em 12 de 12 conversas ([capítulo 9](docs/09-observabilidade-e-testes.md)).
- **Respostas:** o modelo às vezes oferece "fechar a compra" (o agente não vende) e responde de
  forma otimista antes de verificar o pedido.
- **Avaliações pequenas** (35, 22 e 12 casos), verificadas por expressões regulares.
- **Sem streaming;** feriados, frete para outras cidades e data de recebimento não estão nos dados.

Lista completa e próximos passos no [capítulo 10](docs/10-decisoes-e-limitacoes.md#limitações-conhecidas).

## Uso de assistentes de código

O projeto foi desenvolvido com o **Claude Code** como par de programação. As decisões de
arquitetura, o escopo de cada etapa e a revisão do que entrou no repositório foram meus; o
assistente escreveu boa parte do código, dos testes e da documentação a partir dessas decisões, e
cada etapa foi validada com a suíte de testes, com o LLM real e no navegador. A reestruturação em
estágios seguiu um plano por fases escrito antes da implementação.
