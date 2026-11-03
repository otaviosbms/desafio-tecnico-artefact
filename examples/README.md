# Conversas de exemplo

Transcrições reais do agente, sem edição, geradas com o pipeline completo (guardrails → roteador →
agente) e o LLM real:

```bash
python manage.py generate_examples            # todos os cenários
python manage.py generate_examples --only 03-devolucao-de-pedido
```

Cada arquivo registra o momento da geração, o modelo, o modo dos estágios e, antes de cada
resposta, o que os guardrails e o roteador decidiram e as ferramentas que o agente chamou. Se o LLM
falhar em alguma resposta, o comando não grava nada.

| Arquivo | Cenário | O que demonstra |
|---|---|---|
| [01-catalogo-violoes.md](01-catalogo-violoes.md) | Violões até R$ 1.000 + PIX e parcelamento | Busca com filtros; contexto entre mensagens ("o Yamaha C40"); cálculo de PIX e parcelamento |
| [02-preco-e-estoque.md](02-preco-e-estoque.md) | Preço do Takamine GD20 + produto esgotado | Consulta de preço; indisponibilidade com alternativas trazidas pela ferramenta |
| [03-devolucao-de-pedido.md](03-devolucao-de-pedido.md) | "Me arrependi, posso devolver?" | **Não trivial:** políticas + verificação de identidade + prazo de arrependimento calculado sobre o pedido (já vencido) e a garantia como saída |
| [04-informacoes-da-loja.md](04-informacoes-da-loja.md) | Endereço, horário e pagamento | Consulta às políticas com vários tópicos numa chamada; loja fechada no momento e próxima abertura |
| [05-fora-do-escopo.md](05-fora-do-escopo.md) | Acessórios, receita de bolo, prompt injection | Limites do escopo; intenção `fora_escopo` sem ferramentas; regra de manipulação dos guardrails; fail-open quando o gate LLM ficou sem cota |

Os estágios estavam no modo padrão, `shadow`: os guardrails e o roteador avaliam e registram, mas
não restringem o agente. No 05, o bloqueio leve por manipulação aparece como "só registrado" por
isso; em `enforce`, ele viraria uma orientação no prompt do agente
([capítulo 4](../docs/04-estagios-de-ia.md)).
