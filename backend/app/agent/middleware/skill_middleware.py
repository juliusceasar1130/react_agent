# backend/app/agent/middleware/skill_middleware.py
"""
技能中间件。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 注册 `load_scenario` 工具，支持二级技能披露
- 强化提示词，引导先加载领域再按需加载场景
"""

import logging
from typing import Callable, List

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage

from backend.app.agent.state import CustomState
from backend.app.agent.tools.skill_tools import load_scenario, load_skill
from backend.app.skills.registry import get_all_skills

logger = logging.getLogger(__name__)


def _build_skills_prompt(skills: List[dict]) -> str:
    """从技能列表构建技能描述（description）文本"""
    skills_list = [f"- **{skill['name']}**: {skill['description']}" for skill in skills]
    return "\n".join(skills_list)


class SkillMiddleware(AgentMiddleware[CustomState]):
    """
    技能描述注入中间件。

    在每次模型调用前，将可用技能列表注入到系统提示词中，
    引导 Agent 先加载领域技能，再按需加载固定场景。
    """

    state_schema = CustomState
    tools = [load_skill, load_scenario]

    def __init__(self, db=None) -> None:
        """初始化"""
        from backend.app.agent.utils.skeleton_service import SkeletonService
        self.skeleton_service = SkeletonService(db)

    def before_agent(self, state: CustomState, runtime) -> dict | None:
        """
        💡 框架原生周期钩子：在新一轮对话开始时拦截，
        强制将 skills_loaded 收窄为当前 active_skill，擦除历史辅助遗留，自动瘦身。
        """
        active = state.get("active_skill")
        if active:
            return {
                "skills_loaded": [active]
            }
        return None

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """将技能大纲、当前主技能全量 DDL 以及关联辅助技能骨架 DDL 动态拼装入 System Prompt"""
        skills_prompt = _build_skills_prompt(get_all_skills())
        skills_addendum = (
            f"\n\n## Available Skills\n\n{skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed domain knowledge. "
            "If the loaded domain skill shows a matching fixed scenario, use the "
            "load_scenario tool before composing SQL. For fixed statistics or "
            "fixed report-style questions, prefer loading a scenario instead of "
            "planning from scratch."
        )

        active_skill = request.state.get("active_skill") if request.state else None
        skills_loaded = request.state.get("skills_loaded", []) if request.state else []

        # 1. 载入主激活技能 (全量 DDL 与 Gotchas 说明)
        active_ddl_addendum = ""
        if active_skill:
            from backend.app.skills import load_domain_content
            skill_content = load_domain_content(active_skill)
            if skill_content:
                active_ddl_addendum = (
                    f"\n\n## Active Domain Knowledge: {active_skill}\n"
                    "下列是当前激活领域的核心表结构 DDL 以及业务易错规则，请在编写 SQL 时严格遵守：\n\n"
                    f"{skill_content}\n"
                )

        # 2. 🔴 计算差集并载入关联辅助技能的极简 Schema 骨架 (免读库缓存反射)
        secondary_skills = [s for s in skills_loaded if s != active_skill]
        secondary_ddl_blocks = []
        for sec_skill in secondary_skills:
            sec_ddl = self.skeleton_service.get_skeleton_ddl(sec_skill)
            if sec_ddl:
                secondary_ddl_blocks.append(
                    f"### 辅助关联技能表结构: {sec_skill}\n"
                    f"```sql\n{sec_ddl}\n```"
                )
        secondary_prompt = "\n\n".join(secondary_ddl_blocks) if secondary_ddl_blocks else ""

        # 3. 级联拼装 SystemMessage 文本块
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        if active_ddl_addendum:
            new_content.append({"type": "text", "text": active_ddl_addendum})
        if secondary_prompt:
            new_content.append({"type": "text", "text": f"\n\n## Secondary Domain Knowledge\n{secondary_prompt}"})
            
        new_system_message = SystemMessage(content=new_content)

        return request.override(system_message=new_system_message)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """同步模式：注入技能描述到系统提示词"""
        modified_request = self._modify_request(request)

        logger.info("📋 1.系统提示词 (ModelRequest.system_message):")
        logger.info(str(modified_request.system_message.content))

        system_msgs = [
            msg for msg in modified_request.messages if isinstance(msg, SystemMessage)
        ]
        if system_msgs:
            logger.info(f"📋 2.消息历史中的系统消息 (共 {len(system_msgs)} 条):")
            for i, msg in enumerate(system_msgs, 1):
                logger.info(f"  [{i}] {str(msg.content)}")

        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """异步模式：注入技能描述到系统提示词"""
        modified_request = self._modify_request(request)

        logger.info("📋 系统提示词 (ModelRequest.system_message):")
        logger.info(str(modified_request.system_message.content))

        system_msgs = [
            msg for msg in modified_request.messages if isinstance(msg, SystemMessage)
        ]
        if system_msgs:
            logger.info(f"📋 消息历史中的系统消息 (共 {len(system_msgs)} 条):")
            for i, msg in enumerate(system_msgs, 1):
                logger.info(f"  [{i}] {str(msg.content)}")

        return await handler(modified_request)
