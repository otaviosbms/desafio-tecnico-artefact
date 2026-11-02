# Preço de um modelo e produto esgotado

**Objetivo:** Consulta de preço por nome (com variação de escrita) e produto sem estoque, em que o agente deve informar a indisponibilidade e sugerir alternativas.

- Gerado em: segunda-feira, 02/11/2026 02:50 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Comando: `python manage.py generate_examples --only 02-preco-e-estoque`

> Transcrição real, sem edição. As linhas "Ferramentas" mostram o que o agente consultou.

---

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 Ferramenta: `detalhes_produto` `{"produto": "Takamine GD20"}`

**Assistente:**

O Takamine GD20 Dreadnought Natural está por **R$ 2.199,00** e tem 5 unidades em estoque.

Quer que eu veja as condições de pagamento (PIX, parcelamento, frete pra Campo Grande) ou tem mais alguma dúvida sobre ele?

---

**Cliente:** E o Giannini GF-3D, tem?

> 🔧 Ferramenta: `buscar_produtos` `{"termo": "Giannini GF-3D"}`

**Assistente:**

O Giannini GF-3D Dreadnought Sunburst está **esgotado no momento** e não tem previsão de reposição no sistema.

Quer que eu procure violões dreadnought semelhantes nessa faixa de preço ou de outras marcas?

---
