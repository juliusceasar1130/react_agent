# DeepAgent 多智能体单点 RAG 检索与状态继承优化规范 (RAG Optimization Spec)

> **文档路径**：`docs/deepagent/rag_single_retrieval_spec.md`  
> **关联规范**：`docs/deepagent/phase1_implementation_spec.md`  
> **更新时间**：2026-08-10  
> **技术基线**：`deepagents 0.7.5` + `langchain 1.3.14` + `langgraph 1.2.9`  

---

## 1. 背景与问题定义 (Problem Statement)

在最初的阶段一多智能体架构中，`BusinessRagMiddleware` 被同时挂载在主 Agent 与 SQL 子智能体（`sql_domain_agent`）侧。经过源码核验与运行期诊断，发现该“双重 RAG 挂载”设计存在以下核心缺陷：

1. **同 Turn 内重复检索开销**：SQL 子智能体在 SQL 生成与语法试错（ReAct）循环中，每一次 LLM 思考与工具回包都会重复触发向量数据库与三层物理词典检索，带来高达数百毫秒至数秒的无谓延迟。
2. **检索 Query 含有委派指令噪声**：子智能体的首条消息是主 Agent 生成的 `Task` 描述文本，其中包含了“探索性查询”、“请充分利用 search_db_value_lexicon 探查...”等系统级指令文本。这些指令噪声混入向量检索 Query 中，稀释了业务术语的召回精准度。
3. **判重机制失效死结**：由于 RAG 文本改由 `PromptCompilerMiddleware` / `RagPromptInjectorMiddleware` 通过 `ModelRequest.override` 动态编译注入，未向 Checkpointer 的 `state["messages"]` 追加 `SystemMessage`，导致基于 `_has_rag_system_message` 的旧版防重复逻辑永远失效。

---

## 2. 底层机制与理论验证 (Empirical Verification)

通过对 `deepagents` (v0.7.5) 本地源码 (`deepagents/subagents.py`) 的物理核查，确认以下机制 100% 成立：

```python
# deepagents/subagents.py 源码机制
_EXCLUDED_STATE_KEYS = {"messages", "todos", "structured_response"}

def create_subagent_task_tool(...):
    @tool
    def task(subagent: str, description: str, state: Annotated[dict, InjectedState]):
        target = subagents_by_name[subagent]
        subagent_runnable = target.runnable
        
        # 1. 拷贝父 State，仅剔除 _EXCLUDED_STATE_KEYS 中的 3 个 key
        parent_state = {k: v for k, v in state.items() if k not in _EXCLUDED_STATE_KEYS}
        parent_state = copy.deepcopy(parent_state)
        
        # 2. 组装输入传给子图 runnable
        subagent_input = {
            **parent_state,
            "messages": [HumanMessage(content=description)],
        }
        return subagent_runnable.invoke(subagent_input)
```

### 核心结论：
1. **State 状态深拷贝**：主 Agent 在入口处检索并写入 `state` 的 `lexicon_context`、`rag_query`、`rag_context` 等字段，在 `task` 工具委派时会被 **100% 完整拷贝并透传** 给子智能体（无论是 `SubAgent` 还是 `CompiledSubAgent`）。
2. **子智能体天然具备注入能力**：子智能体挂载的 `PromptCompilerMiddleware` 具备读取 `state["lexicon_context"]` 并将其格式化为 `<runtime_context>` 注入子智能体 Prompt 的完整逻辑。
3. **主 Agent 单点 RAG 机制完全成立**：子智能体**无需挂载检索中间件**即可享用主 Agent 检索到的最新、最纯净的业务术语与 Schema 上下文。

---

## 3. 优化架构设计 (Optimization Architecture)

### 3.1 架构对比

```
【旧架构：主子双重检索（死结与噪声）】
用户提问 ──► [主 Agent (RAG检索器)] ──(生成 Task 描述)──► [SQL 子智能体 (RAG检索器)]
                 │ (基于纯净用户提问)                          │ (基于带指令噪声的 Task 描述)
                 ▼                                              ▼
          写入主 State                                   再次重复查 Milvus & 词典

──────────────────────────────────────────────────────────────────────────────────────────

【新架构：主 Agent 统一单点检索 + 子智能体 State 继承透传（D-2 方案）】
用户提问 ──► [主 Agent (BusinessRagMiddleware)]
                 │ (100% 纯净 Query 检索，写入 state.lexicon_context)
                 ▼
            [task 委派] ──► (DeepAgent 自动 deepcopy 状态透传)
                                 │
                                 ▼
                     [SQL 子智能体 (PromptCompilerMiddleware)]
                         │ (0ms 开销直接读取 state.lexicon_context 注入 Prompt)
                         ▼
                     [专业 SQL 生成与 ReAct 试错 (无二次检索干扰)]
```

