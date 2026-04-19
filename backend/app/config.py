import os
import tempfile
from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

# 防止本地/VPN 系统代理（如 Clash/V2Ray）拦截 localhost 请求导致 502 Bad Gateway 错误
if "NO_PROXY" not in os.environ:
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,172.22.44.99,192.22.44.99"
elif "localhost" not in os.environ["NO_PROXY"]:
    os.environ["NO_PROXY"] += ",localhost,127.0.0.1"


def _parse_debug_flag(raw_value: str | None) -> bool:
    """兼容多种环境标记写法的 DEBUG 解析。"""
    normalized = (raw_value or "true").strip().lower()
    if normalized in {"1", "true", "yes", "on", "debug", "dev"}:
        return True
    if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
        return False
    return True


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
    analytics_database_url: str = os.getenv(
        "ANALYTICS_DATABASE_URL",
        "",
    )
    analytics_db_search_path: str = os.getenv(
        "ANALYTICS_DB_SEARCH_PATH",
        "mart,fct,dim,ods,meta,public",
    )

    # MySQL 生产数据库配置（SQL Agent 使用）
    mysql_database_url: str = os.getenv(
        "MYSQL_DATABASE_URL",
        "mysql+pymysql://root:root@localhost:3306/mds?charset=utf8mb4",
    )
    # SQL Agent 软限制：用于 System Prompt 引导 LLM 生成 SQL 时自带 LIMIT 子句的数量，默认为 2000
    sql_agent_top_k: int = int(os.getenv("SQL_AGENT_TOP_K", "1000"))

    # SQL 结果硬限制：代码层面对查询结果集的强制截断上限，防止大量数据加载到 LLM 上下文中造成溢出或性能崩溃
    sql_result_hard_limit: int = int(os.getenv("SQL_RESULT_HARD_LIMIT", "500"))
    
    # SQL 结果预览行数：当查询结果触发硬限制被截断时，实际回吐给 LLM 观察的前 N 条数据行数
    sql_result_preview_rows: int = int(os.getenv("SQL_RESULT_PREVIEW_ROWS", "5"))

    # SQL 导出文件配置：前端下载能力使用的临时导出目录与过期时间
    sql_export_dir: str = os.getenv(
        "SQL_EXPORT_DIR",
        str(Path(tempfile.gettempdir()) / "sql_agent_exports"),
    )
    sql_export_ttl_hours: int = int(os.getenv("SQL_EXPORT_TTL_HOURS", "24"))
    chart_artifact_dir: str = os.getenv(
        "CHART_ARTIFACT_DIR",
        str(Path(tempfile.gettempdir()) / "sql_agent_charts"),
    )
    chart_artifact_ttl_hours: int = int(
        os.getenv("CHART_ARTIFACT_TTL_HOURS", "24")
    )
    chart_artifact_max_points: int = int(
        os.getenv("CHART_ARTIFACT_MAX_POINTS", "100")
    )

    # 服务器配置
    debug: bool = _parse_debug_flag(os.getenv("DEBUG", "true"))

    # Agent配置
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    agent_max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "120"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    
    # RAG 配置
    rag_backend: str = os.getenv("RAG_BACKEND", "milvus_hybrid")  # pgvector | milvus_hybrid
    rag_similarity_threshold: Optional[float] = (
        float(os.getenv("RAG_SIMILARITY_THRESHOLD"))
        if os.getenv("RAG_SIMILARITY_THRESHOLD")
        else None
    )

    # Milvus 混合检索配置（RAG_BACKEND=milvus_hybrid 时生效）
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    milvus_collection_name: str = os.getenv("MILVUS_COLLECTION_NAME", "rag_store")
    milvus_embed_dim: int = int(os.getenv("MILVUS_EMBED_DIM", "1024"))
    milvus_rrf_k: int = int(os.getenv("MILVUS_RRF_K", "60"))
    milvus_chunk_size: int = int(os.getenv("MILVUS_CHUNK_SIZE", "512"))
    milvus_chunk_overlap: int = int(os.getenv("MILVUS_CHUNK_OVERLAP", "50"))
    # Milvus 初始化配置（数据导入使用）
    _default_data_dir = str(Path(__file__).resolve().parent / "agent" / "vector" / "milvus_init" / "data" / "examples")
    milvus_data_dir: str = os.getenv("MILVUS_DATA_DIR", _default_data_dir)
    milvus_overwrite: bool = os.getenv("MILVUS_OVERWRITE", "true").lower() == "true"

    # Embedding Provider 配置（Milvus 混合检索共用）
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    llama_cpp_embed_base_url: str = os.getenv(
        "LLAMA_CPP_EMBED_BASE_URL", "http://127.0.0.1:8081"
    )
    llama_cpp_embed_model: str = os.getenv(
        "LLAMA_CPP_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0"
    )
    llama_cpp_embed_timeout: float = float(
        os.getenv("LLAMA_CPP_EMBED_TIMEOUT", "30")
    )
    qwen_query_instruction_enabled: bool = (
        os.getenv("QWEN_QUERY_INSTRUCTION_ENABLED", "true").lower() == "true"
    )
    qwen_query_instruction: str = os.getenv(
        "QWEN_QUERY_INSTRUCTION",
        "Given a web search query, retrieve relevant passages that answer the query",
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
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:30b")
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    ollama_keep_alive: int = int(os.getenv("OLLAMA_KEEP_ALIVE", "-1"))
    
    # Ollama Embedding 配置 (用于本地化 RAG 嵌入)
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")

    # Graph & LangSmith 配置
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")

    # NVIDIA AI 配置（用于向量库 Embeddings）
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @field_validator("debug", mode="before")
    @classmethod
    def _normalize_debug(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return _parse_debug_flag(str(value))


settings = Settings()

if __name__ == "__main__":
    print("Settings loaded successfully!")
    print(f"Database URL: {settings.database_url}")
    print(f"LangSmith Tracing: {settings.langsmith_tracing}")
