import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # DeepSeek配置
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "")

    # 数据库配置
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://root:root@localhost:5432/agent_memory"
    )

    # PostgreSQL 数据库配置（用于 rollerbed tracking system）
    rollerbed_database_url: str = os.getenv(
        "ROLLERBED_DATABASE_URL",
        "postgresql://root:root@localhost:5432/rollerbed_tracking_db",
    )

    # MySQL 生产数据库配置（SQL Agent 使用）
    mysql_database_url: str = os.getenv(
        "MYSQL_DATABASE_URL",
        "mysql+pymysql://root:root@localhost:3306/mds?charset=utf8mb4",
    )
    sql_agent_top_k: int = int(os.getenv("SQL_AGENT_TOP_K", "10"))

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Agent配置
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    agent_max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
    
    # RAG配置
    rag_similarity_threshold: Optional[float] = (
        float(os.getenv("RAG_SIMILARITY_THRESHOLD"))
        if os.getenv("RAG_SIMILARITY_THRESHOLD")
        else None
    )

    # Rerank 配置
    rerank_enabled: bool = os.getenv("RERANK_ENABLED", "false").lower() == "true"
    rerank_model: str = os.getenv("RERANK_MODEL", "nvidia/rerank-qa-mistral-4b")
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "3"))
    rerank_score_threshold: Optional[float] = (
        float(os.getenv("RERANK_SCORE_THRESHOLD"))
        if os.getenv("RERANK_SCORE_THRESHOLD")
        else None
    )

    # Ollama 配置 (RTX 5090 优化)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://192.22.44.99:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:30b")
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    ollama_keep_alive: int = int(os.getenv("OLLAMA_KEEP_ALIVE", "-1"))

    # Graph & LangSmith 配置
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")

    # NVIDIA AI 配置（用于向量库 Embeddings）
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()

if __name__ == "__main__":
    print("Settings loaded successfully!")
    print(f"Database URL: {settings.database_url}")
    print(f"LangSmith Tracing: {settings.langsmith_tracing}")
