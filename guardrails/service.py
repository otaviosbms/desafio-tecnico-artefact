"""Avaliação da mensagem e decisão do efeito (seguir, seguir com orientação, bloquear)."""

import os
from dataclasses import dataclass, field

from core.logging import LogCategory, log_event
from llm import LLMCall, LLMService, Message

from .detector import detect
from .prompts import build_messages
from .responses import HUMAN_HANDOFF_GUIDANCE
from .schemas import GuardrailsOutput

OFF, SHADOW, ENFORCE = 'off', 'shadow', 'enforce'
MODES = (OFF, SHADOW, ENFORCE)
DEFAULT_MODE = SHADOW  # avalia e registra sem bloquear; `enforce` depois de conferir o eval_guardrails
DEFAULT_MAX_CONSECUTIVE_BLOCKS = 3


def check_mode(mode: str) -> str:
    mode = mode.lower()
    if mode not in MODES:
        raise ValueError(f'GUARDRAILS_MODE inválido: {mode!r}. Use {", ".join(MODES)}.')
    return mode


def default_mode() -> str:
    """Modo do .env (GUARDRAILS_MODE), ou o padrão do código."""
    return check_mode(os.getenv('GUARDRAILS_MODE') or DEFAULT_MODE)


@dataclass
class GuardrailsDecision:
    mode: str
    source: str  # off | detector | llm | fallback
    allowed: bool = True  # o que a avaliação concluiu
    category: str = 'ok'
    severity: str = 'none'
    guidance: str | None = None
    requires_human: bool = False
    reasoning: str = ''
    rule: str | None = None  # regra do detector, quando foi ele
    llm_calls: list[LLMCall] = field(default_factory=list)

    @property
    def applied(self) -> bool:
        """O efeito vale de fato? (em shadow e off, nunca)"""
        return self.mode == ENFORCE

    @property
    def hard_block(self) -> bool:
        return self.applied and not self.allowed and self.severity == 'hard'

    @property
    def agent_guidance(self) -> str | None:
        """Orientação para o system prompt do agente (bloqueio leve e/ou caso para a equipe)."""
        if not self.applied:
            return None
        parts = [self.guidance] if not self.allowed and self.severity == 'soft' and self.guidance else []
        if self.requires_human:
            parts.append(HUMAN_HANDOFF_GUIDANCE)
        return '\n'.join(parts) or None

    def as_dict(self) -> dict:
        return {
            'modo': self.mode, 'origem': self.source, 'regra': self.rule, 'permitido': self.allowed,
            'categoria': self.category, 'severidade': self.severity, 'orientacao': self.guidance,
            'requer_humano': self.requires_human, 'justificativa': self.reasoning, 'aplicada': self.applied,
        }


class Guardrails:
    def __init__(self, llm: LLMService, mode: str | None = None, max_consecutive_blocks: int | None = None):
        self.llm = llm
        self.mode = check_mode(mode or default_mode())
        if max_consecutive_blocks is None:
            max_consecutive_blocks = int(os.getenv('GUARDRAILS_MAX_CONSECUTIVE_BLOCKS')
                                         or DEFAULT_MAX_CONSECUTIVE_BLOCKS)
        self.max_consecutive_blocks = max_consecutive_blocks

    def evaluate(self, message: str, previous: list[Message] | None = None,
                 mode: str | None = None) -> GuardrailsDecision:
        """`mode` sobrescreve o modo do guardrails só nesta chamada (ex.: escolhido na UI)."""
        decision = self._evaluate(message, previous, check_mode(mode or self.mode))
        log_event('guardrails_evaluated', LogCategory.DECISION, **decision.as_dict())
        return decision

    def _evaluate(self, message: str, previous: list[Message] | None, mode: str) -> GuardrailsDecision:
        if mode == OFF:
            return GuardrailsDecision(mode=OFF, source='off')

        detection = detect(message)
        if detection:
            return GuardrailsDecision(
                mode=mode, source='detector', rule=detection.rule, allowed=detection.allowed,
                category=detection.category, severity=detection.severity, guidance=detection.guidance,
                reasoning=detection.reasoning,
            )

        result = self.llm.structured(caller='guardrails.evaluate', role='guardrails',
                                     messages=build_messages(message, previous), output_model=GuardrailsOutput)
        if result.value is None:
            log_event('guardrails_fail_open', LogCategory.DEGRADATION, reason='llm_unavailable_or_invalid')
            return GuardrailsDecision(mode=mode, source='fallback', llm_calls=result.calls,
                                      reasoning='Guardrails indisponível: a mensagem segue (fail-open).')
        output = result.value
        return GuardrailsDecision(
            mode=mode, source='llm', allowed=output.allowed, category=output.category,
            severity=output.severity, guidance=output.guidance, requires_human=output.requires_human,
            reasoning=output.reasoning, llm_calls=result.calls,
        )
