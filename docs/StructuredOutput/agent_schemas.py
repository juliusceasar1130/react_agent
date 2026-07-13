# backend/app/agent/agent_schemas.py
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

class ReasoningStep(BaseModel):
    step: int = Field(description="思考步骤序号")
    thought: str = Field(description="模型思考内容（中文）")
    confidence: Literal["high", "medium", "low", "assumption"] = Field(description="可信度")
    user_should_verify: bool = Field(default=False, description="是否需要用户确认")
    suggestion: Optional[str] = Field(default=None, description="验证建议")

class TableData(BaseModel):
    title: Optional[str] = Field(default=None, description="表格标题")
    headers: list[str] = Field(description="表头列名列表")
    rows: list[list[Any]] = Field(description="数据行列表")

class StructuredDataResult(BaseModel):
    """强结构化数据输出模型（适用于报表与数据查询）"""
    judgment: str = Field(description="对查询意图的基本判断与数据范围说明")
    reasoning_process: Optional[list[ReasoningStep]] = Field(default=None, description="模型推理思考步骤")
    tables: list[TableData] = Field(description="查询结果表格数据列表")
    columns: Optional[list[dict]] = Field(default=None, description="列渲染控制定义")
    insights: list[str] = Field(description="数据洞察与核心结论列表")
    used_tables: Optional[list[str]] = Field(default=None, description="实际使用的数据表名列表（非必填，大模型基于上下文抄写）")
    query_time: Optional[str] = Field(default=None, description="数据真实查询时刻（非必填，大模型基于上下文抄写）")
    execution_trace_id: Optional[str] = Field(default=None, description="工具调用执行记录追踪ID（非必填，大模型基于上下文抄写）")
    total_count: Optional[int] = Field(default=None, description="总数据条数")
    data_freshness: Optional[str] = Field(default=None, description="数据新鲜度说明")

class FreeMarkdownResult(BaseModel):
    """自由文本输出模型（适用于 RAG 问答、开发问题、澄清问题等）"""
    response_type: Literal["explanation", "clarification", "refusal", "other"] = Field(description="回复类型分类标签")
    content: str = Field(description="支持包含 Mermaid、代码块等任意 Markdown 格式的主体文本")
    suggested_tables: Optional[list[str]] = Field(default=None, description="可能相关的数据表建议")
    suggested_questions: Optional[list[str]] = Field(default=None, description="可能具体的查询问法建议")
