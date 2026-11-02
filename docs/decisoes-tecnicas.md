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

### Modelo em uso

- **OpenRouter** com `nvidia/nemotron-3-ultra-550b-a55b:free`: gratuito e com suporte a function
  calling. Na chamada de teste, escolheu a ferramenta certa, com argumentos corretos, e redigiu
  a resposta final com os dados retornados.
- **Ponto de atenção:** latência de ~80–95 s por chamada nos testes (modelo grande em tier
  gratuito). Um turno com ferramentas faz pelo menos 2 chamadas, então o timeout foi elevado
  para 180 s. Para a demo, vale comparar com um modelo menor ou pago; a troca é só no `.env`.

## 4. LangGraph para orquestrar o agente (implementado)

- **Grafo:** `agent/graph.py` tem dois nós, `agent` (chama o LLM com as ferramentas) e `tools`
  (executa as chamadas e devolve os resultados). Eles se alternam até o modelo responder em texto.
- **Sem modelos do LangChain:** os nós chamam o `LLMClient` próprio. O estado guarda mensagens no
  formato Chat Completions (dicts), então o histórico é independente de provedor.
- **System prompt fora do estado:** é montado a cada chamada com a data/hora de Campo Grande e se
  a loja está aberta. Assim o histórico não envelhece e o contexto está sempre certo.
- **Proteções:**
  - **limite de rodadas:** no máximo 4 rodadas de ferramentas por mensagem; depois disso o modelo
    é chamado sem ferramentas e precisa responder;
  - **falha do provedor:** um `LLMError` vira uma resposta amigável com o contato da equipe;
  - **resposta vazia:** recebe o mesmo tratamento de falha;
  - **argumentos inválidos:** JSON quebrado volta ao modelo como erro, para ele se corrigir.
- **Histórico enviado ao LLM:** só as últimas 40 mensagens, sempre começando numa mensagem do
  cliente. Assim a conversa nunca é cortada no meio de uma rodada de ferramentas, o que os
  provedores rejeitam.
- **Persistência:** checkpointer `PostgresSaver` (por `thread_id`) no mesmo banco do projeto.
  O histórico sobrevive a reinícios. No fallback SQLite, usa `InMemorySaver`.
- **Alternativa descartada:** `create_react_agent` pronto do LangGraph. Ele exige modelos do
  LangChain, e o grafo próprio deixa explícitos o limite de rodadas e o tratamento de erros.

### Estratégia de prompt (`agent/prompts.py`)

- **Origem:** as diretrizes internas do manual (seção 7) viraram regras do prompt.
  - **Tom:** informal, mas profissional.
  - **Precisão:** nunca informar preço, estoque ou status sem consultar o sistema.
  - **Situações especiais:** produto esgotado, fora de linha, "em breve"; promoção expirada; reclamação.
  - **Escopo:** pedidos de acessórios são redirecionados.
- **Formato de chat:** mensagens curtas, sem tabelas nem títulos, no máximo 5 produtos por lista.
  No primeiro teste com LLM real, as respostas vieram com tabelas markdown longas.
- **Roteamento explícito:** dados → ferramentas de dados; regras → `consultar_politicas`.
  Informação ausente → dizer que não sabe e oferecer a equipe, sem completar com conhecimento geral.
- **Escopo em três níveis:**
  - assuntos da loja: atendidos normalmente;
  - dúvidas gerais sobre instrumentos que ajudam na compra: resposta breve;
  - o resto: recusa gentil em uma frase.
- **Proteção contra prompt injection:** o agente não revela as instruções nem muda de papel.

## 5. Function calling com ferramentas específicas (implementado: dados)

- Ferramentas tipadas em `agent/tools.py` em vez de **text-to-SQL**: são previsíveis, seguras
  (sem SQL gerado pelo modelo) e testáveis.

