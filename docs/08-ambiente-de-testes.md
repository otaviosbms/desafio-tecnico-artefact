# 8. Ambiente de testes (UI e CLI)

A UI web não simula só o chat do cliente: é um ambiente para inspecionar e experimentar o agente.
Template Django com JavaScript puro (`conversation/templates/`, `conversation/static/`), sem
framework nem CDN. Abre em `http://localhost:8000` com `python manage.py runserver`.

Visual em vermelho e branco, com tema claro e escuro (segue o sistema; o botão da barra superior
alterna). A barra superior mostra o modelo, o relógio em uso e se a loja está aberta, e tem as
ações de nova conversa, exportar em Markdown e tema.

## Três painéis

### Configuração

Só o essencial, em cartões; tudo vale por mensagem e é validado no backend:

- **Modelo:** do agente (vazio = o do `.env`; provedor e chave vêm sempre do `.env`).
- **Data e hora:** simulada, com presets. Afeta o horário da loja, os prazos de pedidos e o system prompt.
- **Estágios:** modo dos guardrails e do roteador num controle segmentado (padrão do `.env`, `off`,
  `shadow`, `enforce`).
- **Cenários de teste:** perguntas prontas por assunto (um grupo aberto por vez) e, só com
  `DEBUG=True`, os pedidos fictícios do desafio, que inserem número e e-mail na mensagem.
- **Avançado** (recolhido): temperatura, modelo dos guardrails e do roteador e o id da conversa.

Sem mensagens, a conversa mostra quatro sugestões que enviam direto.

### Conversa

Etiquetas por resposta (ferramentas, tempo, chamadas ao LLM, tokens, erro) e um indicador com
contador de tempo enquanto o modelo responde. Enter envia; Shift+Enter quebra a linha.
Estatísticas da conversa: mensagens, tempo, tokens, custo e chamadas ao LLM por mensagem.

### Inspetor

| Aba | Conteúdo |
|---|---|
| **Rastro** | Por mensagem: cada chamada ao modelo (caller, duração, tokens, custo, `finish_reason`, ferramentas pedidas, erro), cada ferramenta (argumentos, resultado, código de erro, duração) e os eventos de decisão e bloqueio |
| **Decisões** | O que cada estágio decidiu: guardrails (passa ou bloqueio, por regra ou LLM, se foi aplicado), intenção (intenções, confiança, ferramentas liberadas), transferência para a equipe, uso (chamadas, tokens, custo) |
| **Prompt** | O system prompt exato para a data em uso |
| **Ferramentas** | Os schemas enviados ao modelo |

## Responsivo

- **Desktop (1200 px ou mais):** 3 colunas.
- **Tablet (900 a 1199 px):** o inspetor vira gaveta.
- **Celular:** um painel por vez, com navegação inferior e contador de novidades no inspetor.

Verificado em 1366, 1280, 1024 e 375 px, sem rolagem horizontal.

## Segurança

- **XSS:** o markdown é renderizado só depois de escapar o HTML.
- **CSRF:** exigido nos POSTs.
- **Validação:** nome de modelo, temperatura (0 a 2), data, modos e id de thread.
- **Dados pessoais:** os dados de teste com e-mails só aparecem em `DEBUG`.

## CLI

```bash
python manage.py chat                              # interativo
python manage.py chat --show-tools --logs          # mostra ferramentas e eventos estruturados
python manage.py chat -m "Oi" -m "Qual o endereço?" # conversa roteirizada
python manage.py chat --thread <id>                # retoma uma conversa
```

## Conversas de exemplo

`python manage.py generate_examples [--only <cenário>]` roda os 5 cenários de `examples/` com o
LLM configurado e grava cada transcrição sem edição: o que os guardrails e o roteador decidiram, as
ferramentas chamadas e a resposta. Se o LLM falhar em alguma resposta, nada é gravado.

## Limitação

A resposta chega de uma vez, sem streaming. Streaming (SSE) com os eventos do LangGraph seria a
próxima melhoria.

---

Anterior: [7. Dados e regras](07-dados-e-regras.md) · [Índice](README.md) · Próximo: [9. Observabilidade e testes](09-observabilidade-e-testes.md)
