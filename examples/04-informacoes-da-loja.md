# Informações gerais: endereço, horário e formas de pagamento

**Objetivo:** Perguntas respondidas pelo manual de políticas, incluindo se a loja está aberta no momento da conversa.

- Gerado em: segunda-feira, 02/11/2026 22:17 (horário de Campo Grande)
- Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`
- Estágios: guardrails `shadow` · roteador `shadow`
- Comando: `python manage.py generate_examples --only 04-informacoes-da-loja`

> Transcrição real, sem edição. Antes de cada resposta: o que os guardrails e o roteador decidiram e as ferramentas que o agente consultou.

---

**Cliente:** Qual o endereço da loja?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `politicas` · llm · confiança 0.98
> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["loja"]}`

**Assistente:**

A loja fica na **Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333**.

Se precisar, o WhatsApp/telefone é **(67) 3341-4444**.

Posso ajudar com mais alguma coisa? 🎸

---

**Cliente:** Vocês estão abertos agora? E quais formas de pagamento aceitam?

> 🛡️ Guardrails: passou · llm
> 🧭 Intenção: `politicas` · llm · confiança 0.97
> 🔧 Ferramenta: `consultar_politicas` `{"topicos": ["horario", "pagamento"]}`

**Assistente:**

Agora estamos **fechados** (são 22:18 de segunda-feira). A loja abre terça-feira às **09:00**.

**Formas de pagamento:**
- **PIX** à vista → 5% de desconto (não acumula com promoções)
- **Cartão de débito** à vista
- **Cartão de crédito** em até **12x sem juros** (parcela mínima: R$ 50 até 3x, R$ 80 de 4 a 6x, R$ 100 de 7 a 12x)
- **Boleto** à vista (compensa em até 3 dias úteis)

Também dá pra combinar formas (ex.: PIX + cartão) em compras acima de R$ 2.000.

O WhatsApp segue o mesmo horário; fora do expediente a equipe retorna no próximo dia útil.

Precisa de mais alguma coisa? 😊

---
