# LangChain SQL Agent 最佳实践指南

本文档基于 `test_agent_V2.py` 的重构经验，总结了构建生产级 SQL Agent 的核心架构模式、工具设计策略和提示词工程规范。

## 1. 核心架构设计

### 1.1 中间件模式 (Middleware Pattern)
使用 `AgentMiddleware` 动态注入上下文，而不是将所有信息硬编码在 System Prompt 中。这允许 Agent 根据运行时环境（如已加载的技能）动态调整行为。

**关键代码**:
```python
class SkillMiddleware(AgentMiddleware[CustomState]):
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        # 动态构建提示词附加内容
        skills_addendum = f"..." 
        # 注入到 SystemMessage
        new_content = list(request.system_message.content_blocks) + [...]
        return request.override(system_message=SystemMessage(content=new_content))
```

### 1.2 状态驱动依赖 (State-Driven Dependencies)
利用 `AgentState` 追踪关键状态（如 `skills_loaded`），并在工具内部强制检查这些状态，确保 Agent 遵循预定义的工作流。

```python
class CustomState(AgentState):
    skills_loaded: NotRequired[list[str]]
```

## 2. 工具设计策略

### 2.1 复合工具包装 (Consolidated Tool Wrapping)
**原则**: 不要让 LLM 负责多步骤的串行调用（如 Check -> Execute -> Sanitize），而应该将这些步骤封装在单一的原子工具中。

**优势**:
- **原子性**: 保证语法检查和日期清洗一定会被执行。
- **简化决策**: LLM 只需决定"查询数据"，无需关注执行细节。

**实现模式**:
```python
@langchain_tool
def sql_db_query(query: str, runtime: ToolRuntime) -> str:
    """Execute a SQL query (Atomic Operation)."""
    
    # 1. 状态检查 (State Guard)
    if not runtime.state.get("skills_loaded"):
        return "Error: 必须先加载业务技能..."

    # 2. 自动语法检查 (Auto Check)
    if checker_tool:
        check_result = checker_tool.invoke({"query": query})
        if "error" in str(check_result).lower():
            return f"Syntax Error: {check_result}"

    # 3. 执行查询 (Execute)
    result = original_query_tool.invoke({"query": query})

    # 4. 结果清洗 (Sanitize)
    return normalize_dates(str(result))
```

### 2.2 领域隔离 (Domain Isolation)
**原则**: 移除通用的 `list_tables` 和 `schema` 工具，强制 Agent 通过 `load_skill` 获取特定领域的表结构信息。

**优势**:
- 防止 Agent 访问不相关的表（领域泄漏）。
- 解决不同领域表名冲突或混淆问题。

```python
# 移除通用探索工具
tools = [t for t in raw_tools if t.name not in ["sql_db_list_tables", "sql_db_schema"]]
# Agent 只能通过 load_skill 能够看到的表进行查询
```

## 3. 提示词工程

### 3.1 显式工作流 (Explicit Workflow)
在 System Prompt 中明确定义操作步骤，而不是依赖模型推理。

```text
工作流程：
1. 在查询数据前，你必须先使用 load_skill 工具加载相关业务领域的技能
2. 从技能内容中了解可用的表结构、字段含义和业务规则
3. 根据技能提供的信息编写 SQL 查询
4. 使用 sql_db_query 工具执行查询（会自动进行语法检查）
```

### 3.2 交互规范
```text
注意事项：
- <DATE_EVT> 是字符串格式，需使用 STR_TO_DATE 进行转换
- 如果用户问题边界模糊，直接提问澄清，不要猜测
- 回答简明扼要
```

## 4. 总结

通过**移除冗余工具**、**包装原子操作**和**状态强校验**，我们将原本开放式的 LangChain SQL Agent 改造为了一个**领域受限、执行可靠**的业务 Agent。这种模式特别适用于企业级复杂数据查询场景。
