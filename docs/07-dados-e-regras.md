# 7. Dados e regras de negócio

Os dados do desafio, como foram carregados, as regras do manual e as suposições feitas onde os
dados ou o manual não bastam.

## Tabelas (`data/*.csv`)

| Arquivo | Linhas | Observações |
|---|---|---|
| categories.csv | 9 | Guitarras, Baixos, Baterias, Teclados, Violões, Sopro (madeiras/metais), Cordas orquestrais, Ukuleles |
| products.csv | 65 | `status`: `active`, `coming_soon` ou `discontinued`; `specs` é JSON; alguns com estoque 0 |
| promotions.csv | 25 | Só **4 ativas** (`is_active=1`): produtos 127, 121, 90 e 94 |
| customers.csv | 50 | Nome, telefone, e-mail, cidade (várias cidades de MS) |
| orders.csv | 20 | `status`: pending, confirmed, shipped, delivered, cancelled; cancelados têm motivo em `notes` |
| order_items.csv | 22 | Pedidos 15 e 20 têm 2 itens |

Casos especiais úteis para os exemplos de conversa:

| Produto | Situação |
|---|---|
| 96 Giannini GF-3D | Ativo, **sem estoque** |
| 113 Shelby SN-7C | **Descontinuado**, sem estoque |
| 130 Kala KA-ABP-CTG | **Em breve** (`coming_soon`), com 2 unidades |
| 136 Ibanez Bass 2X | **Descontinuado**, com 13 unidades |
| 95 Takamine GD20 | R$ 2.199 (citado no enunciado). Promoção "Oferta Especial" **inativa** |

## Tratamento na carga (`load_data`)

- Mantém os IDs dos CSVs (as FKs dependem deles) e ajusta as sequences no Postgres.
- Remove espaços extras; strings vazias viram `NULL` ou `''`.
- `specs` vira JSON; e-mails em minúsculas; datas no formato ISO.
- O `total_brl` dos pedidos é o valor histórico pago e **não** é recalculado (ex.: o pedido 3
  tem 2x o produto 130 por R$ 3.450, enquanto o preço atual é R$ 1.749 cada).

## Regras de negócio (manual de políticas)

- **Horário:** seg–sex 09h–18h, sáb 09h–13h, domingos e feriados fechado.
- **Pagamento:**
  - PIX com 5% de desconto (não acumula com promoção);
  - débito;
  - crédito em até 12x sem juros;
  - boleto (compensação em até 3 dias úteis).
- **Parcelamento:**
  - até 3x sem valor mínimo;
  - de 4x a 6x, parcela mínima de R$ 80;
  - de 7x a 12x, parcela mínima de R$ 100;
  - combinar formas de pagamento só acima de R$ 2.000.
- **Trocas e devoluções:**
  - arrependimento: 7 dias corridos após o **recebimento**, em compras online;
  - defeito: 30 dias corridos após a compra;
  - preferência: 7 dias;
  - não elegíveis: itens personalizados, liquidação "venda final" e boquilhas.
- **Frete em Campo Grande:** grátis acima de R$ 500, senão R$ 35; entrega em 1 a 3 dias úteis.
- **Frete para outras cidades:** PAC, SEDEX ou Jadlog, com cotação pelo CEP.
- **Garantia:** legal de 90 dias; a do fabricante varia de 6 meses a 2 anos.
- **Escopo:** a loja vende **somente instrumentos**. Pedidos de acessórios (cordas, cabos,
  palhetas, pedais, amplificadores, cases) devem ser redirecionados com educação.
- **Precisão:** nunca informar preço, estoque ou prazo sem consultar o sistema.
- **Promoções:** mostrar o preço original, o percentual e o preço final.
- **Fora do expediente:** informar o horário de retorno.

## Inconsistências encontradas no manual

| Tema | Conflito | Suposição adotada |
|---|---|---|
| WhatsApp | (67) 3341-4444 (capa e seção 1.2, "Telefone / WhatsApp") × (67) 3321-4500 (seção 7) | **(67) 3341-4444**: aparece duas vezes, inclusive na tabela oficial de dados da empresa. O agente informa um só número para não confundir o cliente |
| E-mail | contato@emporiodamusica.com.br (capa) × contato@empóriodamusica.com.br (seção 1.2) | Versão **sem acento** (domínio válido) |
| Parcelamento | Tabela: "até 12x, parcela mínima R$ 100" × regras da seção 3.1, com faixas | Seção 3.1, mais detalhada |
| Parcelamento até 3x | "sem valor mínimo (exceto abaixo de R$ 50)", texto ambíguo | Parcela mínima de R$ 50 |
| Catálogo | Manual fala em "mais de 300 instrumentos"; o CSV tem 65 | O CSV é a fonte da verdade |

## Suposições das ferramentas

| Tema | Suposição |
|---|---|
| Data de recebimento | Não existe nos dados. Para pedidos entregues, usa-se `estimated_delivery` como data de recebimento |
| Arrependimento (7 dias) | Vale para todos os pedidos do sistema (são compras com envio, portanto online) |
| Troca por preferência (7 dias) | O manual não diz desde quando; conta-se do recebimento |
| Troca por defeito (30 dias) | Conta-se da data da compra (`order_date`), como diz o manual |
| Produto descontinuado com estoque | Não é vendável (política 7.3: "não faz mais parte do catálogo") |
| `coming_soon` com estoque | Não é vendável ainda |
| Mais de uma promoção ativa no mesmo produto | Vale a de maior desconto (promoções não são cumulativas) |
| Frete grátis "acima de R$ 500" | Estritamente maior que R$ 500; o mesmo vale para "acima de R$ 2.000" na combinação de formas de pagamento |

---

Anterior: [6. Ferramentas e políticas](06-tools.md) · [Índice](README.md) · Próximo: [8. Ambiente de testes](08-ambiente-de-testes.md)
