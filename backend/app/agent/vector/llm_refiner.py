import json
import logging
from typing import Tuple
from backend.app.agent.service import _create_llm

logger = logging.getLogger(__name__)

def refine_sql_case_with_llm(
    raw_query: str,
    raw_sql: str
) -> Tuple[str, str]:
    """调用大模型进行意图改写（指代消解）和 SQL 脱敏参数化
    
    Returns:
        (rewritten_query, desensitized_sql)
    """
    prompt = f"""你是一个专业的 SQL 分析专家。你的任务是处理一个生产 data 查询案例：
1. 用户的查询意图（可能在括号中带有澄清交互历史）。
2. 执行成功的 SQL。

你需要将数据提炼并输出为一个标准的 JSON 对象，包含以下两个字段：
- "rewritten_query": 改写后的用户查询，必须是一个语义完整、消解了指代关系、可以直接用于向量库语义检索的单句提问。
- "desensitized_sql": 脱敏后的 SQL。请将 SQL 中具体的字面值（例如特定日期、具体车身号、批次号等）用占位符替换（如 '<日期>', '<车身号>', '<产线ID>'）。严禁改变 SQL 的表名、列名、语法结构或任何 SQL 关键字结构。

输入案例：
User Query: {raw_query}
SQL: {raw_sql}

请直接返回合法的 JSON 对象，不要输出 Markdown 块或任何解释性文本。例如：
{{"rewritten_query": "查询昨天二产线的流挂车数", "desensitized_sql": "SELECT count(*) FROM paint_vehicle WHERE line_id = <产线ID> AND production_date = <日期>"}}
"""
    try:
        llm = _create_llm()
        resp = llm.invoke(prompt)
        content = resp.content.strip()
        
        # 清洗 Markdown 的 ```json 包裹标记
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip("` \n")
        
        data = json.loads(content)
        rewritten_query = data.get("rewritten_query", raw_query)
        desensitized_sql = data.get("desensitized_sql", raw_sql)
        return rewritten_query, desensitized_sql
        
    except Exception as e:
        logger.error("LLM 提炼案例失败，将降级使用原始问题与原始 SQL。错误: %s", e)
        # 容错降级：返回原始文本与 SQL，确保业务闭环不中断
        return raw_query, raw_sql
