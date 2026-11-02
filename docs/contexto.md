# Contexto

## O desafio

Desafio técnico de AI Engineer da Artefact: prototipar um **agente de atendimento por
mensagens de texto** para a **Empório da Música**, loja fictícia de instrumentos musicais
em Campo Grande/MS. A equipe da loja está sobrecarregada com perguntas recorrentes
(horários, status de pedido, preço e disponibilidade de produtos).

O agente deve:

- assumir uma **persona** alinhada ao tom da loja (informal, mas profissional);
- responder com base no contexto disponível;
- saber **quando consultar dados** (estoque, preço, pedidos) e **quando consultar políticas**
  (trocas, horários, pagamento);
- lidar com perguntas **fora do escopo** da loja.

Única restrição obrigatória: **Python**.

## Entregáveis

1. Repositório público no GitHub, com histórico de commits real (sem force-push).
2. `README.md` com:
   - instruções para rodar o projeto;
   - justificativa das decisões técnicas;
   - limitações conhecidas;
   - uso de assistentes de código.
3. De 3 a 5 exemplos de conversa (`.md`, `.txt` ou imagem). Pelo menos um deve ser não trivial,
   consultando dados ou aplicando políticas.

Sugestões de cenários do enunciado:
- violões até R$ 1000;
- endereço da loja;
- preço do Takamine GD20;
- arrependimento e devolução de compra.

## Material fornecido (`data/`)

- `categories.csv`, `products.csv`, `promotions.csv`, `customers.csv`, `orders.csv`, `order_items.csv`
- `politicas_da_loja.pdf`: manual interno de atendimento (horários, pagamento, trocas, frete,
  promoções, diretrizes do WhatsApp, garantia, LGPD)

Detalhes e inconsistências em [dados.md](dados.md).

## Estado atual

| Data | Etapa |
|---|---|
| 2026-11-02 | Projeto Django criado (`config/`), dados copiados para `data/` |
| 2026-11-02 | App `store` com models e comando `load_data` (validado em SQLite) |
| 2026-11-02 | Módulo genérico `llm/` (qualquer provedor compatível com a API da OpenAI) + testes |
| 2026-11-02 | Chamada real validada via OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`), texto e function calling |

Ambiente de desenvolvimento: Windows, Python 3.14, **Postgres 16 local** (serviço do Windows).
O `docker-compose.yml` existe como alternativa para quem for rodar o projeto.

Próximos passos: ver o roadmap (fora do repositório, em `Downloads/roadmap-desafio-artefact`).
