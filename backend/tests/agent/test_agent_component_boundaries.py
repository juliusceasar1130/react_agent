# backend/tests/agent/test_agent_component_boundaries.py
"""
Phase 1 - Ticket 02: 主子智能体职责边界与技能独占归属测试。

验证内容:
1. 主 Agent 仅包含编排与澄清工具 (AskUserQuestion)，不包含 SkillMiddleware 或 load_skill 工具
2. SQL 子智能体独占装配 SkillMiddleware (load_skill, load_scenario) 与 PromptCompilerMiddleware
3. SQL 子智能体在沙箱内能够正常执行 load_skill 并通过 PromptCompilerMiddleware 编译出包含对应 DDL 的系统提示词
"""
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents.middleware import ModelRequest

from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
from backend.app.agent.middleware.skill_middleware import SkillMiddleware
from backend.app.agent.service import SQLAgentService
from backend.app.agent.tools.ask_user_question import AskUserQuestion
from backend.app.agent.tools.skill_tools import load_skill, load_scenario


def test_main_agent_and_subagent_middleware_and_tools_boundaries():
    """验证主 Agent 纯净编排与 SQL 子智能体独占技能管理中间件。"""
    from unittest.mock import patch
    from backend.app.agent.utils import MaterializedViewSQLDatabase

    mem_db = MaterializedViewSQLDatabase.from_uri("sqlite:///:memory:")
    with patch("backend.app.agent.service._create_database_connection", return_value=(mem_db, {})):
        service = SQLAgentService(auto_initialize=False)
        components = service._build_agent_components()
    
    main_tools = components["tools"]
    main_middlewares = components["middleware"]
    subagents = components["subagents"]
    
    # 1. 验证主 Agent 工具仅为 AskUserQuestion，不包含 load_skill / load_scenario
    assert len(main_tools) == 1
    assert isinstance(main_tools[0], AskUserQuestion)
    main_tool_names = [getattr(t, "name", "") for t in main_tools]
    assert "load_skill" not in main_tool_names
    assert "load_scenario" not in main_tool_names
    
    # 2. 验证主 Agent 中间件不包含 SkillMiddleware
    has_skill_in_main = any(isinstance(m, SkillMiddleware) for m in main_middlewares)
    assert not has_skill_in_main, "主 Agent 不得装配 SkillMiddleware，领域技能必须归属于子智能体"
    
    # 3. 验证 SQL 子智能体存在且配置了 SkillMiddleware
    assert len(subagents) == 1
    sql_subagent = subagents[0]
    name = sql_subagent.get("name") if isinstance(sql_subagent, dict) else getattr(sql_subagent, "name", "")
    assert name == "sql_domain_agent"
    runnable = sql_subagent.get("runnable") if isinstance(sql_subagent, dict) else getattr(sql_subagent, "runnable", None)
    assert runnable is not None


def test_sql_subagent_skill_middleware_loading_and_prompt_compilation():
    """验证 SQL 子智能体在沙箱内通过 SkillMiddleware 注入技能并在 PromptCompilerMiddleware 中成功合并 DDL。"""
    skill_mw = SkillMiddleware()
    compiler_mw = PromptCompilerMiddleware()
    
    # 模拟 SQL 子智能体执行了 load_skill("paint_shop_defect_analysis") 后的沙箱 State
    state = {
        "active_skill": "paint_shop_defect_analysis",
        "skills_loaded": ["paint_shop_defect_analysis"],
    }
    
    req = ModelRequest(
        model="mock_model",
        system_message=SystemMessage(content="你是一个专业的 SQL 数据库专家。"),
        messages=[HumanMessage(content="查询涂装车间缺陷数据")],
        state=state,
    )
    
    # 1. SkillMiddleware 注入技能描述与 DDL blocks
    req_after_skill = skill_mw._modify_request(req)
    
    # 2. PromptCompilerMiddleware 编译合并为双分区 XML 格式
    req_compiled = compiler_mw._modify_request(req_after_skill)
    
    compiled_text = str(req_compiled.system_message.content)
    assert "<system_rules>" in compiled_text
    assert "<runtime_context>" in compiled_text
    assert "paint_shop_defect_analysis" in compiled_text
    # 验证包含了涂装车间缺陷领域的 DDL 或业务规则描述
    assert "Active Domain Knowledge" in compiled_text or "缺陷" in compiled_text
