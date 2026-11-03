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

- [Conversas de exemplo](examples/README.md): 5 transcrições reais, sem edição (entregável 3)
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

Cada escolha pedida no enunciado, com o motivo. A tabela completa, com as alternativas
descartadas, está no [capítulo 10](docs/10-decisoes-e-limitacoes.md).

### Framework e abordagem do agente: function calling num grafo LangGraph

- **Function calling com ferramentas tipadas**, e não text-to-SQL nem ReAct livre: são 6
  ferramentas (busca, detalhes, promoções, pagamento, pedido, políticas) com argumentos validados
  por Pydantic. São previsíveis, seguras (o modelo nunca gera SQL) e testáveis.
- **O modelo nunca faz contas:** promoções (vale a maior), PIX (5%, não acumula com promoção),
  parcelamento por faixas, frete e prazos de devolução são calculados em Python e chegam prontos e
  formatados ("R$ 2.199,00"). O LLM decide o que consultar e redige.
- **LangGraph com grafo próprio** (`guardrails → roteador → agente ⇄ ferramentas → finalize`), e não
  o agente pronto da biblioteca: deixa explícitos os estágios, o limite de 4 rodadas de ferramentas
  e o tratamento de falhas, e já traz o checkpointer para o histórico.
- **Pipeline em estágios:** os guardrails barram ou orientam mensagens problemáticas e o roteador
  de intenção define quais ferramentas o agente pode usar. O LLM classifica, mas quem decide é o
  código (mapa fixo de ferramentas, respostas fixas de bloqueio). Se um estágio falha, o atendimento
  continua (fail-open), e os dois começam em `shadow` (registram sem agir) até as avaliações
  justificarem o `enforce`.
- **Django** como base: ORM, migrations, admin e templates num só framework.

### Modelo e provedor: OpenAI `gpt-6-luna`, trocável pelo `.env`

- **Por que o `gpt-6-luna`:** responde em 1 a 4 s por chamada, usa ferramentas bem e custa
  US$ 0,10 / 0,50 por 1M de tokens de entrada/saída (cerca de US$ 0,0007 por mensagem). Com ele,
  as avaliações atingiram as metas (abaixo). Comecei com um modelo gratuito do OpenRouter, mas a
  latência chegava a minutos por chamada e a cota diária travava os testes.
- **Provedor desacoplado:** um módulo próprio (`llm/`) sobre o padrão Chat Completions atende
  OpenAI, Anthropic, Gemini, Groq, OpenRouter, Ollama e outros só pelo `.env`, sem LangChain nem
  LiteLLM. Cada camada (conversa, roteador, guardrails) pode ter o seu modelo e provedor.
- **Saída estruturada portável:** roteador e guardrails pedem JSON validado por Pydantic, com
  fallback em três níveis para provedores que não aceitam `json_schema`.

### Arquitetura de retrieval: políticas por tópico, sem RAG vetorial

- O manual em PDF (~3 mil tokens) foi reescrito à mão em **9 seções Markdown** (loja, horário,
  pagamento, trocas, frete, promoções, garantia, privacidade, reclamações). A ferramenta
  `consultar_politicas` recebe uma lista de tópicos de um `enum` e devolve o texto exato.
- **Por que não embeddings:** com um documento pequeno e tópicos claros, a escolha por tópico é mais
  precisa e auditável (não há trecho errado vindo da busca) e o teste confere exatamente o que o
  modelo leu. RAG vetorial (pgvector) passaria a valer se o manual crescesse.
- **Dados da loja** são consultados por ferramentas sobre o banco, com busca aproximada por nome
  (`pg_trgm`: "takamine gd 20" encontra o "Takamine GD20").

### Estratégia de prompt

- **Persona e regras vindas do manual:** as diretrizes internas (seção 7: tom informal mas
  profissional, situações especiais, reclamações) viraram o system prompt; o que é para o cliente
  ficou nas políticas consultáveis.
- **Contexto vivo:** o prompt é montado a cada chamada com a data e a hora de Campo Grande e se a
  loja está aberta, e não fica salvo no histórico (não envelhece).
