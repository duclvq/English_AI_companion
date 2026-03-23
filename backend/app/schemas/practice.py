import uuid
from pydantic import BaseModel


class PracticePromptOut(BaseModel):
    id: uuid.UUID
    topic: str
    difficulty: int
    scenario: str
    hint: str | None


class PracticeSubmitRequest(BaseModel):
    prompt_id: uuid.UUID
    user_text: str


class HighlightItem(BaseModel):
    phrase: str
    suggestion: str
    reason: str


class PracticeFeedbackResponse(BaseModel):
    overall_encouragement: str
    highlights: list[HighlightItem]
    corrected_version: str
    beary_tip: str