| Ferramenta | Para quê |
|---|---|
| `buscar_produtos` | Catálogo por termo, categoria (enum vindo do banco) e faixa de preço |
| `detalhes_produto` | Um modelo específico: preço, estoque, specs; alternativas se indisponível; candidatos se ambíguo |
| `listar_promocoes` | Promoções ativas com preço original, desconto e preço final |
| `condicoes_pagamento` | Total de um ou mais itens: PIX, parcelamento, boleto, débito e frete em Campo Grande |
| `consultar_pedido` | Status, itens, rastreio e prazos de troca, devolução e garantia (exige verificação) |
| `consultar_politicas` | Seções do manual (aceita vários tópicos numa chamada); `horario` inclui se a loja está aberta agora |

- **As regras de negócio ficam em Python** (`store/pricing.py`, `store/catalog.py`,
  `store/orders.py`). O LLM nunca faz conta:
  - **promoções:** preço promocional sempre com o original e o percentual; promoções não se
    acumulam, então vale a maior ativa;
  - **PIX:** 5% de desconto, que não vale sobre itens em promoção (num carrinho misto, incide só
    sobre os itens sem promoção);
  - **parcelamento:** o maior número de parcelas sem juros que respeita as parcelas mínimas de
    cada faixa;
  - **disponibilidade:** ativo com estoque; esgotado; "em breve" (não vendável); fora de linha
    (não vendável, mesmo com estoque).
- **Valores já formatados** ("R$ 2.199,00") nas respostas das ferramentas, para o modelo não
  errar a formatação nem o arredondamento.
- **Erros viram `{"erro": ...}`** em vez de exceções, para o modelo poder se corrigir, por exemplo
  pedindo ao cliente qual dos produtos encontrados ele quer.

### Busca aproximada de produtos

- `Product.search_name` guarda nome + categoria normalizados: sem acento, em minúsculas e com
  letras separadas de números. Assim "GD20", "gd-20" e "gd 20" ficam iguais.
- **No Postgres:** usa `pg_trgm` (`TrigramWordSimilarity`), com a **média da similaridade por
  palavra** da busca. A similaridade da frase inteira misturava os termos: em "violão yamaha", o
  baixo Yamaha pontuava como os violões.
- **No SQLite:** usa `difflib` em Python como fallback. Os mesmos testes passam nos dois bancos.
- **Corte:** pontuação mínima de 0.5 e, além disso, pelo menos 75% da melhor pontuação. Se os
  dois melhores resultados ficam a menos de 0.1 um do outro, a busca é tratada como ambígua.
- **Escala:** o filtro é feito no banco, mas a ordenação acontece em Python sobre os candidatos.
  Isso é suficiente para 65 produtos; um catálogo grande pediria um índice GIN trigram e
  `ORDER BY` no SQL.

### Base de conhecimento das políticas (sem RAG vetorial)

- **Formato:** o manual (cerca de 8 páginas, ~3k tokens) foi convertido **à mão** em 9 seções
  Markdown (`agent/knowledge/*.md`), uma por tópico: loja, horário, pagamento, trocas e
  devoluções, frete e entrega, promoções, garantia, privacidade e reclamações.
- **Revisão:** o texto foi reescrito para o cliente final, e as inconsistências do PDF foram
  resolvidas nele (WhatsApp, e-mail, parcelamento; ver `docs/dados.md`). Extrair o PDF
  automaticamente levaria essas contradições para dentro das respostas.
- **Por que não RAG vetorial:** com um documento pequeno e tópicos bem definidos, um `enum`
  de tópicos na ferramenta é mais preciso e auditável que busca por embeddings. Não há risco
  de trazer o trecho errado, e o teste confere exatamente o que o modelo recebe.
- **Vários tópicos por chamada:** a ferramenta aceita mais de um tópico de uma vez (ex.: troca +
  frete), o que economiza idas e voltas ao LLM. Isso importa com o modelo lento atual.
- **Fora da ferramenta:** as diretrizes internas do manual (tom de voz, fluxo de atendimento,
  situações especiais) não são consultadas pelo cliente. Elas vão para o system prompt.
