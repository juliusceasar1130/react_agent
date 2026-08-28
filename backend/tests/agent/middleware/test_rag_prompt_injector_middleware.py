# backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py
"""
单元测试：RagPromptInjectorMiddleware 提示词注入中间件。

测试缝隙 (Seam): RagPromptInjectorMiddleware._modify_request(request)
- 验证当 state 中包含 lexicon_context 时，RAG 格式化文本是否被正确编译注入到 ModelRequest.system_message 的 <runtime_context> 动态区。
- 验证当 state 为空或缺少 lexicon_context 时，ModelRequest.system_message 保持不变 (Safe No-Op)。
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.agent.middleware.rag_prompt_injector_middleware import RagPromptInjectorMiddleware
from backend.app.agent.state import CustomState
from langchain.agents.middleware import ModelRequest


def test_rag_prompt_injector_injects_rag_text_into_system_message():
    """测试 1: 当 state 包含 lexicon_context 时，应将 formatted_text 编译注入到 system_message"""
    middleware = RagPromptInjectorMiddleware()
    
    # 构建包含 lexicon_context 的 Mock State
    state = CustomState(
        lexicon_context={
            "formatted_text": "## 1. 业务术语参考\n\n#### 底漆车间\n在制车数量为 42 辆"
        }
    )
    
    initial_sys_msg = SystemMessage(content="你是一个通用助手。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="查询底漆车间")],
        state=state,
        model=MagicMock(),
    )
    
    modified_request = middleware._modify_request(request)
    
    # 验证 SystemMessage 包含了 <runtime_context> 和 RAG 文本
    sys_content = modified_request.system_message.content
    assert isinstance(sys_content, str)
    assert "<runtime_context>" in sys_content
    assert "底漆车间" in sys_content
    assert "在制车数量为 42 辆" in sys_content


def test_rag_prompt_injector_noop_when_no_lexicon_context():
    """测试 2: 当 state 缺少 lexicon_context 时，应保持原 system_message 不变 (No-Op)"""
    middleware = RagPromptInjectorMiddleware()
    
    state = CustomState()
    initial_sys_msg = SystemMessage(content="你是一个通用助手。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="你好")],
        state=state,
        model=MagicMock(),
    )
    
    modified_request = middleware._modify_request(request)
    
    # 验证 SystemMessage 保持原样
    assert modified_request.system_message.content == "你是一个通用助手。"


def test_rag_prompt_injector_thinking_config():
    """测试 3: 验证 RagPromptInjectorMiddleware 正确注入 thinking profile"""
    from langchain_core.runnables import RunnableConfig

    middleware = RagPromptInjectorMiddleware()
    state = CustomState()
    initial_sys_msg = SystemMessage(content="你是一个通用助手。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="你好")],
        state=state,
        model=MagicMock(),
    )

    # 模拟 RunnableConfig 上下文
    from langchain_core.runnables.config import var_child_runnable_config
    config: RunnableConfig = {"configurable": {"enable_thinking": True}}
    token = var_child_runnable_config.set(config)

    try:
        modified_request = middleware._modify_request(request)
        assert modified_request.model_settings is not None
        # top_level 参数注入
        assert modified_request.model_settings["temperature"] == 1.0
        assert modified_request.model_settings["top_p"] == 0.95
        # extra_body 参数注入
        assert modified_request.model_settings["extra_body"]["top_k"] == 20
        # chat_template_kwargs 参数注入（含 reasoning_effort，Qwen3 模板变量）
        assert modified_request.model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
        assert modified_request.model_settings["extra_body"]["chat_template_kwargs"]["reasoning_effort"] == "medium"
    finally:
        var_child_runnable_config.reset(token)


def test_rag_prompt_injector_thinking_false_injects_fast_profile():
    """测试 4: enable_thinking=False 时注入 fast profile 参数"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = RagPromptInjectorMiddleware()
    state = CustomState()
    initial_sys_msg = SystemMessage(content="你是一个通用助手。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="你好")],
        state=state,
        model=MagicMock(),
    )

    config: RunnableConfig = {"configurable": {"enable_thinking": False}}
    token = var_child_runnable_config.set(config)

    try:
        modified_request = middleware._modify_request(request)
        assert modified_request.model_settings is not None
        # fast profile 的 top_level 参数
        assert modified_request.model_settings["temperature"] == 0.7
        assert modified_request.model_settings["top_p"] == 0.8
        # fast profile 的 extra_body 参数
        assert modified_request.model_settings["extra_body"]["top_k"] == 20
        # chat_template_kwargs 参数（含 reasoning_effort）
        assert modified_request.model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    finally:
        var_child_runnable_config.reset(token)


def test_rag_prompt_injector_enable_thinking_none_no_override():
    """测试 5: enable_thinking=None 时中间件不覆写 model_settings"""
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config

    middleware = RagPromptInjectorMiddleware()
    state = CustomState()
    initial_sys_msg = SystemMessage(content="你是一个通用助手。")
    request = ModelRequest(
        system_message=initial_sys_msg,
        messages=[HumanMessage(content="你好")],
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
        modified_request = middleware._modify_request(request)
        # None 时不应覆写任何值
        assert modified_request.model_settings["temperature"] == 0.5
        assert modified_request.model_settings["extra_body"]["custom_key"] == "custom_value"
    finally:
        var_child_runnable_config.reset(token)
