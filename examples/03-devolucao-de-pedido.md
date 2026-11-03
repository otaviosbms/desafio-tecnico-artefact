# Arrependimento e devolução de pedido (políticas + dados do pedido)

**Objetivo:** Caso não trivial: o agente pede verificação de identidade antes de consultar o pedido e aplica os prazos do manual à data de recebimento do pedido.

- Gerado em: segunda-feira, 02/11/2026 22:17 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Estágios: guardrails `shadow` · roteador `shadow`
- Comando: `python manage.py generate_examples --only 03-devolucao-de-pedido`

> Transcrição real, sem edição. Antes de cada resposta: o que os guardrails e o roteador decidiram e as ferramentas que o agente consultou.

---

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `pedido`, `politicas` · llm · confiança 0.90
> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["trocas_e_devolucoes"]}`

**Assistente:**

Sim, para compras online você tem **7 dias corridos após o recebimento** para devolver por arrependimento, sem precisar justificar. O produto deve estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais. O frete da devolução é por nossa conta e o reembolso sai na mesma forma de pagamento em até 10 dias úteis.

Para ver se o seu pedido ainda está no prazo, preciso do **número do pedido** e do **e-mail ou telefone** cadastrado na compra. Pode me passar?

---

**Cliente:** É o pedido 4

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `pedido` · llm · confiança 0.98

**Assistente:**

Preciso também do **e-mail ou telefone** que você usou no cadastro da compra para consultar o pedido 4. Pode me informar?

---

**Cliente:** lucas.mendes@jmail.com

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `pedido` · llm · confiança 0.99
> 🔧 Ferramenta: `consultar_pedido` `{"numero_pedido": "4", "email_ou_telefone": "lucas.mendes@jmail.com"}`

**Assistente:**

O pedido **#4** (Giannini GF-3D Dreadnought Sunburst) foi entregue em **22/12/2025**. O prazo de 7 dias para devolução por arrependimento terminou em **29/12/2025**, então já está fora do período legal.

Se o instrumento apresentar **defeito de fabricação**, a garantia do fabricante costuma valer de 6 meses a 2 anos (conforme o certificado que acompanha o produto). A loja pode intermediar o contato com o fabricante, se você quiser.

Quer que eu veja como acionar a garantia ou tem mais alguma dúvida?

---
