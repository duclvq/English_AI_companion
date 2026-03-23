"""Check correct_index distribution and shuffle choices if all are index 0."""
import asyncio
import random
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.question import Question


async def main():
    async with AsyncSessionLocal() as db:
        # Check distribution
        r = await db.execute(
            select(Question.correct_index, func.count())
            .group_by(Question.correct_index)
        )
        print("Current distribution:")
        for idx, cnt in r.all():
            print(f"  correct_index={idx}: {cnt} questions")

        # Shuffle all questions
        r = await db.execute(select(Question))
        questions = r.scalars().all()
        shuffled = 0
        for q in questions:
            choices = list(q.choices)
            correct_answer = choices[q.correct_index]
            random.shuffle(choices)
            new_index = choices.index(correct_answer)
            q.choices = choices
            q.correct_index = new_index
            shuffled += 1

        await db.commit()
        print(f"\nShuffled {shuffled} questions.")

        # Verify
        r = await db.execute(
            select(Question.correct_index, func.count())
            .group_by(Question.correct_index)
        )
        print("\nNew distribution:")
        for idx, cnt in r.all():
            print(f"  correct_index={idx}: {cnt} questions")


asyncio.run(main())
