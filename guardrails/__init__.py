"""Guardrails: portão antes do roteador e do agente.

1. **Detector determinístico** (`detector.py`): regras por regex, sem LLM. Pega o óbvio (mensagem
   vazia, "ignore suas instruções", pedido de dados de outra pessoa) e conversa trivial.
2. **Gate LLM** (`service.py`): só quando o detector não decidiu. O modelo classifica; o código
   decide o efeito.

Bloqueio **leve** segue para o agente com uma orientação no system prompt; bloqueio **duro**
responde com uma mensagem fixa (`responses.py`) sem chamar o agente. Na falha, segue (fail-open).
"""
