# Limitações conhecidas

Base para a seção "Limitações e próximos passos" do README.

## Observadas nas conversas reais (`examples/`)

| Observação | Exemplo | Possível melhoria |
|---|---|---|
| Ainda oferece "fechar a compra", mesmo com a regra no prompt | 01: "Quer fechar ou precisa de mais alguma info?" | Reforçar com exemplos (few-shot) ou testar outro modelo |
| Resposta inicial otimista antes de verificar o pedido | 03: "Sim, você pode devolver..." antes de saber o pedido | Instruir a condicionar a resposta até consultar o pedido |
| Frase com relação causal estranha | 03: "Como a compra foi no boleto, o reembolso... não é mais possível" (o motivo é o prazo, não o boleto) | Modelo mais forte; avaliação automática de respostas |
| No produto esgotado, ofereceu procurar em vez de já sugerir alternativas | 02: usou `buscar_produtos`, que não trazia alternativas | **Corrigido na ferramenta** (a busca sem itens disponíveis agora traz alternativas). Falta regerar o 02 (cota diária esgotada) |
| Pede o contato de novo quando o cliente manda só o número do pedido | 03: comportamento correto, mas exige uma mensagem a mais | Aceitável (verificação obrigatória) |

## Técnicas

- **Latência:** o modelo gratuito (`nemotron-3-ultra-550b:free` via OpenRouter) leva de 1 a 3 min
  por chamada. Uma resposta com ferramenta faz 2 chamadas. Sem streaming, a UI só mostra
  "Digitando...".
- **Cota do plano gratuito:** o OpenRouter limita os modelos `:free` por dia (erro 429
  `free-models-per-day`; com US$ 10 em créditos, o limite sobe para 1.000 requisições por dia).
  Quando isso acontece, o agente responde com a mensagem de contingência.
- **Sem streaming:** a resposta chega inteira de uma vez.
- **Feriados:** não estão nos dados, então o cálculo de "aberta agora" não os considera.
- **Data de recebimento dos pedidos:** não existe nos dados; usa-se a previsão de entrega.
- **Frete para outras cidades:** não é calculado, por falta de tabela de CEP, peso e medidas.
- **Avaliação:** os testes cobrem ferramentas e grafo com um LLM falso. A qualidade das respostas
  do LLM real foi verificada manualmente, sem um conjunto de avaliação automatizado.
- **Busca:** a ordenação é feita em Python sobre os candidatos (adequado para 65 produtos). Um
  catálogo grande precisaria de índice GIN trigram e ordenação no SQL.
- **Concorrência:** a UI usa o servidor de desenvolvimento do Django, com requisições síncronas.
