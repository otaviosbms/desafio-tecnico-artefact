from typing import Literal

from pydantic import BaseModel, Field, model_validator

Category = Literal['ok', 'fora_escopo', 'manipulacao', 'abusivo', 'reclamacao_grave']
Severity = Literal['none', 'soft', 'hard']


class GuardrailsOutput(BaseModel):
    """Avaliação do gate LLM. Validada pelo LLMService (saída estruturada)."""

    allowed: bool = Field(description='true só com severity none; false com soft ou hard.')
    category: Category
    severity: Severity = Field(description='none = segue normalmente; soft = segue com orientação; hard = não responde o pedido.')
    guidance: str | None = Field(None, description='Orientação curta para o atendente. Obrigatória se allowed=false.')
    requires_human: bool = Field(False, description='true se o caso precisa da equipe humana (ex.: reclamação grave).')
    reasoning: str = Field(description='Justificativa curta, em uma frase.')

    @model_validator(mode='after')
    def _coerente(self):
        # A severidade decide: alguns modelos marcam allowed=true num bloqueio leve, porque a mensagem
        # ainda segue para o atendente.
        if self.severity != 'none':
            self.allowed = False
        if not self.allowed and self.severity == 'none':
            raise ValueError('allowed=false exige severity "soft" ou "hard".')
        if not self.allowed and not (self.guidance or '').strip():
            raise ValueError('allowed=false exige guidance.')
        return self
