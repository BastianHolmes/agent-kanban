from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 8000
    kimi_api_key: str = ""
    kimi_api_url: str = "https://api.moonshot.ai/v1/chat/completions"
    kimi_model: str = "kimi-k2.5"
    kimi_router_model: str = "kimi-k2-thinking-turbo"
    go_api_url: str = "http://api:8080"
    qdrant_url: str = "http://qdrant:6333"
    database_url: str = "/data/agent.db"
    embedding_model: str = "intfloat/multilingual-e5-large"
    max_message_length: int = 2000
    max_tool_calls: int = 5
    tool_timeout: int = 30
    code_reindex_interval_minutes: int = 15

    class Config:
        env_prefix = ""


settings = Settings()
