from pydantic import BaseModel, Field

from .intents import Intent


class RouterOutput(BaseModel):
    """O que o modelo devolve. Validado pelo LLMService (saída estruturada)."""

    intents: list[Intent] = Field(min_length=1, description='Uma ou mais intenções da mensagem atual.')
    confidence: float = Field(ge=0, le=1, description='Confiança na classificação, de 0 a 1.')
    reasoning: str = Field(description='Justificativa curta, em uma frase.')
