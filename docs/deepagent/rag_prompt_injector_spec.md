# 轻量级 RAG 提示词注入中间件规范 (RagPromptInjectorMiddleware Spec)

> **文档路径**：`docs/deepagent/rag_prompt_injector_spec.md`  
> **关联模块**：`backend/app/agent/middleware/rag_prompt_injector_middleware.py` & `backend/app/agent/service.py`  
> **更新时间**：2026-08-09  
> **实施设计**：解耦主 Agent 的轻量级 RAG 提示词注入与 SQL 子 Agent 的重型工具消息裁剪  

---

## Problem Statement

主 Agent (`create_deep_agent`) 需要将 `BusinessRagMiddleware` 存入 `state["lexicon_context"]` 的召回内容注入到发给 LLM 的 SystemMessage 中。现有的 `PromptCompilerMiddleware` 包含了专门针对 SQL 子智能体频繁调库试错的“消息极限删除”与“大文本工具折叠”重型逻辑。若让主 Agent 直接运行该重型中间件，会导致不必要的遍历开销与职责过载。

---

## Solution

将 RAG 提示词注入逻辑从重型 `PromptCompilerMiddleware` 中物理剥离，专门创建一个轻量级、无状态开销的 `RagPromptInjectorMiddleware`。
主 Agent 挂载 `RagPromptInjectorMiddleware`，仅实现“读取 State -> 注入 SystemMessage”；SQL 子 Agent 继续挂载 `PromptCompilerMiddleware`，维护复杂的 SQL 试错历史折叠。

---

## User Stories

1. 作为面向用户的总客服（主 Agent），我希望在接收到业务提问时能极速将向量库/物理词典召回结果注入 Prompt，以便毫秒级解答用户的业务概念与规则疑问。
2. 作为系统架构师，我希望主 Agent 不需要跑 SQL 工具消息折叠算法，以便降低 CPU 遍历开销与运行延时。
3. 作为 SQL 分析专家（子 Agent），我希望继续保留重型提示词编译器的 SQL 工具裁剪能力，以便试错上下文不爆 Token。

---

## Implementation Decisions

### 1. 修改与新增的模块
- **[NEW] `backend/app/agent/middleware/rag_prompt_injector_middleware.py`**：
  - 新建 `RagPromptInjectorMiddleware` 继承 `AgentMiddleware[CustomState]`。
  - 在 `wrap_model_call` / `awrap_model_call` 中提取 `request.state.get("lexicon_context")` 中的 `formatted_text`，包装为 `<runtime_context>` 追加到 `request.system_message`。
- **[MODIFY] `backend/app/agent/service.py`**：
  - `main_middleware_list` 装配 `RagPromptInjectorMiddleware()`；
  - `subagent_middleware_list` 装配 `PromptCompilerMiddleware()`。

### 2. 职责隔离矩阵

| 功能点 | 主 Agent (`RagPromptInjectorMiddleware`) | SQL 子 Agent (`PromptCompilerMiddleware`) |
| :--- | :---: | :---: |
| **RAG 文本提取与 SystemMessage 注入** | ✅ 支持 (极速) | ✅ 支持 |
| **系统日期注入** | ✅ 支持 | ✅ Support |
| **SQL 工具历史极限删除 (search_db_*)** | ❌ 跳过 (无需求) | ✅ 支持 |
| **历史超大工具输出折叠 (sql_db_query)** | ❌ 跳过 (无需求) | ✅ 支持 |
| **静态/动态 DDL 区合并** | ❌ 跳过 (无需求) | ✅ 支持 |

---

## Testing Decisions

- **行为测试**：运行 `test_compiled_subagent_v2_poc.py`，验证主 Agent 能正常收到带 RAG 动态区的 System Prompt。
- **边界测试**：无 RAG 召回内容时 `RagPromptInjectorMiddleware` 安全 `noop` 跳过，不影响基础对话。

---

## Out of Scope

- 不修改底层向量数据库与向量索引结构。
- 不影响子智能体已有的 `PromptCompilerMiddleware` 执行。

---

## Further Notes

- 该解耦提升了代码的单一职责（SRP）特性，为后续引入更多轻量领域子 Agent 奠定了基础。
