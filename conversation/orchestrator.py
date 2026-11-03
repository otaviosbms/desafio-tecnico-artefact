"""Orquestrador do turno: o ponto de entrada da UI, do CLI e dos comandos.

Cada conversa é uma `thread_id`; o histórico fica no checkpointer (ver `checkpoints.py`).
`run_turn` abre o contexto do turno (logs com `turn_id`), roda o grafo
(guardrails -> roteador -> agente <-> ferramentas -> finalize) e devolve um `TurnResult`
com o que aconteceu nesta mensagem.
"""

import dataclasses
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache

from langgraph.checkpoint.base import BaseCheckpointSaver

from core.logging import LogCategory, log_event
from core.turn_context import start_turn
from guardrails.service import Guardrails
from llm import LLMClient, LLMConfig, LLMService
from router.service import IntentRouter

from .checkpoints import default_checkpointer
from .graph import build_graph


@dataclass(frozen=True)
class TurnOptions:
    """Opções de uma mensagem (o ambiente de testes escolhe por mensagem)."""

    now: datetime | None = None  # data/hora simulada (None = relógio real)
    router_mode: str | None = None  # off | shadow | enforce (None = o do orquestrador)
    guardrails_mode: str | None = None

    def configurable(self) -> dict:
        values = {
            'agora': self.now.isoformat() if self.now else None,
            'router_mode': self.router_mode,
            'guardrails_mode': self.guardrails_mode,
        }
        return {key: value for key, value in values.items() if value is not None}


@dataclass
class TurnResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # [{'nome': ..., 'argumentos': {...}}]
    trace: list[dict] = field(default_factory=list)  # eventos deste turno (estágios, LLM, ferramentas)
    decisions: list[dict] = field(default_factory=list)  # decisões deste turno (guardrails, roteador, final)
    usage: dict = field(default_factory=dict)  # chamadas ao LLM, tokens, custo, duração
    transfer: str | None = None  # motivo, se o turno pediu a equipe humana
    duration_ms: int = 0
    model: str = ''  # modelo do agente


def _parse_arguments(raw: str | None):
    try:
        return json.loads(raw or '{}')
    except ValueError:
        return raw


class ConversationOrchestrator:
    def __init__(
        self,
        llm: LLMClient | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        service: LLMService | None = None,
        router_mode: str | None = None,
        guardrails_mode: str | None = None,
        **graph_kwargs,
    ):
        """`llm` fixa o cliente do papel `agent` (testes); `service` substitui tudo.

        `router_mode` e `guardrails_mode` sobrescrevem ROUTER_MODE e GUARDRAILS_MODE do .env; por
        mensagem, `TurnOptions` sobrescreve os dois de novo.
        """
        if service is None:
            service = LLMService(llm, role_clients={'agent': llm}) if llm else LLMService()
        self.service = service
        self.llm = service.client_for('agent')
        self.router = IntentRouter(service, mode=router_mode)
        self.guardrails = Guardrails(service, mode=guardrails_mode)
        self.graph = build_graph(service, router=self.router, guardrails=self.guardrails, **graph_kwargs).compile(
            checkpointer=checkpointer or default_checkpointer()
        )

    @property
    def model(self) -> str:
        return self.llm.config.model

    def _config(self, thread_id: str, options: TurnOptions | None = None) -> dict:
        return {'configurable': {'thread_id': thread_id, **(options.configurable() if options else {})}}

    def state(self, thread_id: str) -> dict:
        return self.graph.get_state(self._config(thread_id)).values or {}

    def run_turn(self, thread_id: str, text: str, options: TurnOptions | None = None) -> TurnResult:
        options = options or TurnOptions()
        before = self.state(thread_id)
        counts = {key: len(before.get(key, [])) for key in ('messages', 'trace', 'decisions')}

        start = time.perf_counter()
        with start_turn(thread_id) as turn:
            log_event('turn_started', LogCategory.LIFECYCLE, **options.configurable())
            try:
                result = self.graph.invoke(
                    # Campos por mensagem zerados aqui; `consecutive_blocks` atravessa as mensagens.
                    {'messages': [{'role': 'user', 'content': text}], 'tool_rounds': 0, 'allowed_tools': None,
                     'intents': None, 'guidance': None, 'blocked': False},
                    self._config(thread_id, options),
                )
            except Exception as exc:
                log_event('turn_finished', LogCategory.LIFECYCLE, success=False, error=repr(exc), **turn.summary())
                raise
            usage = turn.summary()
            log_event('turn_finished', LogCategory.LIFECYCLE, success=True, **usage)

        new = {key: result.get(key, [])[count:] for key, count in counts.items()}
        final = next((d for d in reversed(new['decisions']) if d['estagio'] == 'final'), {})
        return TurnResult(
            text=result['messages'][-1]['content'],
            tool_calls=[
                {'nome': call['function']['name'], 'argumentos': _parse_arguments(call['function']['arguments'])}
                for message in new['messages']
                for call in message.get('tool_calls') or []
            ],
            trace=new['trace'],
            decisions=new['decisions'],
            usage=usage,
            transfer=final.get('motivo') if final.get('transferencia') else None,
            duration_ms=round((time.perf_counter() - start) * 1000),
            model=self.model,
        )

    def trace(self, thread_id: str) -> list[dict]:
        """Todos os eventos de execução da conversa (campo `turno` = nº da mensagem do cliente)."""
        return self.state(thread_id).get('trace', [])

    def decisions(self, thread_id: str) -> list[dict]:
        return self.state(thread_id).get('decisions', [])

    def history(self, thread_id: str) -> list[dict]:
        """Mensagens visíveis da conversa (cliente e assistente, sem as ferramentas)."""
        return [
            {'role': m['role'], 'content': m['content']}
            for m in self.state(thread_id).get('messages', [])
            if m['role'] in ('user', 'assistant') and m.get('content')
        ]


@cache
def get_orchestrator(model: str | None = None, temperature: float | None = None, router_model: str | None = None,
                     guardrails_model: str | None = None) -> ConversationOrchestrator:
    """Um orquestrador por combinação de modelos por processo; todos compartilham o histórico.

    Sem argumentos, usa os modelos do .env (LLM_MODEL e LLM_MODEL_*). O provedor (URL e chave) é
    sempre o do .env: a UI de testes troca só os modelos e a temperatura do agente.
    """
    if model is None and temperature is None and router_model is None and guardrails_model is None:
        return ConversationOrchestrator()
    base = LLMConfig.from_env()
    role_clients = {}
    if model is not None or temperature is not None:
        role_clients['agent'] = LLMClient(dataclasses.replace(
            base,
            model=model or base.model,
            temperature=base.temperature if temperature is None else temperature,
        ))
    for role, role_model in (('router', router_model), ('guardrails', guardrails_model)):
        if role_model:
            role_clients[role] = LLMClient(dataclasses.replace(base, model=role_model))
    return ConversationOrchestrator(service=LLMService(role_clients=role_clients))
