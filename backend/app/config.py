from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/english_companion"
    secret_key: str = "change-me-to-a-random-32-char-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cloud_ai_provider: str = "qwen"
    claude_api_key: str = ""
    openai_api_key: str = ""
    qwen_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    class Config:
        env_file = ".env"


settings = Settings()
