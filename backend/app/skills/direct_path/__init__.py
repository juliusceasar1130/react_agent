"""
直通模式 (Direct Path) 执行引擎包

包含了绕过 Agent 推理的直行路线核心组件：
- resolver: 参数解析与默认值/控件推断
- executor: SQL 模板安全绑定与参数化执行
- formatter: 结果输出格式化 (table / scalar)
"""

from .resolver import infer_widget, resolve_params, resolve_source_options
from .executor import build_executed_sql, execute_scenario
from .formatter import format_result

__all__ = [
    "infer_widget",
    "resolve_params",
    "resolve_source_options",
    "build_executed_sql",
    "execute_scenario",
    "format_result",
]
