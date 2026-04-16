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
from backend.app.skills import SKILLS

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

    def __init__(self) -> None:
        """初始化并生成技能提示词"""
        self.skills_prompt = _build_skills_prompt(SKILLS)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """将技能描述（description）注入到系统提示词"""
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed domain knowledge. "
            "If the loaded domain skill shows a matching fixed scenario, use the "
            "load_scenario tool before composing SQL. For fixed statistics or "
            "fixed report-style questions, prefer loading a scenario instead of "
            "planning from scratch."
        )

        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
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
