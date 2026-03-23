import uuid
from pydantic import BaseModel


class QuestionOut(BaseModel):
    id: uuid.UUID
    type: str
    difficulty: int
    topic: str
    question_text: str
    choices: list[str]


class OnboardingAnswer(BaseModel):
    question_id: uuid.UUID
    chosen_index: int


class OnboardingSubmit(BaseModel):
    answers: list[OnboardingAnswer]
