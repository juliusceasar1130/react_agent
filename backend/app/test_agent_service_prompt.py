import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.app.agent.service import SQLAgentService, _build_system_prompt


def test_system_prompt_requires_explicit_chart_guidance() -> None:
    prompt = _build_system_prompt(SimpleNamespace(dialect="sqlite"))

    assert "当结果属于时间趋势、分类对比、Top N 排名或双指标对比时" in prompt
    assert "必须明确提醒用户这组结果可以生成图表" in prompt
    assert "你可以直接回复“生成图表”、“生成趋势图”或“生成柱状图”" in prompt
    assert "不要只用“是否需要进一步分析”" in prompt


def test_system_prompt_requires_category_split_for_multi_series_chart() -> None:
    prompt = _build_system_prompt(SimpleNamespace(dialect="sqlite"))

    assert "build_chart_artifact 的 series 只允许这些键" in prompt
    assert "不要使用 metric、label、type、axis 等自定义键" in prompt
    assert "如果图表要对比多个车型、缺陷类型或其他分类" in prompt
    assert "不要只重复引用同一个 field 作为多条系列" in prompt
    assert "必须为每条系列补充 category_field/category_value" in prompt
    assert "或至少在系列名称里包含可识别的分类值" in prompt


def test_context_warning_middleware_is_appended_when_enabled(monkeypatch) -> None:
    service = SQLAgentService(
        use_ollama=False,
        managed_runtime=False,
        auto_initialize=False,
    )
    monkeypatch.setattr("backend.app.agent.service._configure_proxy_settings", lambda: None)
    monkeypatch.setattr("backend.app.agent.service._create_llm", lambda _use_ollama: object())
    monkeypatch.setattr(
        "backend.app.agent.service._create_database_connection",
        lambda: (SimpleNamespace(dialect="sqlite"), {}),
    )
    monkeypatch.setattr("backend.app.agent.service._prepare_tools", lambda db, llm, retriever=None: [])
    monkeypatch.setattr("backend.app.agent.service._build_system_prompt", lambda db: "prompt")
    monkeypatch.setattr(
        "backend.app.agent.service.create_business_retriever_and_reranker",
        lambda: (None, None),
    )
    monkeypatch.setattr(
        "backend.app.agent.service.SummarizationMiddleware",
        lambda **kwargs: SimpleNamespace(__class__=SimpleNamespace(__name__="SummarizationMiddleware")),
    )
    monkeypatch.setattr("backend.app.agent.service.settings.llm_context_warning_enabled", True)
    mock_create_agent = MagicMock()
    monkeypatch.setattr("backend.app.agent.service.create_agent", mock_create_agent)
    monkeypatch.setattr(service, "_ainitialize_persistence", AsyncMock(return_value=None))

    asyncio.run(service._ainitialize_agent())

    middleware = mock_create_agent.call_args.kwargs["middleware"]
    assert middleware[-1].__class__.__name__ == "ContextWarningMiddleware"
