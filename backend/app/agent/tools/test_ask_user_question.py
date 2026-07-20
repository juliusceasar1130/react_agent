import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from backend.app.agent.tools.ask_user_question import AskUserQuestion

def test_ask_user_question_in_graph():
    # 1. 定义一个简易节点，用来调用工具
    def call_tool_node(state):
        tool = AskUserQuestion()
        questions_payload = [
            {
                "question": "Which indexing option to use?",
                "header": "Performance Tuning",
                "multiSelect": False,
                "options": [
                    {"label": "B-Tree", "description": "Standard B-Tree Index"}
                ]
            }
        ]
        # 调用工具，此处触发 interrupt 并挂起
        res = tool.invoke({"questions": questions_payload})
        # 将工具返回值（恢复后的答案）存入状态
        return {"answers": res}

    # 2. 编译带有 Checkpointer 的 Graph
    builder = StateGraph(dict)
    builder.add_node("call_tool", call_tool_node)
    builder.add_edge(START, "call_tool")
    builder.add_edge("call_tool", END)
    
    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    
    # 3. 首次运行，应该被中断并挂起
    config = {"configurable": {"thread_id": "test-thread"}}
    graph.invoke({"answers": None}, config=config)
    
    # 检查状态是否成功挂起，并检查中断的值
    state = graph.get_state(config)
    assert len(state.tasks[0].interrupts) > 0
    
    interrupt_val = state.tasks[0].interrupts[0].value
    assert interrupt_val["type"] == "ask_user_question"
    assert interrupt_val["questions"][0].question == "Which indexing option to use?"
    
    # 4. 传入 Command(resume=...) 恢复运行
    user_answers = {"Which indexing option to use?": "B-Tree"}
    res = graph.invoke(Command(resume=user_answers), config=config)
    
    # 验证工具将 Command 传入的 answers 作为执行结果成功返回
    assert res["answers"] == user_answers


def test_ask_user_question_string_input():
    tool = AskUserQuestion()
    questions_string = '[{"question": "What is the db?", "options": [{"label": "PG"}]}]'
    validated = tool.args_schema.model_validate({"questions": questions_string})
    assert len(validated.questions) == 1
    assert validated.questions[0].question == "What is the db?"
    assert validated.questions[0].options[0].label == "PG"


def test_ask_user_question_optional_options():
    tool = AskUserQuestion()
    validated = tool.args_schema.model_validate({
        "questions": [{"question": "Please enter vehicle ID"}]
    })
    assert validated.questions[0].options is None

def test_ask_user_question_limit_boundaries():
    tool = AskUserQuestion()
    # 测试 0 个提问卡片拦截
    with pytest.raises(Exception):
        tool.args_schema.model_validate({"questions": []})

    # 测试 5 个提问卡片拦截
    oversized = [{"question": f"Q{i}"} for i in range(5)]
    with pytest.raises(Exception):
        tool.args_schema.model_validate({"questions": oversized})


def test_ask_user_question_parser_error_exposure():
    tool = AskUserQuestion()
    broken_json = '{broken json string'
    
    # 传入解析失败的字符串，应当抛出 ValidationError，且错误内容中包含解析失败自定义文本
    with pytest.raises(Exception) as excinfo:
        tool.args_schema.model_validate({"questions": broken_json})
    assert "澄清提问列表解析失败" in str(excinfo.value)