- **Regras explícitas:** preço, estoque e status só com consulta às ferramentas; dados vêm das
  ferramentas de dados e regras de `consultar_politicas`; informação ausente = dizer que não sabe e
  oferecer a equipe; pedido só com número + e-mail ou telefone.
- **Escopo em três níveis:** assuntos da loja normalmente; dúvidas gerais sobre instrumentos que
  ajudam na compra, de forma breve; o resto, recusa gentil. Acessórios (a loja só vende
  instrumentos) são redirecionados.
- **Formato de chat:** mensagens curtas, sem tabelas nem títulos, no máximo 5 produtos por lista.
- **Blocos por mensagem:** quando os guardrails ou o roteador atuam, o prompt recebe uma orientação
  ou o escopo daquela mensagem. Contra prompt injection, o agente não revela instruções nem muda de
  papel, e a mensagem do cliente é tratada como dado nos estágios de classificação.
- **Versionado:** o texto exato dos prompts fica em snapshots; qualquer mudança aparece no diff.

### Interface: ambiente de testes web, CLI e API

Uma UI web que, além do chat, mostra por mensagem o rastro das chamadas ao modelo e às
ferramentas, as decisões de cada estágio, o system prompt e o custo, com data/hora simulada (para
testar loja fechada ou prazos de devolução). Foi pensada para quem avalia e ajusta o agente, não só
para o cliente. Também há o CLI (`manage.py chat`) e a API (`POST /api/mensagem/`).

### Persistência do histórico

Faz sentido para a experiência: o cliente responde "é o pedido 4" e depois o e-mail, e o agente
precisa lembrar. O histórico fica no checkpointer do LangGraph no Postgres, por conversa, e
sobrevive a reinícios. Só as últimas 40 mensagens vão ao modelo, sempre começando numa mensagem do
cliente.

### Tratamento dos dados

- `load_data` importa os CSVs mantendo os IDs, remove espaços, normaliza vazios, e-mails e datas, e
  não recalcula o total histórico dos pedidos.
- Cada produto ganha um nome normalizado para a busca (sem acento, letras separadas de números).
- O manual foi revisado à mão, resolvendo as contradições (abaixo).
- **LGPD:** um pedido só aparece com o número + o e-mail ou telefone do cadastro; pedido inexistente e
  contato errado dão o mesmo erro; e-mails e telefones nunca vão para os logs.

### Suposições

O enunciado pede para documentar as suposições. As principais:

| Tema | Conflito ou lacuna | Suposição |
|---|---|---|
| WhatsApp | O manual traz (67) 3341-4444 e (67) 3321-4500 | (67) 3341-4444, que aparece duas vezes, inclusive na tabela oficial |
| E-mail | Versões com e sem acento no domínio | Sem acento (domínio válido) |
| Parcelamento | Tabela resumida × regras com faixas | As faixas da seção 3.1 (até 3x sem mínimo; 4–6x, mínimo R$ 80; 7–12x, mínimo R$ 100) |
| Data de recebimento | Não existe nos dados | A previsão de entrega dos pedidos entregues |
| Arrependimento | Vale para compras online | Todos os pedidos do sistema (são compras com envio) |
| Produto fora de linha ou "em breve" com estoque | O manual não diz | Não é vendável |
| Duas promoções no mesmo produto | Promoções não se acumulam | Vale a de maior desconto |
| "Acima de R$ 500" (frete grátis) | Ambíguo | Estritamente maior |
| Catálogo | O manual fala em "mais de 300 instrumentos"; o CSV tem 65 | O CSV é a fonte da verdade |

A lista completa está no [capítulo 7](docs/07-dados-e-regras.md).

## Resultados

Com o `gpt-6-luna` e os estágios em `shadow`, as avaliações com o LLM real
([capítulo 9](docs/09-observabilidade-e-testes.md); relatórios em `evals/reports/`):

