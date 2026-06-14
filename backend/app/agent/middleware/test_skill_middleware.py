import pytest
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest

from backend.app.agent.middleware.skill_middleware import SkillMiddleware
from backend.app.agent.state import CustomState

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
    
    middleware = SkillMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    assert "Available Skills" in content
    assert "Active Domain Knowledge: paint_shop_vehicle_logistics" in content
    assert "ods.carbody_history" in content


def test_load_skill_tool_overwrites_state():
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

    # 3. 断言返回的 Command 状态更新中，skills_loaded 仅包含新激活项，旧的被剔除重置
    assert cmd.update["skills_loaded"] == ["paint_shop_vehicle_logistics"]
    assert cmd.update["active_skill"] == "paint_shop_vehicle_logistics"

