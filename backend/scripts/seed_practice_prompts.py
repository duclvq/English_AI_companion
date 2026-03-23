"""Seed practice_prompts table. Run once: python -m scripts.seed_practice_prompts"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.practice import PracticePrompt

PROMPTS = [
    dict(topic="past_perfect", difficulty=2,
         scenario="You just returned from a trip. Tell Beary about something interesting that happened before you arrived at your destination.",
         hint='Try to use "had" in your answer'),
    dict(topic="past_perfect", difficulty=2,
         scenario="You missed an important event. Tell Beary what had already happened by the time you arrived.",
         hint='Use "had already" to describe something completed before another past event'),
    dict(topic="past_perfect", difficulty=3,
         scenario="Describe a time when you realized you had made a mistake. What had you done, and what happened next?",
         hint=None),
    dict(topic="present_perfect", difficulty=2,
         scenario="Tell Beary about something you have never done but would like to try.",
         hint='Use "have never" or "have always wanted to"'),
    dict(topic="present_perfect", difficulty=2,
         scenario="Describe your experience with learning a new skill. Have you ever struggled with something before getting better?",
         hint='Use "have + past participle" (e.g. have tried, have learned)'),
    dict(topic="past_tense", difficulty=1,
         scenario="Describe what you did last weekend. Where did you go and who did you meet?",
         hint="Use past tense verbs: went, saw, ate, talked..."),
    dict(topic="past_tense", difficulty=1,
         scenario="Tell Beary about a memorable meal you had. What did you eat and where were you?",
         hint=None),
    dict(topic="conditionals", difficulty=3,
         scenario="If you could live anywhere in the world, where would you choose and why?",
         hint='Use "would" and "if I could..." or "if I were..."'),
    dict(topic="conditionals", difficulty=2,
         scenario="What would you do if you found a large amount of money on the street?",
         hint='Use "I would..." to describe your choices'),
    dict(topic="articles", difficulty=2,
         scenario="Describe your favourite place in your city to a friend visiting for the first time.",
         hint='Pay attention to when to use "a", "an", or "the"'),
    dict(topic="prepositions", difficulty=2,
         scenario="Describe how to get from your home to the nearest supermarket.",
         hint="Use prepositions of place and movement: at, on, in, next to, turn left..."),
    dict(topic="idioms", difficulty=3,
         scenario="Tell Beary about a time when you felt completely overwhelmed. Try to use at least one idiom.",
         hint='Try phrases like "bite off more than you can chew" or "in over my head"'),
    dict(topic="synonyms", difficulty=2,
         scenario="Describe a beautiful place you have visited. Try to use varied and descriptive vocabulary instead of simple words like 'nice' or 'good'.",
         hint="Replace simple words with richer alternatives: stunning, breathtaking, serene..."),
    dict(topic="phrasal_verbs", difficulty=2,
         scenario="Tell Beary about a problem you had to deal with recently. How did you handle it?",
         hint="Try phrasal verbs: deal with, figure out, give up, look into..."),
    dict(topic="present_simple", difficulty=1,
         scenario="Describe your daily morning routine to Beary. What do you usually do?",
         hint="Use present simple for habits: wake up, have breakfast, go to..."),
]


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        for p in PROMPTS:
            session.add(PracticePrompt(**p))
        await session.commit()
    print(f"Inserted {len(PROMPTS)} practice prompts.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
