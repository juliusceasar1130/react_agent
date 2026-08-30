"""工具错误处理契约（N6）与 tokenizer 失败熔断（N5）回归测试。

对应修复：
- N6: 六把工具补 handle_tool_error=True；错误文案统一 "Error: " 前缀
- N5: Vllm/LlamaCpp TokenEstimator 首次 HTTP 失败后熔断，不再重复请求
"""

import httpx


class _FailingClient:
    """伪造 httpx 客户端：每次 post 都抛 404，并计数。"""

    def __init__(self):
        self.post_count = 0

    def post(self, *args, **kwargs):
        self.post_count += 1
        raise httpx.HTTPStatusError(
            "404 Not Found",
            request=httpx.Request("POST", "http://127.0.0.1:1/tokenize"),
            response=httpx.Response(404),
        )

    def close(self):
        pass


def _fallback_count(text: str) -> int:
    return max(1, len(text) // 2)


def test_vllm_estimator_breaker_on_http_failure():
    from backend.app.agent.utils.vllm_token_estimator import VllmTokenEstimator

    est = VllmTokenEstimator(base_url="http://127.0.0.1:1", model_name="m", timeout=1.0)
    fake = _FailingClient()
    est._client = fake

    first = est.count_text_tokens("hello world")   # 触发一次 HTTP 失败并熔断
    second = est.count_text_tokens("hello world")  # 直接兜底，不再发 HTTP
    third = est.count_messages_tokens([{"role": "user", "content": "hi"}])

    assert first == _fallback_count("hello world")
    assert second == first
    assert third > 0
    assert fake.post_count == 1, "熔断后不应再发出 tokenize 请求"


def test_llama_cpp_estimator_breaker_on_http_failure():
    from backend.app.agent.utils.llama_cpp_token_estimator import (
        LlamaCppTokenEstimator,
        _estimate_fallback_tokens,
    )

    est = LlamaCppTokenEstimator(base_url="http://127.0.0.1:1", timeout=1.0)
    fake = _FailingClient()
    est._client = fake

    first = est.count_text_tokens("hello world")
    second = est.count_text_tokens("hello world")

    assert first == second == _estimate_fallback_tokens("hello world")
    assert fake.post_count == 1, "熔断后不应再发出 tokenize 请求"


class _RaisingLexiconRetriever:
    """伪造物理词典检索器：index 全部为空，*retriever.retrieve 抛异常。"""

    value_index = None
    row_index = None
    schema_index = None

    class _Raiser:
        @staticmethod
        def retrieve(query, **kwargs):
            raise RuntimeError("retriever boom")

    value_retriever = _Raiser
    row_retriever = _Raiser
    schema_retriever = _Raiser


def test_lexicon_tools_error_prefix_and_handle_flag():
    from backend.app.agent.subagents.sql.tools import (
        create_db_row_lexicon_tool,
        create_db_table_schema_tool,
        create_db_value_lexicon_tool,
    )

    retriever = _RaisingLexiconRetriever()
    for factory in (
        create_db_value_lexicon_tool,
        create_db_row_lexicon_tool,
        create_db_table_schema_tool,
    ):
        tool = factory(retriever)
        assert tool.handle_tool_error is True, f"{factory.__name__} 缺少 handle_tool_error=True"
        out = str(tool.invoke({"query": "测试查询"}))
        assert out.startswith("Error: "), f"{factory.__name__} 错误文案缺少 Error: 前缀: {out!r}"


def test_skill_tools_handle_flag():
    from backend.app.agent.tools.skill_tools import load_scenario, load_skill

    assert load_skill.handle_tool_error is True
    assert load_scenario.handle_tool_error is True
