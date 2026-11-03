# 4. Estágios de IA: guardrails e roteador

Dois estágios rodam antes do agente. Os dois seguem as mesmas regras:

- **Saída estruturada validada:** o LLM devolve JSON validado por um modelo Pydantic
  (`LLMService.structured`, capítulo 5);
- **O LLM classifica, o código decide:** o roteador propõe intenções, mas as ferramentas vêm de um
  mapa fixo; o guardrails classifica, mas a resposta de um bloqueio duro é um texto fixo;
- **Fail-open:** LLM indisponível ou saída inválida não derrubam o atendimento; o turno segue sem
  restrição, com um log `DEGRADATION`;
- **Três modos**, no `.env` ou por mensagem na UI:

  | Modo | Comportamento |
  |---|---|
  | `off` | Não avalia (a decisão `off` fica no rastro) |
  | `shadow` (padrão) | Avalia e registra, mas não age. Serve para medir antes de aplicar |
  | `enforce` | Aplica a decisão |

- **Modelo próprio:** `LLM_MODEL_GUARDRAILS` e `LLM_MODEL_ROUTER`. Os dois só classificam, então um
  modelo menor e mais rápido costuma bastar.

## Guardrails (`guardrails/`)

Primeiro nó do grafo. Avalia a mensagem do cliente antes do roteador e do agente.

### 1. Detector determinístico (`detector.py`), sem LLM

| Regra | Exemplos | Resultado |
|---|---|---|
| `mensagem_vazia` | "", "👍👍", "?!" | Bloqueio duro: pede para escrever de novo |
| `manipulacao` | "ignore suas instruções", "qual é o seu prompt?", "aja como", "modo desenvolvedor" | Bloqueio leve: orientação para manter o papel e não conceder condições fora das ferramentas |
| `dados_de_terceiros` | "pedido do João", "endereço da minha amiga", "dados de outra pessoa" | Bloqueio leve: lembrar a verificação de identidade |
| `conversa` | "oi", "boa noite!", "valeu" | Passa, sem LLM |

### 2. Gate LLM (`caller=guardrails.evaluate`)

Só roda quando nenhuma regra casou. O modelo devolve `GuardrailsOutput` (`allowed`, `category`,
`severity`, `guidance`, `requires_human`, `reasoning`). A validação exige coerência (`allowed=false`
pede severidade e orientação). O prompt diz que bloquear um cliente legítimo é pior do que deixar passar.

### Efeitos (em `enforce`)

| Resultado | Efeito |
|---|---|
| Passa | Segue para o roteador |
| Bloqueio leve | Segue, com a orientação no bloco `# Orientação para esta mensagem` do prompt do agente (só nesta mensagem) |
| Bloqueio duro | `respond_blocked`: resposta fixa de `responses.py`; o agente não é chamado |
| `requires_human` | Orientação para oferecer a equipe (WhatsApp) e decisão `transferencia` registrada |
| 3 bloqueios seguidos | Resposta oferecendo a equipe, decisão `transferencia` e o contador zera (`GUARDRAILS_MAX_CONSECUTIVE_BLOCKS`) |
| LLM falhou ou saída inválida | Fail-open, com `DEGRADATION` (`guardrails_fail_open`) |

Em `shadow`, a decisão vai para o rastro e para o log, mas nunca bloqueia nem orienta.

**Limitação conhecida:** a regra de dados de terceiros pega "pedido da Gibson" (marca com inicial
maiúscula). O efeito é só uma orientação extra ao agente, não um bloqueio.

## Roteador de intenção (`router/`)

Classifica a mensagem do cliente em uma ou mais intenções. A última resposta do assistente (até 600
caracteres) vai junto como contexto, para "e no PIX?" herdar o assunto. O LLM propõe as intenções;
o código decide as ferramentas pelo mapa fixo de `router/intents.py`:

| Intenção | Ferramentas liberadas |
|---|---|
| `catalogo` | `buscar_produtos`, `detalhes_produto`, `listar_promocoes` |
| `preco_pagamento` | `detalhes_produto`, `condicoes_pagamento`, `buscar_produtos`, `consultar_politicas` |
| `pedido` | `consultar_pedido`, `consultar_politicas` |
| `politicas` | `consultar_politicas` |
| `saudacao_conversa`, `fora_escopo` | nenhuma |

- **Em `enforce`:** o agente recebe só as ferramentas das intenções, o prompt ganha o bloco
  `# Escopo desta resposta` e o executor recusa as outras (`tool_not_allowed`).
- **Fail-open:** LLM indisponível, saída fora do schema ou confiança abaixo de
  `ROUTER_MIN_CONFIDENCE` (0,5) liberam todas as ferramentas, com `DEGRADATION` (`router_fail_open`).
- **Atalho sem LLM:** mensagens de até 4 palavras feitas só de cumprimento, agradecimento ou
  despedida ("oi", "boa noite!", "valeu, tchau") viram `saudacao_conversa` sem chamar o modelo.
  "ok", "sim" e "beleza" ficam de fora, porque costumam continuar um assunto.

## Rastro, logs e avaliação

| | Guardrails | Roteador |
|---|---|---|
| Evento no rastro | `decisao` (origem, regra, avaliação, se foi aplicada, orientação, bloqueios seguidos) e `bloqueio` quando a resposta é fixa | `llm` (`caller=router.classify`) e `decisao` (modo, origem, intenções, confiança, ferramentas propostas e liberadas) |
| Log | `DECISION/guardrails_evaluated`, `DECISION/human_handoff` | `DECISION/intent_classified` |
| Avaliação | `eval_guardrails`: 22 casos (12 normais, 10 problemáticos); meta de **zero falsos bloqueios** | `eval_router`: 35 casos; meta de **85% de acerto** |

As avaliações estão no [capítulo 9](09-observabilidade-e-testes.md). Os dois estágios vêm em
`shadow` por padrão: a ideia é passar para `enforce` depois de conferir os números com o modelo em uso.

---

Anterior: [3. Pipeline do turno](03-pipeline-do-turno.md) · [Índice](README.md) · Próximo: [5. Camada de LLM](05-camada-llm.md)
