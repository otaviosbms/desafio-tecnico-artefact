# Empório da Música · agente de atendimento

Protótipo de um agente de atendimento por mensagens de texto para a **Empório da Música**, loja
fictícia de instrumentos musicais em Campo Grande/MS (desafio técnico de AI Engineer da Artefact).

O agente responde sobre catálogo, preços, promoções, formas de pagamento, pedidos, trocas,
horário e endereço. Consulta os dados da loja e o manual de políticas por ferramentas, verifica a
identidade antes de mostrar um pedido e recusa com educação o que está fora do escopo.

**Stack:** Python 3.14 · Django 6 · LangGraph · SDK da OpenAI (qualquer provedor compatível) · PostgreSQL (ou SQLite)

```
mensagem ─► guardrails ─► roteador de intenção ─► agente ⇄ ferramentas ─► finalize ─► resposta
```

- [Conversas de exemplo](examples/README.md): 5 transcrições reais, sem edição
- [Documentação técnica](docs/README.md): 10 capítulos

---

## Como rodar

### 1. Ambiente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. LLM

No `.env`, escolha o provedor e o modelo. Qualquer endpoint compatível com a API de Chat
Completions da OpenAI serve, desde que o modelo suporte function calling:

```env
LLM_PROVIDER=openai          # openai, anthropic, gemini, groq, openrouter, deepseek, ollama, lmstudio, custom
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...        # ou a variável do provedor escolhido, ou LLM_API_KEY
```

Para rodar sem chave paga: `LLM_PROVIDER=ollama` com um modelo local que suporte ferramentas, ou
`LLM_PROVIDER=openrouter` com um modelo `:free`. Modelos de raciocínio podem exigir
`LLM_REASONING_EFFORT=none` para usar ferramentas. Todas as opções estão no
[capítulo 5](docs/05-camada-llm.md).

### 3. Banco de dados

**Opção A, sem configuração (SQLite):** apague a linha `DATABASE_URL` do `.env`. A busca usa um
fallback em Python e o histórico das conversas fica em memória (some ao reiniciar).

**Opção B, PostgreSQL (recomendado):** busca por trigramas e histórico persistente.

```bash
docker compose up -d db      # ou um Postgres próprio, ajustando DATABASE_URL
```

### 4. Dados e execução

```bash
python manage.py migrate
python manage.py load_data   # importa data/*.csv (pode rodar de novo sem duplicar)
python manage.py runserver   # ambiente de testes em http://localhost:8000
```

Ou pelo terminal:

```bash
python manage.py chat --show-tools
```

> No Windows, se o console reclamar de emoji (`UnicodeEncodeError`), defina `PYTHONIOENCODING=utf-8`.

### Testes e avaliações

```bash
python manage.py test                   # 172 testes, sem rede (LLM falso)
python manage.py eval_router --report   # avaliações com o LLM real (gravam em evals/reports/)
python manage.py eval_guardrails --report
python manage.py eval_agent --report
python manage.py generate_examples      # regenera examples/ com o LLM configurado
```

---

## O que tem dentro

| Peça | Resumo | Detalhes |
|---|---|---|
| **Guardrails** | Regras por regex (mensagem vazia, manipulação, dados de terceiros) e um gate LLM. Bloqueio leve vira orientação ao agente; bloqueio duro tem resposta fixa; casos sensíveis vão para a equipe | [Cap. 4](docs/04-estagios-de-ia.md) |
| **Roteador de intenção** | Classifica a mensagem (catálogo, pagamento, pedido, políticas, conversa, fora de escopo) e libera só as ferramentas daquela intenção | [Cap. 4](docs/04-estagios-de-ia.md) |
| **Agente** | Grafo LangGraph: o LLM escolhe as ferramentas e redige; no máximo 4 rodadas por mensagem; falhas viram uma resposta de contingência | [Cap. 3](docs/03-pipeline-do-turno.md) |
| **Ferramentas** | 6 ferramentas tipadas com Pydantic: busca, detalhes, promoções, pagamento, pedido, políticas. Preços, PIX, parcelamento e prazos são calculados em Python | [Cap. 6](docs/06-tools.md) |
| **Políticas** | O manual em PDF virou 9 seções Markdown revisadas, consultadas por tópico | [Cap. 6](docs/06-tools.md) |
| **Camada de LLM** | Um módulo para qualquer provedor compatível com a OpenAI, modelo por papel, custo estimado, saída estruturada em 3 níveis | [Cap. 5](docs/05-camada-llm.md) |
| **Ambiente de testes** | UI com data/hora simulada, troca de modelo e de modo dos estágios por mensagem, e um inspetor com rastro, decisões, prompt e schemas | [Cap. 8](docs/08-ambiente-de-testes.md) |
| **Qualidade** | Eventos estruturados por turno, 172 testes, snapshots dos prompts, teste da regra de camadas e 3 avaliações com o LLM real | [Cap. 9](docs/09-observabilidade-e-testes.md) |

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
