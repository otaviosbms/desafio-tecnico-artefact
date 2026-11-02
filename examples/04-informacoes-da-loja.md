# Informações gerais: endereço, horário e formas de pagamento

**Objetivo:** Perguntas respondidas pelo manual de políticas, incluindo se a loja está aberta no momento da conversa.

- Gerado em: segunda-feira, 02/11/2026 02:50 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Comando: `python manage.py generate_examples --only 04-informacoes-da-loja`

> Transcrição real, sem edição. As linhas "Ferramentas" mostram o que o agente consultou.

---

**Cliente:** Qual o endereço da loja?

> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["loja"]}`

**Assistente:**

Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333

Se precisar de mais alguma informação, é só chamar! 😊

---

**Cliente:** Vocês estão abertos agora? E quais formas de pagamento aceitam?

> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["horario", "pagamento"]}`

**Assistente:**

A loja está **fechada agora** (são 02:51 da madrugada). Abrimos hoje às **09:00** e funcionamos até 18:00 (segunda a sexta). No sábado vamos até 13:00. 😊

**Formas de pagamento:**
- **PIX** à vista — 5% de desconto (não cumulativo com promoções)
- **Cartão de débito** à vista
- **Cartão de crédito** até 12x sem juros (parcela mínima: R$ 50 até 3x, R$ 80 de 4–6x, R$ 100 de 7–12x)
- **Boleto** à vista (compensa em até 3 dias úteis)

Dá para combinar formas (ex.: PIX + cartão) em compras acima de R$ 2.000,00.

Quer simular o valor de algum instrumento no PIX ou parcelado?

---