### 3.2 详细设计规范

#### 1. 中间件解耦分层 (`backend/app/agent/service.py`)
- **主 Agent 中间件链 (`main_middleware_list`)**：
  - `BusinessRagMiddleware`：统一负责全局 RAG 检索（向量 + 三层物理词典）；
  - `RagPromptInjectorMiddleware`：轻量级 System Message 注入（含 `_inject_thinking_config`）；
  - `SummarizationMiddleware` / `ContextWarningMiddleware` / `ModelCallLimitMiddleware`。
- **SQL 子智能体中间件链 (`subagent_middleware_list`)**：
  - **移除 `BusinessRagMiddleware`**；
  - 保留 `PromptCompilerMiddleware`：直接读取透传过来的 `state["lexicon_context"]` 并无痕注入；
  - `SkillMiddleware` / `ModelCallLimitMiddleware` / `ToolCallLimitMiddleware`。

#### 2. `BusinessRagMiddleware` 同 Turn 判重与防空控制 (`backend/app/agent/middleware/rag_middleware.py`)
- **`_extract_query` 判定升级**：
  ```python
  existing_rag_query = state.get("rag_query")
  existing_lexicon_ctx = state.get("lexicon_context")
  if existing_lexicon_ctx is not None and isinstance(existing_rag_query, str) and existing_rag_query == user_query:
      logger.debug("BusinessRagMiddleware: 当前 query 已在当次 Turn 中完成 RAG 检索，跳过重复检索。")
      return None
  ```
- **空命中/失败清空控制**：
  若当次 Turn 检索未命中任何参考信息，返回 `{"rag_query": user_query, "lexicon_context": None, "rag_context": []}`，既清空上一轮残留上下文，又防止同 Turn 内重试。

#### 3. 主 Agent 思考模式注入 (`backend/app/agent/middleware/rag_prompt_injector_middleware.py`)
- 植入 `_inject_thinking_config`，从 `RunnableConfig` 捕获客户端传入的 `enable_thinking` 并动态改写 `model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"]`，保证主 Agent 路由层推理能力。

#### 4. 精细化流式领域识别 (`backend/app/services.py`)
- 在流式 Chunk 遍历中动态维持 `active_task_call_ids: set[str]`；
- 仅当 `ns` 中的工具 ID 在 `active_task_call_ids` 中或包含 `sql_domain_agent` 时判定进入子智能体，区分主 Agent 自身文件工具（`read_file` / `write_file`）与真正的子智能体委派，杜绝前端徽章闪烁。

---

## 4. 收益与代价评估 (Impact & Trade-offs)

### 收益 (Benefits)
1. **性能提升**：SQL 子智能体 ReAct 循环减少 100% 的向量/词典检索开销（单次 Turn 节省数百毫秒至数秒）。
2. **检索精度 100%**：RAG 仅基于原始用户提问触发，彻底隔离主 Agent Task 委派指令噪声。
3. **架构极简**：消除主/子智能体在中间件内部的分支判断逻辑。

### 代价 (Trade-offs)
1. **文档规范对齐**：需将 `phase1_implementation_spec.md` 中“双重全量 RAG”字面更新为“主 Agent 统一检索 + 子智能体 State 继承透传”。
2. **单一兜底**：若主 Agent 侧 RAG 检索服务挂掉，子智能体不再尝试单独重试（但原实现共享检索器实例，主侧挂掉子侧同样不可用，实际无新增风险）。

---

## 5. 验收标准 (Acceptance Criteria)

- [x] **单元测试全绿**：`test_rag_prompt_injector_middleware.py` 与 `test_rag_middleware.py` 100% 通过。
- [ ] **同 Turn 0 重复检索**：单轮对话中 `BusinessRagMiddleware` 检索日志仅触发 1 次。
- [ ] **思考模式注入**：主 Agent 收到 `enable_thinking=True` 时网络包携带对应参数。
- [ ] **徽章零闪烁**：主 Agent 执行读写文件工具时，前端徽章保持为“通用助手”，仅在 `task` 委派时切换为“SQL数据助手”。
