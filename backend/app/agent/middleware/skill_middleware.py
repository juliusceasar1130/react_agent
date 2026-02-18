# backend/app/agent/middleware/skill_middleware.py
"""
技能中间件

在请求处理过程中自动注入技能描述到系统提示词中，
使 Agent 了解可用的业务技能。
"""

import logging
from typing import Callable, List

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage

from backend.app.agent.state import CustomState
from backend.app.agent.tools.skill_tools import load_skill
from backend.app.skills import SKILLS

logger = logging.getLogger(__name__)


def _build_skills_prompt(skills: List[dict]) -> str:
    """从技能列表构建技能描述文本"""
    skills_list = [f"- **{skill['name']}**: {skill['description']}" for skill in skills]
    return "\n".join(skills_list)


class SkillMiddleware(AgentMiddleware[CustomState]):
    """
    技能描述注入中间件

    在每次模型调用前，将可用技能列表注入到系统提示词中，
    引导 Agent 在需要时使用 load_skill 工具加载详细技能信息。
    """

    state_schema = CustomState
    tools = [load_skill]

    def __init__(self) -> None:
        """初始化并生成技能提示词"""
        self.skills_prompt = _build_skills_prompt(SKILLS)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """将技能描述注入到系统提示词"""
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed information "
            "about handling a specific type of request."
        )

        # 追加系统提示词
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
        
        # 记录系统提示词
        logger.info("📋 1.系统提示词 (ModelRequest.system_message):")
        logger.info(str(modified_request.system_message.content))
        
        # 记录消息历史中的系统消息
        system_msgs = [msg for msg in modified_request.messages if isinstance(msg, SystemMessage)]
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
        
        # 记录系统提示词
        logger.info("📋 系统提示词 (ModelRequest.system_message):")
        logger.info(str(modified_request.system_message.content))
        
        # 记录消息历史中的系统消息
        system_msgs = [msg for msg in modified_request.messages if isinstance(msg, SystemMessage)]
        if system_msgs:
            logger.info(f"📋 消息历史中的系统消息 (共 {len(system_msgs)} 条):")
            for i, msg in enumerate(system_msgs, 1):
                logger.info(f"  [{i}] {str(msg.content)}")
        
        return await handler(modified_request)
