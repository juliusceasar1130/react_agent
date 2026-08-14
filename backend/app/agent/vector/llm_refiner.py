import json
import logging
from typing import Tuple
from pydantic import BaseModel, Field
from backend.app.agent.llm import _create_llm

logger = logging.getLogger(__name__)

class RefinedSQLCase(BaseModel):
    """自演进系统提炼的黄金 SQL Few-Shot 案例模板"""
    rewritten_query: str = Field(
        description="改写后的用户意图。必须是一个语义完整、消解了多轮指代关系、可以直接用于向量库语义检索的单句中文提问。需融入澄清问答历史中的有效限制条件。"
    )
    desensitized_sql: str = Field(
        description="参数化脱敏后的 SQL 模板。仅将动态过滤条件的值（如特定日期、具体车身号、序列号、具体工号、具体车型的代码字面值）替换为描述性占位符，且占位符格式必须使用 {{占位符名称}}。严禁改动任何表名、列名、JOIN关联条件或固定枚举/状态值常量/布尔值。"
    )

def refine_sql_case_with_llm(
    raw_query: str,
    raw_sql: str
) -> Tuple[str, str]:
    """调用大模型进行意图改写（指代消解）和 SQL 脱敏参数化（基于 LangChain 1.0 推荐的结构化输出方式）
    
    Returns:
        (rewritten_query, desensitized_sql)
    """
    prompt = f"""你是一个专业的 SQL 分析专家。你的任务是将一个生产数据查询案例提炼为高泛化性的"黄金 Few-Shot 模板"。

输入案例包含：
1. 用户的原始查询与澄清问答历史（格式为：原始提问 [澄清提问: xxx -> 澄清回答: yyy]）。
2. 执行成功的 SQL 语句（可能是单步 SQL，也可能是包含多个 `-- Step N` 注释分割的多步 SQL 序列）。

你需要根据以下规则完成提炼：
- 对于 rewritten_query：你必须把 `[澄清提问: ... -> 澄清回答: ...]` 里的补充约束条件融入到重写意图中。
  例如："昨天面漆段流挂车有多少？ [澄清提问: 请问是一产线还是二产线？ -> 澄清回答: 二产线]"
  应改写为："查询昨天二产线面漆段流挂缺陷的车辆总数"。
  
- 对于 desensitized_sql：
  1. 仅将表示具体动态过滤条件的值（如特定日期、具体车身号、序列号、具体工号、具体车型的代码字面值）替换为双大括号占位符，例如 `line_id = {{{{产线ID}}}}`。
  2. 如果 SQL 中存在前后步骤的动态参数依赖关系（例如 Step 2 使用了 Step 1 查询返回的 ID 值），请务必将该依赖值 parameterize 为指向性的占位符，例如 `position_id = {{{{Step1.id}}}}` 或 `position_id = {{{{第一步查询返回的ID}}}}`。
  3. 如果输入是多步 SQL，必须保留所有以 `-- Step N` 开头的步骤注释，不能将其删减或合一，且需依次对各步 SQL 执行脱敏。
  4. 严禁改变 SQL 的表名、列名、JOIN 关联条件或任何 SQL 关键字。
  5. 严禁脱敏业务常量、状态码或枚举值。例如：`status = 1` 中的 `1`，`is_deleted = 0` 中的 `0`，`is_history = 'N'` 中的 `'N'`，`line_type = 'paint'` 中的 `'paint'`，布尔值 `true`/`false` 必须原样保留。

输入案例：
User Query: {raw_query}
SQL: {raw_sql}
"""
    try:
        llm = _create_llm()
        # 使用 with_structured_output 绑定 Pydantic 模型，并开启 include_raw=True 从而支持安全审计与降级
        structured_llm = llm.with_structured_output(RefinedSQLCase, include_raw=True)
        response = structured_llm.invoke(prompt)
        
        parsed_data = response.get("parsed")
        parsing_error = response.get("parsing_error")
        
        if parsing_error is not None:
            logger.error("LLM 结构化输出解析失败。错误原因: %s, 原始输出: %s", parsing_error, response.get("raw"))
            return raw_query, raw_sql
            
        if parsed_data is not None:
            return parsed_data.rewritten_query, parsed_data.desensitized_sql
            
        return raw_query, raw_sql
        
    except Exception as e:
        logger.error("LLM 提炼案例失败，将降级使用原始问题与原始 SQL。错误: %s", e)
        # 容错降级：返回原始文本与 SQL，确保业务闭环不中断
        return raw_query, raw_sql

