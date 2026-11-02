# Catálogo: violões até R$ 1.000 e condições de pagamento

**Objetivo:** Busca com filtros de categoria e preço, seguida de uma pergunta que depende do contexto da conversa ("esse Yamaha") e do cálculo de PIX e parcelamento.

- Gerado em: segunda-feira, 02/11/2026 02:50 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Comando: `python manage.py generate_examples --only 01-catalogo-violoes`

> Transcrição real, sem edição. As linhas "Ferramentas" mostram o que o agente consultou.

---

**Cliente:** Oi! Quais opções de violões disponíveis custando até R$1000?

> 🔧 Ferramenta: `buscar_produtos` `{"preco_max": 1000, "apenas_disponiveis": true, "categoria": "Violões", "limite": 5}`

**Assistente:**

Temos 12 violões disponíveis até R$ 1.000. Aqui estão os 5 mais relevantes:

- **Tagima Memphis AC-39 Nylon Natural** – R$ 429,90 (15 em estoque)
- **Rozini RC-104 Nylon Estudante** – R$ 459,90 (10 em estoque)
- **Shelby SN-100 Folk Aço Preto** – R$ 549,00 (5 em estoque)
- **Giannini GF-1R Aço Folk Sunburst** – R$ 579,90 (7 em estoque)
- **Yamaha C40 Nylon Natural** – R$ 599,90 (12 em estoque)

Os outros 7 também estão disponíveis. Quer que eu mostre mais algum, ou tem preferência por nylon, aço, cutaway, etc.? 🎸

---

**Cliente:** Gostei do Yamaha C40. Quanto fica no PIX? E dá pra parcelar em quantas vezes?

> 🔧 Ferramenta: `condicoes_pagamento` `{"itens": [{"produto": "Yamaha C40 Nylon Natural", "quantidade": 1}]}`

**Assistente:**

No PIX o Yamaha C40 sai por **R$ 569,90** (5% de desconto, R$ 30,00 a menos).

No cartão de crédito dá pra parcelar em **até 6× sem juros** de **R$ 99,98**.

E o frete é grátis pra região metropolitana de Campo Grande. 😊

Quer fechar ou precisa de mais alguma info?

---
