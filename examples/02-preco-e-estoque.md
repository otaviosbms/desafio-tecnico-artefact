# Preço de um modelo e produto esgotado

**Objetivo:** Consulta de preço por nome e produto sem estoque, em que o agente deve informar a indisponibilidade e sugerir alternativas.

- Gerado em: segunda-feira, 02/11/2026 22:16 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Estágios: guardrails `shadow` · roteador `shadow`
- Comando: `python manage.py generate_examples --only 02-preco-e-estoque`

> Transcrição real, sem edição. Antes de cada resposta: o que os guardrails e o roteador decidiram e as ferramentas que o agente consultou.

---

**Cliente:** Quanto custa o Takamine GD20?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `preco_pagamento`, `catalogo` · llm · confiança 0.95
> 🔧 Ferramenta: `detalhes_produto` `{"produto": "Takamine GD20"}`

**Assistente:**

O Takamine GD20 Dreadnought Natural tá por **R$ 2.199,00** e tem 5 unidades em estoque.

É um violão dreadnought com tampo sólido em cedro, braço em mogno, laterais e fundo em sapele, escala de 650mm e cordas de aço (não tem captação).

Quer que eu simule as condições de pagamento (PIX, parcelamento etc.) ou precisa de mais alguma coisa? 😊

---

**Cliente:** E o Giannini GF-3D, tem?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `catalogo` · llm · confiança 0.98
> 🔧 Ferramenta: `detalhes_produto` `{"produto": "Giannini GF-3D"}`

**Assistente:**

O Giannini GF-3D Dreadnought Sunburst tá **esgotado no momento** (R$ 799,90).

O sistema me trouxe três opções parecidas que tão disponíveis:

- **Shelby SGD-195E Elétrico Aço Sunburst** – R$ 799,00 (6 em estoque)  
- **Yamaha C70 Nylon Natural** – R$ 849,00 (8 em estoque)  
- **Tagima Dallas Tuner Aço Natural** – R$ 749,00 (9 em estoque)

Quer que eu mostre mais detalhes de algum deles ou prefere que eu busque outros modelos nessa faixa?

---
