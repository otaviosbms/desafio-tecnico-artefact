# Arrependimento e devolução de pedido (políticas + dados do pedido)

**Objetivo:** Caso não trivial: o agente pede verificação de identidade antes de consultar o pedido e aplica os prazos do manual à data de recebimento do pedido.

- Gerado em: segunda-feira, 02/11/2026 02:50 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Comando: `python manage.py generate_examples --only 03-devolucao-de-pedido`

> Transcrição real, sem edição. As linhas "Ferramentas" mostram o que o agente consultou.

---

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["trocas_e_devolucoes"]}`

**Assistente:**

Sim, você pode devolver por arrependimento se a compra foi online e estiver dentro do prazo de **7 dias corridos após o recebimento**. As condições são:

- Produto na embalagem original, sem sinais de uso, com todos os acessórios e manuais
- O frete da devolução é por nossa conta
- Reembolso na mesma forma de pagamento em até 10 dias úteis

Para saber se o seu pedido ainda está no prazo, preciso do **número do pedido** e do **e-mail ou telefone** cadastrado. Pode me passar?

---

**Cliente:** É o pedido 4

**Assistente:**

Para consultar o pedido e ver se ainda está no prazo de devolução, preciso também do **e-mail ou telefone** que você usou no cadastro. Pode me informar?

---

**Cliente:** lucas.mendes@jmail.com

> 🔧 Ferramenta: `consultar_pedido` `{"email_ou_telefone": "lucas.mendes@jmail.com", "numero_pedido": "4"}`

**Assistente:**

O pedido **#4** (Giannini GF-3D Dreadnought Sunburst) foi entregue em **22/12/2025**. O prazo de arrependimento de 7 dias corridos encerrou em **29/12/2025**, então hoje ele já está fora desse período.

Como a compra foi no boleto, o reembolso por arrependimento não é mais possível pelo prazo legal.

Se o violão apresentar **defeito de fabricação**, a troca pela loja valia até 30 dias (até 09/01/2026). Depois disso, a garantia é diretamente com o fabricante (geralmente de 6 meses a 2 anos, conforme o certificado). A loja pode intermediar esse contato, se você quiser.

Posso ajudar com mais alguma coisa?

---
