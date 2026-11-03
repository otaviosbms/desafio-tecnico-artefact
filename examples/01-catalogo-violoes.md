# Catálogo: violões até R$ 1.000 e condições de pagamento

**Objetivo:** Busca com filtros de categoria e preço, seguida de uma pergunta que depende do contexto da conversa ("esse Yamaha") e do cálculo de PIX e parcelamento.

- Gerado em: segunda-feira, 02/11/2026 22:15 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Estágios: guardrails `shadow` · roteador `shadow`
- Comando: `python manage.py generate_examples --only 01-catalogo-violoes`

> Transcrição real, sem edição. Antes de cada resposta: o que os guardrails e o roteador decidiram e as ferramentas que o agente consultou.

---

**Cliente:** Oi! Quais opções de violões disponíveis custando até R$1000?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `catalogo` · llm · confiança 0.95
> 🔧 Ferramenta: `buscar_produtos` `{"apenas_disponiveis": true, "preco_max": 1000, "limite": 5, "categoria": "Violões"}`

**Assistente:**

Temos 12 violões disponíveis até R$ 1.000. Aqui estão os 5 primeiros:

- **Tagima Memphis AC-39 Nylon Natural** – R$ 429,90 (nylon)
- **Rozini RC-104 Nylon Estudante** – R$ 459,90 (nylon)
- **Shelby SN-100 Folk Aço Preto** – R$ 549,00 (aço)
- **Giannini GF-1R Aço Folk Sunburst** – R$ 579,90 (aço)
- **Yamaha C40 Nylon Natural** – R$ 599,90 (nylon)

Quer que eu mostre os outros 7 ou prefere ver mais detalhes de algum desses?

---

**Cliente:** Gostei do Yamaha C40. Quanto fica no PIX? E dá pra parcelar em quantas vezes?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `preco_pagamento` · llm · confiança 0.95
> 🔧 Ferramenta: `condicoes_pagamento` `{"itens": [{"produto": "Yamaha C40 Nylon Natural", "quantidade": 1}]}`

**Assistente:**

No PIX sai por **R$ 569,90** (5% de desconto, R$ 30,00 a menos).

No cartão de crédito dá pra parcelar em até **6x sem juros** de **R$ 99,98**.

Outras opções:
- Débito ou boleto: R$ 599,90 (boleto compensa em até 3 dias úteis)
- Frete grátis para Campo Grande e região metropolitana

Quer fechar ou precisa de mais alguma info?

---
