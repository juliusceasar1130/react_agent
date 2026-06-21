from typing import List, Optional, Type
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
import json

class QuestionOption(BaseModel):
    label: str = Field(description="选项标签文本")
    description: Optional[str] = Field(None, description="选项的详细描述")

class QuestionItem(BaseModel):
    question: str = Field(description=(
        "具体的澄清提问。注意：这也会作为用户回复答案字典（dict）中的 Key 值返回给您。 "
        "【重要约束】：每个 QuestionItem 必须是单一维度的澄清，禁止混合模式。如果你既需要用户做选择，"
        "又需要用户输入数据，必须在 questions 列表中传入两个 QuestionItem，"
        "第一题为选择模式（带 options），第二题为开放式问答模式（options 为空或 None）。"
        "严禁在单个 QuestionItem 中混合两个或多个参数要求（例如：不要在单个问题中同时要求用户‘选择读写站并输入车身号’）。"
    ))
    header: Optional[str] = Field(None, description="卡片头分类信息，如 '查询意图确认'、'参数确认'，用于前端小徽章展示。")
    multiSelect: bool = Field(False, description="是否支持多选。设置为 true 表示多选复选框，false 表示单选框。当 options 为空时本字段无意义。")
    options: Optional[List[QuestionOption]] = Field(None, description="备选项列表，推荐 2~4 个。如果为 None 或空，前端将只显示纯文本输入框供用户输入（例如车身号、日期输入等场景）。")

class AskUserQuestionSchema(BaseModel):
    questions: List[QuestionItem] = Field(description=(
        "澄清问题卡片列表，支持 1~4 个。"
        "【重要规则】：每个 QuestionItem 必须是单一维度的澄清，禁止混合模式。"
        "如果你既需要用户做选择，又需要用户输入数据："
        "- 【错误做法】：在 questions 列表中仅传入 1 个 QuestionItem，question 设为 '请选择读写站并提供车身号'，且提供 options 列表。这会导致前端交互断裂！"
        "- 【正确做法】：在 questions 列表中传入 2 个 QuestionItem，例如："
        "  1. 选项卡片: {\"question\": \"请选择要查询的读写站（Station ID）\", \"options\": [{\"label\": \"Station A\"}, ...]}"
        "  2. 输入框卡片: {\"question\": \"请提供目标车身号（FIS，如782026xxxxxxxx）\"}"
    ))

    @field_validator("questions", mode="before")
    @classmethod
    def parse_questions(cls, v):
        if isinstance(v, str):
            v = v.strip()
            # If wrapped in markdown code blocks, strip them
            if v.startswith("```"):
                lines = v.splitlines()
                if len(lines) > 2:
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                v = "\n".join(lines).strip()
            try:
                v = json.loads(v)
            except Exception:
                try:
                    import ast
                    v = ast.literal_eval(v)
                except Exception:
                    pass
        return v

class AskUserQuestion(BaseTool):
    name: str = "AskUserQuestion"
    description: str = (
        "当需求不明确、需要用户补充车身号等查询条件，或需要进行技术权衡时调用。"
        "支持提供备选项（单选/多选）或纯文本问答（不传options即可），支持多问答组合。"
    )
    args_schema: Type[BaseModel] = AskUserQuestionSchema

    def _run(self, questions: List[dict]) -> dict:
        answers = interrupt({
            "type": "ask_user_question",
            "questions": questions
        })
        return answers
