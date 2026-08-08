import os
import tempfile
from pathlib import Path
from typing import Optional
from pydantic import field_validator, Field
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

    # PostgreSQL 业务分析数据库配置（用于 SQL Agent 检索）
    analytics_database_url: str = os.getenv(
        "ANALYTICS_DATABASE_URL",
        "postgresql://root:root@localhost:5432/analytics_db",
    )
    analytics_db_search_path: str = os.getenv(
        "ANALYTICS_DB_SEARCH_PATH",
        "mart,fct,dim,ods,meta,public",
    )

    # SQL Agent 软限制：用于 System Prompt 引导 LLM 生成 SQL 时自带 LIMIT 子句的数量，默认为 2000
    sql_agent_top_k: int = int(os.getenv("SQL_AGENT_TOP_K", "1000"))

    # 系统提示词模板文件路径
    system_prompt_path: str = os.getenv(
        "SYSTEM_PROMPT_PATH",
        str(Path(__file__).resolve().parent / "agent" / "prompts" / "base_system_prompt.md"),
    )

    # SQL Checker 模式：fast(仅本地Linter) | safety(同步checker=当前默认)
    sql_checker_mode: str = os.getenv("SQL_CHECKER_MODE", "fast")

    # SQL 结果硬限制：代码层面对查询结果集的强制截断上限，防止大量数据加载到 LLM 上下文中造成溢出或性能崩溃
    sql_result_hard_limit: int = int(os.getenv("SQL_RESULT_HARD_LIMIT", "30"))

    # SQL 结果预览行数：当查询结果触发硬限制被截断时，实际回吐给 LLM 观察的前 N 条数据行数
    sql_result_preview_rows: int = int(os.getenv("SQL_RESULT_PREVIEW_ROWS", "5"))

    # 纯维度表查询时的宽松截断上限
    dimension_result_hard_limit: int = int(
        os.getenv("DIMENSION_RESULT_HARD_LIMIT", "300")
    )

    # 维度表/字典表白名单列表（原始逗号分隔字符串）
    dimension_tables_raw: str = os.getenv("DIMENSION_TABLES", "")

    @property
    def dimension_tables(self) -> set[str]:
        if not self.dimension_tables_raw:
            return set()
        return {
            t.strip().lower() for t in self.dimension_tables_raw.split(",") if t.strip()
        }

    # === SQL Linter 配置 ===
    sql_linter_enabled: bool = False
    sql_linter_max_subquery_depth: int = 3
    sql_linter_max_cte_count: int = 3
    sql_linter_allowed_schemas_raw: str = Field(
        default="mart,fct,dim,ods,meta,public",
        validation_alias="sql_linter_allowed_schemas"
    )
    sql_linter_rules_severity_raw: str = Field(
        default="",
        validation_alias="sql_linter_rules_severity_override"
    )
    sql_linter_disabled_rules_raw: str = Field(
        default="",
        validation_alias="sql_linter_disabled_rules"
    )

    @property
    def sql_linter_allowed_schemas(self) -> list[str]:
        return [s.strip().lower() for s in self.sql_linter_allowed_schemas_raw.split(",") if s.strip()]

    @property
    def sql_linter_rules_severity_override(self) -> dict[str, str]:
        result = {}
        if not self.sql_linter_rules_severity_raw:
            return result
        for pair in self.sql_linter_rules_severity_raw.split(","):
            if ":" in pair:
                rule_id, severity = pair.split(":", 1)
                result[rule_id.strip().upper()] = severity.strip().upper()
        return result

    @property
    def sql_linter_disabled_rules(self) -> set[str]:
        if not self.sql_linter_disabled_rules_raw:
            return set()
        return {
            r.strip().upper() for r in self.sql_linter_disabled_rules_raw.split(",") if r.strip()
        }


    # SQL 导出文件配置：前端下载能力使用的临时导出目录与过期时间
    sql_export_dir: str = os.getenv(
        "SQL_EXPORT_DIR",
        str(Path(tempfile.gettempdir()) / "sql_agent_exports"),
    )
    sql_export_ttl_hours: int = int(os.getenv("SQL_EXPORT_TTL_HOURS", "24"))
    sql_export_max_rows: int = int(os.getenv("SQL_EXPORT_MAX_ROWS", "100000"))
    lexicon_similarity_top_k: int = int(os.getenv("LEXICON_SIMILARITY_TOP_K", "5"))
    chart_artifact_dir: str = os.getenv(
        "CHART_ARTIFACT_DIR",
        str(Path(tempfile.gettempdir()) / "sql_agent_charts"),
    )
    chart_artifact_ttl_hours: int = int(os.getenv("CHART_ARTIFACT_TTL_HOURS", "24"))
    chart_artifact_max_points: int = int(os.getenv("CHART_ARTIFACT_MAX_POINTS", "100"))

    # 服务器配置
    debug: bool = _parse_debug_flag(os.getenv("DEBUG", "true"))

    # Agent配置
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    agent_max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "120"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # Agent调用限制配置：防止Agent无限调用工具无法跳出
    # ModelCallLimitMiddleware: 限制单次对话中模型调用总次数（含推理+工具响应后的再推理）
    agent_model_call_run_limit: int = int(os.getenv("AGENT_MODEL_CALL_RUN_LIMIT", "15"))
    # ToolCallLimitMiddleware: 限制单次对话中工具调用总次数
    agent_tool_call_run_limit: int = int(os.getenv("AGENT_TOOL_CALL_RUN_LIMIT", "10"))
    # 超限后行为: 'end' = 优雅结束并总结已知信息, 'error' = 抛出异常
    agent_call_limit_exit_behavior: str = os.getenv("AGENT_CALL_LIMIT_EXIT_BEHAVIOR", "end")
    llm_top_p: Optional[float] = (
        float(os.getenv("LLM_TOP_P")) if os.getenv("LLM_TOP_P") else None
    )
    llm_top_k: Optional[int] = (
        int(os.getenv("LLM_TOP_K")) if os.getenv("LLM_TOP_K") else None
    )
    llm_repetition_penalty: Optional[float] = (
        float(os.getenv("LLM_REPETITION_PENALTY"))
        if os.getenv("LLM_REPETITION_PENALTY")
        else None
    )
    llm_presence_penalty: Optional[float] = (
        float(os.getenv("LLM_PRESENCE_PENALTY"))
        if os.getenv("LLM_PRESENCE_PENALTY")
        else None
    )
    llm_min_p: Optional[float] = (
        float(os.getenv("LLM_MIN_P")) if os.getenv("LLM_MIN_P") else None
    )
    llm_enable_thinking: Optional[bool] = (
        os.getenv("LLM_ENABLE_THINKING", "").lower() == "true"
        if os.getenv("LLM_ENABLE_THINKING")
        else True
    )
    llm_context_warning_enabled: bool = (
        os.getenv("LLM_CONTEXT_WARNING_ENABLED", "false").lower() == "true"
    )
    llm_context_window: int = int(os.getenv("LLM_CONTEXT_WINDOW", "16384"))
    llm_context_warn_tokens: int = int(os.getenv("LLM_CONTEXT_WARN_TOKENS", "12000"))
    llm_context_summarize_trigger_tokens: int = int(
        os.getenv("LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS", "10000")
    )
    llm_context_collapse_protect_turns: int = int(
        os.getenv("LLM_CONTEXT_COLLAPSE_PROTECT_TURNS", "3")
    )
    llm_context_redaction_keep_count: int = int(
        os.getenv("LLM_CONTEXT_REDACTION_KEEP_COUNT", "3")
    )
    llm_context_safety_buffer: int = int(os.getenv("LLM_CONTEXT_SAFETY_BUFFER", "512"))
    token_estimator_engine: str = os.getenv("TOKEN_ESTIMATOR_ENGINE", "llama_cpp")
    vllm_tokenize_base_url: str = os.getenv("VLLM_TOKENIZE_BASE_URL", "")
    vllm_tokenize_model: str = os.getenv("VLLM_TOKENIZE_MODEL", "")
    llama_cpp_tokenize_base_url: str = os.getenv(
        "LLAMA_CPP_TOKENIZE_BASE_URL",
        "http://127.0.0.1:8089",
    )
    llm_context_tokenizer_timeout: float = float(
        os.getenv("LLM_CONTEXT_TOKENIZER_TIMEOUT", "5")
    )

    # RAG 配置
    rag_backend: str = os.getenv(
        "RAG_BACKEND", "milvus_hybrid"
    )  # pgvector | milvus_hybrid
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
    _default_data_dir = str(
        Path(__file__).resolve().parent
        / "agent"
        / "vector"
        / "milvus_init"
        / "data"
        / "examples"
    )
    milvus_data_dir: str = os.getenv("MILVUS_DATA_DIR", _default_data_dir)
    milvus_overwrite: bool = os.getenv("MILVUS_OVERWRITE", "true").lower() == "true"
    db_lexicon_sync_on_startup: bool = (
        os.getenv("DB_LEXICON_SYNC_ON_STARTUP", "true").lower() == "true"
    )
    lexicon_schema_top_k: int = int(os.getenv("LEXICON_SCHEMA_TOP_K", "5"))
    lexicon_value_top_k: int = int(os.getenv("LEXICON_VALUE_TOP_K", "5"))
    lexicon_row_top_k: int = int(os.getenv("LEXICON_ROW_TOP_K", "5"))

    # Embedding Provider 配置（Milvus 混合检索共用）
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    llama_cpp_embed_base_url: str = os.getenv(
        "LLAMA_CPP_EMBED_BASE_URL", "http://127.0.0.1:8081"
    )
    llama_cpp_embed_model: str = os.getenv(
        "LLAMA_CPP_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0"
    )
    llama_cpp_embed_timeout: float = float(os.getenv("LLAMA_CPP_EMBED_TIMEOUT", "30"))
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

    # Rule Extractor 配置
    rule_extractor_safety_enabled: bool = (
        os.getenv("RULE_EXTRACTOR_SAFETY_ENABLED", "true").lower() == "true"
    )
    rule_extractor_safety_blocked_keywords: str = os.getenv(
        "RULE_EXTRACTOR_SAFETY_BLOCKED_KEYWORDS", "DROP,DELETE,TRUNCATE,UPDATE,INSERT,GRANT"
    )
    rule_extractor_safety_warning_markers: str = os.getenv(
        "RULE_EXTRACTOR_SAFETY_WARNING_MARKERS", "SAFETY WARNING,BLOCKED BY SECURITY FILTER,PERMISSION DENIED"
    )
    rule_extractor_empty_result_enabled: bool = (
        os.getenv("RULE_EXTRACTOR_EMPTY_RESULT_ENABLED", "true").lower() == "true"
    )
    rule_extractor_single_sql_enabled: bool = (
        os.getenv("RULE_EXTRACTOR_SINGLE_SQL_ENABLED", "true").lower() == "true"
    )
    rule_extractor_backtrack_enabled: bool = (
        os.getenv("RULE_EXTRACTOR_BACKTRACK_ENABLED", "true").lower() == "true"
    )
    rule_extractor_backtrack_max_turns: int = int(os.getenv("RULE_EXTRACTOR_BACKTRACK_MAX_TURNS", "3"))
    rule_extractor_domain_enabled: bool = (
        os.getenv("RULE_EXTRACTOR_DOMAIN_ENABLED", "true").lower() == "true"
    )
    rule_extractor_max_sql_steps: int = int(os.getenv("RULE_EXTRACTOR_MAX_SQL_STEPS", "3"))

    @property
    def rule_extractor_blocked_keywords(self) -> list[str]:
        if not self.rule_extractor_safety_blocked_keywords:
            return []
        return [
            kw.strip().upper()
            for kw in self.rule_extractor_safety_blocked_keywords.split(",")
            if kw.strip()
        ]

    @property
    def rule_extractor_warning_markers(self) -> list[str]:
        if not self.rule_extractor_safety_warning_markers:
            return []
        return [
            marker.strip().upper()
            for marker in self.rule_extractor_safety_warning_markers.split(",")
            if marker.strip()
        ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
