import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # DeepSeek配置
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "")

    # 数据库配置
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./research_agent.db")

    # MySQL 生产数据库配置（SQL Agent 使用）
    mysql_database_url: str = os.getenv("MYSQL_DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/mds?charset=utf8mb4")
    sql_agent_top_k: int = int(os.getenv("SQL_AGENT_TOP_K", "10"))

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Agent配置
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    agent_max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "2000"))

    # Ollama 配置 (RTX 5090 优化)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:30b")
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "-1")


    class Config:
        env_file = ".env"


settings = Settings()
