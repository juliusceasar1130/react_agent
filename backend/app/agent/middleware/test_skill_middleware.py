import pytest
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest

from backend.app.agent.middleware.skill_middleware import SkillMiddleware
from backend.app.agent.state import CustomState

class DummyDB:
    def __init__(self):
        self._custom_table_info = {
            "fct_vehicle_position_current": "CREATE TABLE fct_vehicle_position_current (\n  vehicle_id VARCHAR\n);"
        }

def test_skill_middleware_injects_active_ddl():
    # 模拟已激活领域技能的状态
    state = CustomState(
        messages=[],
        skills_loaded=["paint_shop_vehicle_logistics"],
        active_skill="paint_shop_vehicle_logistics"
    )
    
    request = ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = SkillMiddleware(DummyDB())
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    assert "Available Skills" in content
    assert "Active Domain Knowledge: paint_shop_vehicle_logistics" in content


def test_load_skill_tool_appends_state():
    from unittest.mock import MagicMock
    from langchain.tools import ToolRuntime
    from backend.app.agent.tools.skill_tools import load_skill

    # 1. 模拟 ToolRuntime，携带初始包含 A 领域的状态
    initial_state = {
        "messages": [],
        "skills_loaded": ["paint_shop_defect_analysis"],
        "active_skill": "paint_shop_defect_analysis"
    }
    runtime = MagicMock(spec=ToolRuntime)
    runtime.state = initial_state
    runtime.tool_call_id = "test_call_id"

    # 2. 调用 _build_load_skill_command 逻辑
    from backend.app.agent.tools.skill_tools import _build_load_skill_command
    cmd = _build_load_skill_command("paint_shop_vehicle_logistics", runtime)

    # 3. 断言返回的 Command 状态更新中，skills_loaded 进行了去重追加
    assert "paint_shop_defect_analysis" in cmd.update["skills_loaded"]
    assert "paint_shop_vehicle_logistics" in cmd.update["skills_loaded"]
    assert cmd.update["active_skill"] == "paint_shop_vehicle_logistics"


def test_load_skill_tool_truncates_over_limit():
    from unittest.mock import MagicMock
    from langchain.tools import ToolRuntime
    from backend.app.agent.tools.skill_tools import _build_load_skill_command

    initial_state = {
        "messages": [],
        "skills_loaded": ["skill_a", "skill_b", "skill_c"],
        "active_skill": "skill_c"
    }
    runtime = MagicMock(spec=ToolRuntime)
    runtime.state = initial_state
    runtime.tool_call_id = "test_call_id"

    # 加载第 4 个技能，最先进入的 "skill_a" 应该被截断除去
    cmd = _build_load_skill_command("paint_shop_vehicle_logistics", runtime)
    loaded = cmd.update["skills_loaded"]
    
    assert len(loaded) == 3
    assert "skill_a" not in loaded
    assert "paint_shop_vehicle_logistics" in loaded


def test_before_agent_resets_loaded_skills():
    db = DummyDB()
    middleware = SkillMiddleware(db)
    
    state = {
        "active_skill": "paint_shop_defect_analysis",
        "skills_loaded": ["paint_shop_defect_analysis", "paint_shop_vehicle_logistics"]
    }
    
    # 验证 before_agent 原生钩子能够过滤排除，瘦身重置为只包含主激活技能
    update = middleware.before_agent(state, None)
    assert update == {"skills_loaded": ["paint_shop_defect_analysis"]}


def test_skill_middleware_injects_secondary_skeleton():
    # 模拟主技能为质量缺陷，且物流技能被加载为辅助
    state = CustomState(
        messages=[],
        skills_loaded=["paint_shop_defect_analysis", "paint_shop_vehicle_logistics"],
        active_skill="paint_shop_defect_analysis"
    )
    
    request = ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    db = DummyDB()
    # 注入物流追踪相关的物理 DDL 缓存，用于辅助反射
    db._custom_table_info["fct_vehicle_position_current"] = "CREATE TABLE fct_vehicle_position_current (\n  vehicle_id VARCHAR\n);"
    
    middleware = SkillMiddleware(db)
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    # 1. 验证大纲
    assert "Available Skills" in content
    # 2. 验证主技能全量展开
    assert "Active Domain Knowledge: paint_shop_defect_analysis" in content
    # 3. 验证辅助技能骨架被自动挂载到 Secondary 块中
    assert "Secondary Domain Knowledge" in content
    assert "辅助关联技能表结构: paint_shop_vehicle_logistics" in content
    assert "CREATE TABLE fct_vehicle_position_current" in content



