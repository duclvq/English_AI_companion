from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, onboarding, questions, progress

app = FastAPI(title="English AI Companion")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
app.include_router(questions.router, prefix="/questions", tags=["questions"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])


@app.get("/health")
async def health():
    return {"status": "ok"}
