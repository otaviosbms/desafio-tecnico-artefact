# 8. Ambiente de testes (UI e CLI)

A UI web não simula só o chat do cliente: é um ambiente para inspecionar e experimentar o agente.
Template Django com JavaScript puro (`conversation/templates/`, `conversation/static/`), sem
framework nem CDN. Abre em `http://localhost:8000` com `python manage.py runserver`.

## Três painéis

### Configuração

- **Conversa:** id da thread (copiar, abrir uma existente, por exemplo criada no CLI), nova
  conversa e exportação em Markdown.
- **Modelo e temperatura:** trocáveis por mensagem; provedor e chave vêm sempre do `.env`.
- **Data/hora simulada:** com presets. Afeta o horário da loja, os prazos de pedidos e o system prompt.
- **Estágios:** modo dos guardrails e do roteador (`off`, `shadow`, `enforce` ou o padrão do `.env`)
  e o modelo de cada um, por mensagem. Tudo é validado no backend.
- **Exibição:** opções de visualização e tema.
- **Cenários de teste:** perguntas prontas, agrupadas por assunto.
- **Dados de teste:** pedidos e e-mails fictícios do desafio. Só aparecem com `DEBUG=True`.

### Conversa

Etiquetas por resposta (ferramentas, tempo, chamadas ao LLM, tokens, erro) e um contador de tempo
enquanto o modelo responde. Estatísticas da conversa: mensagens, tempo, tokens, custo e chamadas
ao LLM por mensagem.

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
python manage.py chat --thread <id>                # retoma uma conversa (também abre na UI)
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
