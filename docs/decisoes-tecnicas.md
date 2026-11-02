# Decisões técnicas

Cada decisão traz o motivo e as alternativas descartadas. Esta seção vira a base do README final.

## 1. Django como framework base

- **Motivo:** ORM, migrations, admin (útil para a equipe da loja inspecionar dados) e templates
  para uma UI de chat simples, tudo em um só framework.
- **Alternativas:** FastAPI + front separado (mais peças para pouco ganho em um protótipo).

## 2. PostgreSQL (com fallback para SQLite)

- **Motivo:** é o banco de produção mais provável e tem `unaccent` + `pg_trgm` para busca
  aproximada por nome de produto (ex.: o cliente digita "takamine gd 20"). Também guarda o
  histórico de conversas.
- **Fallback:** sem `DATABASE_URL`, o projeto usa SQLite, para rodar com zero configuração.
  Funcionalidades específicas do Postgres precisam degradar bem nesse caso.

## 3. Módulo de LLM próprio sobre o SDK da OpenAI

- **Motivo:** a API de Chat Completions virou o padrão de fato. OpenAI, Anthropic, Gemini,
  Groq, OpenRouter, DeepSeek, Ollama e LM Studio expõem endpoints compatíveis. Um módulo
  fino (`llm/`) com presets permite **trocar de provedor ou modelo só pelo `.env`**, inclusive
  rodar 100% local com Ollama, sem chave paga.
- **Por que Chat Completions e não a Responses API:** a Responses API é específica da OpenAI;
  Chat Completions é o que os outros provedores implementam.
- **Respostas normalizadas** (`ChatResponse`, `ToolCall`): o resto do projeto não depende dos
  tipos do SDK, e argumentos de ferramenta com JSON inválido não derrubam o agente.
- **Alternativas:** `langchain-openai` (mais uma camada de abstração e dependência) e LiteLLM
  (bom, mas desnecessário quando o padrão OpenAI já cobre os provedores desejados).

## 4. LangGraph para orquestrar o agente (planejado)

- **Motivo:** estado explícito, fácil adicionar nós (guardrail, roteamento) e checkpointer em
  Postgres para persistir o histórico.
- Os nós chamam o `LLMClient` próprio, não modelos do LangChain. O LangGraph não exige isso.

## 5. Function calling com ferramentas específicas (planejado)

- Ferramentas tipadas (`buscar_produtos`, `detalhes_produto`, `listar_promocoes_ativas`,
  `consultar_pedido`, `consultar_politicas`) em vez de **text-to-SQL**: são previsíveis,
  seguras e testáveis.
- **Regras de negócio em Python, não no LLM:**
  - preço promocional junto com o original e o percentual;
  - PIX não acumula com promoção;
  - status de estoque;
  - prazos de devolução.
- **Políticas:** o manual tem cerca de 8 páginas (~3k tokens). Em vez de RAG vetorial, ele é
  dividido em seções Markdown revisadas, servidas por ferramenta. RAG vetorial fica como
  evolução, caso o manual cresça.

## 6. Privacidade (LGPD) na consulta de pedidos (planejado)

- Um pedido só é exibido se o número vier junto com o e-mail ou o telefone do cliente.

## 7. Front com templates do Django (planejado)

- Tela de chat simples com `fetch`/HTMX, sem framework de front.
