from pydantic import BaseModel


class StatsOut(BaseModel):
    total_answered: int
    correct_count: int
    streak: int
    weak_topics: dict
    strong_topics: dict
