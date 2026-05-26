import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware

def test_safe_merge_no_rag_message_remains_untouched():
    """测试当消息列表中没有 RAG 系统消息时，中间件不做任何修改"""
    middleware = SafeMergeSystemMiddleware()
    
    original_system = SystemMessage(content="You are an agent.")
    messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    # 模拟中间件转换
    modified_request = middleware._modify_request(request)
    
    assert modified_request.system_message.content == "You are an agent."
    assert len(modified_request.messages) == 2
    assert isinstance(modified_request.messages[0], HumanMessage)

def test_safe_merge_with_rag_message_collapses_successfully():
    """测试当消息列表第一条包含 RAG 标识的 SystemMessage 时，两者被合并，且列表中该消息被剔除"""
    middleware = SafeMergeSystemMiddleware()
    
    original_system = SystemMessage(content="You are a SQL agent.")
    rag_content = "__business_rag_context__\n\n## 业务知识库\n- 术语 A: 含义 A"
    messages = [
        SystemMessage(content=rag_content),
        HumanMessage(content="Query昨天的数据")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    modified_request = middleware._modify_request(request)
    
    # 验证合并后的 system_message 内容包含两部分，默认使用 \n\n 拼接
    expected_content = "You are a SQL agent.\n\n__business_rag_context__\n\n## 业务知识库\n- 术语 A: 含义 A"
    assert modified_request.system_message.content == expected_content
    
    # 验证原 RAG 消息已经被从 messages 对话历史里剥离
    assert len(modified_request.messages) == 1
    assert isinstance(modified_request.messages[0], HumanMessage)
    assert modified_request.messages[0].content == "Query昨天的数据"

def test_safe_merge_with_rag_message_content_blocks():
    """测试 content_blocks 格式下的 RAG 标识识别与合并"""
    middleware = SafeMergeSystemMiddleware()
    
    original_system = SystemMessage(content="Base rules.")
    messages = [
        SystemMessage(content_blocks=[{"type": "text", "text": "Some other text __business_rag_context__ info"}]),
        HumanMessage(content="Query")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    modified_request = middleware._modify_request(request)
    
    # 健壮断言：支持列表格式
    content = modified_request.system_message.content
    found = False
    if isinstance(content, str):
        found = "__business_rag_context__" in content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str) and "__business_rag_context__" in item:
                found = True
                break
            elif isinstance(item, dict) and "__business_rag_context__" in item.get("text", ""):
                found = True
                break
                
    assert found
    assert len(modified_request.messages) == 1
    assert isinstance(modified_request.messages[0], HumanMessage)


def test_safe_merge_with_rag_message_in_middle_of_history():
    """测试当 RAG 消息被夹在历史对话的中间位置（非首位）时，依然能被全局扫描定位、安全合并并被彻底抽干剔除"""
    middleware = SafeMergeSystemMiddleware()
    
    original_system = SystemMessage(content="Base instruction.")
    messages = [
        HumanMessage(content="Hi"),
        AIMessage(content="Hello"),
        SystemMessage(content="__business_rag_context__\n\n## 业务知识库\n- 术语 B: 含义 B"),
        HumanMessage(content="Query")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    modified_request = middleware._modify_request(request)
    
    # 验证是否成功合并
    expected_content = "Base instruction.\n\n__business_rag_context__\n\n## 业务知识库\n- 术语 B: 含义 B"
    assert modified_request.system_message.content == expected_content
    
    # 验证是否在历史列表中彻底剔除 (由 4 条变成了 3 条)
    assert len(modified_request.messages) == 3
    assert isinstance(modified_request.messages[0], HumanMessage)
    assert isinstance(modified_request.messages[1], AIMessage)
    assert isinstance(modified_request.messages[2], HumanMessage)  # 原本夹在中间的 SystemMessage 被安全物理抽干！


def test_safe_merge_with_mixed_list_and_str_collapses_to_pure_str():
    """测试当核心提示词是 List[Dict] 块结构且 RAG 提示词是纯 Str 时，合并后能够完美自愈为纯文本 String"""
    middleware = SafeMergeSystemMiddleware()
    
    # 模拟 SkillMiddleware 注入后的 List[Dict] 块结构
    original_system = SystemMessage(
        content=[
            {"type": "text", "text": "Base instruction."},
            {"type": "text", "text": "\n\n## Available Skills\n- Skill 1\n- Skill 2"}
        ]
    )
    
    rag_content = "__business_rag_context__\n\n## 业务知识库\n- 知识 A"
    messages = [
        SystemMessage(content=rag_content),
        HumanMessage(content="Query")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    modified_request = middleware._modify_request(request)
    
    # 验证最终合并后的 system_message 必须是一个干净的字符串类型，以避免 vLLM 的 400 报错
    assert isinstance(modified_request.system_message.content, str)
    
    expected_content = (
        "Base instruction.\n"
        "\n\n## Available Skills\n- Skill 1\n- Skill 2"
        "\n\n"
        "__business_rag_context__\n\n## 业务知识库\n- 知识 A"
    )
    assert modified_request.system_message.content == expected_content
    
    # 验证 RAG 消息已经被抽干
    assert len(modified_request.messages) == 1
    assert isinstance(modified_request.messages[0], HumanMessage)


def test_safe_merge_with_multiple_rag_messages_in_history():
    """测试多轮对话下（第二轮及后续），当历史消息队列中存在多条 RAG 系统消息时，能够全量一次性打捞合并，并全部从列表中抽干物理抹除"""
    middleware = SafeMergeSystemMiddleware()
    
    original_system = SystemMessage(content="Base rules.")
    messages = [
        HumanMessage(content="Hi"),
        SystemMessage(content="__business_rag_context__\n- First RAG info"),
        AIMessage(content="Hello"),
        SystemMessage(content="__business_rag_context__\n- Second RAG info"),
        HumanMessage(content="Query")
    ]
    
    request = ModelRequest(
        model=object(),
        system_message=original_system,
        messages=messages
    )
    
    modified_request = middleware._modify_request(request)
    
    # 1. 验证合并后的 system_message 包含基础提示词 + 两条 RAG 消息的内容，采用 \n\n 分割
    expected_content = (
        "Base rules.\n\n"
        "__business_rag_context__\n- First RAG info\n\n"
        "__business_rag_context__\n- Second RAG info"
    )
    assert modified_request.system_message.content == expected_content
    
    # 2. 验证消息队列历史（由 5 条变成了 3 条），原本夹在不同位置的 2 个 SystemMessage 被干净地物理抹除抽干！
    assert len(modified_request.messages) == 3
    assert isinstance(modified_request.messages[0], HumanMessage)
    assert isinstance(modified_request.messages[1], AIMessage)
    assert isinstance(modified_request.messages[2], HumanMessage)


