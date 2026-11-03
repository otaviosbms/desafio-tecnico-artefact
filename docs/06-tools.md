# 6. Ferramentas e políticas

O agente consulta dados e políticas por **function calling**, com ferramentas tipadas em vez de
**text-to-SQL**: são previsíveis, seguras (sem SQL gerado pelo modelo) e testáveis.

## As ferramentas

| Ferramenta | Para quê |
|---|---|
| `buscar_produtos` | Catálogo por termo, categoria (enum vindo do banco) e faixa de preço |
| `detalhes_produto` | Um modelo específico: preço, estoque, specs; alternativas se indisponível; candidatos se ambíguo |
| `listar_promocoes` | Promoções ativas com preço original, desconto e preço final |
| `condicoes_pagamento` | Total de um ou mais itens: PIX, parcelamento, boleto, débito e frete em Campo Grande |
| `consultar_pedido` | Status, itens, rastreio e prazos de troca, devolução e garantia (exige verificação) |
| `consultar_politicas` | Seções do manual (aceita vários tópicos numa chamada); `horario` inclui se a loja está aberta agora |

## Contrato, registry e executor (`tools/`)

Cada ferramenta é uma classe em `tools/handlers/` com `name`, `description` (quando usar),
`input_model` (Pydantic) e `execute(ctx, args) -> ToolResult`. O mesmo `input_model` gera o
schema enviado ao LLM (`parameters_schema` tira títulos, defaults, `$ref` e `anyOf` com `null`) e
valida os argumentos recebidos. Os handlers são finos: as regras ficam em `store/` e `knowledge/`.

| Peça | Papel |
|---|---|
| `ToolContext` | `now` (relógio da conversa, real ou simulado), `thread_id`, `turn_id` |
| `ToolResult` | `data` (payload), `error` (código: `not_found`, `ambiguous`, `unavailable`, `verification_failed`, ...), `error_message` (vai ao modelo como `"erro"`), `transfer_to_human`, `meta` (só rastro) |
| `registry` | `register_tool`, `get_tool`, `all_tools`, `definitions(nomes)`; preenchido no `ready()` do app |
| `ToolExecutor.run` | JSON → valida → executa → `ToolResult`. **Nunca lança**: erros viram `tool_not_found`, `tool_not_allowed`, `tool_invalid_args` ou `tool_failed`, com log `SILENT_FAILURE` |

- **Erros viram `{"erro": ...}`** para o modelo, em vez de exceções, para ele poder se corrigir
  (por exemplo, perguntando ao cliente qual dos produtos encontrados ele quer).
- **`allowed`:** o executor recebe as ferramentas liberadas pelo roteador e recusa as outras.
- Os schemas ficam num snapshot (`tools/snapshots/definitions.json`, capítulo 9).

## Regras de negócio em Python

O LLM nunca faz conta. `store/pricing.py`, `store/catalog.py`, `store/orders.py` e `store/hours.py`
calculam e as ferramentas devolvem os valores prontos:

- **promoções:** preço promocional sempre com o original e o percentual; promoções não se
  acumulam, então vale a maior ativa;
- **PIX:** 5% de desconto, que não vale sobre itens em promoção (num carrinho misto, incide só
  sobre os itens sem promoção);
- **parcelamento:** o maior número de parcelas sem juros que respeita as parcelas mínimas de
  cada faixa;
- **disponibilidade:** ativo com estoque; esgotado; "em breve" (não vendável); fora de linha
  (não vendável, mesmo com estoque);
- **prazos do pedido:** arrependimento, troca por preferência, defeito e garantia, calculados a
  partir das datas do pedido e da data atual (real ou simulada);
- **horário:** se a loja está aberta agora e a próxima abertura.

**Valores já formatados** ("R$ 2.199,00"), para o modelo não errar a formatação nem o arredondamento.

## Busca aproximada de produtos

- `Product.search_name` guarda nome + categoria normalizados: sem acento, em minúsculas e com
  letras separadas de números. Assim "GD20", "gd-20" e "gd 20" ficam iguais.
- **No Postgres:** usa `pg_trgm` (`TrigramWordSimilarity`), com a **média da similaridade por
  palavra** da busca. A similaridade da frase inteira misturava os termos: em "violão yamaha", o
  baixo Yamaha pontuava como os violões.
- **No SQLite:** usa `difflib` em Python como fallback. Os mesmos testes passam nos dois bancos.
- **Corte:** pontuação mínima de 0.5 e, além disso, pelo menos 75% da melhor pontuação. Se os
  dois melhores resultados ficam a menos de 0.1 um do outro, a busca é tratada como ambígua.
- **Sem resultado disponível:** a busca já traz alternativas da mesma categoria.
- **Escala:** o filtro é feito no banco, mas a ordenação acontece em Python sobre os candidatos.
  Isso basta para 65 produtos; um catálogo grande pediria um índice GIN trigram e `ORDER BY` no SQL.

## Base de conhecimento das políticas (`knowledge/`, sem RAG vetorial)

- **Formato:** o manual (cerca de 8 páginas, ~3k tokens) foi convertido **à mão** em 9 seções
  Markdown, uma por tópico: loja, horário, pagamento, trocas e devoluções, frete e entrega,
  promoções, garantia, privacidade e reclamações.
- **Revisão:** o texto foi reescrito para o cliente final, e as inconsistências do PDF foram
  resolvidas nele (capítulo 7). Extrair o PDF automaticamente levaria essas contradições para
  dentro das respostas.
- **Por que não RAG vetorial:** com um documento pequeno e tópicos bem definidos, um `enum` de
  tópicos na ferramenta é mais preciso e auditável que busca por embeddings. Não há risco de trazer
  o trecho errado, e o teste confere exatamente o que o modelo recebe.
- **Vários tópicos por chamada** (ex.: troca + frete), o que economiza idas e voltas ao LLM.
- **Fora da ferramenta:** as diretrizes internas do manual (tom de voz, fluxo de atendimento,
  situações especiais) não são consultadas pelo cliente. Elas vão para o system prompt (capítulo 3).
- **Evolução:** RAG vetorial (pgvector) faria sentido se o manual crescesse ou passasse a ter
  muitos documentos.

## Privacidade (LGPD) na consulta de pedidos

- **Verificação:** o pedido só é exibido se o número vier junto com o e-mail (sem diferenciar
  maiúsculas) ou o telefone (com ou sem DDD, mínimo de 8 dígitos) do cadastro.
- **Resposta de erro:** pedido inexistente e contato errado devolvem a mesma mensagem, para não
  revelar quais números de pedido existem.
- **Guardrails:** pedidos de dados de outra pessoa recebem uma orientação extra (capítulo 4).

---

Anterior: [5. Camada de LLM](05-camada-llm.md) · [Índice](README.md) · Próximo: [7. Dados e regras](07-dados-e-regras.md)
