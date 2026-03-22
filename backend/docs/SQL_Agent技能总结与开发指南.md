# SQL Agent 技能状态管理与精确校验指南

## 1. 背景与问题定义

在构建基于 LangChain / LangGraph 的 SQL Agent 时，通常采用“渐进式披露（Progressive Disclosure）”策略，即 Agent 初始只知道有哪些业务技能可用，具体的表结构等详细元数据需要通过调用 `load_skill()` 工具按需加载。

### 潜在风险：跨轮次状态“污染”
当系统启用了 **Checkpointer（状态持久化）** 后，Agent 会记住上一轮加载的技能。如果校验逻辑过于宽松（例如：只要 `skills_loaded` 列表不为空即放行），会导致以下问题：
- **用户第一轮**：询问 A 业务问题，Agent 加载了 A 技能。
- **用户第二轮**：询问 B 业务问题，Agent 检查发现“已有技能已加载”（A 技能），于是跳过 `load_skill` 直接生成 B 业务的 SQL。
- **结果**：由于模型 Prompt 中只有 A 的表定义，生成的 B 业务 SQL 极大概率出现字段幻觉或查询不存在的表。

## 2. 优化方案：精确技能校验模式

参考 LangChain 官方 `skills-sql-assistant` 最佳实践，我们采用了**“参数声明 + 状态强制校验”**的模式。

### 核心实现原则
1. **工具契约化**：在 `sql_db_query` 等核心工具中，强制模型传入 `required_skill` 字段，声明本次查询属于哪个业务域。
2. **状态精确比对**：工具内部不再只检查 `skills_loaded` 是否为空，而是检查 `required_skill` 是否在已加载列表中。
3. **闭环反馈**：若校验失败，工具必须返回明确的 Error 指令，指导模型先调用 `load_skill`。

## 3. 关键代码规范

### 工具层定义 (`sql_tools.py`)
```python
@langchain_tool
def sql_db_query(query: str, required_skill: str, runtime: ToolRuntime) -> str:
    """
    执行 SQL 查询。
    IMPORTANT: 必须指定 'required_skill' 参数（例如 'paint_shop'）。
    """
    skills_loaded = runtime.state.get("skills_loaded", [])
    if required_skill not in skills_loaded:
        return f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再执行查询。"
    # ... 执行逻辑
```

### 提示词引导 (`service.py`)
在系统提示词（System Prompt）中明确工作流程：
- 强调调用查询工具时必须通过 `required_skill` 声明依赖。
- 强调切换业务领域时必须先执行 `load_skill()`。

## 4. 经验总结与注意事项

- **状态持久化与清理**：在 CLI 环境或生产环境，`thread_id` 是状态绑定的唯一标识。调试跨域问题时，请确保测试用例覆盖了“同线程跨业务域”的交互逻辑。
- **Docstring 的重要性**：大模型决定是否调用工具、如何传参，完全依赖工具的 Docstring。对于必填的 `required_skill`，必须在 Docstring 中使用 `IMPORTANT` 或 `MUST` 等强语气修饰。
- **类型安全**：当工具在错误或校验场景返回 `str`（提示信息），在正常场景返回 `List` 或其他对象时，请务必使用 `Union` 正确标注返回类型，以通过静态分析并避免运行时异常。

---
*更新时间：2026-03-21*
*优化人：Antigravity*
