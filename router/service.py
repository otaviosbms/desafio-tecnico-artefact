"""Classificação de intenção e decisão das ferramentas liberadas."""

import os
from dataclasses import dataclass, field

from core.logging import LogCategory, log_event
from core.text import has_contact, is_small_talk
from llm import LLMCall, LLMService

from .intents import Intent, tools_for
from .prompts import build_messages
from .schemas import RouterOutput

OFF, SHADOW, ENFORCE = 'off', 'shadow', 'enforce'
MODES = (OFF, SHADOW, ENFORCE)
DEFAULT_MODE = SHADOW  # mede sem restringir; `enforce` depois de conferir o eval_router
DEFAULT_MIN_CONFIDENCE = 0.5


def check_mode(mode: str) -> str:
    mode = mode.lower()
    if mode not in MODES:
        raise ValueError(f'ROUTER_MODE inválido: {mode!r}. Use {", ".join(MODES)}.')
    return mode


def default_mode() -> str:
    """Modo do .env (ROUTER_MODE), ou o padrão do código."""
    return check_mode(os.getenv('ROUTER_MODE') or DEFAULT_MODE)


@dataclass
class RouterDecision:
    mode: str
    source: str  # off | shortcut | llm | fallback
    intents: list[str] = field(default_factory=list)
    confidence: float | None = None
    reasoning: str = ''
    proposed_tools: list[str] | None = None  # o que as intenções liberariam
    allowed_tools: list[str] | None = None  # o que vale de fato (None = todas)
    llm_calls: list[LLMCall] = field(default_factory=list)

    @property
    def restricted(self) -> bool:
        return self.allowed_tools is not None

    def as_dict(self) -> dict:
        return {
            'modo': self.mode, 'origem': self.source, 'intencoes': self.intents, 'confianca': self.confidence,
            'justificativa': self.reasoning, 'ferramentas_propostas': self.proposed_tools,
            'ferramentas_liberadas': self.allowed_tools,
        }


def adjust_intents(intents: list[str], message: str) -> list[str]:
    """Correções determinísticas sobre a classificação do LLM.

    - Mensagem com e-mail ou telefone é dado para consultar pedido: inclui `pedido`, para a
      ferramenta não ficar de fora em enforce (ex.: o cliente responde só "fulano@email.com").
    - `saudacao_conversa` junto de outra intenção é só o "Oi!" do começo da frase: sai.
    """
    result = list(dict.fromkeys(intents))
    if has_contact(message) and Intent.PEDIDO not in result:
        result.append(Intent.PEDIDO.value)
    if len(result) > 1 and Intent.SAUDACAO_CONVERSA in result:
        result.remove(Intent.SAUDACAO_CONVERSA.value)
    return result


class IntentRouter:
    def __init__(self, llm: LLMService, mode: str | None = None, min_confidence: float | None = None):
        self.llm = llm
        self.mode = check_mode(mode or default_mode())
        if min_confidence is None:
            min_confidence = float(os.getenv('ROUTER_MIN_CONFIDENCE') or DEFAULT_MIN_CONFIDENCE)
        self.min_confidence = min_confidence

    def classify(self, message: str, last_assistant: str | None = None, mode: str | None = None) -> RouterDecision:
        """`mode` sobrescreve o modo do roteador só nesta chamada (ex.: escolhido na UI)."""
        decision = self._classify(message, last_assistant, check_mode(mode or self.mode))
        log_event('intent_classified', LogCategory.DECISION, **decision.as_dict())
        return decision

    def _classify(self, message: str, last_assistant: str | None, mode: str) -> RouterDecision:
        if mode == OFF:
            return RouterDecision(mode=OFF, source='off')

        if is_small_talk(message):
            return self._decide(RouterDecision(
                mode=mode, source='shortcut', intents=[Intent.SAUDACAO_CONVERSA.value], confidence=1.0,
                reasoning='Só cumprimento ou agradecimento (atalho, sem LLM).',
            ))

        result = self.llm.structured(caller='router.classify', role='router',
                                     messages=build_messages(message, last_assistant), output_model=RouterOutput)
        if result.value is None:
            log_event('router_fail_open', LogCategory.DEGRADATION, reason='llm_unavailable_or_invalid')
            return RouterDecision(mode=mode, source='fallback', reasoning='Roteador indisponível: todas as '
                                  'ferramentas liberadas.', llm_calls=result.calls)
        output = result.value
        return self._decide(RouterDecision(
            mode=mode, source='llm', intents=adjust_intents([str(i) for i in output.intents], message),
            confidence=output.confidence, reasoning=output.reasoning, llm_calls=result.calls,
        ))

    def _decide(self, decision: RouterDecision) -> RouterDecision:
        decision.proposed_tools = tools_for([Intent(i) for i in decision.intents])
        confident = decision.confidence is not None and decision.confidence >= self.min_confidence
        if decision.mode == ENFORCE and confident:
            decision.allowed_tools = decision.proposed_tools
        elif decision.mode == ENFORCE:
            log_event('router_fail_open', LogCategory.DEGRADATION, reason='low_confidence',
                      confidence=decision.confidence, min_confidence=self.min_confidence)
        return decision
