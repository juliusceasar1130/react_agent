import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from backend.app.agent.llm import ReasoningAwareChatDeepSeek, QwenChatDeepSeek, _create_llm

def test_create_llm_instantiates_chat_deepseek(monkeypatch):
    """验证 _create_llm 在使用默认/DeepSeek模式时可正确实例化 ReasoningAwareChatDeepSeek"""
    with patch("backend.app.agent.llm.ReasoningAwareChatDeepSeek") as mock_chat_deepseek:
        mock_instance = MagicMock()
        mock_chat_deepseek.return_value = mock_instance
        
        llm = _create_llm(use_ollama=False)
        
        assert llm == mock_instance
        mock_chat_deepseek.assert_called_once()
        call_kwargs = mock_chat_deepseek.call_args.kwargs
        assert "api_key" in call_kwargs
        assert "api_base" in call_kwargs
        assert "openai_api_key" not in call_kwargs
        assert "openai_api_base" not in call_kwargs

def test_chat_deepseek_reasoning_content_mapping():
    """验证 ReasoningAwareChatDeepSeek 反序列化时保留 reasoning_content"""
    from pydantic import BaseModel

    class MockMessage(BaseModel):
        role: str = "assistant"
        content: str = "744 台正常车"
        reasoning_content: str = "正在分析车间各区域车辆分布..."

    class MockChoice(BaseModel):
        index: int = 0
        message: MockMessage
        finish_reason: str = "stop"

    class MockChatCompletion(BaseModel):
        id: str = "chatcmpl-test"
        object: str = "chat.completion"
        created: int = 123456789
        model: str = "gpt-5-nano"
        choices: list[MockChoice]

    llm = ReasoningAwareChatDeepSeek(
        model="gpt-5-nano",
        api_base="http://localhost:8089/v1",
        api_key="EMPTY",
    )
    
    mock_response = MockChatCompletion(choices=[MockChoice(message=MockMessage())])
    
    result = llm._create_chat_result(mock_response)
    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.content == "744 台正常车"
    assert message.additional_kwargs.get("reasoning_content") == "正在分析车间各区域车辆分布..."

def test_chat_deepseek_model_extra_reasoning_fallback():
    """验证 ReasoningAwareChatDeepSeek 从 model_extra 中提取 reasoning 后备字段"""
    from pydantic import BaseModel, ConfigDict

    class MockExtraMessage(BaseModel):
        model_config = ConfigDict(extra="allow")
        role: str = "assistant"
        content: str = "测试数据"

    class MockChoice(BaseModel):
        index: int = 0
        message: MockExtraMessage
        finish_reason: str = "stop"

    class MockChatCompletion(BaseModel):
        id: str = "chatcmpl-test"
        object: str = "chat.completion"
        created: int = 123456789
        model: str = "gpt-5-nano"
        choices: list[MockChoice]

    llm = ReasoningAwareChatDeepSeek(
        model="gpt-5-nano",
        api_base="http://localhost:8089/v1",
        api_key="EMPTY",
    )
    
    mock_msg = MockExtraMessage(reasoning_content="从 model_extra 提取的思考过程")
    mock_response = MockChatCompletion(choices=[MockChoice(message=mock_msg)])
    result = llm._create_chat_result(mock_response)
    message = result.generations[0].message
    assert message.additional_kwargs.get("reasoning_content") == "从 model_extra 提取的思考过程"




def test_qwen_chat_deepseek_stream_chunk_mapping():
    """验证 QwenChatDeepSeek 在流式 _convert_chunk_to_generation_chunk 时拦截 reasoning 字段"""
    from backend.app.agent.llm import QwenChatDeepSeek

    llm = QwenChatDeepSeek(
        model="gpt-5-nano",
        api_base="http://localhost:8089/v1",
        api_key="EMPTY",
    )

    mock_chunk = {
        "id": "chatcmpl-stream-1",
        "object": "chat.completion.chunk",
        "created": 123456789,
        "model": "gpt-5-nano",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": "",
                    "reasoning": "正在思考...",
                },
                "finish_reason": None,
            }
        ],
    }

    gen_chunk = llm._convert_chunk_to_generation_chunk(mock_chunk, None, None)

    assert gen_chunk is not None
    assert gen_chunk.message.additional_kwargs.get("reasoning_content") == "正在思考..."
