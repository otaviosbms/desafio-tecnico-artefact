# Documentação

Documentação técnica do agente de atendimento da Empório da Música, em capítulos. O
[README do repositório](../README.md) resume como rodar e as principais decisões.

| Capítulo | Conteúdo |
|---|---|
| [1. Visão geral](01-visao-geral.md) | O desafio, a solução em uma página, estrutura de pastas e histórico |
| [2. Ciclo request/response](02-ciclo-request-response.md) | Entradas (UI, API, CLI), endpoints, envelope da resposta, orquestrador e persistência |
| [3. Pipeline do turno](03-pipeline-do-turno.md) | O grafo LangGraph, o estado, as proteções e o prompt do agente |
| [4. Estágios de IA](04-estagios-de-ia.md) | Guardrails e roteador de intenção: regras, gate LLM, modos, fail-open |
| [5. Camada de LLM](05-camada-llm.md) | Provedores compatíveis, `LLMService`, modelo por papel, custo, saída estruturada |
| [6. Ferramentas e políticas](06-tools.md) | As 6 ferramentas, contrato/registry/executor, regras de negócio, busca, base de conhecimento, LGPD |
| [7. Dados e regras](07-dados-e-regras.md) | Os CSVs, a carga, as regras do manual, inconsistências e suposições |
| [8. Ambiente de testes](08-ambiente-de-testes.md) | A UI (configuração, conversa, inspetor), o CLI e a geração dos exemplos |
| [9. Observabilidade e testes](09-observabilidade-e-testes.md) | Eventos estruturados, testes automatizados, snapshots, regra de camadas e avaliações |
| [10. Decisões e limitações](10-decisoes-e-limitacoes.md) | Decisões técnicas com alternativas, limitações conhecidas e próximos passos |
