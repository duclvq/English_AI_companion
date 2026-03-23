from pydantic import BaseModel
from typing import Literal


class GoalUpdateRequest(BaseModel):
    goal: Literal["travel", "exam", "work", "general"]
    daily_goal: Literal[5, 10, 20, 30]
