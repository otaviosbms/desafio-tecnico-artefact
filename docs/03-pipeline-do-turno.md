# 3. Pipeline do turno

Cada mensagem do cliente é um turno: uma execução do grafo LangGraph de `conversation/graph.py`.

## O grafo

```
START
  │
  ▼
guardrails ──(bloqueio duro ou 3 bloqueios seguidos)──► respond_blocked ──┐
  │ (passou, ou bloqueio leve → orientação guardada)                      │
  ▼                                                                       │
router  (classifica a intenção → ferramentas liberadas; falha = todas)    │
  │                                                                       │
  ▼                                                                       │
agent ◄──────────────┐  (LLM com as ferramentas liberadas + orientação)   │
  │ tool_calls?      │                                                    │
  ├── sim ─► tools ──┘  (ToolExecutor; no máximo 4 rodadas)               │
  │                                                                       │
  └── não ─► finalize ◄───────────────────────────────────────────────────┘
               │  (decisão final: transferência, bloqueio, uso de LLM)
               ▼
              END
```

| Nó | O que faz | Chama o LLM? |
|---|---|---|
| `guardrails` | Avalia a mensagem (capítulo 4). Guarda a orientação de um bloqueio leve | Só se nenhuma regra casou |
| `respond_blocked` | Responde com um texto **fixo** (o LLM classifica, mas não escreve o que o cliente lê) | Não |
| `router` | Classifica a intenção e define as ferramentas liberadas (capítulo 4) | Só fora do atalho de saudação |
| `agent` | Monta o system prompt e chama o LLM com as ferramentas liberadas | Sim |
| `tools` | Executa as chamadas pedidas pelo modelo e devolve os resultados (capítulo 6) | Não |
| `finalize` | Registra a decisão `final` do turno: transferência e motivo, se foi bloqueado, uso de LLM | Não |

## Estado (`AgentState`)

| Campo | Escopo | Conteúdo |
|---|---|---|
| `messages` | Conversa | Histórico no formato Chat Completions |
| `trace` | Conversa | Eventos para o inspetor da UI (nunca vão ao LLM) |
| `decisions` | Conversa | Decisões de cada estágio, por turno |
| `consecutive_blocks` | Conversa | Bloqueios seguidos dos guardrails |
| `allowed_tools`, `intents` | Mensagem | Saída do roteador |
| `guidance`, `blocked` | Mensagem | Saída dos guardrails |
| `tool_rounds` | Mensagem | Rodadas de ferramentas já feitas |

As opções da mensagem (`agora`, `router_mode`, `guardrails_mode`) chegam pela `configurable` da
execução, não pelo estado. A data simulada chega às ferramentas por um `ContextVar` (`core/clock.py`).

## Proteções

- **Limite de rodadas:** no máximo 4 rodadas de ferramentas por mensagem. Depois disso o modelo é
  chamado sem ferramentas e precisa responder.
- **Falha do provedor ou resposta vazia:** viram a resposta de contingência (`FALLBACK_REPLY`), com
  o contato da equipe, e um log `DEGRADATION`.
- **Argumentos inválidos:** JSON quebrado ou fora do schema volta ao modelo como erro, para ele se
  corrigir.
- **Histórico enviado ao LLM:** só as últimas 40 mensagens, sempre começando numa mensagem do
  cliente. Assim a conversa nunca é cortada no meio de uma rodada de ferramentas, o que os
  provedores rejeitam.
- **Fail-open nos estágios:** se o guardrails ou o roteador falham, o turno segue com todas as
  ferramentas (capítulo 4). Só o agente é indispensável.

## Prompt do agente (`conversation/prompts.py`)

O system prompt **não fica no estado**: é montado a cada chamada com a data/hora de Campo Grande e
se a loja está aberta. Assim o histórico não envelhece e o contexto está sempre certo.

- **Origem:** as diretrizes internas do manual (seção 7) viraram regras do prompt.
  - **Tom:** informal, mas profissional.
  - **Precisão:** nunca informar preço, estoque ou status sem consultar o sistema.
  - **Situações especiais:** produto esgotado, fora de linha, "em breve"; promoção expirada; reclamação.
  - **Escopo:** pedidos de acessórios são redirecionados.
- **Formato de chat:** mensagens curtas, sem tabelas nem títulos, no máximo 5 produtos por lista.
  No primeiro teste com LLM real, as respostas vieram com tabelas markdown longas.
- **Roteamento explícito:** dados → ferramentas de dados; regras → `consultar_politicas`.
  Informação ausente → dizer que não sabe e oferecer a equipe, sem completar com conhecimento geral.
- **Escopo em três níveis:** assuntos da loja são atendidos normalmente; dúvidas gerais sobre
  instrumentos que ajudam na compra recebem resposta breve; o resto, recusa gentil em uma frase.
- **Proteção contra prompt injection:** o agente não revela as instruções nem muda de papel.

Dois blocos só aparecem quando há algo a dizer nesta mensagem:

- `# Orientação para esta mensagem`: orientação dos guardrails (bloqueio leve, caso para a equipe);
- `# Escopo desta resposta`: intenções e ferramentas desta mensagem, quando o roteador restringiu
  as ferramentas (modo `enforce`).

O texto exato do prompt fica versionado em snapshots (capítulo 9) e aparece na aba Prompt da UI.

## Por que um grafo próprio

- **Sem modelos do LangChain:** os nós chamam o `LLMService` próprio (capítulo 5), e o histórico
  fica independente de provedor.
- **Alternativa descartada:** `create_react_agent` pronto do LangGraph. Ele exige modelos do
  LangChain, e o grafo próprio deixa explícitos os estágios, o limite de rodadas e o tratamento de erros.

---

Anterior: [2. Ciclo request/response](02-ciclo-request-response.md) · [Índice](README.md) · Próximo: [4. Estágios de IA](04-estagios-de-ia.md)