- **Horário:** `store/hours.py` calcula se a loja está aberta agora e a próxima abertura.
  Feriados não estão nos dados e não são considerados (limitação documentada).
- **Evolução:** RAG vetorial (pgvector) faria sentido se o manual crescesse ou passasse a ter
  muitos documentos.

## 6. Privacidade (LGPD) na consulta de pedidos (implementado)

- **Verificação:** o pedido só é exibido se o número vier junto com o e-mail (sem diferenciar
  maiúsculas) ou o telefone (com ou sem DDD, mínimo de 8 dígitos) do cadastro.
- **Resposta de erro:** pedido inexistente e contato errado devolvem a mesma mensagem, para não
  revelar quais números de pedido existem.

## 7. Interfaces

- **CLI:** `python manage.py chat`, interativo ou com `-m` para conversas roteirizadas; `--show-tools`
  mostra as ferramentas chamadas.
- **UI web, um ambiente de testes do agente** (`agent/templates/agent/chat.html`,
  `agent/static/agent/`): template Django com JavaScript puro, sem framework nem CDN. A ideia é
  facilitar a inspeção e a experimentação, não só simular o chat do cliente. Tem três painéis:
  - **Configuração:**
    - **conversa:** id da thread (copiar, abrir uma existente, por exemplo do CLI), nova conversa
      e exportação em Markdown;
    - **modelo e temperatura:** podem ser trocados por mensagem; provedor e chave vêm sempre do
      `.env`;
    - **data/hora simulada:** com presets, afeta o horário da loja, os prazos de pedidos e o
      system prompt;
    - **exibição:** opções de visualização e tema;
    - **cenários de teste:** perguntas prontas, agrupadas por assunto;
    - **dados de teste:** pedidos e e-mails fictícios do desafio; só aparecem com `DEBUG=True`.
  - **Conversa:** etiquetas por resposta (ferramentas, tempo, chamadas ao LLM, tokens, erro) e
    um contador de tempo enquanto o modelo responde.
  - **Inspetor:**
    - **Rastro:** por mensagem, cada chamada ao modelo (duração, tokens, `finish_reason`,
      ferramentas pedidas, erro) e a cada ferramenta (argumentos, resultado, duração);
    - **Prompt:** o system prompt exato para a data em uso;
    - **Ferramentas:** os schemas enviados ao modelo.
- **Responsivo:**
  - **desktop (1200 px ou mais):** 3 colunas;
  - **tablet (900 a 1199 px):** o inspetor vira gaveta;
  - **celular:** um painel por vez, com navegação inferior e contador de novidades no inspetor.
  - Testado em 1280, 1024 e 375 px, sem rolagem horizontal.
- **Backend do ambiente de testes:**
  - **rastro:** é guardado no estado do grafo (`trace`), separado de `messages`. Nunca vai para
    o LLM e é restaurado junto com o histórico ao reabrir a conversa;
  - **data/hora simulada:** vai na config da execução do LangGraph e chega às ferramentas por um
    `ContextVar` (`agent/clock.py`);
  - **modelo e temperatura:** cada combinação tem um `StoreAgent` em cache, e todos compartilham
    o mesmo checkpointer, então trocar de modelo no meio da conversa mantém o histórico;
  - **endpoints:** `GET /api/contexto/` (prompt, ferramentas e situação da loja para uma data) e
    `POST /api/conversa/` (abrir uma thread).
- **Segurança:**
  - **XSS:** o markdown é renderizado só depois de escapar o HTML;
  - **CSRF:** exigido nos POSTs;
  - **validação:** nome de modelo, temperatura (0 a 2), data e id de thread são validados;
  - **dados pessoais:** os dados de teste com e-mails só aparecem em `DEBUG`.
- **Limitação:** a resposta chega de uma vez, sem streaming, e o modelo gratuito pode levar
  minutos. Streaming (SSE) com os eventos do LangGraph seria a próxima melhoria.
