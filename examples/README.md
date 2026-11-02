# Conversas de exemplo

Transcrições reais do agente, sem edição, geradas com:

```bash
python manage.py generate_examples            # todos os cenários
python manage.py generate_examples --only 03-devolucao-de-pedido
```

Cada arquivo registra o momento da geração, o modelo usado e as ferramentas que o agente chamou
em cada resposta.

| Arquivo | Cenário | O que demonstra |
|---|---|---|
| [01-catalogo-violoes.md](01-catalogo-violoes.md) | Violões até R$ 1.000 + PIX e parcelamento | Busca com filtros; contexto entre mensagens; cálculo de pagamento |
| [02-preco-e-estoque.md](02-preco-e-estoque.md) | Preço do Takamine GD20 + produto esgotado | Consulta de preço; indisponibilidade com alternativas |
| [03-devolucao-de-pedido.md](03-devolucao-de-pedido.md) | "Me arrependi, posso devolver?" | **Não trivial:** verificação de identidade + prazos do manual aplicados ao pedido |
| [04-informacoes-da-loja.md](04-informacoes-da-loja.md) | Endereço, horário e pagamento | Consulta às políticas; loja aberta ou fechada no momento |
| [05-fora-do-escopo.md](05-fora-do-escopo.md) | Acessórios, receita de bolo, prompt injection | Limites do escopo e resistência a manipulação |

O modelo usado é gratuito e lento (minutos por resposta). Por isso, as conversas foram geradas por
comando, e não digitadas na UI.
