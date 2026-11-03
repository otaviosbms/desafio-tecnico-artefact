"""Roteador de intenção: classifica a mensagem do cliente e decide quais ferramentas o agente recebe.

O LLM propõe as intenções; o código decide as ferramentas (mapa fixo em `intents.py`), aplica o
limiar de confiança e o modo (`off`, `shadow`, `enforce`). Na dúvida ou na falha, libera tudo
(fail-open): restringir demais é pior do que não restringir.
"""