| Avaliação | Resultado | Meta |
|---|---|---|
| Roteador de intenção (35 mensagens) | 97% de acerto, 100% de cobertura de ferramentas | 85% |
| Guardrails (22 mensagens) | 0 falsos bloqueios, 10/10 casos problemáticos detectados | 0 falsos bloqueios |
| Agente de ponta a ponta (12 conversas) | 12/12 | todas |

Além disso, 190 testes automatizados (sem rede). As [conversas de exemplo](examples/README.md)
cobrem os quatro cenários sugeridos e um de fora do escopo; a não trivial é a de devolução de
pedido (verificação de identidade + prazos do manual aplicados ao pedido). Elas foram geradas com o
modelo gratuito usado no início do projeto; `generate_examples` as refaz com o modelo do `.env`.

## Limitações conhecidas

- **Latência e custo por mensagem:** de 3 a 4 chamadas ao LLM em sequência (guardrails, roteador,
  agente).
- **Estágios em `shadow`:** as metas foram atingidas, mas o roteador e os guardrails ainda não
  restringem nada por padrão.
- **Respostas:** o modelo às vezes oferece "fechar a compra" (o agente não vende) e pode antecipar a
  regra antes de verificar o pedido.
- **Avaliações pequenas** (35, 22 e 12 casos), verificadas por expressões regulares.
- **Sem streaming:** a resposta chega inteira.
- **Dados ausentes:** feriados, frete para outras cidades (sem tabela de CEP, peso e medidas) e
  data de recebimento dos pedidos.
- **Servidor de desenvolvimento** do Django, com requisições síncronas (também no Docker).

## O que eu faria com mais tempo

1. Passar roteador e guardrails para `enforce`, depois de rodar o agente com os dois aplicando.
2. Rodar guardrails e roteador em paralelo (são independentes) e usar um modelo menor neles.
3. Streaming (SSE) das respostas e dos eventos na UI.
4. Um juiz LLM nas avaliações, para medir tom e correção além das expressões regulares, e mais
   casos de teste vindos de conversas reais.
5. Handoff de verdade para a equipe (fila de atendimento ou integração com o WhatsApp).
6. Deploy com servidor de aplicação (gunicorn/uvicorn), Postgres gerenciado e os logs enviados ao
   Kafka ou ao New Relic (o centralizador já tem o ponto de encaixe).
7. RAG vetorial com pgvector, se o manual de políticas crescer.

## Uso de assistentes de código

Usei o **Claude Code** (app desktop) como par de programação durante todo o projeto. O workflow:

1. **Contexto antes de código:** o assistente leu o enunciado, os CSVs e o manual e montou a
   documentação de contexto (dados, inconsistências, regras). Eu decidi as suposições e mantive um
   roadmap fora do repositório, atualizado a cada etapa.
2. **Plano por fases:** a reestruturação do agente em estágios (guardrails, roteador, ferramentas
   desacopladas, observabilidade) foi escrita como um plano de 10 fases, com critérios de aceite,
   antes da implementação. Eu revisei e aprovei cada fase antes de seguir para a próxima.
3. **Implementação em passos pequenos:** cada fase terminava com a suíte de testes verde (com um LLM
   falso, sem rede) e a documentação atualizada. Eu escolhia quando commitar e pedia commits
   separados por assunto, para o histórico contar a evolução.
4. **Validação de verdade:** o assistente rodou as avaliações com o LLM real e conferiu a UI num
   navegador embutido (desktop e celular). As avaliações acharam problemas que os testes não pegavam
   (o modelo recusava ferramentas com raciocínio ligado; o gate dos guardrails caía em fail-open;
   o agente consultava pedido sem e-mail). Eu decidi as correções e o assistente as implementou e
   mediu de novo.
5. **Decisões e revisão comigo:** stack, provedor e modelo, o que entra ou sai da UI, Docker, o
   formato dos logs e a tabela de preços foram pedidos e revisados por mim; quando o pedido era
   ambíguo, o assistente perguntava antes de implementar. Credenciais ficaram só no `.env` local.

O assistente escreveu a maior parte do código, dos testes e da documentação; o meu papel foi
definir o que construir, escolher entre as alternativas, revisar e validar o resultado.
