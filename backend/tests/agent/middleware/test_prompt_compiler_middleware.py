# backend/tests/agent/middleware/test_prompt_compiler_middleware.py
"""
单元测试：PromptCompilerMiddleware 采样参数注入（子智能体路径对称测试）。

测试缝隙 (Seam): PromptCompilerMiddleware._inject_thinking_config(request)
- 验证子智能体路径同样正确注入 thinking/fast profile 采样参数。
- 与 RagPromptInjectorMiddleware 测试对称，确保双中间件行为一致。
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
from backend.app.agent.state import SqlSubAgentState
from langchain.agents.middleware import ModelRequest


@pytest.fixture(autouse=True)
def _clear_lru_cache():
    """每个测试前后清理 profile_loader 缓存，避免测试间污染。"""
    from backend.app.agent.config.profile_loader import _load_profiles

    _load_profiles.cache_clear()
    yield
    _load_profiles.cache_clear()


@pytest.fixture(autouse=True)
def _default_effort_transport(monkeypatch):
    """统一默认 transport=top_level，避免开发机环境变量干扰存量用例。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "top_level")


def test_prompt_compiler_injects_thinking_profile():
    """测试 1: enable_thinking=True 时注入 thinking profile"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": True}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        # top_level 参数
        assert request.model_settings["temperature"] == 1.0
        assert request.model_settings["top_p"] == 0.95
        # extra_body 参数
        assert request.model_settings["extra_body"]["top_k"] == 20
        # reasoning_effort 参数（extra_body 顶层，LangChain 合并进请求体顶层）
        assert request.model_settings["extra_body"]["reasoning_effort"] == "medium"
        # chat_template_kwargs 参数
        assert request.model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
    finally:
        var_child_runnable_config.reset(token)


def test_prompt_compiler_injects_fast_profile():
    """测试 2: enable_thinking=False 时注入 fast profile"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": False}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        # fast profile 参数
        assert request.model_settings["temperature"] == 0.7
        assert request.model_settings["top_p"] == 0.8
        assert request.model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    finally:
        var_child_runnable_config.reset(token)


def test_prompt_compiler_enable_thinking_none_no_override():
    """测试 3: enable_thinking=None 时不覆写 model_settings"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    # 初始 model_settings 已有值
    request.model_settings = {
        "temperature": 0.5,
        "extra_body": {"custom_key": "custom_value"},
    }

    config: RunnableConfig = {"configurable": {"enable_thinking": None}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings["temperature"] == 0.5
        assert request.model_settings["extra_body"]["custom_key"] == "custom_value"
    finally:
        var_child_runnable_config.reset(token)


# -----------------------------------------------------------------------------
# Phase 3: thinking_level 覆写
# -----------------------------------------------------------------------------

def test_prompt_compiler_thinking_level_high_overrides_effort():
    """测试 4: thinking_level=high 时覆写 reasoning_effort=xhigh"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": True, "thinking_level": "high"}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        assert request.model_settings["extra_body"]["reasoning_effort"] == "xhigh"
    finally:
        var_child_runnable_config.reset(token)


def test_prompt_compiler_thinking_level_none_defaults_medium():
    """测试 5: thinking_level=None 时 reasoning_effort=medium（Phase 2 兼容）"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": True, "thinking_level": None}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        assert request.model_settings["extra_body"]["reasoning_effort"] == "medium"
    finally:
        var_child_runnable_config.reset(token)


def test_prompt_compiler_fast_with_thinking_level_ignores_level():
    """测试 6: fast + thinking_level=high 时不注入 reasoning_effort"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": False, "thinking_level": "high"}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        assert "reasoning_effort" not in request.model_settings.get("extra_body", {})
    finally:
        var_child_runnable_config.reset(token)


def test_prompt_compiler_thinking_level_high_transport_ctk(monkeypatch):
    """测试 7: transport=chat_template_kwargs + thinking_level=high → reasoning_effort 落在 ctk 段"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "chat_template_kwargs")

    middleware = PromptCompilerMiddleware()
    state = SqlSubAgentState()
    initial_sys_msg = SystemMessage(content="你是一个 SQL 专家。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询在制车")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": True, "thinking_level": "high"}}
    token = var_child_runnable_config.set(config)

    try:
        middleware._inject_thinking_config(request)
        assert request.model_settings is not None
        assert request.model_settings["extra_body"]["chat_template_kwargs"]["reasoning_effort"] == "xhigh"
        assert "reasoning_effort" not in request.model_settings["extra_body"]
    finally:
        var_child_runnable_config.reset(token)
