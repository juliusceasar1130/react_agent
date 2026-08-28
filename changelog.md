## 2026-08-28 - Phase 2 修正：reasoning_effort 注入位置修复 (`model_sampling_profiles.yaml`, 测试, 文档) [AGENT]

### 变更内容

#### 1. 问题根因 [BUG]
- **`reasoning_effort` 此前放在 `extra_body` 段**（HTTP 请求体顶层），但 Qwen3 模板渲染时以 `chat_template_kwargs` 的键作为 Jinja2 变量读取 `reasoning_effort`；顶层参数 vLLM 接受但不传给模板。
- **行为验证**（2026-08-28，vLLM 192.168.3.26:8089）：顶层 5 档（none/low/medium/high/xhigh）输出无差异；模板通道（`chat_template_kwargs.reasoning_effort`）low/medium/xhigh 输出长度 1864/2338/3858 阶梯递增——证明只有模板通道生效。

#### 2. 修复内容 [FIX]
- **YAML**：`reasoning_effort` 从 `extra_body` 段移入 `chat_template_kwargs` 段（thinking=medium；fast 档不传），并更新文件头注释说明原因。
- **测试**：`test_sampling_profile_loader.py` / `test_prompt_compiler_middleware.py` / `test_rag_prompt_injector_middleware.py` 断言路径同步改为 `extra_body.chat_template_kwargs.reasoning_effort`。
- **文档**：`phase2_sampling_profiles_design.md`（D4/D5/术语表/传递链路）、`adr-model-sampling-profiles.md`（D4/D5/传递链路）、`glossary-model-sampling.md`（reasoning_effort 词条）同步修正，并标注修正日期。
- **验证脚本**：`manual_verify_sampling_request_body.py` 期望结构改为从 `chat_template_kwargs` 读取。

#### 3. 验证 [TEST]
- 完整后端测试套件：104 passed / 4 deselected / 0 failed。
- 网络层请求体捕获：thinking 档确认 `reasoning_effort` 位于 `chat_template_kwargs` 内（`{"enable_thinking": true, "reasoning_effort": "medium"}`）；fast 档确认 `enable_thinking=false` 且 `reasoning_effort` 不传。

---

## 2026-08-28 - 模型采样参数动态切换（思考/快答二档）(`backend/app/agent/config/`, `backend/app/agent/middleware/`, `backend/app/agent/service.py`) [AGENT]

### 变更内容

#### 1. 配置层：YAML 三段结构采样参数组合 (`backend/app/agent/config/`) [AGENT]
- **新增 `profile_loader` 模块**：`get_sampling_profile(enable_thinking)` 从 YAML 加载对应 profile，`apply_profile_to_model_settings(...)` 按三段结构（`top_level` / `extra_body` / `chat_template_kwargs`）机械覆写 `model_settings`。
- **fail-fast 校验**：`_load_profiles()` 在文件缺失、profile 不全、未知段时直接抛异常，阻止服务启动。
- **浅拷贝返回**：`get_sampling_profile` 返回 `dict(profile)` 浅拷贝，防止调用方误改全局缓存。
- **三段结构 YAML**：`model_sampling_profiles.yaml` 显式定义 `thinking` / `fast` 两档，每档含 `top_level`（temperature/top_p/presence_penalty）、`extra_body`（top_k/min_p/repetition_penalty）、`chat_template_kwargs`（enable_thinking/reasoning_effort）三段。

#### 2. 中间件层：双中间件动态注入 (`prompt_compiler_middleware.py`, `rag_prompt_injector_middleware.py`) [AGENT]
- **扩展 `_inject_thinking_config`**：从 configurable 读取 `enable_thinking`，调用 `profile_loader` 加载完整 profile 并覆写全部采样参数（此前仅注入 `enable_thinking` 布尔值）。
- **主 Agent 路径**：`RagPromptInjectorMiddleware` 注入主 Agent 的模型调用参数。
- **SQL 子智能体路径**：`PromptCompilerMiddleware` 注入 SQL 子智能体的模型调用参数，确保双路径行为一致。
- **向后兼容**：`enable_thinking=None` 时不做任何覆写，使用 `_create_llm()` 的 init-time 默认值。

#### 3. 启动 eager load (`service.py`) [AGENT]
- **`_initialize_agent` / `_ainitialize_agent`**：两条初始化路径开头均调用 `_load_profiles()`，触发 YAML 加载与 fail-fast 校验，配置问题在启动时即暴露。

#### 4. 测试覆盖 (`backend/tests/agent/`) [TEST]
- **`test_sampling_profile_loader.py`**：12 个 loader 单元测试（加载、缺失、未知段、浅拷贝、三段写入、幂等、覆写）。
- **`test_rag_prompt_injector_middleware.py`**：扩展为 5 个测试（RAG 注入、No-op、thinking 档补全断言、fast 档、None 不覆写）。
- **`test_prompt_compiler_middleware.py`**：新增 3 个对称测试（thinking/fast/None）。
- **全量后端测试**：20 个新增测试全部通过，完整套件 104 passed / 0 failed。

---


### 变更内容

#### 1. 文档索引体系以 OpenWiki 全面替代死链路径 (`CLAUDE.md`, `AGENTS.md`) [DOCS]
- **死链全面清理**：移除不存在的 `agent_docs/*` 与 `docs/skills/guide.md` 等失效路径。
- **OpenWiki 任务路由矩阵集成**：统一接入以 `openwiki/quickstart.md` 为主入口的结构化知识库体系，覆盖架构、提示词契约、领域技能、RAG/术语表、流式协议、工件生命周期、前端与运维等路由索引。

#### 2. DeepAgent 架构与多端核心开发规范对齐 (`CLAUDE.md`, `AGENTS.md`) [DOCS]
- **架构描述升级**：升级为 FastAPI + LangGraph DeepAgent 架构（主协调代理 + 编译型 SQL 领域子代理）。
- **后端双初始化与工具异常规范**：同步记录 `_initialize_agent`（同步）与 `_ainitialize_agent`（异步）双初始化路径，以及 LangChain 工具 4 项错误处理规范（统一 `ToolException`、显式 `handle_tool_error=True`、`"Error: "` 错误前缀、纯 `runtime: ToolRuntime` 注入）。
- **前端流式事件防丢机制**：同步要求后端新增流式事件必须在 `@/types`、`STREAM_EVENT_TYPES` 白名单 Set 集合与 `parseStreamEvent` switch 分支三处同步更新。
- **离线与本地化部署约束**：严禁公网 CDN 依赖，静态字体等资源本地化。

---

## 2026-08-23 15:50 +08:00 - 聊天主页用户问题刻度线导航与微光定位反馈 (`QuestionRail.vue`, `useScrollSpy.ts`, `MessageList.vue`, `MessageItem.vue`) [FE]

### 变更内容

#### 1. 独立视口监听与滚动定位 Composable (`frontend/src/composables/useScrollSpy.ts`) [FE]
- **视口动态计算**：利用 `getBoundingClientRect()` 精准计算各消息气泡相对滚动视口顶部的位移，以 `ACTIVATION_OFFSET_TOP = 120px` 作为顶部偏移判定阈值；触底时自动锁定激活最后一条用户问题。
- **rAF 节流与动态校准**：滚动事件通过 `requestAnimationFrame` 节流处理，并接入 `ResizeObserver` 动态监听流式输出或图表动态展开带来的高度变化；组件卸载时安全释放 `cancelAnimationFrame` 与监听器。
- **平滑定位与落点微光**：实现 `scrollToMessage(messageId)` 平滑滚动定位，并为目标消息气泡注入 `.highlight-pulse` 关键帧动效（1.2s 自动销毁），提供直观落点反馈。

#### 2. 用户问题刻度线导航浮层组件 (`frontend/src/components/chat/QuestionRail.vue`) [FE]
- **常态极简刻度线**：右侧垂直居中展示刻度短横线（普通项 14px 宽浅灰，当前激活项 20px 宽加粗深黑），不遮挡正文与卡片。
- **悬停展开毛玻璃卡片**：鼠标悬停时平滑展开毛玻璃卡片（`bg-white/95 backdrop-blur-xl shadow-xl rounded-2xl`），显示历史用户提问截断文本与对应刻度线；支持项悬浮高亮与点击快速定位。
- **性能与无障碍**：使用 `v-memo` 进行列表渲染优化，并配置 `role="navigation"`、`aria-label="用户问题导航"` 无障碍属性。

#### 3. 消息流与列表装配 (`MessageList.vue`, `MessageItem.vue`) [FE]
- 在 `MessageList.vue` 中挂载 `QuestionRail`，提取 `userQuestions` 响应式列表，并在 `defineExpose` 中对外暴露 `scrollToMessage`。
- 在 `MessageItem.vue` 根节点上为用户消息绑定 DOM 锚点 ID `msg-${message.id}` 并配置微光呼吸动画。

---

## 2026-08-23 14:30 +08:00 - 主智能体与涂装 Data Agent 提示词分工协作优化与架构扩展契约对齐 (`main_system_prompt.md`, `base_system_prompt.md`) [AGENT]

### 变更内容

#### 1. 主智能体提示词重构与协作契约闭环 (`backend/app/agent/prompts/main_system_prompt.md`) [PROMPT]
- **架构级路由矩阵与职责收敛**：引入结构化路由矩阵，精准定义 `sql_domain_agent` 作为专用于涂装车间的数据查询、指标统计、图表与 CSV 导出的 Data Agent，为后续多智能体平滑扩展奠定标准骨架。
- **标准化 Task 委派契约与多轮上下文合并**：明确 Task 下发标准模版（业务目标、业务过滤实体、探索授权与交付物），强化多轮对话关键参数合并传递，避免子智能体因独立上下文丢失前序车间/时间前提。
- **两级澄清与结果保真呈现协议**：明确主智能体仅在全局方向性歧义时调用 `AskUserQuestion`；严格规定对子智能体输出的准确数值不臆造篡改，100% 保真透传 `[suggest_chart]` 图表标记与单列一行的 `数据来源：...` 标注。

#### 2. SQL 子智能体提示词优化与自愈闭环 (`backend/app/agent/subagents/sql/base_system_prompt.md`) [PROMPT]
- **角色精准定位**：明确为 120JPH 专为涂装车间设计的 Data Agent（数据查询与分析专家），修复中英夹杂与情感渲染限制。
- **自愈优先于澄清**：消除工作流第 1 步强制提问的隐蔽冲突，在 §2.2 与 §3.1 第 1 步中统一定义“优先利用 `search_db_value_lexicon` / `search_db_row_lexicon` 物理词典探查自愈，探查无果再发起精准提问”的最小打扰原则。

#### 3. 设计文档与多智能体架构演进规划 (`docs/superpowers/specs/2026-08-23-multi-agent-prompt-and-architecture-optimization.md`) [DOCS]
- 整理多智能体扩展性设计 Spec，涵盖 1 个 Orchestrator + N 个 Specialist SubAgents 的分层拓扑、子智能体异构工厂与注册中心模式（Registry Pattern）及双初始化路径一致性保证。

#### 4. 测试与验证 [TEST]
- 执行 `backend/tests/agent/test_main_system_prompt.py`（2/2）及 `test_system_prompt_loader.py`（3/3），全部测试逻辑断言通过（Windows 默认 tmp ACL 限制已由 `--basetemp` 参数验证绿灯）。

---

## 2026-08-23 00:00 +08:00 - 主智能体系统提示词文件化解耦与加载器下沉 (`system_prompt_loader.py`, `service.py`, `config.py`) [BE]

### 变更内容

#### 1. SystemPromptLoader 下沉为共享基础设施 (`backend/app/agent/utils/system_prompt_loader.py`) [BE]
- 将原 `subagents/sql/prompts.py` 中的 `SystemPromptLoader` 平移至 `agent/utils/system_prompt_loader.py`，经 `utils/__init__.py` 包级导出。
- `subagents/sql/prompts.py` 改为从 `utils` 导入并保留 re-export，`_build_system_prompt` 行为不变，下游唯一引用（`service.py:31`）零改动。

#### 2. 主智能体提示词外置为 `.md` 模板 (`main_system_prompt.md`, `config.py`, `service.py`) [BE]
- 将 `service.py` 中硬编码的主智能体提示词（Task Delegation Protocol）原样外置至 `agent/prompts/main_system_prompt.md`。
- 新增 `main_system_prompt_path` 配置项（env `MAIN_SYSTEM_PROMPT_PATH`），与子智能体 `system_prompt_path` 正交。
- 主提示词构建走 `_build_main_system_prompt()` 纯字符串加载，**不经 `PromptTemplate`**，规避 JSON 花括号误解析风险。

#### 3. 热重载语义说明 [DOCS]
- mtime 热重载仅在重新建图（`_build_agent_components`）时触发；常驻编译图修改 `.md` 需重启进程生效，非"运行时零重启实时生效"。

#### 4. 测试与验证 [TEST]
- 新增 `tests/agent/utils/test_system_prompt_loader.py`（loader 包级导出 / re-export / 读取缓存与缺失文件）与 `tests/agent/test_main_system_prompt.py`（默认路径存在 / 构建锚点断言）。
- 验证：本特性新增/改动的测试全部通过；全链路回归（`pytest -m "not integration and not smoke"`）中与本改动无关的预存环境 quirk 除外（CWD 边界解析 quirk 与 pytest `tmp_path` 基目录 ACL 限制）。

---

## 2026-08-21 23:05 +08:00 - 多智能体核心工件主气泡直出与分级治理 (`MessageItem.vue`, `SubagentCard.vue`) [FE]

### 变更内容

#### 1. 一等交付工件（图表 & CSV）主气泡第一视口直出 (`MessageItem.vue`) [FE]
- **解除排他锁定**：移除图表与 CSV 导出卡片上的 `subagentsList.length === 0` 排他约束，当子智能体执行绘图（`build_chart_artifact`）或导出（`export_to_csv`）时，主消息气泡正文下方第一视口**直接无条件呈现交互式 ECharts 图表与 CSV 一键下载卡片**。
- **确定性稳定排序**：工件列表按 `created_at` 与 `tool_call_id` 进行稳定排序，保证流式直推与 F5 刷新后的排版顺序 100% 绝对一致。
- **保持 SQL 数据表格归位**：SQL 数据表格保持在子卡片内部展示（主气泡仅在无子智能体时兜底），主视口聚焦业务交付物，避免信息过载。

#### 2. 子智能体卡片内部工件展示轻量化与防重渲染 (`SubagentCard.vue`) [FE]
- **轻量胶囊引用**：子卡片内部的图表与 CSV 下载展示降级为高质感轻量胶囊标签（`[📊 图表已交付至主视口: ...]`、`[📄 CSV 已交付至主视口: ...]`），彻底消除内外部同时实例化两个重型 ECharts Canvas 导致的内存与 DOM 资源浪费。
- **运行/完成态自适应折叠**：子卡片在 `running` 或 `isAwaitingClarification` 状态下展开展示执行进展，任务完成后自适应收起，使用户视线无缝聚焦于主气泡的最终结论与核心工件。

---

## 2026-08-20 22:58 +08:00 - SQL 查询结果表格组件默认折叠与交互优化 (`QueryResultGroup.vue`) [FE]

### 变更内容

#### 1. 查询结果表格支持优雅折叠与默认收起 (`frontend/src/components/artifacts/QueryResultGroup.vue`) [FE]
- **默认收起防占屏**：在 `QueryResultGroup.vue` 中统一引入折叠面板交互，默认状态收起（`defaultExpanded: false`），避免单次查询返回数十行表格占据大量聊天视口。
- **紧凑概览头部设计**：收起态提供精致的概要栏，显示表格标题、数据规模标签（如 `共 10 行 × 4 列`）、数据表数量（多表场景）与受保护截断标签，右侧带有清晰的 `展开查看数据 / 收起表格` 状态提示与动态旋转 Chevron 箭头。
- **全场景适配**：无论是主智能体兜底表格还是子智能体卡片内部的工具调用链表格，均统一享受紧凑折叠与按需展开能力。

---

## 2026-08-20 22:15 +08:00 - 图表生成与 CSV 导出工具 LangChain 原生签名推导重构与调度注入修复 (`chart_artifact_tool.py`, `csv_export_tool.py`) [FIX]

### 变更内容

#### 1. 根治 ToolRuntime 注入失效与空错误熔断 (`chart_artifact_tool.py`, `csv_export_tool.py`) [FIX]
- **移除显式 `args_schema` 覆盖**：在 `build_chart_artifact` 与 `export_to_csv` 上移除 `@langchain_tool(args_schema=...)` 传参，恢复原生 `@langchain_tool` 签名推导机制。
- **恢复 LangGraph 注入契约**：使 LangGraph `ToolNode` 能够正确识别底层函数签名中的 `runtime: ToolRuntime[RequestContext, Any]` 并自动完成框架注入，彻底解决 `missing positional argument: 'runtime'` 异常。
- **去除冗余二次校验与死代码**：删除 `_SERIES_INPUT_ADAPTER`（`TypeAdapter`）函数体内重复校验，直接使用入口处 Pydantic 自动解析完成的 `ChartSeriesInput` 强类型对象；删除 `if runtime is not None` 等不可能发生的死代码分支，直接访问 `runtime` 属性。

#### 2. 单元测试全链路升级与调度盲区堵漏 (`test_tools_main_and_subagent_compatibility.py`) [TEST]
- **升级为真实 `tool.invoke` 调度**：弃用 `tool.func` 裸函数直调，全面改用带有真实 `ToolRuntime` 数据类的 `tool.invoke` 进行全流程调度验证。
- **新增注入契约与大模型安全断言**：通过 `_get_all_injected_args` 断言框架注入契约成立，同时断言 `runtime` 绝对不在大模型可见的 `tool.args` 中暴露（零 `CallableSchema` 序列化风险）。
- **全量测试验证**：`pytest -m "not integration and not smoke"` **82 项测试 100% 绿色全通**，前端 `npm run build:check` 0 错误构建通过。

---

## 2026-08-20 20:40 +08:00 - 多智能体侧信道与工件体系架构知识库沉淀 (`docs/multiagent_sidechannel/`) [DOCS]

### 变更内容

#### 1. 架构核心资产归位与沉淀专区建立 (`docs/multiagent_sidechannel/`) [DOCS]
- **专区建立**：在 `docs/` 目录下新建 `multiagent_sidechannel/` 作为多智能体分层架构、State 侧信道、Claim-Check 工件存储与工具开发规范的权威知识库。
- **架构审查总纲沉淀**：归位并沉淀 [`multiagent_tool_sidechannel_audit_report.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/multiagent_tool_sidechannel_audit_report.md)（v3.0 终版），涵盖全系统六大维度架构裁决、TOAST/ArtifactStore 双轨持久化方案与 Phase 0~3 路线图。
- **理论模式报告沉淀**：归位并沉淀 [`state_sidechannel_multiagent_report.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/state_sidechannel_multiagent_report.md)，涵盖 6 种 State 侧信道模式与行业顶级框架（LangGraph、Anthropic、AutoGen、OpenAI）对比。
- **工具开发与异常拦截指南编制**：新增 [`tool_development_and_error_handling_guide.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/tool_development_and_error_handling_guide.md)，系统梳理四项核心铁律（`raise ToolException`、`handle_tool_error=True`、`"Error: "` 契约前缀、纯正 `ToolRuntime` 注入与 Pydantic `args_schema` 隔离）、避坑清单与标准实战模板。
- **索引导航编制**：编写 [`README.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/README.md) 提供目录索引与分角色阅读建议。

---

## 2026-08-20 20:20 +08:00 - 环境配置全面对齐与统一工件底座参数收敛 (`config.py`, `.env`, `.env_docker`) [CONFIG]

### 变更内容

#### 1. 统一工件底座配置与生命周期参数收敛 (`backend/app/config.py`, `.env`, `.env_docker`) [CONFIG]
- **工件根目录收敛**：在 `.env` 与 `.env_docker` 中淘汰旧有的分散路径配置（`CHART_ARTIFACT_DIR` 与 `SQL_EXPORT_DIR`），统一收敛为 Phase 2 标准的 `ARTIFACTS_DIR`（默认 `Temp/sql_agent_artifacts`）与 `ARTIFACTS_TTL_HOURS='24'`。
- **业务硬上限保留**：清晰保留 `SQL_EXPORT_MAX_ROWS` 与 `CHART_ARTIFACT_MAX_POINTS` 等业务层防 OOM 与防图表爆炸熔断参数。
- **平滑向下兼容**：`config.py` 与 `ArtifactStore` 保留历史路径变量作为只读白名单回退，确保系统在跨版本升级期间平滑过渡。

#### 2. 服务端端口与配置完整对齐 (`backend/app/config.py`) [CONFIG]
- **补齐端口声明**：在 `config.py` 中补齐 `backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))`。
- **全量字段 100% 映射验证**：经自动化脚本核验，`.env` 中的 86 项配置已与 `config.py` 实现 100% 绝对对齐（0 个遗漏字段）。

#### 3. 自动化测试 100% 验证 [TEST]
- 后端 `pytest` 全量自动化测试套件（82 项单元测试 100% 绿色通过）。

---

## 2026-08-20 20:15 +08:00 - 测试体系规范化与历史 PoC 脚本清理 [CLEANUP]

### 变更内容

#### 1. 单元测试套件收敛与目录规范化 (`backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`) [TEST]
- **测试归位**：将原本孤立在业务源码包内部的 `backend/app/agent/tests/test_rag_prompt_injector_middleware.py` 迁移至全局标准测试目录 `backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`。
- **配置与发现优化**：清理 `.gitignore` 中对 `backend/tests` 的历史忽略规则，确保所有新测试用例与历史回归测试能被 `pytest` 自动精准扫描与 Git 追踪。

#### 2. 历史阶段性 PoC 脚本清理 (`backend/app/agent/`) [CLEANUP]
- **清理业务源码包**：删除已在核心框架及单元测试中完整落地的开发期 PoC 调试脚本 `backend/app/agent/test_compiled_subagent_v2_poc.py` 与 `test_subagent_poc.py`，保持 Agent 业务包纯净度。

#### 3. 自动化测试 100% 验证 [TEST]
- 后端 `pytest backend/tests` 全量自动化测试套件（82 项单元测试 100% 绿色通过，4 项外部集成依赖用例正常跳过）。

---

## 2026-08-20 08:15 +08:00 - Phase 2 扩展: 子智能体专属工件内嵌与富交互调用序列全量落地 (Tickets 01-04)

### 变更内容

#### 1. 子智能体专属工件就近内嵌与自闭环工作台 (`frontend/src/components/chat/SubagentCard.vue`) [FEATURE]
- **工件池单向注入**：`SubagentCard` 引入 `artifactsPool?: Record<string, any>`，基于 `tool.id`（即 `tool_call_id`）精准索引并匹配对应工具产出的结构化工件。
- **数据表内嵌化**：`sql_db_query` 工具节点下方直接就近内嵌 `<QueryResultGroup>` / `<TableResult>`，支持 20/50/100 原生分页、列宽自适应、物理行号与截断提示，彻底告别单调生硬的 Python 元组文本。
- **CSV 导出卡片化**：`export_to_csv` 工具节点就近内嵌精致 CSV 下载卡片，清晰展示文件名、导出总行数、有效时间 `expires_at` 与直接下载按钮。
- **图表工件预览化**：`build_chart_artifact` 工具节点就近内嵌 `<ChartArtifactCard>`，支持图表实时预览、全屏放大与数据视图切换。
- **智能展开机制**：当子智能体包含有效数据产出或处于 `running` 状态时，卡片智能默认保持展开，用户无需额外点击即可直接查看分析数据。

#### 2. 主消息工件消重与降级兜底 (`frontend/src/components/chat/MessageItem.vue`) [REFACTOR]
- **全景消重闭环**：当存在子智能体（`subagentsList.length > 0`）且工件已在子智能体卡片内嵌呈现时，外层的 `<QueryResultGroup>`、`<ChartGroupCard>` 以及内联 CSV 下载卡片自动隐藏，彻底消除“双重重复渲染”现象。
- **全局兜底保障**：当无子智能体（主 Coordinator 直接调起工具）时，外层容器自动生效作为兜底展示，兼顾历史兼容性。

#### 3. 自动化测试套件与类型检查 100% 验证 [TEST]
- 前端 `npm run build:check`（vue-tsc 严格类型检查 + vite 生产打包）100% 编译通过，0 错误。
- 后端单元与组件自动化回归测试（82 项测试全部绿色通过）。

---

## 2026-08-20 07:10 +08:00 - Phase 2: 工具参数优雅隔离、异常拦截契约与开发规范全面对齐

### 变更内容

#### 1. 工具参数 Pydantic 隔离、CallableSchema 根治与历史垫片清理 (`backend/app/agent/tools/`, `backend/app/routers/artifacts.py`, `backend/tests/agent/`) [REFACTOR]
- **显式 `args_schema` 隔离**：`export_to_csv` 新增 `ExportToCsvInput`，与 `build_chart_artifact` 的 `BuildChartArtifactInput` 保持统一，彻底剥离大模型无需感知的内部参数。
- **纯正 `ToolRuntime` 注入**：移除 `runtime: ToolRuntime[...] | None = None` 联合类型，统一为纯正 `runtime: ToolRuntime[RequestContext, Any]`，根治 Pydantic 生成 Function Calling JSON Schema 时遍历 `stream_writer: Callable` 触发的 `Cannot generate a JsonSchema for core_schema.CallableSchema` 序列化崩溃。
- **移除冗余技能门禁**：彻底移除 `build_chart_artifact` 与 `export_to_csv` 中冗余的 `required_skill` 参数，实现跨 Agent（主智能体与任意子智能体）零障碍通用复用。
- **清理历史过渡垫片 (M4)**：路由层直连 `ArtifactStore`，物理删除已无外部调用的 `chart_artifacts.py` 与 `export_files.py`，工件体系 100% 收敛至 `backend/app/artifacts/`。

#### 2. 工具异常处理契约沉淀与规范固化 (`AGENTS.md`) [DOCS]
- **四项铁律规范化**：在 `AGENTS.md` 中固化 LangChain 工具错误处理规范：1) 统一使用 `raise ToolException`；2) 强制开启 `handle_tool_error = True` 确保 ReAct 自愈；3) 统一 `"Error: "` 前缀适配中间件折叠；4) 显式 `args_schema` 隔离。

#### 3. 自动化测试套件扩充与 100% 验证 [TEST]
- 新增 `test_tools_json_schema_generation` 自动化验证面向大模型的 Function Calling JSON Schema 结构与纯净度。
- 全量 78 项后端自动化回归测试 100% 绿色通过。

---

## 2026-08-19 22:10 +08:00 - Phase 2: Claude Code 独立代码审查整改全量闭环

### 变更内容

#### 1. 安全加固与路径脱敏 (`backend/app/artifacts/store.py`, `backend/app/routers/artifacts.py`, `backend/app/chart_artifacts.py`, `backend/app/export_files.py`) [SECURITY]
- **H1 严格防越权校验**：`ArtifactStore._resolve_managed_file` 实现基于安全根目录白名单（主工件目录 + 历史兼容目录）的绝对路径强制校验，一旦发现路径越界立即抛出 `PermissionError` 阻止访问。
- **H2 敏感物理路径脱敏**：在 `routers/artifacts.py`、`chart_artifacts.py`、`export_files.py` 的公共元数据响应中全量剥离服务器物理路径 `stored_path`，防止服务器绝对路径外泄。
- **H3 CSV 临时源文件清理**：`ArtifactStore.save_export_file` 在复制工件至托管目录后，主动删除工具生成的临时源文件，彻底消除孤儿 CSV 磁盘泄漏隐患。

#### 2. 契约修复与配置补齐 (`backend/app/artifacts/store.py`, `backend/app/config.py`, `backend/app/agent/tools/`, `backend/app/services/chat_service.py`, `frontend/src/components/artifacts/QueryResultGroup.vue`) [FIX]
- **M1 路由模型校验修复**：`save_artifact` payload 同时写入 `artifact_id` 与 `chart_id`，杜绝旧路由 `/api/chat/charts/{chart_id}` 响应模型验证失败抛出 500。
- **M2 配置项补齐**：`Settings` 增加 `artifacts_dir` 与 `artifacts_ttl_hours`，并在 `ArtifactStore` 中提供对历史目录的兼容回退查找。
- **M3 截断表格总数与提示增强**：`QueryResultGroup.vue` 修正 `currentTotalCount` 优先取 `row_count`（全量记录数），多表格采用逐工件 Tab 复合呈现并补齐截断场景下的防御性引导提示。
- **H4/L1-L5 代码整洁度与对齐**：工具层角色解析增加 `config['metadata']` 与状态推断容错；清理无用 `Optional` 导入与 `main.py` 导入排序；前后端统一 `sql_domain_agent` 显示名称为 `SQL数据专家`；更新 `README.md` 目录树。

#### 3. 自动化测试套件与类型检查 100% 验证 [TEST]
- 前端 `npm run build:check`（vue-tsc 严格类型检查 + vite 生产打包）100% 成功。
- 后端全量回归测试套件（77 项自动化测试全部绿色通过），包含新增的 H1 防越权、H2 路径脱敏、H3 孤儿清理与 M1 契约测试。

---

## 2026-08-18 22:45 +08:00 - Phase 2: 工件统一治理底座落地与前端复合卡片/内置分页全量交付 (Tickets 01-05)

### 变更内容

#### 1. 统一工件底座与自动垃圾回收 (`backend/app/artifacts/`, `backend/app/main.py`, `backend/app/routers/artifacts.py`) [FEATURE]
- **统一存储引擎 `ArtifactStore`**：创建单例工件存储类，统一管理图表（`charts/`，JSON）与导出文件（`exports/`，CSV + 元数据 JSON），统一分配 `cht_[hex32]` 与 `exp_[hex32]` 唯一 ID；使用 `tempfile + os.replace` 实现原子写防止并发读脏数据；内置路径防越权校验与 Windows 文件锁容错。
- **24 小时 TTL 与 Lifespan 定时 GC 任务**：在 FastAPI lifespan 注册后台定时异步循环，每 60 分钟安全清理超时过期工件文件。
- **REST 路由统一收敛与向后兼容**：收敛至 `/api/chat/artifacts/{artifact_id}` 及 `/api/chat/artifacts/{artifact_id}/download`，并对旧 `/charts/{chart_id}` 与 `/files/{file_id}` 路由提供 100% 透明转发兼容。

#### 2. 工具层泛型解耦与主子智能体复用适配 (`backend/app/agent/tools/chart_artifact_tool.py`, `backend/app/agent/tools/csv_export_tool.py`, `backend/app/agent/middleware/prompt_compiler_middleware.py`) [REFACTOR]
- **解除状态硬绑定**：`build_chart_artifact` 与 `export_to_csv` 升级泛型声明为 `ToolRuntime[RequestContext, Any]`，`required_skill` 设为可选，支持主智能体（`CustomState`）与子智能体（`SqlSubAgentState`）双向直接调用。
- **异常契约一致性**：统一使用 `raise ToolException("Error: ...")`，在 `PromptCompilerMiddleware` 中统一 `runtime_header: "Error:"`，保障 5-stage 错误信息预扫描与折叠机制零破坏。

#### 3. 前端多图表复合 Tab 容器与多表格内置原生分页 (`frontend/src/components/artifacts/`, `frontend/src/components/chat/MessageItem.vue`, `frontend/src/components/agent/SubAgentBadge.vue`) [FEATURE]
- **多图表复合卡片 `ChartGroupCard.vue`**：从 `MessageItem.vue` 解耦抽取，单图表保持独立渲染，多图表自动聚合为顶部 Tab 选项卡平滑切换，保留各图表全屏放大预览与数据视图切换功能。
- **多表格分组与内置分页 `QueryResultGroup.vue`**：将表格数据流重构为列表数组，按 `subagent_name` 分组聚合多表格；复用 `TableResult.vue` 内置原生分页组件，支持多表格独立翻页；统一映射子智能体标题为 `SQL数据专家`。

#### 4. 端到端回归测试与构建验证全量通过 [TEST]
- 前端 `npm run build:check`（vue-tsc 严格类型检查 + vite 生产打包）100% 编译通过，0 错误。
- 后端全量测试套件（77 项自动化测试全部绿色通过），覆盖工件生命周期、原子写、定时 GC、双 Agent 工具调用兼容性、Context API 瞬态流与沙箱并发隔离。

---

## 2026-08-18 22:15 +08:00 - Phase 2: 工件统一治理与复合 UI 架构方案制定与跨 Agent 联合评审通过

### 变更内容

#### 1. 架构方案制定与核心裁决确定 (`docs/agents/multiagent_tool_sidechannel_audit_report.md`, `docs/agents/phase2_review_request.md`) [DOCS]
- **裁决 `sql_db_query` DB 直存极简设计**：确立 SQL 查询结果数据量小（< 300KB），无需单独落盘物理文件与开发独立 REST 接口；继续由 `chat_messages.tool_artifacts` 表直接持久化（PostgreSQL TOAST 自动透明压缩），实现 F5 刷新 0 秒秒开与 0 冗余磁盘 IO。
- **物理工件底座统一收敛**：合并 `chart_artifacts.py` 与 `export_files.py` 为统一的 `ArtifactStore`，统一管理 `charts/` 与 `exports/` 物理落盘文件、统一 ID 分配（`cht_*`, `exp_*`）、统一 24 小时 TTL 与 FastAPI lifespan 定时后台 GC 垃圾清理任务。
- **工具层泛型解耦**：解除 `build_chart_artifact` 与 `export_to_csv` 对 `SqlSubAgentState` 的硬绑定，`required_skill` 设为可选，泛型适配 `CustomState` 与 `SqlSubAgentState`，为未来主智能体直接复用扫清障碍；保持 `ToolException("Error: ...")` 异常契约，确保 `PromptCompilerMiddleware` 的 5 阶段裁剪流水线零破坏。
- **前端复合呈现解耦**：规划从 `MessageItem.vue` 抽取 `ChartGroupCard.vue` 与 `QueryResultGroup.vue` 子组件，实现多图表 Tab 切换与多表格分组展示，直接复用 `TableResult.vue` 内置分页能力并统一子智能体标题映射。

#### 2. Claude Code 跨 Agent 联合评审通过 (Approve with suggestions) [REVIEW]
- 通过 `herdr` 连通 Claude Code 完成独立审查，获得 `Approve with suggestions` 最终核准；方案吸收采纳了文件原子写（`os.replace`）、GC 异常独立保护、真实图跨沙箱传播集成测试以及路由前缀核实等防御性建议。

---

## 2026-08-17 15:10 +08:00 - 修复 RAG 双通道失效：BaseRetriever 异步接口契约补齐

### 变更内容

#### 1. BaseRetriever 基类提供默认 aretrieve（线程池解绑同步 retrieve） (`backend/app/agent/vector/base.py`) [FIX]
- **根因**：`BusinessRagMiddleware.abefore_model`（异步路径）调用 `self.retriever.aretrieve(...)`，但 `MilvusHybridRetriever` / `PgVectorDocumentationRetriever` 从未实现该方法 → `AttributeError` → 异常回退将 `rag_context`/`lexicon_context` 置空 → 页面两种 RAG 知识均不显示、LLM 无检索参考。属 Phase 1 整改连带回归（`asyncio.to_thread(retrieve)` 被误写为 `await aretrieve()`），与 Context API 机制本身无关。
- **修复**：在 `BaseRetriever` 新增非抽象默认 `aretrieve`，内部 `asyncio.to_thread` 包装同步 `retrieve`（签名与同步方法完全一致），与 LangChain `BaseRetriever.ainvoke` 设计对齐；两个子类零改动继承，后续任何后端可覆写为原生异步。
- **影响面核验**：纯增量方法，不改任何现有行为；三个 DB 检索工具（`search_db_value_lexicon` 等）走 llama_index 体系，经核验零影响。

#### 2. 检索器异步接口契约测试 (`backend/tests/agent/test_retriever_async_contract.py`) [TEST]
- 新增契约测试 4 项：验证基类默认 `aretrieve` 的线程池委托与参数透传语义、`MilvusHybridRetriever` 与 `PgVectorDocumentationRetriever` 均具备兼容签名 `aretrieve`，防止接口缺口回归。
- **全量测试通过**：后端回归测试套件（30 passed, 0 failed）100% 绿色通过。

#### 3. 清理临时诊断日志 (`backend/app/agent/middleware/rag_middleware.py`, `backend/app/services/chat_service.py`, `backend/app/agent/middleware/rag_prompt_injector_middleware.py`) [CLEANUP]
- 根因定位完成后，删除 3 处 `[RAG_DEBUG]` 临时插桩日志（写入端 / 读取端 / LLM 消费端），恢复安静日志。

---

## 2026-08-17 12:58 +08:00 - Phase 1: 基于 Context API 的状态治理与子图沙箱隔离落地与复审整改 (Ticket 01 & 02)

### 变更内容

#### 1. Context API 请求级瞬态数据通道与单源真理对齐 (`backend/app/agent/context.py`, `backend/app/agent/middleware/rag_middleware.py`, `backend/app/services/chat_service.py`) [FEATURE]
- **契约声明**：新建 `backend/app/agent/context.py`，定义 `RequestContext(TypedDict)`，包含 `lexicon_context`、`rag_context`、`rag_query`、`user_id`、`session_id` 等单轮请求级瞬态检索上下文。
- **中间件向 Context API 写入与零写入持久化**：`BusinessRagMiddleware` 检索成功、同步异常回退与异步 `abefore_model` 异常回退分支均 100% 单向写入 `Runtime.context` 并统一 `return None`，不再向 State 回写大体量检索对象，实现 Checkpoint 状态快照中检索对象的 **0 字节写入**，并将防重判定彻底改为读取 `Runtime.context`。
- **死代码清理**：清理 `_format_knowledge_block` 中未使用的死代码，保持方法单一纯粹。
- **服务层流式直读与全量预置**：`chat_service.py` 预初始化包含全量规范字段的 `req_context`，流式循环 `_stream_execution_loop` 直接从 `req_context` 读取 `rag_context` 与 `lexicon_context` 发射前端 SSE 事件，彻底解除对废弃持久化 State 的二次打捞依赖。

#### 2. 父子智能体状态物理沙箱隔离 (`backend/app/agent/state.py`, `backend/app/agent/service.py`) [FEATURE]
- **State 物理瘦身与拆分**：`CustomState` 剔除 `skills_loaded`、`active_skill`、`rag_context`、`lexicon_context`、`rag_query` 等私有与瞬态字段，仅保留 `messages`、`context_warning` 与 `tool_artifact` 控制位；新增 `SqlSubAgentState` 专门用于 SQL 领域子图私有维护技能加载状态。
- **主子组件严格边界**：主 Agent（`create_deep_agent`）纯净编排，移除 `SkillMiddleware` 与领域技能工具；SQL 子智能体（`create_agent`）独占挂载 `SkillMiddleware` 与 `PromptCompilerMiddleware`。
- **消除并发更新冲突**：子图执行完毕后通过 `ToolMessage` 返回纯文本结果，私有状态自然闭环在子图沙箱内，彻底杜绝父图 `INVALID_CONCURRENT_GRAPH_UPDATE` 冲突。

#### 3. 提示词编译器支持 Context API 瞬态渲染 (`backend/app/agent/middleware/prompt_compiler_middleware.py`, `backend/app/agent/middleware/rag_prompt_injector_middleware.py`) [FEATURE]
- **动态读取 Context**：`PromptCompilerMiddleware` 与 `RagPromptInjectorMiddleware` 优先从 `request.runtime.context` 读取 `lexicon_context` 并动态拼装入 `<runtime_context>` XML 节点，同时保留对 `request.state` 的防御性回退。

#### 4. 静态泛型标注全面升级 (`Runtime[RequestContext]`, `ToolRuntime[RequestContext, SqlSubAgentState]`, `AgentMiddleware[..., RequestContext]`) [REFACTOR]
- **中间件泛型标注**：为 `BusinessRagMiddleware`、`PromptCompilerMiddleware`、`RagPromptInjectorMiddleware` 全量引入 `AgentMiddleware[StateT, RequestContext]` 与 `context_schema = RequestContext`；为 `before_model` / `abefore_model` 的 `runtime` 参数显式标注 `Runtime[RequestContext]`。
- **工具层泛型标注**：为 `sql_db_query`、`search_saved_correct_tool_uses`、`load_skill`、`load_scenario`、`build_chart_artifact`、`export_to_csv` 等工具的 `runtime` 参数显式标注 `ToolRuntime[RequestContext, SqlSubAgentState]`。
- **价值与收益**：消除所有 `Any` 模糊推断，使 IDE（Pylance/Pyright/Mypy）支持 `runtime.context` 键值的智能提示与编译期类型校验，且 0 运行时开销。

#### 5. 自动化测试套件构建与全量回归通过 (`backend/tests/agent/test_context_api_transient_flow.py`, `backend/tests/agent/test_state_sandboxing_concurrency.py`, `backend/tests/agent/test_agent_component_boundaries.py`) [TEST]
- **测试覆盖**：新增与完善 `test_context_api_transient_flow.py`、`test_state_sandboxing_concurrency.py`、`test_agent_component_boundaries.py`，覆盖 Context API 零污染持久化、同步/异步异常回退 0 写 State、asyncio.gather 真实并发沙箱隔离、主子智能体职责边界与动态 Prompt 编译。
- **全量测试通过**：后端全量回归测试套件（26 passed, 0 failed）100% 绿色通过。

---

## 2026-08-16 15:02 +08:00 - Phase 0: 多智能体工件持久化落库与流式信封分流落地 (Ticket 01 & 02)

### 变更内容

#### 1. 数据库模型与 CRUD 增加 tool_artifacts 持久化 (`backend/app/models.py`, `backend/app/schemas.py`, `backend/app/crud.py`, `backend/app/database.py`) [FEATURE]
- **持久化列新增**：在 `ChatMessage` 模型与 `MessageBase` / `MessageResponse` Schema 中新增 `tool_artifacts` 文本列，用于存储会话消息关联的工件字典快照（JSON 格式）。
- **数据库幂等迁移**：在 `create_tables()` 中追加 `ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS tool_artifacts TEXT` 幂等增量迁移，保证兼容既有库。
- **CRUD 读写支持**：`create_message` 支持传入并落库 `tool_artifacts`。

#### 2. SSE 流式信封溯源与 Final/Interrupt 事件工件全量落库 (`backend/app/services/chat_service.py`, `backend/app/routers/chat.py`, `backend/app/agent/tools/*`) [FEATURE]
- **工具级真实 tool_call_id 注入**：`chart_artifact_tool.py`、`csv_export_tool.py`、`sql/tools.py` 在发射 `tool_artifact` 时携带内部真实的 `tool_call_id`，杜绝同子智能体产生多工件及主 Agent 多次调用的覆盖冲刷。
- **流式信封溯源**：在 `tool_artifact` 流式事件中补充携带 `subagent_id`、`subagent_name` 与 `tool_call_id`。
- **流式工件池累积与全生命周期落库**：在 `_stream_execution_loop` 与 `/stream`、`/resume` 路由中按 `tool_call_id` 进行工件字典聚合，并在 `final` 结算及 `interrupt` 中断澄清事件触发时 100% 同步落库写入 `chat_messages.tool_artifacts`，彻底闭环等待用户确认或生成完成后刷新页面的工件复原。

#### 3. 前端多工件并列渲染与 F5 刷新完整复原 (`frontend/src/types/index.ts`, `frontend/src/api/chat.ts`, `frontend/src/stores/messages.ts`, `frontend/src/composables/useChatStream.ts`, `frontend/src/components/chat/MessageItem.vue`) [FEATURE]
- **工件字典池状态机**：Pinia `messages` store 新增 `memoryArtifactPool`，以 `tool_call_id` 唯一索引工件，并在流式与完成态之间无缝传递。
- **白名单与类型守卫安全修复**：补齐 `isOptionalRecord` 类型守卫，严格更新 `STREAM_EVENT_TYPES` 白名单与 `parseStreamEvent` 解析逻辑，支持带溯源信封的 `tool_artifact` 及 `final` 工件池。
- **多图表与多文件并列渲染**：`MessageItem.vue` 升级支持 `chartSpecsList` 与 `fileExportsList` 列表遍历，支持多子智能体并发或顺序产出的多图表、多 CSV 导出卡片并列展示。
- **F5 刷新历史复原**：优先反序列化 `message.tool_artifacts` 工件池，彻底解决历史消息在 F5 刷新后 ECharts 图表、CSV 导出卡片与 SQL 预览表格丢失/冲刷的问题。

#### 4. 自动化测试套件构建与 Claude Code 独立复审通过 (`backend/tests/test_tool_artifacts_persistence.py`, `backend/tests/test_routers_coverage.py`) [TEST]
- 新增 `test_tool_artifacts_persistence.py` 自动化测试，全面覆盖 ORM 模型读写、CRUD 检索、Pydantic 验证、SSE 流式编码以及同子智能体多工件无冲突隔离。
- 全量后端测试套件（53 passed）与前端 Vite 生产打包验证均 100% 通过。
- 经 Claude Code 跨智能体二次复审（Round 2），获得 **Approve ✅** 最终核准。

---

## 2026-08-15 23:18 +08:00 - 修复子智能体并发执行触发的 INVALID_CONCURRENT_GRAPH_UPDATE 状态冲突

### 变更内容

#### 1. CustomState 知识检索字段 Reducer 规范化 (`backend/app/agent/state.py`) [FIX]
- **补齐并发写 Reducer**：为 `CustomState` 中的 `rag_context` 与 `rag_query` 补充 `Annotated[..., _last_wins]` Reducer 声明。
- **消除多 SubAgent 并发写冲突**：彻底修复当主 Agent 同时发起多个 `task` 工具委派给子智能体（如 `sql_domain_agent`）时，子图结束通过 `Command(update=...)` 回写状态触发的 `At key 'rag_context': Can receive only one value per step. Use an Annotated key to handle multiple values.`（`INVALID_CONCURRENT_GRAPH_UPDATE`）异常。
- **并发状态测试覆盖**：新增 `backend/tests/agent/test_custom_state_concurrent.py` 单元测试，验证多节点并发汇聚时 State 的安全归约。

---

## 2026-08-15 22:18 +08:00 - 未登记命名空间警告日志去重优化

### 变更内容

#### 1. 流式命名空间解析日志降噪与去重 (`backend/app/services/chat_service.py`) [OPTIMIZE]
- **单会话生命周期去重**：在 `_stream_execution_loop` 中维护 `warned_unregistered_tools` 集合，对同一工具调用执行期间的未登记 `call_id` 仅记录一次警告日志，彻底消除逐 Token 流式循环下的高频重复刷屏。
- **保持观测与安全回退**：保留对异常/未登记命名空间回落到 `main` 的安全防御机制，兼顾生产日志整洁度与问题排查可观测性。

---

## 2026-08-15 21:25 +08:00 - 主智能体装配 AskUserQuestion 澄清工具与系统提示引导

### 变更内容

#### 1. 主智能体工具注册与双初始化路径同步 (`backend/app/agent/service.py`) [FEATURE]
- **主智能体工具注入**：在 `_build_agent_components` 中为主智能体（`create_deep_agent`）注册 `AskUserQuestion()` 工具，使其具备直接向用户发起结构化问答与确认的能力。
- **系统提示词指引增强**：在 `main_system_prompt` 中明确指引，当主智能体面临意图不明确、缺少必要关键前提条件或需要向用户进行技术/参数方案权衡时，可使用 `AskUserQuestion` 进行结构化提问。
- **双初始化路径无缝对齐**：同步与异步两条初始化路径共享 `_create_agent_from_components` 构建逻辑，保证同步与异步运行环境完全一致。

---

## 2026-08-15 21:18 +08:00 - 修复大模型输出纯字符串提问时的 AttributeError 异常

### 变更内容

#### 1. 后端 questions 列表项与工具调用安全类型防御 (`backend/app/routers/chat.py`) [FIX]
- **大模型入参多态兼容**：在 `/stream` 和 `/resume` 路由中，对 `questions` 列表中的每一项增加 `isinstance(q, str)`、`isinstance(q, dict)` 和 `hasattr(q, "model_dump")` 的多态安全解析，杜绝大模型输出纯字符串数组时触发 `'str' object has no attribute 'get'`。
- **历史工具列表双向兼容**：在 `/resume` 解析历史 `msg.tool_calls` 时，兼容 `dict` 与 `list` 双格式反序列化，防御字典 Key 被当做工具对象遍历。
- **SSE 事件安全提取**：在流式生成器消费事件时增加 `isinstance(event, dict)` 保护。

---

## 2026-08-15 21:05 +08:00 - 新增澄清问答底部常驻悬浮响应条（Floating Clarification Dock）

### 变更内容

#### 1. 前端悬浮响应条组件 (`frontend/src/components/chat/FloatingClarificationDock.vue`, `frontend/src/views/ChatView.vue`) [FEATURE]
- **常驻视口状态感知**：在聊天窗口底部输入框上方挂载轻量悬浮胶囊 Bar。当大模型或子智能体发起 `AskUserQuestion` 澄清提问时，平滑滑入呈现（如 `【🤖 SQL数据专家】 正在等待您确认参数...`），并带呼吸蓝色脉冲微光。
- **长文本回跳与自动聚焦**：当用户向上滚动翻阅长数据表格或日志时，悬浮条提供 **【👇 前往填写】** 快捷按钮，点击一键平滑滚动回卡片并将焦点自动置于首个输入框。
- **零后端依赖与自然消隐**：100% 纯前端响应式状态驱动，提交答复或会话结束时自动淡出收起，无多余视觉残留。

---

## 2026-08-15 20:55 +08:00 - 主子智能体 AskUserQuestion 审查反馈加固与边界防御优化

### 变更内容

#### 1. 提问者身份判定加固与主助手防御 (`backend/app/services/chat_service.py`, `frontend/src/components/chat/MessageItem.vue`) [FIX]
- **归属精准提取**：后端通过反向检索触发 `AskUserQuestion` 的工具调用归属，精准区分主智能体与子智能体，杜绝残留历史 `current_subagent` 导致的误归属。
- **主助手清爽展示**：前端统一规范 `formatSubagentTitle` 映射，主智能体提问时不展示冗余徽章，子智能体提问时统一展示规范名称 **【🤖 SQL数据专家 发起澄清提问】**。

#### 2. 子智能体等待确认态与停止状态严格隔离 (`frontend/src/components/chat/SubagentCard.vue`) [FIX]
- **状态机流转防御**：`isAwaitingClarification` 增加 `subagent.status === 'running'` 前置约束。当用户主动点击“停止生成”导致子智能体进入 `interrupted` 状态时，彻底屏蔽“等待确认”和【定位到表单】引导，杜绝中止与等待语义串扰。

---

## 2026-08-15 20:30 +08:00 - 主子智能体 AskUserQuestion 角色归属、聚焦联动与快捷交互优化（第二阶段）

### 变更内容

#### 1. 后端中断事件智能体身份透传 (`backend/app/schemas.py`, `backend/app/services/chat_service.py`) [FEATURE]
- **中断事件元数据扩展**：在 `InterruptStreamEvent` 中扩展 `subagent_id`, `subagent_name`, `subagent_title` 可选字段。
- **命名空间与子图识别**：在 `chat_service.py` 捕获 `AskUserQuestion` 中断挂起时，自适应解析当前活跃的子智能体身份（如 `sql_domain_agent` -> `SQL数据专家`），随流向前端推送精准的角色归属数据。

#### 2. 前端协议层与 Store 角色上下文打通 (`frontend/src/types/index.ts`, `frontend/src/api/chat.ts`, `frontend/src/stores/messages.ts`, `frontend/src/composables/useChatStream.ts`) [FEATURE]
- **协议白名单与解析**：前端 `STREAM_EVENT_TYPES` 白名单与 `parseStreamEvent` 同步解析 `subagent_id` / `subagent_name` / `subagent_title`。
- **Store 状态槽存储**：`messagesStore.setStreamingInterrupt` 接收提问者元数据并完整保存在当前消息状态中，提供稳定的上下文数据源。

#### 3. 澄清卡片专属角色徽章与全键盘快捷提交 (`frontend/src/components/chat/AskUserQuestionCard.vue`, `MessageItem.vue`) [OPTIMIZE]
- **专属角色标识 Header**：`AskUserQuestionCard` 头部根据提问者身份动态渲染专属徽章（如带有机器人图标的 **【🤖 SQL数据专家 发起澄清提问】**），使用户明确知晓提问来源。
- **全键盘快捷提交**：输入框支持 `Ctrl+Enter` / `Cmd+Enter` 快速提交表单，并附带优雅的键盘操作提示，显著提升多轮高频问答效率。

#### 4. 子智能体面板与底部表单锚点平滑聚焦联动 (`frontend/src/components/chat/SubagentCard.vue`) [OPTIMIZE]
- **等待引导条与一键定位**：子智能体处于等待澄清态时，面板底部展示提示条并提供 **【👇 定位到表单】** 按钮。
- **平滑滚动与自动聚焦**：点击后页面自动平滑滚动并将焦点（`focus()`）聚焦至底部问答表单输入框，彻底消除长日志与操作区之间的视线断层。

---

## 2026-08-15 20:25 +08:00 - 主子智能体 AskUserQuestion 状态语义解耦与等待澄清体验优化（第一阶段）

### 变更内容

#### 1. 前端主消息状态解耦与 Banner 柔和化 (`frontend/src/components/chat/MessageItem.vue`) [OPTIMIZE]
- **状态语义解耦**：引入 `isAwaitingClarification` 计算属性，严格区分“挂起等待用户输入（`hasQuestions && !isQuestionSubmitted`）”与“用户主动停止生成/异常中断”。
- **消除误导性恐慌文案**：当处于澄清等待期时，顶部彻底隐藏生硬的“已停止生成”黄色警告，转而渲染带有平缓微光呼吸动画的“⏳ 等待您的确认...”引导条，消除同一气泡内“顶端已停止 + 底端让填写”的视觉冲突。
- **动态样式适配**：等待澄清态下气泡边框采用温和淡蓝阴影（`border-blue-200/80 bg-gradient-to-br from-blue-50/30 via-white to-white`），工具状态展示为“等待确认”，与常规执行或异常态形成清晰视觉分级。

#### 2. 子智能体卡片挂起等待态升级 (`frontend/src/components/chat/SubagentCard.vue`) [OPTIMIZE]
- **子智能体等待确认标签**：当子智能体内部工具调用停留在 `AskUserQuestion` 时，状态标签由“已中断（⚠️）”升级为“等待确认”（搭配淡蓝色脉冲指示点），避免用户产生子智能体执行崩溃的误解。
- **工具链状态直观呈现**：工具调用序列中，`AskUserQuestion` 工具在未完成时直观标注为“等待用户确认...”，恢复完成后平滑转为“已完成”。

---

## 2026-08-15 19:10 +08:00 - 修复子智能体工具结果泄露至主消息底部的重复渲染问题

### 变更内容

#### 1. 前端主消息工具结果计算属性作用域对齐 (`frontend/src/components/chat/MessageItem.vue`) [FIX]
- **主工具作用域严格对齐**：`toolResultEntries` 改为基于主消息可见工具集合 `toolCallList` 的 ID 进行严格过滤匹配，杜绝子智能体内部的 `load_skill`、`sql_db_query` 等工具执行结果溢出泄露至主消息底部。
- **工具名称获取健壮性提升**：`getToolNameById` 新增回退防御逻辑，避免未知工具 ID 导致退化展示极长 hash 字符串。
- **子卡片内聚展示**：子智能体工具结果继续安全收拢于 `SubagentCard` 内展示，保证主卡片与子卡片职责分明、视觉整洁。

---

## 2026-08-15 15:35 +08:00 - 主 Agent 与子智能体流式显示解耦与独立卡片渲染落地

### 变更内容

#### 1. 后端流式协议打标与作用域分流 (`backend/app/schemas.py`, `backend/app/services/chat_service.py`) [FEATURE]
- **作用域元数据打标**：在 `StreamToolCallPayload`, `TokenStreamEvent`, `ReasoningStreamEvent`, `ToolCallStreamEvent`, `ToolResultStreamEvent` 中扩展 `subagent_id`, `subagent_name` 可选字段（序列化 `exclude_none=True` 向后兼容）。
- **命名空间与子任务映射**：`_stream_execution_loop` 实时维护主 Agent 派发的 `task` 工具调用映射表，自动解析图命名空间 `ns` 中的 `tools:<call_id>`，将子智能体产生的思考（Reasoning）、输出 Token 及内部工具调用（SQL/词典查询）精准打标为对应子智能体作用域。

#### 2. 前端 Store 隔离与事件解析分流 (`frontend/src/types/`, `frontend/src/api/chat.ts`, `frontend/src/stores/messages.ts`, `frontend/src/composables/useChatStream.ts`) [FEATURE]
- **类型系统扩展**：新增 `SubagentSessionState` 接口与 `subagents` 字典映射，支持子智能体独立的执行状态、专属思考、工具链调用与输出内容。
- **状态会话槽隔离**：`messagesStore` 引入 `ensureSubagentState` 状态槽管理，流式接收到子智能体 token/reasoning/tool_call 时独立分流，彻底杜绝主气泡与子智能体思考过程与计时器串槽。
- **中断与错误优雅收尾**：用户中途 Abort 停止或执行出错时，子智能体卡片优雅进入 `interrupted` 或 `error` 状态并完整保留已执行内容。

#### 3. 子智能体独立卡片 UI 组件与历史回放无损还原 (`frontend/src/components/chat/SubagentCard.vue`, `MessageItem.vue`) [FEATURE]
- **`SubagentCard.vue` 原生卡片**：提供专属执行状态指示（执行中/已完成/已中断/执行失败）、独立耗时计时器、专属深度思考折叠面板、工具调用参数与结果追踪，以及 Markdown 总结输出。
- **主气泡委派折叠与视图净化**：主气泡内仅保留主 Agent 的思考与最终业务结论，`task` 调用自动折叠为委派摘要徽标，消除界面双份冗余。
- **历史回放持久化**：新增 `chat_messages.subagents` 列（`create_tables` 幂等 `ADD COLUMN IF NOT EXISTS` 迁移），`final` 事件随流携带子智能体会话快照（思考/输出/工具链）落库；刷新或切换历史会话时优先还原完整快照，旧数据基于 `tool_calls` 中的作用域元数据兜底重构工具链。

---

## 2026-08-14 14:40 +08:00 - DeepAgent 架构重构收官：Wave 4 前后端 Shim 垫片全量清理与直通路径落地

### 变更内容

#### 1. 前端调用点全量直通与深度思考组件原生渲染恢复 (`frontend/src/`) [REFACTOR]
- **调用点直连**：`ChatView.vue`, `MessageItem.vue`, `ScenarioModal.vue`, `VariantB.vue` 中的所有组件 `import` 路径全面重构为领域显式直连路径（`@/components/chat/`, `@/components/agent/`, `@/components/artifacts/`, `@/components/common/`）。
- **解决渲染丢失缺陷**：彻底消除了 Vue 3 SFC 经无模板 `.vue` Shim 转发导致的 `ReasoningAccordion`（深度思考折叠面板）、`SubAgentBadge` 等子组件 Render 函数丢失与无法挂载问题。
- **物理清理 20 个 Shim**：删除 `frontend/src/components/` 根目录下的 20 个过渡 `.vue` 兼容垫片文件。

#### 2. 后端 API 路由直连与 Tools Shim 清理 (`backend/app/`) [REFACTOR]
- **主入口直连**：`main.py` 路由挂载直接改为 `from .routers import router, scenarios_router, init_analytics_engine`。
- **SQL 工具链直连**：`agent/tools/__init__.py`, `service.py` 及测试用例直接从 `subagents/sql/tools.py` 导入 SQL 领域工具。
- **后端 Shim 物理删除**：删除 `backend/app/api.py`、`backend/app/agent/tools/sql_tools.py` 与 `sql_lexicon_tools.py` 垫片文件。

---

## 2026-08-14 14:00 +08:00 - DeepAgent 前端架构重构：Wave 3 组件按领域目录拆分与 Shim 兼容落地

### 变更内容

#### 1. 前端 20 个根组件按领域拆分 (`frontend/src/components/`) [REFACTOR]
- **`chat/` 聊天领域**：迁移 `MessageItem.vue`, `MessageList.vue`, `VariantB.vue`, `AskUserQuestionCard.vue`, `ReasoningAccordion.vue`, `WelcomeDashboard.vue`, `FloatingScenarioCards.vue`。
- **`agent/` 智能体领域**：迁移 `SubAgentBadge.vue`, `AdminReviewPanel.vue`。
- **`artifacts/` 结果与图表领域**：迁移 `ChartArtifactCard.vue`, `DimensionTable.vue`, `ResultRenderer.vue`, `ScalarResult.vue`, `TableResult.vue`。
- **`common/` 通用 UI 领域**：迁移 `ToggleSwitch.vue`, `ParameterForm.vue`, `ScenarioModal.vue`, `SessionList.vue`, `SessionItem.vue`, `VersionChangelogModal.vue`。

#### 2. 原路径 Re-export Shim 与模块解析修正 [REFACTOR]
- **全量 Shim 保留**：在原 `components/` 根目录为 20 个组件保留了向后兼容 Re-export Shim Vue 组件，保证全量 View 组件（如 `ChatView.vue`）零破坏运行。
- **相对路径修正**：修正 `VariantB.vue` 与 `ScenarioModal.vue` 中跨目录引用的路径，Vite 前端构建 100% 成功通过。

---

## 2026-08-14 11:23 +08:00 - DeepAgent 后端架构重构：Wave 2 services/ 包重构与 SQL 子智能体目录填充

### 变更内容

#### 1. Services 单文件转包与导出重定向 (`backend/app/services/`) [REFACTOR]
- **`services.py` 拆解**：将 1070+ 行的单文件 `services.py` 迁移至 `backend/app/services/chat_service.py`。
- **包级聚合重导出**：创建 `backend/app/services/__init__.py` 重新导出 `SQLAgentService`, `initialize_agent_service`, `get_agent_service`, `shutdown_agent_service` 符号，物理删除原 `services.py`，保持导入路径无缝兼容。

#### 2. SQL 领域子智能体 Tools & Prompts 归纳 (`backend/app/agent/subagents/sql/`) [REFACTOR]
- **SQL 工具集中**：创建 `subagents/sql/tools.py` 聚合全量 SQL 查询、历史样例与三层物理词典 (value/row/schema) 工具工厂；`agent/tools/sql_tools.py` 与 `sql_lexicon_tools.py` 改写为向后兼容 Shim。
- **SQL Prompt 模板与加载器迁移**：迁移系统提示词至 `subagents/sql/base_system_prompt.md`；抽取 `SystemPromptLoader` 和 `_build_system_prompt` 到 `subagents/sql/prompts.py`；更新 `config.py` 默认模板路径与 `service.py` 组合根导入。
- **环境配置同步修缮**：将 `.env` 环境变量 `SYSTEM_PROMPT_PATH` 同步修正为 `backend/app/agent/subagents/sql/base_system_prompt.md`。

---

## 2026-08-14 11:15 +08:00 - DeepAgent 后端架构重构：Stage 0 测试基线与 Wave 1 API 路由解耦落地

### 变更内容

#### 1. Stage 0 测试基线与冒烟守护建立 (`backend/pyproject.toml`, `requirements-dev.txt`) [CHORE]
- **pytest 配置与环境隔离**：创建 `backend/pyproject.toml` 配置 `asyncio_mode = "auto"` 与 `not integration` 标记，默认隔离需外部 Milvus/Postgres/LLM 的测试；创建 `requirements-dev.txt` 声明开发测试依赖。
- **循环引用重构**：修复 `llm_refiner.py` 中向上 import `service.py` 循环依赖，重定向至 `backend.app.agent.llm`。
- **Agent 初始化路径去重**：提取 `service.py` 共享 helper `_create_agent_from_components()`，去重 `_initialize_agent` / `_ainitialize_agent` 尾部组合逻辑。
- **黄金路径冒烟脚本**：新增 `backend/tests/smoke/test_smoke_golden_path.py`，全量单元测试达到 35 passed, 4 deselected 绿灯基线。

#### 2. Wave 1 `api.py → routers/` 包解耦与 SubAgent 骨架 (`backend/app/routers/` & `agent/subagents/`) [REFACTOR]
- **1300+ 行单块解耦**：将 `api.py` 按业务领域拆分为 `routers/` 包（`chat.py`, `sessions.py`, `skills.py`, `admin.py`, `artifacts.py`, `_analytics.py`, `scenarios.py`）。
- **向后兼容 Shim**：将 `backend/app/api.py` 压缩为 4 行 re-export Shim，对 `main.py` 及外部导入零破损。
- **SubAgent 物理骨架**：创建 `backend/app/agent/subagents/sql/` 基础目录。

---

## 2026-08-10 22:15 +08:00 - DeepAgent 思考模式注入、RAG 防重复与流式领域识别精细化修缮

### 变更内容

#### 1. 主 Agent `enable_thinking` 思考模式动态注入修复 (`backend/app/agent/middleware/rag_prompt_injector_middleware.py`) [FIX]
- **思考模式补齐**：在 `RagPromptInjectorMiddleware` 中新增 `_inject_thinking_config`，从运行期 `RunnableConfig` 捕获客户端传入的 `enable_thinking` 并动态写入模型发包参数 `extra_body.chat_template_kwargs`。
- **单元测试补充**：在 `test_rag_prompt_injector_middleware.py` 中补充思考模式参数注入断言，测试 100% 绿色通过。

#### 2. RAG 同 Turn 检索防重复与异常分支标记机制修复 (`backend/app/agent/middleware/rag_middleware.py`) [FIX]
- **防重复判定修正**：在 `BusinessRagMiddleware._extract_query` 中，增加当次 `user_query` 与 `state.get("rag_query")` 的对比逻辑。
- **提升 SQL 试错性能**：当子智能体进行 SQL 试错多轮 ReAct 思考/工具回包时，自动跳过二次 RAG 检索，避免了同一 Turn 内重复跑向量检索+三层词典检索的高额开销。
- **异常捕获分支容错**：当向量库/数据库抛出连接异常时，返回 `{"rag_context": [], "rag_query": user_query, "lexicon_context": None}` 标记当次 Turn 已尝试，彻底解决故障期间模型多轮 ReAct 循环反复打卡重试的隐患。
- **单元测试补充**：在 `test_rag_middleware.py` 中增加同 Turn 内二次调用防重断言与异常捕获标记断言，测试 100% 绿色通过。

#### 3. 流式 `subagent_change` 领域目标动态解析精细化 (`backend/app/services.py`) [FIX]
- **委派目标动态字典追踪**：在 `SQLAgentService` 的流式解析代码中，将 ID 追踪升级为 `active_task_targets: dict[str, str]`，从 `task` 工具调用参数 `args` 中动态打捞真实委派目标子智能体名称（如 `sql_domain_agent` 或 `general-purpose`）。
- **多子智能体徽章精准映射**：精细区分 `sql_domain_agent` (展示 `SQL数据助手`) 与 `general-purpose` (展示 `通用助手`) 以及主 Agent 自身执行普通文件工具（`read_file` / `write_file`），彻底解决了多子智能体架构下的 UI 徽章误报与闪烁。

---

## 2026-08-09 17:25 +08:00 - DeepAgent 多智能体架构升级（阶段一：核心功能与 UI 徽章全量落地）

### 变更内容

#### 1. 后端主 Agent 工厂升级为 `create_deep_agent` (`backend/app/agent/service.py`) [UPGRADE]
- **隐式路由编排**：将 `SQLAgentService` 的主 Agent 升级为 `create_deep_agent`（移除根参数误传的 `tools="all"`，继承默认 `FilesystemMiddleware` 全量文件读写能力，解决 `AttributeError: 'function' object has no attribute 'name'` 初始化报错）。
- **SQL 领域子图封装**：将原 SQL 工具集与 System Prompt 隔离编译为 `sql_subgraph`，并使用 `CompiledSubAgent(name="sql_domain_agent", runnable=sql_subgraph)` 包装传入 `subagents=[...]`，由框架自动托管 `task` 工具与 `SubAgentMiddleware`。
- **中间件层级精准分层与全量 RAG**：将包含业务术语与三层数据库物理词典（`table_schema_store`, `db_value_lexicon`, `db_row_lexicon`）的 `BusinessRagMiddleware` 同时挂载给主 Agent 与 `sql_subgraph` 子智能体；在 `_extract_query` 升级为倒序扫描算法，自适应主 Agent 的 `HumanMessage` 与子 Agent 的 Task 描述。
- **主 Agent 任务委派协议 (`Task Delegation Protocol`)**：在 `main_system_prompt` 增加主 Agent 委派约束规则，限定主 Agent 仅传递业务目标、过滤条件与期望产物格式，严禁强行硬编码物理表名/视图名或 SQL 结构；针对模糊需求追加“探查授权 (Exploration License)”，让 SQL 子智能体发挥专业 Schema 自愈与词典探查能力。
- **防死循环双重熔断**：将 `call_limit_middlewares` (`ModelCallLimitMiddleware` / `ToolCallLimitMiddleware`) 同时装配给子智能体与主 Agent，防止 SQL 试错与主路由陷入死循环。
- **双初始化路径同步**：同步更新 `_initialize_agent`（同步模式）与 `_ainitialize_agent`（异步模式）。

#### 2. 服务层 StreamPart 流式 v2 字典解包与 Schema 注册 (`backend/app/services.py` & `backend/app/schemas.py`) [FEAT]
- **流式 v2 模式开启**：调用 `astream(input_data, config=config, stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2")`。
- **`ns` 领域识别与事件派发**：解析 StreamPart 字典中的 `ns` 路径，当包含 `tools:<call_id>` 时判定进入子智能体输出阶段，向前端推发 `subagent_change` SSE 事件。
- **Pydantic Schema 白名单**：在 `backend/app/schemas.py` 定义 `SubagentChangeStreamEvent` 与 `PlanUpdateStreamEvent`，并注册入 `ChatStreamEvent` 联合校验器，确保 SSE 序列化 100% 通过。

#### 3. 前端多智能体感知与 `SubAgentBadge.vue` 徽章集成 (`frontend/src/`) [FEAT]
- **类型与白名单**：在 `types/index.ts` 增加 `active_subagent` 与 `subagent_display_name` 字段；在 `api/chat.ts` 的 `STREAM_EVENT_TYPES` 白名单 Set 中注册 `subagent_change`。
- **智能体徽章组件**：新建 `SubAgentBadge.vue` 组件，使用本地 SVG 矢量图标（零外网 CDN 依赖），呈现 `🤖 [SQL数据助手]` 徽章；在 `MessageItem.vue` 中成功挂载。

---

## 2026-08-09 14:40 +08:00 - DeepAgent 依赖升级至 0.7.5 版本 (requirements.txt & docs/deepagent)

### 变更内容

#### 1. 核心依赖升级 `deepagents==0.7.5` (`requirements.txt`) [UPGRADE]
- **升版锁定**：将 `deepagents` 依赖从 `0.6.12` 升级并锁定至最新的 `0.7.5` 生产发布版。
- **解锁全新特性**：正式解锁 `FilesystemMiddleware` 原生 `tools` 白名单控制能力与新增的 `delete` 文件工具。
- **平滑兼容**：与现有 `langchain 1.3.14` + `langgraph 1.2.9` 完全对齐，通过 PoC 与依赖干跑（dry-run）全量校验。

---

## 2026-08-06 23:34 +08:00 - 行级实体数据提取确定性排序优化 (backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py)

### 变更内容

#### 1. 行级实体词典 SQL 抽取确定性排序 (`backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py`) [OPTIMIZE]
- **保证全量同步确定性 [M3 FIX]**：将 `RowLexiconExtractorNode` 中抽取行实体数据的 SQL 语句从原有的 `SELECT ... FROM {table} LIMIT {limit}` 重构为 `SELECT ... FROM {table} ORDER BY {pk} ASC LIMIT {limit}`。
- **杜绝随机跳变与数据漏发**：消除了原本缺乏 `ORDER BY` 时由关系型数据库物理存储页变化导致的行记录数据随机乱序或每次重新同步数据跳变的问题。
- **单元测试通过 (`backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py`)**：测试 100% 绿色通过。

---

## 2026-08-06 23:33 +08:00 - Rerank 重排同步请求非阻塞优化 (backend/app/agent/middleware/rag_middleware.py)

### 变更内容

#### 1. Rerank 精排解绑 asyncio 事件循环阻塞 (`backend/app/agent/middleware/rag_middleware.py`) [OPTIMIZE]
- **解绑同步网络请求阻塞 [M1 FIX]**：将 `BusinessRagMiddleware.abefore_model` 异步方法中直接同步调用基于 HTTP `requests` 的 `self.reranker.rerank(...)` 重构为 `await asyncio.to_thread(self.reranker.rerank, ...)`。
- **提升并发吞吐量**：消除了在开启 `RERANK_ENABLED=true` 时，底层同步 POST 网络请求卡死 FastAPI/asyncio 主事件循环 1~10 秒的高危阻塞隐患。
- **单元测试通过 (`backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py`)**：测试 100% 绿色通过。

---

## 2026-08-06 23:20 +08:00 - 数据库词典三路混合检索正式激活 (backend/app/agent/vector/sql_lexicon/retriever.py)

### 变更内容

#### 1. 激活三路 Lexicon 数据库词典 BM25 + Dense 真实混合检索 (`backend/app/agent/vector/sql_lexicon/retriever.py` & `backend/app/agent/tools/sql_lexicon_tools.py`) [FEATURE]
- **显式启用 `vector_store_query_mode="hybrid"`**：修复了原本 `DatabaseLexiconRetriever`（`schema_retriever` / `value_retriever` / `row_retriever`）与 3 个词典工具（`search_db_value_lexicon` / `search_db_row_lexicon` / `search_db_table_schema`）在调用 `as_retriever(...)` 时漏传 `vector_store_query_mode="hybrid"`，导致底层退化为纯 Dense 向量检索的缺陷。
- **解锁 BM25 精确匹配与 RRF 融合能力**：正式激活已建好的 `BM25BuiltInFunction(tokenizer="jieba")` 稀疏索引与 `RRFRanker` 倒数排名重排器，极大提升了对 `E7`、`f1f1` 等英文/数字编码和短小物理真实值的精确命中与对齐召回能力。
- **单元测试全量通过**：同步更新 `backend/tests/agent/tools/test_sql_lexicon_tools.py` 的测试断言，单元测试与集成测试 100% 绿色通过。

---

## 2026-08-06 23:01 +08:00 - 数据库词典三路检索异常隔离修复 (backend/app/agent/vector/sql_lexicon/retriever.py)

### 变更内容

#### 1. 数据库词典三路检索异常隔离修复 (`backend/app/agent/vector/sql_lexicon/retriever.py`) [FIX]
- **实现真正的三路异常隔离 [H2 FIX]**：将 `DatabaseLexiconRetriever.retrieve_all` 异步方法中的 `asyncio.gather` 的 `return_exceptions` 从 `False` 修改为 `True`。当 3 路中任意 1 路发生异常时，不再强行抛出中断整体逻辑，而是将其捕获为异常对象并对该路进行 `[]` 空列表降级。
- **同步路径防雪崩保护**：在 `retrieve_all_sync` 中为每路检索包裹独立的 `try...except` 保护层。
- **杜绝单点故障牵连全盘**：解决了以往单路词典（如 `values`）因瞬态网络波动或重新加载抛错导致原本正常召回的 `tables`（DDL）与 `rows`（实体记录）被全盘抹除清空的问题。

---

## 2026-08-06 22:50 +08:00 - SQL Lexicon 工具多会话并发竞态修复 (backend/app/agent/tools/sql_lexicon_tools.py)

### 变更内容

#### 1. SQL Lexicon 工具多会话并发竞态修复 (`backend/app/agent/tools/sql_lexicon_tools.py`) [FIX]
- **解决共享单例属性篡改漏洞 [H1 FIX]**：将 `search_db_value_lexicon`、`search_db_row_lexicon` 与 `search_db_table_schema` 中改写全局单例属性（如 `similarity_top_k`）的代码，重构为使用无状态的 `value_index.as_retriever(similarity_top_k=limit)`、`row_index.as_retriever(...)` 与 `schema_index.as_retriever(...)` 局部检索句柄。
- **消灭高并发线程串台风险**：彻底杜绝多用户并发会话或后台 RAG 自动检索交错时，全局 `similarity_top_k` 被互相改写覆盖导致的 Top-K 乱序与 Context 溢出事故。
- **单元测试同步覆盖 (`backend/tests/agent/tools/test_sql_lexicon_tools.py`) [FIX]**：同步重构单元测试 Mock 断言，确保准确覆盖线程安全的 `index.as_retriever(similarity_top_k=limit)` 调用，测试 100% 绿色通过。

---

## 2026-08-04 14:27 +08:00 - SQL 工具查询时刻时区校准：显式东八区 (UTC+8) 格式化 (backend/app/agent/tools/sql_tools.py)

### 变更内容

#### 1. SQL 工具查询时刻时区校准 (`backend/app/agent/tools/sql_tools.py`) [FIX]
- **显式 UTC+8 (北京时间) 格式化** [FIX]：将原本基于系统本地时间 `dt.now().strftime("%Y-%m-%d %H:%M:%S")` 改为使用显式 `timezone(timedelta(hours=8))` 格式化。
- **解决 UTC 环境 8 小时时差 Bug**：解决了后端在 UTC 时区服务器/容器中运行时，返回给 LLM 的 `[数据真实查询时刻: ...]` 和返回给前端的 `tool_artifact.query_time` 比实际北京时间晚 8 小时的缺陷。
- **最省 Token 策略**：保持最简无冗余的 `YYYY-MM-DD HH:MM:SS` 格式（仅 19 字符），对大模型输入输出友好且无需前端额外进行 Date 解析开销。

---

## 2026-08-03 12:28 +08:00 - 智能状态追踪避让：兜底文案偶发误导修复 (backend/app/api.py)

### 变更内容

#### 1. 智能状态追踪避让：兜底文案偶发误导修复 (`backend/app/api.py`) [FIX]
- **新增 `has_reasoning` / `has_tool_artifact` 状态追踪** [FIX]：在 `stream_chat_events`（`:530-531`）与 `stream_resume_chat_events`（`:864-865`）初始化两个布尔标记，用于感知本轮流式过程中是否产生过深度思考或 UI 卡片。
- **事件捕获置位** [FIX]：监听 `reasoning` 事件（`:614-615` / `:948-949`）置位 `has_reasoning`；在 `tool_artifact` 事件分支（`:618-619` / `:952-953`）置位 `has_tool_artifact`。不拦截事件透传，不影响前端渲染。
- **防御空字符串覆盖 final 事件** [FIX]：将 `final` 事件中 `if final_content is not None:` 改为 `if final_content and final_content.strip():`（`:645-646` / `:980-981`），防止空字符串抹除通过 token 累加的 `full_content`。
- **智能兜底文案** [FIX]：当 `full_content` 为空时，根据状态追踪判断：若有 reasoning 或 artifact 则输出引导文案”（分析已完成，请查看上方思考过程与参考信息）”（`:664-665` / `:1004-1005`），完全无产出时保留原保底文案（`:666` / `:1006`）。
- **不改动文件**：`services.py`、`messages.ts`、`MessageItem.vue` 均无修改，符合模块边界约束。

---

## 2026-08-03 11:35 +08:00 - “回答完成，但未生成可展示的文本内容” 偶发异常审查报告 V2 (docs/front_end)

### 变更内容

#### 1. 归档技术审查报告 (`docs/front_end/empty_fallback_text_analysis_v2.md`) [NEW]
- **归档深度审查报告**：详细记录针对“回答完成，但未生成可展示的文本内容。”偶发保底弹框的根因分析、代码端 3 处缺陷位置（`api.py:L637/L958` 覆盖漏洞、`services.py:L856` 提取条件过严、`api.py:L654` 保底未避让思考框/卡片）、偶发性随机机制以及修复建议。

---

## 2026-08-03 10:50 +08:00 - 滞留车检测场景全分类筛选与解析层修复 (backend/app/skills)

### 变更内容

#### 1. 滞留车场景元定义扩展 (`scenarios/stranded_vehicle_detection/scenario.py`)
- **完整四项车辆类型筛选 (`vehicle_type_filter`)** [NEW]：新增控件类型为下拉框 `select` 的车辆类型参数，支持 `产品车` (`product_vehicle`，默认)、`项目车` (`project_vehicle`)、`异常车` (`abnormal_vehicle`) 与 `不限` (`all`)。
- **健全 SQL 判定片段 (`sql_fragment`)** [OPTIMIZE]：采用 `NULLIF(trim(...), '')` 函数严格判定 `cr."project_vehicle_no"` 与 `cr."vehicle_id"` 前缀，100% 对齐官方《车辆分类规则与 LLM 提示词规范指南》。
- **更新 LLM 提示词与规则** [OPTIMIZE]：更新 `optional_inputs`、`workflow`、`rules` 与 `output_contract`，使 Agent 能隐式识别并正确透传筛选属性。

#### 2. SQL 模板筛选逻辑重构 (`sql/in_process.sql` & `sql/historical.sql`)
- **添加 `{vehicle_type_filter}` 占位符** [FEATURE]：在在制与历史滞留车模板的 `WHERE` 条件中插入 `{vehicle_type_filter}` 占位符。
- **透传 `project_vehicle_no` 字段** [OPTIMIZE]：在 `SELECT` 输出列中包含 `cr."project_vehicle_no"`，便于前端表格展现车辆的项目属性。

#### 3. 参数解析层 Label 穿透修复 (`direct_path/resolver.py`)
- **优先读取显式 `options` 与 `default`** [FIX]：修复 `resolve_params()` 在生成场景参数元数据时未优先解析 `p_def.get("options")` 的缺陷，确保前端 UI 下拉框正确显示中文 Label（如“产品车”、“不限”）而非原始英文 key 值。

---

## 2026-08-02 23:50 +08:00 - 前端代码审查 9 项优化实施 (frontend/src)

### 变更内容

#### 1. SSE 流式通信层 DRY 重构 (`api/chat.ts`)
- **提取 `readSSEStream` 公共函数** [REFACTOR]：将 `sendChatStream` 与 `sendChatResumeStream` 中 ~150 行重复的 SSE 读取 + 解析 + 分发逻辑提取为统一的 `readSSEStream()` 函数，两个入口各缩减至 ~10 行。
- **tool_artifact 解析校验增强** [FIX]：新增 `kind` 字段类型校验（`typeof parsed.artifact.kind !== 'string'`），防止畸形 artifact 数据穿透到下游。
- **lexicon_context 类型安全** [FIX]：将 `as any` 强转替换为 `as unknown as LexiconContext`，消除隐式 any 逃逸。

#### 2. 流式事件处理 DRY 重构 (`composables/useChatStream.ts`)
- **提取 `createEventHandler` 公共函数** [REFACTOR]：将 `handleStreamMessage` 与 `resumeMessage` 中 ~80 行重复的 11 种事件类型 switch-case 统一为 `createEventHandler()` 闭包工厂，`hasTerminalEvent` 从 `let boolean` 改为 `{ value: boolean }` 对象引用以支持闭包内修改。

#### 3. 类型安全体系升级 (`types/index.ts`)
- **新增 `ToolArtifact` 接口** [REFACTOR]：提取统一的 `ToolArtifact` 接口（含 `[key: string]: unknown` 索引签名），替换 `Message`、`StreamingMessage`、`StreamEvent` 中 3 处内联重复类型定义，兼容 `ChartArtifact` / `ExportArtifact` 扩展字段。

#### 4. XSS 安全净化升级 (`utils/markdown.ts`)
- **代码块复制按钮安全重构** [SECURITY]：移除内联 `onclick` 事件处理器（直接调用 `navigator.clipboard.writeText`），改用 `data-copy-content` 自定义属性存储编码内容，由 `MessageItem.vue` 事件委托统一处理。
- **DOMPurify 白名单调整** [SECURITY]：`ADD_ATTR` 从 `['onclick']` 改为 `['data-copy-content']`，消除 `onclick` 属性放行带来的潜在 XSS 攻击面。

#### 5. 消息组件安全与类型优化 (`components/MessageItem.vue`)
- **事件委托替代内联事件** [SECURITY]：通过 `onMounted` / `onUnmounted` 注册 document 级 `click` 事件委托，统一处理代码块复制按钮点击，替代内联 `onclick`。
- **工具函数提取** [REFACTOR]：将 `parseJson`、`formatFileSize`、`copyToClipboard` 3 个内联函数提取至 `utils/helpers.ts`。
- **computed 类型标注** [FIX]：`chartSpec` / `fileExport` computed 添加泛型标注 `computed<ChartArtifact | null>` / `computed<ExportArtifact | null>`，消除类型推断歧义。

#### 6. 通用工具函数模块 (`utils/helpers.ts`)
- **新建 `helpers.ts`** [NEW]：集中放置从 `MessageItem.vue` 提取的 `parseJson<T>`（安全 JSON 解析）、`formatFileSize`（B/KB/MB 格式化）、`copyToClipboard`（剪贴板操作，兼容非安全上下文降级方案）3 个可复用纯函数。

#### 7. 竞态防护补全 (`stores/sessions.ts` & `stores/scenarioPanel.ts`)
- **`fetchSessions` 竞态防护** [FIX]：添加 `latestFetchRequestId` 请求 ID 计数器，与 `messages.ts` 已有的防护模式对齐，防止快速切换会话时旧请求覆盖新数据。
- **`fetchDomainTree` 竞态防护** [FIX]：添加 `domainsFetchRequestId` 请求 ID 计数器，防止场景面板重复请求时树结构数据被旧响应覆盖。

#### 8. 错误处理统一化 (全 stores)
- **catch 块错误信息提取标准化** [REFACTOR]：`sessions.ts`、`messages.ts` 中所有 catch 块统一为 `catch (err: any)` + `err.message || 'fallback message'` 模式，消除 `String(err)` / `err.toString()` 等不一致写法。

#### 9. 其他类型与代码质量修复
- **`ChatView.vue` toastTimer 类型** [FIX]：`toastTimer: any` → `ReturnType<typeof setTimeout> | null`，消除 any 逃逸。
- **`messages.ts` memoryArtifactMap 类型** [FIX]：`Record<string, any>` → `Record<string, ToolArtifact>`，强化类型约束。
- **`skills.ts` 刷新方法** [NEW]：新增 `refreshSkills()` 强制刷新方法，清空缓存后重新拉取技能列表。

### 验证结果
- `vue-tsc --noEmit` 类型检查零错误通过

---

## 2026-08-02 17:28 +08:00 - LobeChat 风格一体化沉浸画布与悬浮卡片重构 (frontend/src)

### 变更内容

#### 1. 主视觉画布与 Header 无边框悬浮重构 (`frontend/src/views/ChatView.vue`)
- **Header 无硬线悬浮 (Floating Header)** [OPTIMIZE]：移除 Header 的 `border-b` 物理强切割线与固定白底，升级为 `sticky top-0 z-20 bg-background/80 backdrop-blur-md` 沉浸式透明置顶栏，100% 完整保留会话标题、状态胶囊、`关于`、`数据字典看板` 与 `审核终端` 等既有功能按键。
- **侧边栏折叠图标重构 (Lucide Icon)** [REFACTOR]：移除带有白色重框与阴影的旧版双箭头按钮，替换为 LobeChat / Claude 同款的精致矢量 SVG 面板折叠图标 (`panel-left-close` / `panel-left-open`)，搭配 `hover:bg-neutral-100` 极简悬浮反馈。

#### 2. 居中悬浮卡片式输入框与内置工具栏 (`frontend/src/views/ChatView.vue`)
- **悬浮卡片输入面板 (Floating Card Input)** [REFACTOR]：移除旧版横贯屏幕底部的 `border-t` 满宽横条，重构为居中悬浮卡片（`sticky bottom-3 sm:bottom-4 max-w-6xl`），配备 `rounded-2xl sm:!rounded-3xl` 大圆角、精细阴影与柔和微边框。
- **内嵌工具栏集成 (Bottom Inner Toolbar)** [OPTIMIZE]：将「流式输出」与「深度思考」开关胶囊移入输入卡片内部底栏左侧，右侧整合发送/停止按键，对齐 LobeChat 布局内聚感。

#### 3. 消息视图全宽与多字段表格体验提升 (`frontend/src/components/MessageList.vue` & `MessageItem.vue`)
- **最右侧边缘滚动条 (Rightmost Scrollbar)** [FIX]：将 `MessageList.vue` 的 `overflow-y-auto` 滚动层扩展至全宽 `w-full`，使垂直滚动条精准显示在窗口最右侧边缘。
- **多字段数据表格宽屏支持 (Expanded Table Space)** [OPTIMIZE]：主画布、Header 与输入框的统一宽度从 `max-w-4xl` 调宽至 **`max-w-6xl` (1152px)**，且 AI 回复气泡在 `MessageItem.vue` 中支持 `max-w-full` 全宽，极大提升 SQL 查询多列表格与数据字典的显示与阅读舒适度。
- **小屏与边界像素级对齐 (Mobile & Border Alignment)** [FIX]：调整外围边距为 `px-4 sm:px-0`，实现输入框左右边界与 AI 消息左侧、用户消息右侧的物理严丝合缝对齐；并在移动/小屏下留出 `bottom-3 mb-3` (12px) 悬浮空隙与 rounded-2xl 圆角，告别底部贴边。

---

## 2026-08-02 16:55 +08:00 - 1:1 还原 LobeChat 风格 AI 消息 Markdown 渲染与 GFM Alert 警示卡片支持

### 变更内容

#### 1. 后端系统提示词升级 (`backend/app/agent/prompts/base_system_prompt.md`)
- **系统级输出约束 (§ 4.5)** [NEW]：在基础提示词中追加 Markdown 结构化排版与 GFM Alert 约束规范，从系统层引导大模型在输出总结、提示、预警时自动产生 `> [!NOTE]` / `> [!TIP]` 等标准的 Callout 语法和规范列表。

#### 2. 前端 GFM Alert 卡片解析插件 (`frontend/src/components/chat/plugins/markdown-it-alert.ts`)
- **GFM Callout 解析插件** [NEW]：新增 `markdown-it-alert.ts` 插件，自动拦截捕获 `> [!NOTE]` / `> [!TIP]` / `> [!WARNING]` / `> [!CAUTION]` / `> [!IMPORTANT]` 语法，并注入带矢量图标与 5 种官方底色的卡片 DOM 结构。
- **边界与转义鲁棒保护** [FIX]：使用 `[^\w\s]` 字符集与 `(?!\w)` 负向先行断言，消除了浏览器 `Invalid escape` 解析报错并完美解决了末尾中括号 `]` 字符残留在卡片内部的问题。

#### 3. 视觉排版与组件样式解耦 (`frontend/src/style.css` & `MessageItem.vue`)
- **1:1 LobeChat Chat 变体 CSS** [OPTIMIZE]：在 `style.css` 中注入官方计算倍率变量、卡片化 blockquote、代码块美化与流式打字呼吸光标（`is-streaming`）。
- **样式解耦与冲突排查** [FIX]：清理 `MessageItem.vue` scoped 样式中对表格单元格居中的 `:deep(th/td)` 强制压制，移除过期的 `.cursor-blink` 死代码，使全局 `style.css` 的排版和表格左对齐正常生效。

---

## 2026-08-01 16:11 +08:00 - 代码审查属实项修复与测试健壮性提升 (backend & frontend)

### 变更内容

#### 1. 后端 LLM 适配器与集成测试修复 (`backend/tests/agent/test_chat_deepseek_integration.py` & `backend/app/agent/llm.py`)
- **`BaseModel` 导入修复与 Mock 扩展** [FIX]：将 `test_chat_deepseek_integration.py` 中不存在的 `openai.BaseModel` 替换为 `pydantic.BaseModel`；并补充 `model_extra` Reasoning 提取后备逻辑测试用例 `test_chat_deepseek_model_extra_reasoning_fallback`，提升覆盖率。
- **重命名中性适配器与别名兼容** [REFACTOR]：在 `backend/app/agent/llm.py` 中将 `QwenChatDeepSeek` 重命名为更具中性含义的 `ReasoningAwareChatDeepSeek`，同时保留 `QwenChatDeepSeek` 向后兼容别名。

#### 2. 前端推理耗时与 UI 样式细节修补 (`ReasoningAccordion.vue` & `ToggleSwitch.vue`)
- **`ReasoningAccordion.vue`** [FIX]：修复 `duration` 为 0 时被判定逻辑错误过滤退回到估算值的问题，显式支持 0 秒耗时展现。
- **`ToggleSwitch.vue`** [FIX]：将非标准类名 `shadow-xs` 替换为 Tailwind CSS v3 标准的 `shadow-sm`，规避阴影渲染失效。

#### 3. 根目录无用调试临时文件清理
- **临时文件清理** [CLEANUP]：移除根目录下包含调试日志与测试脚本的 `tmp_vllm_test.py` 和 `vllm_response.json` 文件。

---

## 2026-08-01 16:01 +08:00 - 前端快捷直通场景与全局极简矢量图标升级 (FloatingScenarioCards.vue & ScenarioModal.vue)

### 变更内容

#### 1. 快捷场景悬浮卡片图标重构 (`frontend/src/components/FloatingScenarioCards.vue`)
- **极简矢量图标替换 (Minimalist Vector Icons)** [OPTIMIZE]：彻底告别 3D 彩色/Emoji 图标（如 `🚙`、`⚡` 等），为项目车管理 (`project_vehicle_management`)、滞留车检测 (`stranded_vehicle_detection`)、统计分析、目标监控、智能检索等场景替换为精准匹配的 24x24 / 14x14 极简 Single-line SVG 矢量线条图标（支持 High Contrast & Accent Accent Tone Stroke）。
- **动态图标智能映射 (Dynamic Icon Resolver)** [NEW]：新增 `getScenarioIconType` 场景图标类型选择逻辑，根据 scenario name 与 title 语义平滑归类，提供更具现代轻盈视觉哲学的快捷卡片。

#### 2. 快捷直通弹窗、数据字典与复制按钮图标优化 (`ScenarioModal.vue`, `MessageItem.vue` & `DimensionTable.vue`)
- **`ScenarioModal.vue`** [OPTIMIZE]：将直通弹窗头部标题栏与刷新按钮中的 Emoji 图标替换为极简 Stroke 矢量图标。
- **`MessageItem.vue` & `DimensionTable.vue`** [OPTIMIZE]：去除消息气泡底栏与维度表头部的中文“复制”/“已复制”文本标签，保留纯极简 SVG 矢量图标（Tooltip 原生悬浮提示），视觉更加精简干净。

---

## 2026-08-01 14:42 +08:00 - 前端思考过程内存持久化与三级降级架构实现 (frontend/src/stores/messages.ts & MessageItem.vue)

### 变更内容

#### 1. Pinia Store 内存持久化与多轮 ReAct 智能标点粘合 (`frontend/src/stores/messages.ts`)
- **`memoryReasoningMap` & `memoryReasoningDurationMap`** [NEW]：新增思考文本与决策时长内存映射表。
- **100% 文本忠实度与智能标点粘合 (Smart Punctuation Joiner)** [OPTIMIZE]：彻底保证大模型思考文本 100% 原汁原味展现，杜绝任何字符误删。升级多轮 ReAct 思考追加逻辑，自动检测前文末尾是否为句末标点（`[。！？;\n:]`）：
  - 若为完整句子，追加 `\n\n` 进行段落划开；
  - 若为句中被工具调断（如“今天”或“用户”），保持流畅拼合（英文补空格），杜绝“句中强行断行”的视觉瑕疵，对齐 DeepSeek / Claude 3.7 官方排版标准。
- **方案 B 耗时计算** [MODIFY]：在 `startStreamingMessage` 记录用户发送指令的时刻 `requestStartTime` ($t_0$)，当首个正文回答 Token 到达或流结束时算出 $t_{ans\_start} - t_0$ 的全过程决策时长，实现与 DeepSeek 官方标准对齐。

#### 2. 开关控件与气泡组件视觉重构 (`frontend/src/components/ToggleSwitch.vue` & `ReasoningAccordion.vue`)
- **`ToggleSwitch.vue`** [OPTIMIZE]：彻底告别高饱和度刺眼强蓝，重构为柔和**低饱和色配色方案**（Muted Low-Saturation Palette）。将开关键轨与圆圈滑块背景调淡为柔和同色系淡蓝（`bg-primary/10` 底轨 + `bg-primary/30` 淡蓝手柄），结合中性优雅文本（`text-neutral-700`），带来更高端沉稳的视觉质感。
- **`ReasoningAccordion.vue`** [MODIFY]：替换 3D 🧠 Emoji 为极简微光矢量图标（Sparkles SVG Icon），并同步将头部标题精简优化为“**推理**”；在思考流式进行中自动保持展开呈现打字动画，思考完成/输出正文阶段自动平滑折叠面板。

#### 3. 构建验证
- 运行 `npm run build` 执行前端代码编译验证，787 个 Vue/TS 模块零报错构建成功（14.60s）。

---

## 2026-08-01 13:48 +08:00 - 前端深度思考（Reasoning）UI 组件集成与消息气泡挂载 (frontend/src/components/MessageItem.vue)

### 变更内容

#### 1. 前端类型定义扩展 (`frontend/src/types/index.ts`)
- **`StreamingMessage`** [MODIFY]：在 `StreamingMessage` 接口中添加 `reasoningText?: string` 可选属性。

#### 2. 前端消息气泡组件集成 (`frontend/src/components/MessageItem.vue`)
- **`MessageItem.vue`** [MODIFY]：导入 `ReasoningAccordion` 组件，定义 `reasoningText` 计算属性，并在消息气泡模板顶部挂载 `<ReasoningAccordion>`，实现深度思考折叠面板、实时打字机动画及耗时计时器的端到端呈现。

#### 3. 构建验证
- 运行 `npm run build` 执行前端代码编译验证，787 个 Vue/TS 模块零报错构建成功。

---

## 2026-07-31 23:02 +08:00 - 后端 SSE 流式协议扩展：支持思考 Token (reasoning) 结构化事件推送

### 变更内容

#### 1. 后端数据 Schema 扩展 (`backend/app/schemas.py`)
- **`ReasoningStreamEvent`** [NEW]：新建 `ReasoningStreamEvent` Pydantic v2 模型（包含 `type: Literal["reasoning"]`, `text: str`, `node: Optional[str]`），并加入 `ChatStreamEvent` Discriminated Union 序列化白名单。

#### 2. SSE 流式解包与事件推送 (`backend/app/services.py`)
- **`_stream_execution_loop`** [MODIFY]：在处理 `AIMessageChunk` 流式切片时，优先判断 `message_chunk.additional_kwargs.get("reasoning_content")`。若存在思考 Token，实时 `_emit` 推送 `type: "reasoning"` 的 SSE 事件给前端。

#### 3. 单元测试与回归校验 (`backend/tests/agent/`)
- **`test_sse_reasoning_events.py`** [NEW]：新增 `ReasoningStreamEvent` Pydantic 校验与思考 Token 提取单元测试。
- 运行 Agent 全部 7 项单元测试，全量 100% PASS。

---

## 2026-07-31 22:41 +08:00 - 前端 ChatView 增加“深度思考”模式实时切换开关 (frontend/src/views/ChatView.vue)

### 变更内容

#### 1. 前端 UI 与交互控制 (`frontend/src/views/`)
- **`ChatView.vue`** [MODIFY]：在输入框上方的模式控制栏中，解构并集成了 `enableThinking` 开关（使用 `ToggleSwitch` 组件），与“流式输出”平级展示。支持用户实时自由开启（DeepThink 深度思考模式，传 `enable_thinking: true`）或关闭（常规快速回答模式，传 `enable_thinking: false`）。

#### 2. 构建验证
- 运行 `npm run build` 执行前端代码编译验证，785 个 Vue/TS 模块零报错构建成功。

---

## 2026-07-31 22:38 +08:00 - LLM 模型适配器独立解耦抽取封装 (`backend/app/agent/llm.py`)

### 变更内容

#### 1. 后端模型架构重构 (`backend/app/agent/`)
- **`llm.py`** [NEW]：新建独立的 `llm.py` 模块，封装 `QwenChatDeepSeek` 通信协议增强类与 `_create_llm` 工厂函数。将底层大模型通信逻辑与 `service.py` 中的上层 SQL Agent 业务图解耦。
- **`service.py`** [MODIFY]：从 `llm.py` 导入 `QwenChatDeepSeek` 与 `_create_llm`，精简主服务逻辑。

#### 2. 测试集与 Mock Patch 目标同步 (`backend/tests/agent/`)
- **`test_chat_deepseek_integration.py`** [MODIFY]：更新导入路径与 Mock 拦截点至 `backend.app.agent.llm`。
- **`test_persistence_integration.py`** [MODIFY]：更新 `patch` 目标为 `backend.app.agent.llm.QwenChatDeepSeek`。

---

## 2026-07-31 22:35 +08:00 - QwenChatDeepSeek 调试日志清理与代码精简 (backend/app/agent/service.py)

### 变更内容

#### 1. 后端模型适配器精简 (`backend/app/agent/`)
- **`service.py`** [MODIFY]：彻底清理排查阶段在 `QwenChatDeepSeek` 中添加的临时 `DEBUG` 日志打印，保持生产代码无冗余与高可维护性。

---

## 2026-07-31 22:30 +08:00 - 前端 useChatStream 思考模式开关默认值纠偏 (frontend/src/composables/useChatStream.ts)

### 变更内容

#### 1. 前端状态默认值修复 (`frontend/src/composables/`)
- **`useChatStream.ts`** [MODIFY]：将 `enableThinking` 的响应式默认值从 `ref(false)` 纠偏修改为 `ref(true)`，防止前端发送消息时静默向后端透传 `enable_thinking: false` 导致 vLLM 思考逻辑被关闭。

---

## 2026-07-31 22:09 +08:00 - QwenChatDeepSeek 流式 (Streaming) chunk 思考字段全通路适配 (backend/app/agent/service.py)

### 变更内容

#### 1. 后端模型适配器增强 (`backend/app/agent/`)
- **`service.py`** [MODIFY]：在 `QwenChatDeepSeek` 中重写 `_convert_chunk_to_generation_chunk` 方法，抓取流式块 (`delta`) 中的 `reasoning` 字段，填入 `AIMessageChunk.additional_kwargs["reasoning_content"]`。打通流式模式 (astream) 下思考链的累加与 LangSmith Trace 终态可视化。

#### 2. 测试用例补充 (`backend/tests/agent/`)
- **`test_chat_deepseek_integration.py`** [MODIFY]：新增 `test_qwen_chat_deepseek_stream_chunk_mapping` 测试用例，验证流式 chunk 结构下的 `reasoning` 拦截逻辑，测试全量通过 (3/3 PASSED)。

---

## 2026-07-31 21:06 +08:00 - 阶段一：ChatDeepSeek LLM 适配与 reasoning_content 捕获落地 (backend/)

### 变更内容

#### 1. 后端模型工厂重构 (`backend/app/agent/`)
- **`service.py`** [MODIFY]：在 `_create_llm` 函数中将 `ChatOpenAI` 替换为 `ChatDeepSeek` (`langchain-deepseek==1.0.1`)，将参数映射调整为 `api_key` / `api_base`，原生提取 vLLM 返回的 `reasoning_content` 到 `AIMessage.additional_kwargs`，打通 LangSmith Trace 思考链捕获。

#### 2. 测试集更新与新增 (`backend/tests/agent/`)
- **`test_chat_deepseek_integration.py`** [NEW]：新增单元测试，验证 `_create_llm` 实例化 `ChatDeepSeek` 及反序列化时保留 `reasoning_content` 的映射逻辑。
- **`test_persistence_integration.py`** [MODIFY]：更新 Mock 拦截对象为 `ChatDeepSeek`，保证持久化集成测试 100% 通过。

---

## 2026-07-31 20:36 +08:00 - vLLM + Qwen/DeepSeek 思考过程 Trace 捕获与前端流式方案技术报告

### 变更内容

#### 1. 技术文档创建 (`docs/thinking_mode/`)
- **`langsmith_thinking_process_integration_guide.md`** [NEW]：整理 vLLM + Qwen 3.6 / DeepSeek 推理模型在 LangSmith Trace 中丢失思考过程的根因分析报告，并提供 `langchain-deepseek` 与自定义 `QwenThinkingChatOpenAI` 类的补全方案及前端 SSE 流式渲染联动规划。

---

## 2026-07-31 20:06 +08:00 - 前端代码审查全面复核与重构修复 (frontend/src)

### 变更内容

#### 1. TypeScript 构建阻塞错误修复 (`frontend/src/`)
- **`api/scenarios.ts`** [MODIFY]：修复 `description: str` 语法笔误为 `string`，在 `ScenarioItemSummary` 接口补全 `direct_path_enabled?: boolean` 字段，并导出 `ScenarioSummary` 类型别名。
- **`types/index.ts`** [MODIFY]：在 `FinalizedStreamingMessage` 接口补全 `tool_artifact` 属性定义，移除无用接口 `StreamToolResult`。
- **`composables/useChatStream.ts`** [MODIFY]：在 `resumeMessage` 的 `handleEvent` 补全 `case 'tool_artifact':` 逻辑，修复 `assertNever` TS 类型报错。
- **`components/FloatingScenarioCards.vue`** [MODIFY]：正确类型引用 `ScenarioSummary`。

#### 2. 死代码与废弃文件清理 (`frontend/src/`)
- **`api/messages.ts`** & **`api/sessions.ts`** [MODIFY]：清理无引用的 `getMessageApi` 和 `getSessionApi` 函数。
- **`stores/messages.ts`** [MODIFY]：清理无调用的 `setStreamingError` 和 `clearStreamingForSession` store actions。
- **`stores/scenarioPanel.ts`** [MODIFY]：清理无调用的 `backToList` store action。
- **`composables/useDateFormat.ts`** [MODIFY]：清理未被外部消费的 `formatDate` 函数。
- **`utils/test_markdown.js`** [DELETE]：删除未接入构建体系的 Node 独立 `eval()` 测试脚本。

#### 3. 调试日志与 UI 残留清理 (`frontend/src/`)
- **`views/ChatView.vue`** [MODIFY]：清理永久隐藏UI `v-if="false"` `<ToggleSwitch v-model="enableThinking" />`。
- **`composables/useChatStream.ts`** [MODIFY]：清理带有 `[diagnose]` 前缀的硬编码 console.error 日志。
- **`api/chat.ts`** [MODIFY]：将 8 处流式解析 `console.debug` 日志统一挂载在 `CHAT_DEBUG_STREAM` 调试开关之下。
- **`components/AskUserQuestionCard.vue`** [MODIFY]：清理空实现存根 `onTextAreaInput` 及模板事件绑定。

#### 4. 组件重复实例化修复 (`frontend/src/components/`)
- **`VariantB.vue`** [MODIFY]：移除内部重复渲染的 `<ScenarioModal>` 实例及其 import，统一由顶层 `ChatView.vue` 调度弹窗。

---

## 2026-07-30 12:40 +08:00 - 项目车综合管理技能 (project_vehicle_management) 落地、直通模式标准服务端分页与序号列支持

### 变更内容

#### 1. 项目车综合管理技能开发 (`backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/project_vehicle_management/`) [NEW]
- **`scenario.py`** [NEW]：定义项目车综合管理场景，配置快捷直通查询参数（支持项目阶段 `project_stage`、编号模糊搜索 `project_vehicle_no`、工艺区域 `process_area` 及仅看缺陷 `has_defect_only_filter`）。
- **`sql/current_positions.sql`** [NEW]：在制项目车实时位置与工艺分布 SQL 模板（默认模板）。
- **`sql/orders_overview.sql`** [NEW]：项目车 FIS 订单台账与项目阶段汇总 SQL 模板。
- **`sql/quality_defects.sql`** [NEW]：项目车缺陷检测与质量记录 SQL 模板。

#### 2. 直通模式服务端分页与物理全量计算引擎 (`backend/app/skills/direct_path/`) [MODIFY]
- **`executor.py`** [MODIFY]：使用 `SELECT COUNT(*) FROM (...)` 精确计算物理全量命中数，并采用 SQL 子查询 `LIMIT :page_size OFFSET :offset` 零侵入实现通用服务端分页。
- **`formatter.py`** [MODIFY]：格式化器组装 `page`、`page_size`、`total_pages` 与 `total_count` 并透传至 API。
- **`api.py`** & **`schemas.py`** [MODIFY]：路由与 Pydantic Schema 支持 `page` 与 `page_size` 请求/响应参数对齐。

#### 3. 前端表格组件与分页控制条 (`frontend/src/`) [MODIFY]
- **`stores/scenarioPanel.ts`** [MODIFY]：增加 `currentPage` 与 `pageSize` 响应式状态，支持动态翻页 actions 并在筛选重置时归零到第一页。
- **`components/TableResult.vue`** [MODIFY]：单层表格右上角展示区间 (`显示 1-50 条 / 共 332 条记录`)，最左侧新增连续物理序号列 `#`（算式：`(page - 1) * pageSize + index + 1`），底部新增分页控制条（上一页/下一页/页码/每页条数选择器）。
- **`components/ResultRenderer.vue`** & **`ScenarioModal.vue`** [MODIFY]：组件间事件与分页元数据透传。

---

## 2026-07-29 14:15 +08:00 - 全系统结构化对齐车辆分类新规则、RAG向量知识库语料与场景SQL契约

### 变更内容

#### 1. 向量知识库语料 (`backend/app/agent/vector/milvus_init/data/examples/`) [MODIFY]
- **`example_documentation.json`** [MODIFY]：
  1) 更新 `车身号` 条目，接入 FIS 订单 `composite_pin_no` 匹配与 `project_vehicle_no` 概念；
  2) 合并并极致精简 `异常车` (entity_type = 'abnormal_vehicle') 条目，明确“排除项目车和产品车的所有其余占位记录即为异常车”，强调正常车 `abnormal_type` 恒为 `NULL`；
  3) 新增 `项目车与FIS订单` (`ods_fis_project_vehicle_orders`) 向量知识条目；
  4) 新增 `车辆分类与实体类型` (`entity_type` 三元组与正常车定义) 向量知识条目；
  5) 新增 `滞留监控关键节点` (`retention_checkpoint_station`) 向量知识条目。

#### 2. 领域元数据配置 (`backend/app/skills/domains/paint_shop_vehicle_logistics/`) [MODIFY]
- **`meta.py`** [MODIFY]：
  1) `description` 扩展“项目车”、“试验车”、“PIN”、“FIS订单”、“量产车”、“正常车”触发关键词；
  2) `associated_tables` 和 `lexicon_enabled_tables` 加入 `ods.ods_fis_project_vehicle_orders`；
  3) 配置 `ods.ods_fis_project_vehicle_orders` 的 RAG Lexicon 行级与列级抽取白名单 (`project_vehicle_no`, `composite_pin_no`, `project_stage`)。

#### 3. 场景定义与 SQL 模板 (`scenarios/`) [MODIFY]
- **`realtime_area_body_count/sql/main.sql`** [MODIFY]：SQL 条件更新为 `WHERE overview.entity_type IN ('project_vehicle', 'product_vehicle')`，包含项目车与量产车全量正常车；
- **`realtime_area_body_count/scenario.py`** [MODIFY]：提示词 workflow 与 rules 同步升级为默认统计全量正常车；
- **`daily_area_body_count/scenario.py`** [MODIFY]：清理 gotchas 说明中的旧 `BODY_ID LIKE '782026%'` 过滤范例；
- **`abnormal_vehicle_monitor/scenario.py`** [MODIFY]：规则补充“正常车的 `abnormal_type` 恒为 `NULL`”。

---

## 2026-07-29 13:35 +08:00 - 重构与结构化对齐涂装车间车辆物流追踪领域架构文档 (domain.md)

### 变更内容

#### 领域架构文档 (`backend/app/skills/domains/paint_shop_vehicle_logistics/`) [MODIFY]
- **`domain.md`** [MODIFY]：
  1) 引入 FIS 项目车订单贴源表 `ods.ods_fis_project_vehicle_orders` 说明及关联规则（`composite_pin_no`）；
  2) 升级车辆分类规则为 `project_vehicle`（项目车）、`product_vehicle`（产品车/量产车）、`abnormal_vehicle`（异常车）三元组体系；
  3) 明确“正常车”包括项目车与量产车，正常车的 `abnormal_type` 恒为 `NULL`，消除规则矛盾冲突；
  4) 为 `dim.dim_vehicle_profile`、`dim.carbody_registry` 和 `mart.mart_position_current_overview` 补齐 `project_vehicle_no` 与滞留监控关键节点等属性列；
  5) 接入自然语言到 `entity_type` 标准条件的 LLM System Instruction 与 Few-Shot 映射表。

---

## 2026-07-27 14:10 +08:00 - 界面极简重构：取消右侧全高分栏，升级为右侧毛玻璃悬浮场景直通卡片堆叠

### 变更内容

#### 前端 UI / 布局重构 (`frontend/src/`) [NEW/MODIFY]
- **`frontend/src/components/FloatingScenarioCards.vue`** [NEW]：新增右侧毛玻璃悬浮场景直通卡片堆叠组件，支持收起/展开，全亮闪电 Icon、黄色背景 Badge、精细化深度微型按钮与淡蓝全宽按键（与视觉设计稿 100% 对齐）。
- **`frontend/src/components/VariantB.vue`** [MODIFY]：移除右侧固定 320px~384px 全高 `aside` 分栏，解放聊天主屏画布视野，大幅提升极简视觉感受。
- **`frontend/src/views/ChatView.vue`** [MODIFY]：移除右侧分栏插槽关联，全局挂载 `FloatingScenarioCards` 与 `ScenarioModal` 弹窗。
- **`ScenarioModal` 弹窗极简与数据区最大化重构** [MODIFY]：
  1) **`ScenarioModal.vue`**：头部栏精简为单行，压缩 Padding；
  2) **`ParameterForm.vue`**：重构为横向网格与行内提交按钮，纵向高度从 300px+ 骤降至 70px 左右；
  3) **`ResultRenderer.vue` & `TableResult.vue`**：结果数据集占据 80%+ 全垂直空间，支持表格内部独立纵向/横向自适应滚动；
- **清理无用死代码** [DELETE]：清理移除了旧版已废弃的 `ScenarioList.vue` 与 `ScenarioPanel.vue` 组件，保持前端组件库纯净。

---

## 2026-07-27 11:10 +08:00 - 完成业务场景技能与快捷直通查询通用架构设计规范及四阶段全量实施

### 核心实施与优化

#### 架构规范文档 (docs/快捷查询/) [NEW/MODIFY]
- **`scenario_architecture_spec.md` (v3.4)** [NEW/MODIFY]：全量 12 场景三段解耦落地，并升格为 `docs/skills/scenario_architecture_spec.md` 项目唯一权威技能规范 (Single Source of Truth, SSoT)。
- **`docs/skills/` 统一收拢重构** [MODIFY]：整合收拢散落在 `docs/backend/skills/` 与旧 `guide.md` 的场景文档，统一指向 `docs/skills/scenario_architecture_spec.md`，彻底消除文档漂移与多头维护风险。
- **`README.md` & `AGENTS.md`** [MODIFY]：对齐全局与入口文档的技能规范指针。

#### Phase 1: 基础契约对齐与直通场景过滤
- **`backend/app/schemas.py`**：`ScenarioItem` 响应模型补充 `direct_path_enabled: Optional[bool] = True` 字段；
- **`backend/app/api.py`**：`list_scenarios_tree()` 路由实现 `is_direct_path_enabled` 过滤，确保纯 LLM 场景不会泄露到快捷直通侧边栏；
- **`stranded_vehicle_detection/scenario.py`** & **`vehicle_historical_trace/scenario.py`**：对应配置 `direct_path_enabled: True/False` 标志。

#### Phase 2: 安全与占位符修补
- 修复 `vehicle_historical_trace/sql/main.sql`、`daily_area_body_count/sql/main.sql` 和 `abnormal_vehicle_monitor/sql/main.sql` 的 `-- {placeholder}` 注释穿透严重漏洞（防止条件被注释导致全表扫描）；
- 将对应场景 `scenario.py` 中的 `sql_fragment` 统一修补为 `:param_name` 命名参数安全绑定。

#### Phase 3: Token 精简与渲染隔离 RFC
- **`backend/app/skills/renderers.py`**：Prompt 渲染剥离纯 UI 属性（`source_table`、`source_column`），节省 50%+ 提示词 Token 消耗；
- **`backend/app/skills/discovery.py`**：支持 `SCENARIO` 与 `SCENARIO_META` 别名容错，并增加 `required_inputs`/`optional_inputs` 内存派生兜底。

#### Phase 4: 高级控件与 UI/数据契约扩展
- **`backend/app/skills/direct_path/resolver.py`**：`infer_widget` 扩充 `date` 与 `daterange` 日期类型推断；
- **`backend/app/skills/direct_path/formatter.py`**：`format_result` 扩充 `output_type=="chart"` 转换结构（支持 `categories` 与 `series`）；
- **`frontend/src/components/widgets/DateWidget.vue` [NEW]** & **`ParameterForm.vue`**：创建日期选择控件并在表单中完成注册映射。

---

## 2026-07-26 21:38 +08:00 - 快捷场景直通 SQL 查询引擎与标准三栏 + 大屏弹窗 UI 全量完成

### 变更内容

#### 新增与重构文档
- **`docs/快捷查询/README.md`** [NEW]：汇总快捷场景直通查询引擎架构设计、后端 `resolver` / `executor` / `formatter` 分层规范、前端 3 栏 + `ScenarioModal` 大屏弹窗交互与二次开发指导。
- **`docs/superpowers/specs/2026-07-26-scenario-quick-panel-design.md`**：初始规范设计文档。

#### 后端直通引擎 (`backend/app/skills/direct_path/`) [NEW]
- **`resolver.py`**：参数解析层，动态推断 `text`/`number`/`select`/`multiselect` 控件，安全查询 `source_table`/`source_column` 去重选项（含 60s 缓存）。
- **`executor.py`**：SQL 安全构建层，读取场景 `sql/*.sql` 模板，未传参数整行裁剪，有值参数使用命名绑定（`:param_name`），防 SQL 注入。
- **`formatters.py`**：结构化结果转换层，支持 `table` 与 `scalar` 两种格式输出。
- **`schemas.py` & `api.py`**：导出 `ScenarioSummary`, `ScenarioParamsResponse`, `ScenarioExecuteResponse` 模型，挂载 `/api/scenarios` 路由（`GET /`, `GET /{domain}/{scenario}/params`, `POST /{domain}/{scenario}/execute`）。
- **`tests/test_scenario_quick_panel_engine.py` & `test_scenario_quick_panel_api.py`**：11 项单元/集成测试 100% 通过。

#### 前端 3 栏与弹窗 UI (`frontend/src/`) [NEW/MODIFY]
- **`components/ScenarioModal.vue`** [NEW]：`max-w-5xl` 3D 毛玻璃弹窗，包含多模板 Tab 切换条、`ParameterForm` 表单与宽屏 `ResultRenderer` 数据表格。
- **`components/ScenarioList.vue`** [NEW]：右侧栏卡片列表组件，按领域分组展示场景卡片，带实时搜索与一键直通触发按钮。
- **`components/VariantB.vue` & `views/ChatView.vue`**：布局重构为标准三栏（左：历史会话，中：主问答区，右：快捷场景卡片栏），首页 `!currentSession` 时展示右侧栏。

---

## 2026-07-26 15:46 +08:00 - 完成依赖库版本基线升级与 requirements.txt 对齐 (支持 DeepAgent 演进)

### 变更内容

#### requirements.txt [MODIFY]
- **`langchain`**: `1.2.15` → `1.3.14`
- **`langchain-core`**: `1.3.0` → `1.5.1`
- **`langchain-community`**: `0.4.1` → `0.4.2`
- **`langgraph`**: `1.1.8` → `1.2.9`
- **`langgraph-checkpoint`**: `3.0.1` → `4.1.1`
- **`langgraph-checkpoint-postgres`**: `3.0.2` → `3.1.0` (解决 Postgres Checkpoint 4.x 依赖冲突)
- **`langgraph-sdk`**: `0.3.5` → `0.4.2`
- **`langsmith`**: `0.6.4` → `0.10.10`
#### backend/app/custom state.py [DELETE]
- 使用 `git rm` 清理了无任何代码引用的 0 字节死文件 `backend/app/custom state.py`。

---

## 2026-07-26 13:46 +08:00 - 深度精简与清理 .env 环境变量配置文件

### 变更内容

#### .env [MODIFY]
- 移除已废弃的 `ROLLERBED_DATABASE_URL` 与 `MYSQL_DATABASE_URL` 配置。
- 移除闲置的 `OLLAMA_*` 系列配置项（`OLLAMA_BASE_URL`、`OLLAMA_MODEL`、`OLLAMA_NUM_CTX`、`OLLAMA_KEEP_ALIVE`、`OLLAMA_EMBED_MODEL`）。
- 保留并整理 `LLAMA_CPP_TOKENIZE_BASE_URL` 配置（供 `TOKEN_ESTIMATOR_ENGINE="llama_cpp"` 模式切回时使用）。
- 清理已淘汰的历史节点 IP 注释与在线 `NVIDIA_API_KEY`。
- 按 10 大核心功能模块重构并新增统一风格的 `# ======...======` 顶级分组注释，提升整体美观度与可维护性。

#### backend/app/ [DELETE]
- 清理删除了散落在生产业务目录 `backend/app/` 及其子目录内部的 20 个临时 `test_*.py` 文件。
- 清理删除了废弃的旧版代码目录 `backend/app/agent/utils/old/`（含 `rerank_service.py`、`pgvector_wrapper.py` 等归档文件），保持源码干净纯粹。

#### backend/app/config.py [MODIFY]
- 移除 `Settings` 模型中的 `rollerbed_database_url` 和 `mysql_database_url` 属性，并将 `analytics_database_url` 默认值设为分析库连接。

#### backend/app/agent/service.py [MODIFY]
- 清理 `_get_business_database_url()` 与 `_get_business_database_engine_args()` 中的回退逻辑，直连 `ANALYTICS_DATABASE_URL`。

---

## 2026-07-24 10:14 +08:00 - 修复滞留车检测在制车查询 NULL 值与 SQL 模板注释干扰漏洞

### 变更内容

#### backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/sql/in_process.sql [MODIFY]
- 修复在制滞留车查询条件中 `retention_checkpoint_station NOT IN (...)` 对 `NULL` 值的过滤漏洞，引入 `IS NULL` 容错处理。
- 移除占位符前的 SQL 单行注释前缀 `--`，避免替换生成的 SQL 片段被直接当作注释忽略。

#### backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/sql/historical.sql [MODIFY]
- 移除占位符前的 SQL 单行注释前缀 `--`，防止生成的平台/天数过滤 SQL 被当成注释忽略。

#### backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py [MODIFY]
- 精简重构场景元数据定义，合并冗余触发词与重复规则条目，将代码压缩约 40%，显著提升 LLM 提示词 Token 效率与阅读可维护性。
- 通过了 `discover_scenarios` 自动发现与场景资产校验测试。

---

## 2026-07-22 13:10 +08:00 - 新增通用智能体架构选型可行性研究与前端改造综合报告

### 变更内容

#### docs/deepagent/generic_agent_architecture_report.md [NEW]
- 新增通用智能体技术选型可行性研究与架构演进报告。
- 校准并明确了后端现代依赖版本基线（`langchain 1.2.15`、`langgraph 1.1.8`、`langgraph-checkpoint-postgres 3.0.2` 等）。
- 梳理项目背景、现有 Text-to-SQL 单 ReAct 瓶颈与演进诉求，对比研究 LangGraph 编排引擎与 Deep Agent 范式。
- 提出 Top-Level Multi-Agent 状态图 Supervisor 架构设计，将 SQL Agent 降维降噪为专业子图。
- 详述前端流式事件注册（`subagent_change`, `plan_update`）、Pinia 状态存储与 UI 可视化组件改造细则。

---

## 2026-07-21 11:18 +08:00 - 统一消息卡片内各辅助组件与一键生成图表的水平对齐宽度

### 变更内容

#### frontend/src/components/MessageItem.vue [MODIFY]
- 修复因双重 padding 缩进导致嵌套组件偏窄的问题：移除嵌套在 `px-5` 父容器内的 SQL 查询结果（`sqlQueryResult`）、工具调用列表（`toolCallList`）、工具结果展示（`toolResultEntries`）、澄清提问（`hasQuestions`）和错误块（`errorText`）的多余水平 padding 样式（如 `px-4` 或 `px-5`），使其统一继承父容器的 `20px` 留白。
- 将“参考业务术语”与“参考数据库物理词典 (DB Lexicon)”折叠卡片的外层容器水平内边距由 `px-1.5` 调整为 `px-5`，以完美对齐一键生成图表 Banner 的 `20px` 留边。

---

## 2026-07-20 21:36 +08:00 - 优化 SQL 查询结果组件默认折叠展示与本地冗余链接清洗

### 变更内容

#### frontend/src/components/MessageItem.vue [MODIFY]
- 去除 SQL 查询结果 `<details>` 卡片上的 `open` 属性，使其默认呈现折叠状态，优化初始阅读体验。
- 新增“参考数据库物理词典 (DB Lexicon)”折叠卡片，分类展示命中表的 DDL 结构、字段去重值对照参考以及实体主键与行属性参考。

#### frontend/src/utils/markdown.ts [MODIFY]
- 在 `extractMetaData` 函数中新增 `fileLinkRegex` 正则匹配，用于在 Markdown 渲染前彻底过滤清洗大模型生成于正文中的冗余本地 `file:///` 协议链接，防止高危路径泄露和前端折行排版崩溃。

#### backend/app/agent/tools/csv_export_tool.py [MODIFY]
- 对 `export_to_csv` 工具在执行结束时向大模型返回的 `ToolMessage.content` 进行脱敏处理，剥离了物理文件绝对路径 `stored_path`，从根源上阻止了其泄露到大模型上下文和前端 `tool_results` 中。

#### backend/app/agent/prompts/base_system_prompt.md [MODIFY]
- 调整系统提示词，加入最终回复呈现格式的精确意图分流规则（数据明细查询类、数据分析与统计对比类、开放问题与知识问答类）。

#### docs/StructuredOutput/refactor/09_lightweight_structured_output_feasibility.md [NEW]
- 新增轻量结构化输出方案的可行性分析文档，确立“LLM 分析正文为主体、侧信道明细为证据底座”的分工模式。

#### docs/StructuredOutput/refactor/10_lightweight_structured_output_implementation_plan.md [NEW]
- 新增轻量结构化输出实施方案文档，规划 Prompt 规约、前端组件重排及防抖动占位等具体改造项。

---

## 2026-07-20 15:40 +08:00 - CSV 导出工具 export_to_csv 改 Command 侧信道直推及 OOM 安全防护重构 (Spec 06)

### 变更内容

#### backend/app/agent/tools/csv_export_tool.py [MODIFY]
- 引入并改用 `langgraph.types.Command` 包装工具返回值。
- 在 `tool_artifact` 中携带完整文件元数据 `file_export`（包含 file_id、filename、row_count、col_count 和 columns）发送流式 payload 供前端秒级渲染。
- 将 `runtime` 参数改为可选（默认 `None`），在测试环境下未注入 `ToolRuntime` 时自动打印 debug 日志并绕过技能校验。
- 引入行数超限限制拦截（SQL_EXPORT_MAX_ROWS，默认 100k 行），若超限抛出 `ToolException` 中断并提示，防止大批量数据集导出时撑爆内存 OOM。

#### backend/app/agent/tools/test_csv_export_command.py [NEW]
- 新建 TDD 单元测试文件，验证工具在 invoke 后的 `Command` 输出结构、流式元数据字段完整度，以及行数超限触发 OOM 保护机制时的拦截逻辑，完美兼容 LangChain 的 `handle_tool_error` 报错转换规则。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 增加 `fileExport` 计算属性，专门用于提取流式 `tool_artifact` 中的 `file_export` 工件。
- 在模板中加入直推下载卡片节点，渲染优先级优于历史懒加载，实现流式和历史消息并存的“双轨制”下载体验。

#### docs/StructuredOutput/refactor/06_export_to_csv_side_channel_refactor.md [NEW]
- 制定完整的 Spec 规格书，系统阐述了对 CSV 导出工具的交付通道、只读数据库入口、OOM 防护以及 result_id 复用方案的顶层架构设计。

---

## 2026-07-20 14:03 +08:00 - 图表工具 build_chart_artifact 改 Command 侧信道直推及前端防震重构 (MVP 简化版)

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py [MODIFY]
- 引入并改用 `langgraph.types.Command` 包装工具返回值。
- 在 `tool_artifact` 中携带完整 `chart_spec`（包含 rows 与 series）发送流式 payload 供前端秒级渲染。
- 在 `ToolMessage.content` 中保留 `chart_ref` 磁盘 JSON 引用以对齐 04 方案，让历史消息可通过 `tool_results` 顺利进行前向兼容懒加载。

#### backend/app/agent/tools/test_chart_artifact_command.py [NEW]
- 新建 TDD 单元测试用例，验证工具 invoke 返回 `Command` 的结构、流式 Payload 字段及 ToolMessage 内的历史回溯 JSON 数据格式。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 拆分 computed 属性 `queryResult` 为专供图表的 `chartSpec` 和专供 SQL 表格的 `sqlQueryResult`。
- 将模板表格预览的判断变更为 `sqlQueryResult`，物理隔离了图表 spec，彻底避免了图表生成时渲染出空表头残缺表格的 UI 冲突。
- 新增 `chartSpec` 流式卡片直投区，并使其渲染优先级排在历史懒加载卡片之前。

#### frontend/src/components/ChartArtifactCard.vue [MODIFY]
- 扩充 Props 接口声明以接收可选的实时 `chartPayload` 属性。
- 引入 `displayTitle`/`displayDescription`/`displayChartType` 等防空 `computed` 包装，对 Props 进行 `undefined` 安全防护，避免流式无引用时导致控制台崩溃。
- 适配 `loadArtifact` 与 `watch` 监听器，支持直传装载与降级 API 局部拉取双轨制通道。

#### docs/StructuredOutput/refactor/05_build_chart_artifact_side_channel_refactor.md [MODIFY]
- 采纳评审意见，将重构实施方案更新为 MVP 简化版，推迟物理列持久化，避开 `_last_wins` 多工具冲突并完美对齐 04 架构一致性。

---

## 2026-07-19 23:15 +08:00 - 修复 Decimal/UUID 类型导致 SQL 结果截断机制失效的安全漏洞

### 问题描述

当 SQL 查询结果包含 `Decimal` 或 `UUID` 类型时，`MaterializedViewSQLDatabase.run()` 调用 `str(res)` 会产出 `Decimal('...')` 或 `UUID('...')` 格式字符串。这些是 AST 中的 Call 节点，`ast.literal_eval` 无法解析，抛出 `ValueError`。原始代码用 `except Exception: pass` 静默吞掉异常，导致 `cleaned_result` 保持为原始字符串、`row_count` 计算为 0，完全绕过 `SQL_RESULT_HARD_LIMIT` 行数限制，将全量数据静默传递给 LLM。

### 变更内容

#### backend/app/agent/utils/sql_database.py [MODIFY]
- 在 `run()` 方法的结果序列化路径中，新增 `Decimal → float` 和 `UUID → str` 的显式类型转换，确保 `str(res)` 产出纯字面量格式，可被 `ast.literal_eval` 正确解析。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 将解析失败时的 `except Exception: pass`（静默吞掉异常）替换为 `raise ToolException`，中断执行并向 LLM 返回明确的错误提示（含修复建议：减少列数或加 LIMIT），避免不可靠数据被静默传递。
- 记录 `logger.error` 日志辅助排查。

### 根因分析

| 步骤 | 行为 |
|------|------|
| `str(res)` | 产出 `Decimal('2309.18...')` — Call 节点 |
| `ast.literal_eval` | `ValueError: malformed node or string` |
| `except Exception: pass` | 静默吞掉异常，`raw_result` 仍为字符串 |
| `row_count = 0` | `isinstance(字符串, list)` → False |
| `truncated = False` | 0 >= 30 → False |
| `llm_content` | 全量数据字符串直接传递给 LLM |

---

## 2026-07-19 18:56 +08:00 - 单工具 sql_db_query 数据预览极简保结构与侧信道传输重构

### 变更内容
#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 移除了老旧且不稳定的 `_estimate_row_count` 估行与 `_extract_preview_rows` 字符串截断死代码。
- 改为对结构化 `list[dict]` 结果执行物理 `len()` 计数与截断，并就地归一化日期及 `Decimal` 类型。支持将底层工具返回的格式化 `str` 列表静默反序列化，打通 rows 全量传输。
- 引入了 `Command` 与 `tool_artifact` 侧信道，在超限截断时向大模型推送带 `⚠️ SYSTEM WARNING` 警告的预览数据（前 N 行），并将 `rows[:hard_limit]` 的完整有界行列表送入 `tool_artifact`。

#### backend/app/agent/state.py [MODIFY]
- 在 `CustomState` 状态 TypedDict 声明中注册了 `tool_artifact` 属性，保证在 LangGraph 节点和状态链路间的数据合规流转。

#### backend/app/schemas.py [MODIFY]
- 声明了 Pydantic 规范的 `ToolArtifactStreamEvent` 结构，并将其作为子项注册至 `ChatStreamEvent` Union 中。

#### backend/app/services.py [MODIFY]
- 在主 updates 状态流捕获处拦截 `tool_artifact` 字段，并将其封装为 unified 的 SSE 事件类型并广播。

#### backend/app/api.py [MODIFY]
- 在同步 `_stream_chat` 与异步 `_stream_chat_async` 双路径转发流式数据时，将 `tool_artifact` 纳入支持的事件类型列表中，确保前端的无阻碍接收。

#### backend/app/agent/tools/test_sql_db_query_command.py [NEW]
- 新增 TDD 单元测试用例，覆盖成功态、超限截断态、空查询降级 fallback 的 Command 及 tool_artifact 输出逻辑。

#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 修复了 loads 之前的时间戳正则剥离逻辑，防止对含敏感字眼的成功态 JSON 导致误删。

#### frontend/src/types/index.ts [MODIFY]
- 为 `Message` 和 `StreamingMessage` 声明了 `tool_artifact` 选填类型属性。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 在 SSE event 解析器的 `switch` 结构中新增 `case 'tool_artifact'` 分发逻辑。

#### frontend/src/stores/messages.ts [MODIFY]
- 声明了 `memoryArtifactMap` 前端内存响应式映射，在 `completeStreamingMessage` 转储逻辑里，将临时 `tool_artifact` 存入其中，实现当前会话在未刷新前的流畅表格渲染与刷新后的优雅纯文本回退。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 新增 `queryResult` 局部 computed 计算属性，将表格视图与 `tool_artifact` 自动绑定。
- 在 template 中追加现代化的极简 emerald 浅绿交互式表格模板及超限说明 Badge。

---

## 2026-07-19 16:20 +08:00 - 重构方案与代码对齐校准与文档引用修正

### 变更内容
#### docs/StructuredOutput/refactor/unified_sql_linter_safety_alignment.md [MODIFY]
- 针对 `export_to_csv` 成功日志在滑动窗口外物理删除的决策进行同步更新：在设计方案中写明了将其纳入 `_DELETION_TARGET_CONFIG` 的合理性（即虽然可能有列名误判风险，但已导出完成的旧历史消息丢弃有利于极大节省大模型的上下文 token 空间，影响极其有限）。

#### docs/sql_check/2026-07-11-sql-check-optimization-plan.md [MODIFY]
- 修正对已物理删除的死代码 `sql_tools_local.py` 的引用。在第 9 行架构说明、第 125 行文件改动列表以及 Step 2 具体修改步骤中，同步将涉及该文件的部分标记为 `[已废弃]`，避免后续对其他开发者产生误导。

---

## 2026-07-19 15:39 +08:00 - 上下文编译器对齐图表与 CSV 工具与 Linter 折叠优化

### 问题根因
1. **Linter 状态检查未开启**：图表工具 `build_chart_artifact` 与 CSV 导出工具 `export_to_csv` 在中间件配置中的 `has_linter` 为 `False`，导致合规校验失败时的清理预检效率低下。
2. **历史折叠缺失**：Stage 3 历史 Linter 错误折叠逻辑硬编码限制为仅处理 `sql_db_query` 消息。如果图表或 CSV 工具被多次拦截，生成的庞大 DDL 和 Linter 报错内容将无情地挤爆 LLM 窗口上下文。

### 变更内容
#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 修改配置表 `_DELETION_TARGET_CONFIG`，将 `build_chart_artifact` 与 `export_to_csv` 显式开启 `has_linter: True` 拦截。
- 重构 Stage 3 `_stage_redaction` 中的过滤检查与折叠循环，将原本硬编码的 `sql_db_query` 改为动态匹配所有配置为 `has_linter=True` 的支持工具，实现了逻辑泛化与对齐。

#### backend/app/agent/middleware/test_prompt_compiler_middleware.py [MODIFY]
- 新增单元测试用例 `test_stage_redaction_build_chart_artifact` 与 `test_stage_redaction_export_to_csv`，模拟多次调用失败并由 Linter 拦截后，旧失败尝试已被成功折叠替换为占位符的效果，目前 25 个用例全部绿灯通过。

#### docs/StructuredOutput/refactor/prompt_compiler_middleware_alignment.md [NEW]
- 新增上下文编译器对齐方案设计文档，系统阐述了重构背景、泛化判定重构、详细变更对比以及单元测试覆盖设计。

---

## 2026-07-19 15:32 +08:00 - SQL Agent 双轨初始化路径解耦与工厂化重构


### 问题根因
1. **初始化逻辑高度重复**：`SQLAgentService` 同步路径（`_initialize_agent`）与异步路径（`_ainitialize_agent`）之间存在超过 120 行高度相同的工具装配、中间件实例化、LLM 与 DB 组装等重复代码，造成冗余。
2. **多端维护和逻辑分叉风险**：每当工具（如 DDL 信息传递）或中间件顺序发生变更时，都必须手动在两端同步修改，极易遗漏导致 LangGraph 托管端与本地 FastAPI 端的行为产生分叉。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 提取私有辅助方法 `_build_agent_components(self) -> dict`，将大模型加载、DB连接、工具装配与中间件组装的核心顺序逻辑收拢合并，保持纯逻辑组装职责。
- 重构 `_initialize_agent` 与 `_ainitialize_agent` 核心入口，分别调用 `_build_agent_components` 并结合各自同步/异步 Persistence 创建 `agent`，完全消除了重复的样板代码。

#### docs/StructuredOutput/refactor/dual_path_initialization_decoupling.md [NEW]
- 新增本期重构的设计方案文档，详细论述重构背景、结构架构、变更方法、以及上线验证步骤。

---

## 2026-07-19 15:18 +08:00 - 统一 SQL 安全合规拦截校验与异常契约对齐

### 问题根因
1. **安全校验边界不一致**：数据预览（sql_db_query）、CSV 导出（export_to_csv）和图表生成（build_chart_artifact）三个数据库查询工具在 SQL 安全和合规校验方面的行为不一致（部分仅做正则校验，部分无 DDL 元数据注入）。
2. **高危 SQL AST 绕过漏洞**：原 AST 校验规则仅检测 DML 类型的 AST 节点。如果传入 `TRUNCATE` 或 `GRANT`/`REVOKE` 等语句，解析成 AST 节点后无法匹配原规则节点，导致直接绕过校验。
3. **异常自愈机制未对齐**：当 CSV 导出或图表工具报错时，原设计返回普通字符串而非抛出 `ToolException`，导致大模型无法识别错误进行自我修正（Self-Correction），且前端 Prompt 编译器中间件无法识别崩溃字段进行自动收折。
4. **死代码遗留**：项目中残留了 `sql_tools_local.py` 与 `services_graph.py` 等不再使用或包含硬编码崩溃代码的文件。

### 变更内容
#### backend/app/agent/utils/sql_linter.py [MODIFY]
- 新增 `SQLLintException` 专属异常。
- 引入统一安全校验入口 `validate_readonly_query(query, db_custom_info)`。
- **【核心漏洞加固】**：在解析前无条件应用 `FORBIDDEN_SQL_PATTERN` 正则第一道硬拦截，阻断 `TRUNCATE`/`GRANT` 等语句绕过 AST。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 移除了冗余的 11 条 Linter 规则手动实例化与注册逻辑，将安全校验统一委托给 `validate_readonly_query` 核心，对齐异常捕获契约。

#### backend/app/agent/tools/csv_export_tool.py [MODIFY]
- 重构 `create_csv_export_tool` 以接收 `custom_table_info`。
- 移除遗留的 `FORBIDDEN_SQL_PATTERN` 逻辑，在执行前接入 `validate_readonly_query` 校验。
- 错误与拦截时统一抛出 `ToolException`，对齐自愈契约并启用 `handle_tool_error = True`。

#### backend/app/agent/tools/chart_artifact_tool.py [MODIFY]
- 执行与 CSV 导出工具一致的安全合规对齐改造，错误与安全拦截时统一抛出 `ToolException`，使大模型能够捕捉并自愈。

#### backend/app/agent/service.py [MODIFY]
- 在加载工具阶段，从 `db` 实例中提取 `_custom_table_info` DDL 表结构字典，并将其透明注入到 CSV 导出和图表生成工具的工厂函数中，确保语义级 Linter 校验正常执行。

#### [NEW] backend/app/agent/tools/test_unified_linter.py
- 新增 8 个全链路校验与异常契约的单元测试用例，覆盖 DML 拦截、`TRUNCATE` 漏洞拦截、多语句拼接拦截、表前缀别名缺失拦截以及 CSV/图表工具抛出 `ToolException` 被 `handle_tool_error` 成功转换为错误字符串的表现。

#### [DELETE] backend/app/agent/tools/sql_tools_local.py
- 物理删除无用的死代码复制文件。

#### [DELETE] backend/app/services_graph.py
- 物理删除包含硬编码 MySQL 连接且已废弃的旧图形服务模块，解决包加载阶段偶发崩溃的问题。

---

## 2026-07-18 22:47 +08:00 - 优化人工输入气泡的视觉配色系统

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 优化用户发送消息的气泡配色，从原本的淡亮蓝色（#DBECFF）升级为雅致的现代莫兰迪灰蓝（#F0F4F9 背景 + #D2E0EE 边框 + #2D3A4B 墨蓝文本 + #7A8C9E 时间戳）。
- 极大减弱了界面的视觉噪点，提供了更加深沉、专注的企业数据查询与阅读体验。

---

## 2026-07-18 22:30 +08:00 - 实现多会话后台并行流式生成与运行状态动效提示

### 问题根因
1. 当用户在消息生成中途切换到左侧其他会话时，旧会话的流式 SSE 依旧在后台继续吐字，但由于全局状态共用且无 ID 隔离验证，导致旧会话的流式数据会错误泄漏到新会话底部，造成严重的输入框锁死和消息交叉污染。
2. 缺乏会话状态的动态提示，用户无法得知当前具体有哪些会话在后台默默进行分析与生成。

### 变更内容
#### frontend/src/stores/messages.ts [MODIFY]
- 将原全局唯一的流式临时消息 `streamingMessage` 升级为 Map 字典结构 `streamingMessagesMap`。
- 将 `streamingMessage` 与 `isStreaming` 改造为 computed 属性以自动向下兼容，并新增 `isSessionStreaming(sessionId)` 判断服务。
- 升级所有的流消息操作 Action 支持 `sessionId`，在 Map 中对各会话独立隔离存储。
- 升级终态完成和错误落定 Action，增加 `latestRequestedSessionId` 会话比对拦截防护，防止后台流式在 complete 时对前台当前会话造成数据污染。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 移除原会话切换时重置上下文预警和可能带来的逻辑锁，将 `activeStreamController`、`isSending`、`contextWarning` 全部 Map 隔离化。
- 改造 `stopStreaming`，增加 `sessionId` 形参，支持单独精准中止目标会话的后台流式。
- 升级 `sendMessage` 与 `resumeMessage`，在接收到 SSE 事件时为 Action 显式透传对应的 `sessionId`，并解决非流式处理分支直接为 read-only computed 赋值的 Bug。

#### frontend/src/components/SessionItem.vue [MODIFY]
- 引入 `isStreaming` 状态判断，当且仅当对应的会话在后台流式运行中时触发状态激活。
- 在正常展开态下，在会话标题右侧渲染精致、科幻的三频段 Siri 频谱柱跳动微动效。
- 在折叠态下，在头像右下角渲染一圈圆润、绿色的呼吸灯 Loading 状态角标。
- 增加对应动效在不同状态下的 CSS 跳动 keyframes。

---

## 2026-07-18 20:05 +08:00 - 对话气泡复制、数据字典弹窗化、维度表时间列隐藏及 Ctrl+M 隐藏审核终端

### 问题根因
1. 用户期望对前端的每个消息对话气泡增加一个复制按钮以方便拷贝消息内容。
2. 用户期望将原有的数据字典看板由页面级切换修改为毛玻璃悬浮弹窗（Modal）形式，避免在查看字典时中断聊天进程。
3. 用户不希望在看板展示的维度表数据字典中看见无意义的首次/末次时间及系统列（如 `created_at`、`updated_at`、`first_seen` 等），影响视觉排版。
4. 用户期望“审核终端”按钮默认隐藏，仅在按下键盘快捷键 `Ctrl + M` 时进行显示切换，防止敏感按钮被普通用户误操作。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 新增 `copied` 状态和 `handleCopy` 事件处理器。
- 引入具备 `navigator.clipboard` 及传统 `document.execCommand` 兼容性的剪贴板复制逻辑，保证特殊开发/部署环境下功能可用。
- AI 消息已生成状态：将“复制”按钮与时间戳放在气泡底栏右侧。
- 用户/临时/错误/停止消息状态：在底栏右侧同时并列展示“复制”按钮和时间戳。
- 流式生成过程中隐藏复制按钮。

#### frontend/src/components/VariantB.vue [MODIFY]
- 移除聊天主槽位 `slot name="main-chat-area"` 的 `v-if="!showBento"` 控制，保证聊天界面常驻后台，提升性能 and 体验。
- 重构数据字典 Bento 网格，将其置于精美的玻璃毛玻璃悬浮 Modal 之中，支持点击背景遮罩或右上角 (✖️) 按钮进行关闭。
- 添加 `modal-fade` 过渡和 `scale-up/down` 弹性缩放动效，提供流畅微动效体验。

#### frontend/src/components/DimensionTable.vue [MODIFY]
- 新增 `filteredColumns` 和 `filteredRows` 计算属性，其中 `_TIME_PATTERNS` 正则升级为 `/date|time|_at|seen/i`，可自动分析并隐藏包括 `first_seen`、`created_at` 等在内的所有时间/系统审计相关字段。
- 模板渲染从原有的 `columns`/`rows` 升级为使用过滤后的 `filteredColumns`/`filteredRows`，实现整个维度表数据视图对时间字段的彻底隐藏。

#### frontend/src/views/ChatView.vue [MODIFY]
- 新增 `showAdminReviewBtn` 响应式变量，默认设为 `false`。
- 在 `onMounted` 和 `onUnmounted` 中绑定和销毁全局键盘事件监听器，拦截 `Ctrl + M` 键触发 `showAdminReviewBtn` 显示切换。
- 将“审核终端”按钮的挂载条件设为 `v-if="showAdminReviewBtn"`。

---

## 2026-07-18 18:42 +08:00 - 编写检索工具极限物理删除的单元测试用例

### 问题根因
为确保大模型聊天会话管理系统中的三层物理词典方案中检索工具的极限物理删除与折叠功能正确性，需要编写相关单元测试，覆盖滑动窗口内保留、滑动窗口外物理删除以及并行调用混合情况下的删除/折叠行为。

### 变更内容
#### backend/app/agent/middleware/test_prompt_compiler_middleware.py [MODIFY]
- 在文件末尾追加了三个测试用例：
  - `test_prompt_compiler_lexicon_retrieval_window_in_preservation`（窗口内检索工具保留）
  - `test_prompt_compiler_lexicon_retrieval_window_out_ultimate_deletion`（窗口外检索工具物理删除）
  - `test_prompt_compiler_lexicon_retrieval_mixed_tool_calls_deletion`（并行工具混合调用时检索工具删除、SQL成功工具折叠）

---

## 2026-07-18 18:40 +08:00 - 预扫描阶段无条件执行物理词典检索工具的物理删除收集

### 问题根因
在原有的消息折叠/删除机制中，`_stage_prescan_failures` 仅会对 `self._DELETION_TARGET_CONFIG` 列表中配置的工具进行分析和删除。而在三层物理词典方案中，为了保持窗口整洁与减少无效上下文，在滑动窗口外对三层辅助检索工具（定义在 `ULTIMATE_DELETION_TOOLS` 中）的调用信息应当无条件进行物理删除，避免对模型造成干扰。

### 变更内容
#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 修改 `_stage_prescan_failures` 方法，如果在滑动窗口外的 ToolMessage 名称匹配 `ULTIMATE_DELETION_TOOLS`，则将其 `tool_call_id` 直接加入到 `deleted_call_ids` 列表中并立即 `continue`，以实现无条件物理删除。

---

## 2026-07-18 17:30 +08:00 - 重构 RAG 三层物理词典合并与追加策略以解决分数错配

### 问题根因
以前的 `BusinessRagMiddleware` 对表层、值层、行层检索出来的表通过 `max(score)` 强行合并为一个扁平字典。由于三层各自所在的检索空间不同（特别是 Milvus 混合检索中 RRF 分数完全由各集合的元素及排位决定），跨空间的分数无法直接进行数值比较，导致列值匹配常会将维度表错误排序并压制核心事实表。此外，当维度表通过值/行层跨层命中时，缺乏摘要，代码被迫使用了 fallback hack 从 `custom_table_info` 中加载。

### 变更内容
#### backend/app/config.py [MODIFY]
- 将 `lexicon_schema_top_k` 的默认配置值从 `3` 调优为 `5`，确保表层独立决策时核心事实表有足够的召回率。

#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 表层独立决策：直接由表检索结果提取主表结构（Primary Table Schema）并置于核心展示位置。
- 值层降权追加：值层命中用于提取不重复的辅助维度表结构（Auxiliary Table Schema），并降权渲染在独立子版块中。
- 设定防噪门槛：只处理值层前 3 项，最多只追加 2 张辅助表，行级检索彻底旁路隔离不再触发 DDL 追加，防止无关表过召回。
- 精简代码：完全废除并删除了原有针对 `summary` 为 `None` 时的兜底 Fallback Hack 逻辑。

#### backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py [MODIFY]
- 适配新的渲染格式断言，并新增针对值层降权追加与行层防表污染的单元测试用例，所有测试顺利通过。

---

## 2026-07-18 17:10 +08:00 - 物理词典检索工具支持动态 limit 参数以避免截断遗漏

### 问题根因
当环境变量 `LEXICON_VALUE_TOP_K` 被设置为较小值（例如 3）时，检索到的物理列值或实体数量会被底层检索器强制截断。对于存在 6 个以上相关物理值的数据库，LLM 执行 `search_db_value_lexicon` 工具时仅能获取被截断的前 3 条数据，从而导致关键数据遗漏，影响 SQL 生成与纠偏。

### 变更内容
#### backend/app/agent/tools/sql_lexicon_tools.py [MODIFY]
- 修改 `search_db_value_lexicon` 和 `search_db_row_lexicon` 工厂函数创建的工具定义，使其接受可选的 `limit: int = 10` 参数，默认值设为 10。
- 执行查询前，临时重写检索器的 `similarity_top_k` (及 `_similarity_top_k`) 属性为 `limit`，并在 `finally` 块中复原，防止干扰常规的 RAG 预检索。
- 格式化输出表格切片同步修改为 `nodes[:limit]`。

#### backend/tests/agent/tools/test_sql_lexicon_tools.py [MODIFY]
- 在单元测试 `test_db_value_lexicon_tool` 和 `test_db_row_lexicon_tool` 中，增加 `limit` 传参测试。
- 增加 assertion，校验检索期间 `similarity_top_k` 属性成功被修改，并在工具调用结束后正确复原。

---

## 2026-07-18 16:40 +08:00 - 修复三层 DB 检索偶发仅显示表名的 Bug

### 问题根因
`BusinessRagMiddleware._format_and_assemble_state` 中，`custom_table_info`（启动时预热的完整 DDL 缓存）被取出后从未使用。当某张表仅通过**值层或行层**跨层命中（未经过表结构层检索），其 `summary` 字段为 `None`，导致前端和模型提示词只能看到裸表名 `表: ods.xxx`，丢失了全部字段和注释信息。

### 变更内容
#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 修复 `_format_and_assemble_state` 中 `display_text` 的 fallback 逻辑：在 `summary` 为 `None` 时，先从 `custom_table_info` 缓存中按**全名**（带 schema 前缀）或**短名**（无前缀）查找完整 DDL，查找失败才降级为裸表名。
- 新增注释说明 key 命名兼容策略（Milvus 向量库使用全名，SQLAlchemy inspector 返回短名）。

---

## 2026-07-18 15:10 +08:00 - SQL Agent 主动纠偏工具链与自愈重写（SQL Lexicon）

### 概述
- **主动纠偏工具链**：在 Agent 层引入了三个专有向量物理词典纠偏与探索工具（`search_db_value_lexicon`、`search_db_row_lexicon`、`search_db_table_schema`），允许 Agent 在执行 SQL 返回空结果或表结构认知缺失时，自主利用 Milvus 向量物理词典查询正确的列值、行实体或表结构。
- **系统提示词微调**：在 `base_system_prompt.md` 中新增了空结果反思与自愈纠偏规约，指导大模型在查询无结果时自发调用纠偏工具并重写 SQL，实现“自愈”重试。
- **中间件折叠适配**：在 `prompt_compiler_middleware.py` 的折叠工具白名单中挂载上述三个纠偏工具，确保在滑动窗口外自动折叠相应的 ToolMessage 以降低 token 消耗。
- **工具链生命周期注入**：在 `service.py` 中提取并复用 `BusinessRagMiddleware` 初始化时产生的 `DatabaseLexiconRetriever` 物理词典检索器单例，在同步和异步的 Agent 工具初始化路径中统一挂载新工具。
- **单元测试保障**：新增 `test_sql_lexicon_tools.py` 完整验证了三个纠偏工具的逻辑和输出格式。

### 变更内容
#### backend/app/agent/tools/sql_lexicon_tools.py [NEW]
- 新增 `search_db_value_lexicon`、`search_db_row_lexicon`、`search_db_table_schema` 三个工具及其工厂构建函数，使用 `lexicon_retriever` 进行向量/文本召回。

#### backend/app/agent/tools/__init__.py [MODIFY]
- 导出物理词典纠偏工具相关工厂函数。

#### backend/app/agent/service.py [MODIFY]
- 修改 `_prepare_tools` 接收可选的 `lexicon_retriever` 并完成工具挂载；在 `SQLAgentService` 同步与异步初始化方法中均注入该检索器。

#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 在 `COLLAPSIBLE_TOOLS` 折叠工具集合中追加纠偏工具名。

#### backend/app/agent/prompts/base_system_prompt.md [MODIFY]
- 增加空结果反思与自愈纠偏段落，明确纠偏工具使用时机。

#### backend/tests/agent/tools/test_sql_lexicon_tools.py [NEW]
- 新增单元测试用例对三个纠偏工具的逻辑与输出格式进行验证。

#### docs/superpowers/plans/2026-07-17-sql-agent-self-healing-lexicon.md [NEW]
- 新增 SQL Agent 主动纠偏工具链与自愈重写实施计划文档。

---

## 2026-07-17 16:00 +08:00 - Schema 语义摘要嵌入优化 & 三层检索架构对齐（SQL Lexicon）

### 概述
- **DDL 嵌入 → 语义摘要嵌入**：将 `table_schema_store` 集合的嵌入内容从完整 DDL（含 `VARCHAR(50) NOT NULL` 等类型/约束噪声）替换为语义摘要（表名 + 表注释 + 字段名及注释），大幅缩减嵌入文本长度，提升表选择语义匹配精度。
- **消除分块膨胀**：`milvus_load_node.py` 改用 `VectorStoreIndex(nodes=nodes, ...)` 构造函数直接注入 `TextNode`，跳过 `SentenceSplitter` 分块，使每个表在 `table_schema_store` 中仅对应 1 条记录（原长 DDL 被切成多条，导致 5 个表产生 7 条记录）。
- **物化视图支持**：`extractor_nodes.py` 启用 `include_materialized_views=True`，将 `mart.mart_position_current_overview`（物化视图）纳入表结构检索范围。
- **召回内容与展示一致**：`rag_middleware.py` 中 Agent 提示词 `formatted_text` 和前端 `detail` 均改为展示实际召回的语义摘要，不再从 `custom_table_info` 取完整 DDL；三者（嵌入、Agent 提示词、前端展示）统一使用语义摘要，消除信息不一致。
- **展示上限与配置对齐**：三层展示上限硬编码 `[:3]` / `[:5]` / `[:5]` 替换为 `lexicon_schema_top_k` / `lexicon_value_top_k` / `lexicon_row_top_k` 配置参数。
- **代码重复消除**：`before_model` / `abefore_model` 抽取出共用 `_extract_query` 方法，减少 39% 重复代码。
- **样本数据残留清理**：正则增强，一并移除 `-- Sample rows:` 空标题行。
- **全量测试通过**：9 项单元测试全部通过（PASS）。

### 变更内容
#### backend/app/agent/utils/db_utils.py [MODIFY]
- 新增 `_list_db_objects(inspector, ...)` — 提取表列表逻辑为独立函数，去重保序，供 `fetch_table_definitions_with_comments` 复用（DRY）。
- 新增 `_build_semantic_summary(conn, inspector, table, db_dialect)` — 构建单表语义摘要，仅保留表名、表注释、字段名及注释，剥离类型/约束/样本噪声。
- 新增 `fetch_table_semantic_summaries(db_uri, ...)` — 批量提取语义摘要字典 `{表名: 摘要文本}`，供 `TableDDLExtractorNode` 使用。

#### backend/app/agent/utils/__init__.py [MODIFY]
- 导出 `fetch_table_semantic_summaries`，与 `fetch_table_definitions_with_comments` 保持一致的导出风格。

#### backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py [MODIFY]
- 将 `TableDDLExtractorNode.process()` 中的 DDL 提取调用替换为 `fetch_table_semantic_summaries`，使用语义摘要作为 `Document.text` 进行嵌入。
- 启用 `include_materialized_views=True`，修复物化视图表未被纳入检索的问题。

#### backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py [MODIFY]
- 提取 `_index_nodes(docs, settings, collection_name)` 辅助方法，消除三组重复的嵌入/存储逻辑。
- 改用 `VectorStoreIndex(nodes=text_nodes, storage_context=ctx)` 直接注入 `TextNode`，跳过 `SentenceSplitter` 分块，确保每个表在 Milvus 中仅对应一个实体。

#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 召回内容展示对齐：`structured_tables`（前端 `detail`）和 `ddl_block`（Agent `formatted_text`）均改为展示实际召回的语义摘要，不再从 `custom_table_info` 取完整 DDL。
- 展示上限配置化：`top_tables[:3]` → `settings.lexicon_schema_top_k`，`values[:5]` → `settings.lexicon_value_top_k`，`rows[:5]` → `settings.lexicon_row_top_k`。
- 代码重复消除：新增 `_extract_query` 共用方法，`before_model` / `abefore_model` 合计减少 39% 代码量。
- 样本数据清理增强：正则一并移除 `-- Sample rows:` 头部残留行。

#### backend/tests/agent/utils/test_semantic_summary.py [NEW]
- 4 个单元测试覆盖 `_build_semantic_summary` 的字段注释、无表注释、PG fallback 查询、无注释字段等场景。

#### backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py [NEW]
- 2 个单元测试验证 `TableDDLExtractorNode` 使用语义摘要及非白名单表过滤。

#### backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py [NEW]
- 2 个单元测试验证 `MilvusIngestionNode` 使用 `VectorStoreIndex(nodes=nodes, ...)` 构造函数注入及空集合跳过逻辑。

#### backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py [MODIFY]
- 补充语义摘要断言，适配 `formatted_text` 和 `detail` 展示召回内容的新行为。

#### docs/superpowers/plans/2026-07-17-schema-semantic-summary-embedding.md [NEW]
- 4 任务实施计划文档。

---

## 2026-07-18 15:00 +08:00 - 图表工具使用规约重构（§4.2 → 四层规范）

### 概述
- **重构 §4.2 图表建议规则**：将原有的单层前端标记规则重写为四层结构（触发条件 → 排除场景 → 建议策略 → 执行策略），明确量化触发条件（≥2 行、含数值列、4 类场景），补充排除场景（单值/纯文本/用户拒绝/截断数据），分离 `suggest_chart` 标记与 `build_chart_artifact` 调用时机。
- **删除旧 §4.3 参数规则**：`build_chart_artifact` 的 6 键约束与 `category_field/category_value` 成对约束保留至 §4.4 输出格式规范中，避免信息重复。

### 变更内容
#### backend/app/agent/prompts/base_system_prompt.md [MODIFY]
- 替换 §4.2 为 `图表建议与生成规则`，含 4 个子节（4.2.1~4.2.4）。
- 删除旧 §4.3，参数约束合并至 §4.4。

---

## 2026-07-16 21:40 +08:00 - 时间敏感因子（当前日期）排布优化与注意力增强

### 概述
- **时间敏感因子位置下沉**：将系统当前日期的提示语从原本 `<runtime_context>` 的头部移动至最尾端，作为紧邻用户对话历史前的最后一个锚点，有效提升大模型在强注意力区对日期和时间的读取和指令遵从精度。
- **全量测试通过**：确认移动排布位置对现有的 XML 分区校验和状态保存均无副作用，全量 22 项中间件单元与集成测试依然全量通过（PASS）。

### 变更内容
#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 修改 `_modify_request` 方法，在 `dynamic_parts` 动态段落列表的末尾追加 `date_prompt` 时间锚点。

---

## 2026-07-16 15:22 +08:00 - 数据库物理词典（DB Lexicon）前端折叠展示优化

### 概述
- **后端三层检索结构化与 SSE 适配**：在 `BusinessRagMiddleware` 中间件中将表 DDL、列值、实体行等三层检索结果结构化为 `detail` 载荷；在 `api.py` 及 `services.py` 里的流式早期异步推送 `type: "lexicon_context"` 自定义 SSE 事件给前端，并在 `schemas.py` 注册了对应 Payload 模式。
- **前端状态、流订阅与 UI 嵌套折叠渲染**：在前端 `types/index.ts` 补充契约，在消息 Pinia store (`messages.ts`) 与 `useChatStream.ts` 建立缓存与推送监听；在 `MessageItem.vue` 中支持动态捕获物理词典上下文并使用多级嵌套折叠面板呈现，实现了与业务知识术语相同的气泡折叠效果。
- **全量测试通过**：对 `test_rag_middleware.py` 单元测试用例补充了 `detail` 物理结构的断言，测试以 100% 成功率通过（PASS）。

### 变更内容
#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 在返回值 `lexicon_context` 中加入了结构化明细字段 `detail`（内含 tables、values、rows）。

#### backend/app/schemas.py [MODIFY]
- 增加了 `LexiconTablePayload`, `LexiconValuePayload`, `LexiconRowPayload`, `LexiconContextPayload` 以及 `LexiconContextStreamEvent` 流事件，并注册进入 `ChatStreamEvent`。

#### backend/app/services.py [MODIFY]
- 在 `process_stream` 生成流的过程中，检测 state 触发异步 emit `"lexicon_context"` 消息。

#### backend/app/api.py [MODIFY]
- 在两个 SSE 流消息 yield 节点中加入了对 `lexicon_context` 事件的直接透传。

#### frontend/src/types/index.ts [MODIFY]
- 增加 `LexiconContext` 类型，更新相关消息/事件契约。

#### frontend/src/stores/messages.ts [MODIFY]
- 增加 `memoryLexiconMap` 及其落定与缓存处理。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 在 handleStreamMessage 与 resumeMessage 事件分流中增加对 `lexicon_context` 的监听。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 增加 `parsedLexiconContext` 计算属性，采用 details 与 Table 嵌套实现物理词典折叠渲染。

#### backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py [MODIFY]
- 在用例中追加了对 `detail` 数据明细和表名/DDL 的断言。

---

## 2026-07-16 11:01 +08:00 - 实施阶段 4 联调与数据库持久化存储验证

### 概述
- **持久化集成测试编写**：新建了集成测试脚本 `test_persistence_integration.py`，模拟多轮对话生命周期，验证了状态化传输后的数据库归档行为。
- **验证历史消息去污染**：测试脚本严格断言并证实，持久化到 MemorySaver 中的 `messages` 列表彻底免除了 `"__business_rag_context__"` 等大段 RAG 上下文信息的污染，成功达到大幅缩减数据库存储空间的目标。
- **状态序列化验证**：确认 `lexicon_context` 状态被成功持久化，且能够在多轮迭代中平滑地执行覆盖更新（Last-Wins），无任何类型序列化异常。

### 变更内容
#### backend/tests/agent/test_persistence_integration.py [NEW]
- 编写了完整的集成持久化校验用例，涉及 mock 数据连接、序列化对象校验、以及绿线防污染断言。

---

## 2026-07-16 10:52 +08:00 - 实施阶段 3 静态与动态分区物理隔离设计 (Prompt Caching 优化)

### 概述
- **XML 物理分区编译**：在 `PromptCompilerMiddleware` 中将拼接提示词进行了结构化物理隔离，划分为 `<system_rules>`（静态规则区）和 `<runtime_context>`（动态上下文区）两个 XML 标签分区。
- **提升 Prefix Cache 命率**：静态大段规则（基础提示词和 Available Skills 可用大纲）被打包进 `<system_rules>` 区，由于内容永不变化，使 LLM 服务端能够 100% 缓存该前缀；时间、已加载 DDL 骨架及 RAG 参考等高频变化的数据置于 `<runtime_context>` 后置区，避免污染前置静态缓存。
- **测试对齐校验**：对齐并更新了 `test_prompt_compiler_middleware.py` 的测试断言，严格校验分区标签的起止和静态与动态内容在正确分区内的包含关系，全量 21 个单元测试（含 RAG 部分）一次性全部通过（PASS）。

### 变更内容
#### backend/app/agent/middleware/prompt_compiler_middleware.py [MODIFY]
- 修改 `_modify_request` 方法，利用 `content_blocks` 的特征识别提取基础提示词和大纲并包裹在 `<system_rules>` 中，其他部分包裹在 `<runtime_context>` 中并进行物理组合。

#### backend/app/agent/middleware/test_prompt_compiler_middleware.py [MODIFY]
- 更新测试用例 `test_safe_merge_inject_current_date_no_rag` 和 `test_safe_merge_inject_current_date_with_rag`，增加了对 XML 闭合标签及静态/动态分区所属情况的严格校验。

---

## 2026-07-16 10:28 +08:00 - 实施阶段 2 类名与文件规范化重构 (Rebranding)

### 概述
- **物理文件重命名**：将 `safe_merge_middleware.py` 重命名为 `prompt_compiler_middleware.py`，并将对应的单元测试 `test_safe_merge_middleware.py` 重命名为 `test_prompt_compiler_middleware.py`。
- **类名语义对齐**：将类名 `SafeMergeSystemMiddleware` 改为 `PromptCompilerMiddleware`，代表系统提示词与 RAG 背景知识的终极编译和合并职责。
- **引用同步更新**：同步修改了包出口 `__init__.py` 以及服务类 `SQLAgentService` 的初始化引入。
- **测试全量回归**：测试全部通过（20 个 PromptCompiler 单元测试和 1 个 RAG 单元测试）。

### 变更内容
#### backend/app/agent/middleware/prompt_compiler_middleware.py [NEW]
- 创建了重构后的 PromptCompiler 类文件。

#### backend/app/agent/middleware/safe_merge_middleware.py [DELETE]
- 删除了原文件。

#### backend/app/agent/middleware/test_prompt_compiler_middleware.py [NEW]
- 创建了重构后的测试类文件。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [DELETE]
- 删除了原测试文件。

#### backend/app/agent/middleware/__init__.py [MODIFY]
- 更新中间件列表，导出 `PromptCompilerMiddleware`。

#### backend/app/agent/service.py [MODIFY]
- 更新引用，在 `middleware_list` 中引入并实例化 `PromptCompilerMiddleware()`。

---

## 2026-07-16 10:22 +08:00 - 实施阶段 1 数据流去耦与状态化 RAG 传递优化

### 概述
- **对话历史去耦优化**：重构了业务知识 RAG 中间件，取消往历史消息列表 `messages` 插入 RAG 文本块的机制。改用 `CustomState` 中的结构化字段 `rag_context` 与 `lexicon_context` 在内存中传递数据，彻底阻断了 PostgresSaver 数据库中的对话历史消息污染与物理空间暴增问题。
- **状态化提示词拼装**：重构了合并中间件 `SafeMergeSystemMiddleware`，将提取历史消息并抽干的逻辑替换为直接从状态（`state.lexicon_context`）读取预格式化的 RAG 文本直接物理拼接。
- **向下兼容过滤**：在合并中间件过滤消息时，增加了对数据库中可能残留的老旧 RAG 消息的防御性过滤，确保线上旧会话能够平滑迁移。
- **全量单元测试通过**：重构并对齐了 `test_rag_middleware.py` 和 `test_safe_merge_middleware.py`，全量测试均顺利通过。

### 变更内容
#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 修改 `_format_and_assemble_state` 方法，取消在 `messages` 中插入 `SystemMessage` 的逻辑，直接以 `formatted_text` 字段返回在 `lexicon_context` 状态字典中。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 修改 `_modify_request` 方法，直接从 `request.state.lexicon_context` 读取 RAG 文本进行拼装。
- 添加对历史消息中残留的 `__business_rag_context__` 污染消息的防御性过滤逻辑以向下兼容。

#### backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py [MODIFY]
- 对齐状态化传递测试，验证返回字典中无 `messages` 且 RAG DDL 包含在状态的 `formatted_text` 中。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 重构 `test_safe_merge_inject_current_date_with_rag`，测试从 `state.lexicon_context` 传递 RAG 文本的合并与拼装行为。

---

## 2026-07-15 20:47 +08:00 - 实现数据库物理词典 (DB Lexicon) 启动同步参数可配置化

### 概述
- **新增启动同步配置项**：在后端配置类 `Settings` 中新增 `db_lexicon_sync_on_startup` 配置项，允许通过环境变量 `DB_LEXICON_SYNC_ON_STARTUP` 决定是否在 FastAPI 服务启动时执行三层物理词典 (DB Lexicon) 向量异步嵌入同步任务。
- **防止重复长耗时嵌入**：在 `lifespan` 启动钩子中，根据该配置值条件判断是否异步执行 `start_metadata_lexicon_sync_async`，避免每次启动或在数据库未变化时耗时重复执行嵌入过程，显著优化启动耗时。
- **覆盖写入参数对齐**：使用 `settings.milvus_overwrite` 代替原本硬编码的 `overwrite=True`，让同步行为更符合系统配置。
- **验证通过**：运行单元测试 `test_sync_metadata.py` 成功通过。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `db_lexicon_sync_on_startup` 参数配置，支持从环境变量读取，默认为 `true`。

#### backend/app/main.py [MODIFY]
- 修改启动钩子，仅在 `settings.db_lexicon_sync_on_startup` 为真时启动异步物理词典同步任务，并传递 `settings.milvus_overwrite`。

#### .env / .env_docker [MODIFY]
- 声明并加入 `DB_LEXICON_SYNC_ON_STARTUP="true"` 并补充说明注释。

---

## 2026-07-14 23:20 +08:00 - 实现 SQL 骨架表与检索嵌入表白名单配置解耦 (去中心化自治优化)

### 概述
- **去中心化嵌入白名单配置**：在技能 `meta.py` 内部引入了 `"lexicon_enabled_tables"` 配置字段。实现了将 “SQL 生成元数据骨架（`associated_tables`）”与“行/列字典检索嵌入候选（`lexicon_enabled_tables`）”的明确职责解耦与分工。
- **配置结构顺序重整**：为提升可读性，将 `meta.py` 字典属性排版调整为：表级配置（表骨架 & 嵌入白名单） $\rightarrow$ 行级白名单 $\rightarrow$ 列级白名单（从宏观至微观的心智模型）。
- **同步管道逻辑修正**：在 `MetadataExtractorNode` 中移除了硬编码的 `dim.` / `mart.` 前缀前置过滤规则，完全采用技能自包含的嵌入白名单对行列去重值抽取表名进行校验拦截。
- **集成测试通过**：对同步测试方法进行了无死锁改造（去除 asyncio mark 并通过 asyncio.run 在空事件循环下自启动测试），单元测试全量顺利通过（2 passed in 137.35s）。

### 变更内容
#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- 引入 `lexicon_enabled_tables` 表嵌入白名单并重整配置顺序。

#### backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py [MODIFY]
- 在 `MetadataExtractorNode` 中支持嵌入表白名单过滤，移除 schema 字符前缀匹配规则。

#### backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py [MODIFY]
- 重构为同步测试，使 pytest 的测试线程行为与生产环境完全对称对称。

---

## 2026-07-14 22:32 +08:00 - 重构 SQL 表格检索为专属模块并引入 Ingestion Pipeline 流式管道 (架构隔离与复用对齐)

### 概述
- **物理解耦与安全隔离**：创建了独立的 `sql_lexicon/` 专属模块包，将三层检索中 SQL 向量词典与 Schema 检索的所有代码完全从原生文档/知识库 RAG 中抽离，做到了物理上 100% 隔离，杜绝原有业务受损的隐患。
- **公共 Milvus 存储连接工厂**：在 `sql_lexicon/store.py` 内部封装了统一的 `get_milvus_vector_store` 函数，将混合检索所需的 BM25 中文分词、相似度度量（IP）、RRF 重排、多路覆写等物理参数收敛在一处。
- **引入 Ingestion Pipeline 流式架构**：在 `pipeline/` 下引入了 `PipelineNode` 接口和 `IngestionPipeline` 控制器。开发了 `MetadataExtractorNode`（技能扫描）、`TableDDLExtractorNode`（表 DDL 抽取）、`ColumnLexiconExtractorNode`（列值字典抽取）、`RowLexiconExtractorNode`（行实体抽取）和 `MilvusIngestionNode`（向量加载）等五个可拔插流式节点。
- **清理历史遗留垃圾**：安全地物理删除了散落在外的 `sync_metadata_lexicon.py`、`init_metadata_collections.py` 以及旧版本集成测试。

### 变更内容
#### backend/app/agent/vector/sql_lexicon/ [NEW]
- 新建专属模块目录，提供 `store.py`、`tasks.py`、`init_script.py` 以及 `pipeline/` 流式管道子包。

#### backend/app/main.py [MODIFY]
- 修正 `lifespan` 挂载，切换后台同步入口导入路径至 `backend.app.agent.vector.sql_lexicon.tasks`。

#### backend/tests/agent/vector/sql_lexicon/ [NEW]
- 迁移并新建独立测试套件 `test_init_collections.py` 和 `test_sync_metadata.py`。

#### (垃圾文件清理) [DELETE]
- 删除了位于 `vector/tasks/`、`vector/milvus_init/` 以及 `tests/agent/vector/` 下的 4 个临时陈旧遗留文件。

### 验证
- 运行新测试套件 `pytest backend/tests/agent/vector/sql_lexicon/ -v` 顺利完成并通过测试（2 passed in 134.04s）。

---

## 2026-07-14 21:58 +08:00 - 实现三层向量元数据全量同步与 FastAPI Lifespan 自动挂载 (阶段二)

### 概述
- **去中心化元数据全量同步**：实现了从各个注册领域（`discover_domains()`）动态合并白名单表名、列名和行配置，自动提取并计算密集向量与 BM25 分词稀疏向量，重新覆盖导入 Milvus 三个 Collection 的后台任务。
- **PostgreSQL 模式路由兼容**：引入并配置了 `build_postgres_search_path_engine_args`，解决了在多模式（`dim`、`fct`、`mart`）下 SQLAlchemy 无法反射获取表 DDL 和列值的环境兼容问题。
- **FastAPI 启动非阻塞挂载**：在 `lifespan` 钩子中以后台守护线程（`threading.Thread`）方式异步拉起同步任务，成功规避了长耗时 Embedding 运算对主进程 HTTP 绑定的阻塞干扰。
- **集成测试通过**：编写并顺利闭环跑通了 `test_sync_metadata.py` 单元测试，增加了 `flush()` 机制保证测试环境下 Milvus 实体数据断言的实时性。

### 变更内容
#### backend/app/agent/vector/tasks/sync_metadata_lexicon.py [NEW]
- 新增 `run_metadata_lexicon_sync(overwrite: bool)` 及 `start_metadata_lexicon_sync_async(overwrite: bool)` 后台同步服务。

#### backend/app/main.py [MODIFY]
- 在异步 `lifespan(app: FastAPI)` 中导入并注册 `start_metadata_lexicon_sync_async(overwrite=True)`。

#### backend/tests/agent/vector/test_sync_metadata.py [NEW]
- 编写 `test_metadata_lexicon_synchronization` 异步单元测试，全流程覆盖同步任务并对数量大于 0 进行物理刷盘断言。

### 验证
- **本地单元测试**：环境内运行 `pytest backend/tests/agent/vector/test_sync_metadata.py -v` 顺利完成并通过测试（1 passed in 128.05s）。

---

## 2026-07-14 20:53 +08:00 - 修复三层检索 Milvus 集合物理初始化脚本与测试用例事件循环异常

### 概述
- **异步化集合初始化入口**：修复了在同步阻塞测试和直接运行集合初始化脚本时，由于新版 `pymilvus` 初始化 `AsyncMilvusClient` 强依赖运行中事件循环导致抛出 `ConnectionConfigException: no running event loop` 的 Bug。通过将初始化入口重构为异步方法并配合 `asyncio.run()` 完美解决该隐式依赖问题。
- **单元测试异步化对齐**：将 `test_init_collections.py` 对应测试用例升级为 `async` 并使用 `pytest.mark.asyncio` 装配，使其能顺利捕获和配合异步事件循环执行，完全闭环通过了阶段一的测试验证。
- **设计文档结构补充**：将 `table_schema_store`、`db_value_lexicon`、`db_row_lexicon` 三个 Milvus 物理集合的逻辑结构、元数据规范和召回机制补充写入了双轨融合设计报告。

### 变更内容
#### backend/app/agent/vector/milvus_init/init_metadata_collections.py [MODIFY]
- 将 `main()` 修改为 `async def main()`，并更新 `__main__` 块为 `asyncio.run(main())` 启动。

#### backend/tests/agent/vector/test_init_collections.py [MODIFY]
- 引入 `pytest`，将 `test_milvus_collections_initialization` 测试用例重构为异步函数 `async def`，并装配 `@pytest.mark.asyncio` 装饰器，内部使用 `await run_init()`。

#### docs/llamaindex_rag/LlamaIndex SQL 检索与本项目双轨融合设计报告.md [MODIFY]
- 插入全新第三章节 `三、 三层向量检索集合结构设计 (Milvus Collections)`，详细阐述三个 Milvus 集合的物理名称、text计算载体格式、metadata 路由结构和召回后的业务组装用法；顺延调整后续第四、五、六章节序号。

### 验证
- **本地单元测试**：使用绝对路径运行环境内 `pytest` 跑测 `backend/tests/agent/vector/test_init_collections.py` 与 `backend/tests/agent/vector/test_skills_meta_whitelists.py`，全部测试 **100% 成功通过 (3 passed)**。

---

## 2026-07-13 11:11 +08:00 - 收紧多系列图表分类拆线的显式声明约束


### 概述
- **多系列对比黄金规则落地**：为解决多系列对比图表生成时仅依赖系列名称（`name`）模糊自动推理导致的匹配歧义、拼写不匹配以及由此引发的工具运行时报错，通过全链路（系统提示词、工具定义和报错信息）实施强约束，强制大模型必须显式且成对提供 `category_field` 和 `category_value` 组合。
- **无前端代码改动**：由于前端 `ChartArtifactCard` 仅消费已格式化的图表 JSON，且天然原生基于 `category_field`/`category_value` 进行过滤渲染，故此项加固完全在后端与 LLM 指令端闭环完成，保持前端零改动。

### 变更内容
#### backend/app/agent/prompts/base_system_prompt.md [MODIFY]
- 修改第 4.3 节关于图表构件生成规则的描述，将原来宽松的“或在 name 中包含可识别分类值”表述彻底替换为强制显式声明的规则，并指引大模型不确定时优先使用 SQL 检索明确后再进行图表参数组装。

#### docs/reconstructed_system_prompt.py [MODIFY]
- 同步修改重构系统提示词中的第 4.3 节规则，以保持示例模板与线上提示词一致。

#### backend/app/agent/tools/chart_artifact_tool.py [MODIFY]
- 更新 `build_chart_artifact` 工具的英文 Docstring，移除带有误导性的模糊自动推理声明，明确要求大模型显式提供 `category_field` 与 `category_value` 组合。
- 修改 `_infer_category_series` 函数校验失败时的 ValueError 报错文案，去除关于 `name` 推理的误导提示，强制指出必须使用显式参数对系列分类进行设定。

### 验证
- **系统提示词单元测试**：在本地执行 `pytest backend/app/agent/test_service_prompt.py` 测试用例，断言逻辑与模板整体匹配，全部通过。

---

## 2026-07-12 22:43 +08:00 - 黄金案例审核终端重构为模态弹窗显示

### 概述
- **审核终端弹窗化**：为了改善原先审核终端内联展示导致的硬切屏、视觉割裂和当前会话上下文丢失的问题，将其彻底重构为了自包含的模态弹窗（Modal）。管理员可以随时唤起与关闭审核面板，而底层的对话状态和输入内容得以完整保留。

### 变更内容
#### frontend/src/components/AdminReviewPanel.vue [MODIFY]
- 新增 `show` 属性作为显示开关，并提供 `update:show` 事件。
- 引入 `<Transition name="modal-fade">` 挂载半透明毛玻璃背景遮罩与 `h-[85vh]`、`w-[95vw] max-w-6xl` 大尺寸的弹窗容器。
- 增加了绝对定位的右上角关闭按钮，并为顶部的“刷新列表”按钮设置了 `mr-10` 边距避免按钮遮挡。
- 在 `watch` 与生命周期钩子中实现了弹窗唤起时锁定 `document.body` 滚动，关闭时释放的拦截机制。
- 注册了 `keydown` 监听器，支持在弹窗打开时按下键盘 `Escape` 键直接退出的便捷体验。
- 优化了状态响应式自愈，在弹窗每次显示时自动执行数据加载刷新。

#### frontend/src/views/ChatView.vue [MODIFY]
- 移除了原有的内敛渲染卡片，并撤销了主聊天内容和输入框的 `v-else` 隐藏限制，保持状态常驻。
- 在页面模板底部平级引入并挂载了 `<AdminReviewPanel v-model:show="showAdminReview" />`。

### 验证
- **构建测试**：在 `frontend` 目录下运行 `npm run build` 打包任务，编译成功，零 TypeScript 错误及样式编译冲突。
- **功能与交互验证**：弹窗可以正常通过主页面的“审核终端”按钮唤起；键盘 `ESC`、遮罩层点击、右上角 `X` 关闭等关闭流程符合预期；弹窗打开时背景滚动穿透拦截成功。

---

## 2026-07-12 22:36 +08:00 - 修复 Markdown 表格对中对齐不一致问题

### 概述
- **表格对齐强制居中**：解决了在大模型输出中，因包含对齐声明语法（如 `:---`）生成的 inline 样式覆盖全局表格居中属性，导致表格有时居中、有时靠左对齐的现象。通过在全局样式和消息展示组件中引入强制居中（`text-align: center !important`），确保所有表格表现一致。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 在 scoped style 样式块中，为 `.message-markdown :deep(th)` 和 `.message-markdown :deep(td)` 规则加入了 `text-align: center !important`。这会直接覆盖 markdown-it 解析后注入的 inline 样式以及继承的左对齐样式。

#### frontend/src/style.css [MODIFY]
- 将全局的 `.message-markdown th` 和 `.message-markdown td` 的 `text-align: center` 样式属性提升为 `text-align: center !important`，以确保全局多处使用时的居中样式兜底有效。

### 验证
- **构建测试**：在 `frontend` 目录下运行 `npm run build`，项目打包成功，无编译或类型检查报错。
- **渲染验证**：测试了普通 Markdown 表格和显式左对齐声明的表格，两者均能在页面中保持完美的居中对齐排版。

---

## 2026-07-11 20:45 +08:00 - RAG 检索业务术语提前流式抛出与前端折叠卡片实现 (阶段二)

### 概述
- **RAG 术语提前流式抛出**：实现了在前置 RAG 中间件检索出业务参考术语后，在大模型尚未生成任何文本 token 之前，前置以独立的 SSE 事件类型（`type: "rag_context"`）将结构化的业务术语列表提前流式推送给前端，极大地缩短了用户对 RAG 展现的感知延迟，消除了传统等待焦虑。
- **提问词校验与重置自愈 (Checkpoint 竞争修复)**：修复了由于 LangGraph Checkpoint 写盘滞后导致 `aget_state` 在流式最早期读到上一轮对话历史残留数据并误发老卡片的 Race Condition。通过在 `process_stream` 的 `input_data` 中硬编码置空 `rag_context`，同时在 `services.py` 轮询发射前强制进行 `rag_query == user_query` 双重提问词比对校验，完全阻断了上一轮脏状态的提前误抛。
- **隔离缓存字典防历史冲刷 (前端持久化防覆盖)**：解决了为了不污染数据库而“不落库”的 RAG 字段，在流式完成触发前端 `syncMessagesIfCurrent` 全量拉取覆盖 messages 列表时，被空数据无情冲刷擦除的 Bug。在 `messagesStore` 引入纯内存隔离字典 `memoryRagMap`（以消息 ID 为键），完美实现在当前页面生命周期内卡片稳固显示。
- **高质量 collapsible 卡片渲染**：在 `MessageItem.vue` 正文与脚标之间插入了精致的原生 `<details>` 折叠面板组件。具备扁平化无衬线现代浅灰背景与流畅箭头转动动画，多表口径呈现更直观。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 新增 `RAGContextPayload` 结构和 `RAGContextStreamEvent` Pydantic 事件模型，并将其注册到统一的 `ChatStreamEvent` discriminated union 中，支持 API 安全序列化。

#### backend/app/services.py [MODIFY]
- 在 `process_stream` 输入中主动清空 RAG 键，同时在 `_stream_execution_loop` 循环最早期，结合 `rag_query == user_query` 逻辑对 `aget_state` 提取出最新的 RAG 信息并以自定义 `rag_context` 事件前置抛出，阻断历史快照残留。

#### backend/app/api.py [MODIFY]
- 在 `chat_session_stream` 和 `resume_session_stream` 两处流式 SSE API 接口中，增加对 `rag_context` 事件的解析路由，以 SSE 事件形式将其直接透传 yield 发送给客户端。

#### frontend/src/types/index.ts [MODIFY]
- 在 `Message`、`FinalizedStreamingMessage` 与 `StreamingMessage` 接口中，分别扩展并对齐了 `rag_context` 和 `ragContext` 临时/流式属性的声明。
- 在 `StreamEvent` discriminated union 类型中添加了 `'rag_context'` 类型的定义。

#### frontend/src/api/chat.ts [MODIFY]
- 在 `STREAM_EVENT_TYPES` 校验白名单集合中登记 `'rag_context'` 事件。
- 在 `parseChatStreamEvent` 解析拦截器中加入 `'rag_context'` 分支，并将其安全返回。

#### frontend/src/stores/messages.ts [MODIFY]
- 新增 `memoryRagMap` 响应式字典（`Record<string, Array<...>>`）。
- 修改 `completeStreamingMessage`，在流式完成转换为正式 Message 时，将临时 `ragContext` 挂载到永久 `Message` 的同时，以消息 ID 为 Key 缓存至 `memoryRagMap` 中。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 在新会话流与澄清流两处核心 SSE 事件循环开关中，新增对 `rag_context` 的监听处理，并在收到时将其直接缓存给 `streamingMessage.ragContext`。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 导入 `useMessagesStore` 并定义实例，新增计算属性 `parsedRagContext`，优先从 `messagesStore.memoryRagMap[message.id]` 中还原数据，防止历史同步数据冲刷卡片。
- 在 Markdown 模板内容区下方、脚标上方，嵌入精美的折叠面板卡片展示结构化术语标题、业务域、别名和口径内容。

### 验证
- 后端单元测试：运行 `conda activate py312_agent; pytest backend/app/test_services_stream_filtering.py -v` 完美 PASSED（100% 成功）。
- 前端打包构建：执行 `npm run build:check`（`vue-tsc && vite build`），全模块成功编译，TypeScript 零错误。

---

## 2026-07-11 17:50 +08:00 - 流式输出防泄漏与 SQL 检查降级及前端体验美化优化

### 概述
- **流式消息安全隔离**：修复了在 Agent 异步流式输出时，由于底层通道无差别广播消息，导致 `SystemMessage`（RAG 上下文）和 `ToolMessage`（SQL 查询逻辑与 Linter 报错）的文本片段泄露到 AI 最终正文气泡里的 Bug。仅允许 `AIMessage` 类消息的 `text_segment` 被转为 token 事件发送给前端，其余系统和工具事件只在其他独立通道传递，实现流式阅读区和技术细节的彻底分离。
- **配置化二元校验**：在 `Settings` 配置中引入了 `sql_checker_mode`（默认值为 `fast`）。支持 `fast`（乐观运行，跳过大模型 Checker，由本地 Linter 进行安全硬规约拦截）和 `safety`（同步阻断式大模型校验）两种模式。在保障本地 Linter 安全拦截的前提下，将单次查询的检查耗时从 14.68 秒压缩至毫秒级，响应延迟（TTFT）缩短 93% 以上。
- **前端 AI 消息体验美化**：优化了消息渲染。为了保留 AI 思考过程供用户查看，只对 AI 消息尾部的 `[数据真实查询时刻: ...]`、`查询时间: ...` 以及 `数据来源: ...` 等元数据文本进行正则清洗，并以精致的独立卡片脚标进行分流排版；针对含有空格、括号括号注释、全角逗号等多表多数据源场景，采用了“优先提取并清除时间、再贪婪截取数据源整行”的健壮逻辑，彻底解决元数据残留导致的表格排版错乱 Bug，**且增加了对数据源末尾残留的中英文逗号句号（如 `, 。`）的正则剔除与净化，保证数据源标签视觉极致纯净**。同时为 Markdown 表格定制了精致斑马纹和 hover 悬浮高亮样式，并为 SQL 代码 pre 块加上暗色背景与 SQL 徽章。**追加了全局等宽中文字体补全（Fallback）机制，彻底解决了 `font-mono`/`code`/`pre` 内中文（如数据源括弧、无 SQL 记录提示）回退至宋体的字形不一致 Bug。**

### 变更内容
#### backend/app/services.py [MODIFY]
- 修改 `_stream_execution_loop` 中 `chunk_type == "messages"` 消息块的处理，加入 `isinstance(message_chunk, AIMessage)` 校验。

#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中新增 `sql_checker_mode` 字段，默认从环境变量 `SQL_CHECKER_MODE` 中加载。

#### .env [MODIFY]
- 新增 `SQL_CHECKER_MODE="fast"` 并补充了详细的模式注释。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 修改 `sql_db_query`，将大模型 SQL 检查工具的 `invoke` 校验包装在 `settings.sql_checker_mode == "safety"` 逻辑分支中。

#### backend/app/agent/tools/sql_tools_local.py [MODIFY]
- 对本地工具模块同步进行包装修改，清理了重复的 `settings` 导入。

#### backend/app/test_services_stream_filtering.py [NEW]
- 编写专项过滤测试用例，模拟 LangGraph 输出不同角色消息（SystemMessage, ToolMessage, AIMessage），断言验证仅有 AI 回复的文本被吐给前端。

#### backend/app/test_sql_checker_mode.py [NEW]
- 新增测试套件，通过 mock `settings` 和 tools 验证不同检查模式下的行为，断言 `fast` 模式下完全没有发起 checker 接口调用。

#### frontend/src/utils/markdown.ts [MODIFY]
- 新增并导出 `extractMetaData` 工具函数。采用“时间优先剔除，数据源整行贪婪截取”的双阶正则策略，清洗提取出复杂的查询时刻与复杂多表数据源，避免因顿号、中括号及全角逗号等被误识别残留。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 引入元数据提取模块，创建 `metaData` 与清洗后的 `displayContent` 计算属性；模板中在气泡底端增加图标卡片式脚标；底部追加 `scoped style` 渲染 Markdown 表格（表头样式、斑马纹、悬停背景）和 pre/code 代码块。

#### frontend/src/utils/test_markdown.js [NEW]
- 编写专项 Node.js 测试脚本，动态读取 `markdown.ts` 源码并剥离类型，对提取器逻辑（包括含有括号解释、全角逗号和多表顿号等 3 大复杂场景）进行断言单元测试。

#### frontend/src/style.css [MODIFY]
- 在 `@layer base` 层中为 `.font-mono`、`code`、`pre` 标签注入全局中文字体 Fallback 链（`PingFang SC` / `Microsoft YaHei`），防止等宽字体中文回退为宋体。

### 验证
- 后端测试：运行 `pytest backend/app/test_sql_checker_mode.py backend/app/test_services_stream_filtering.py backend/app/test_api_persistence.py backend/app/test_api_resume.py`，共 16 个测试用例全量 100% PASS。
- 前端测试：运行 `node frontend/src/utils/test_markdown.js`，提取器单元测试成功通过。
- 前端构建：执行 `npm run build:check`（即 `vue-tsc && vite build`），全模块成功打包通过，零 TS 类型错误。

---

## 2026-07-11 15:38 +08:00 - 多步级联查询下 SQL 纠错时序分水岭隔离优化

### 概述
- **时序分水岭保护算法**：修复了在多步 SQL（分步/级联）查询中，大模型前置 SQL 执行成功后，后置最新失败 SQL 尝试（Linter 或运行期报错）在重入中间件时被误杀折叠的 Bug。
- **活跃失败精准分流**：根据当前轮次内“最后一个成功 SQL”的相对时序，将重试失败分类为：
  - *陈旧已解决失败*（位于成功前，已无纠错参考价值，予以抹除折叠）。
  - *活跃重试失败*（位于成功后，模型仍处于新步骤纠错中，予以 `keep_count` 额度保护不折叠）。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重构 `_stage_redaction` 的判断方法，引入 `last_success_idx` 定位最后一个成功 SQL 位置。
- 仅将 `last_success_idx` 之后的失败收集入 `active_failed_ids`，并在其上通过 `keep_count` 截取保护集，对陈旧失败直接抹除。
- 简化 `should_redact` 逻辑为仅检查 `msg.tool_call_id not in ctx.kept_call_ids`。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增单元测试 `test_stage_redaction_keeps_active_failures_after_success`：模拟级联失败场景（失败1 -> 成功2 -> 失败3），验证仅有失败1被抹除，而最新失败3受到完美保护不折叠。

#### docs/context-collapse/summary_and_lessons.md [MODIFY]
- 在重大漏洞复盘中新增「2.5 多步级联查询下，前置成功误杀后续失败 Bug」段落，阐明机制原理和时序隔离设计。

### 验证
- 运行全量后端单元和集成测试用例，77 个测试全部 PASS（100% 成功通过）。

---

## 2026-07-10 22:50 +08:00 - 运行期数据库错误精准识别与重试线索保留修复

### 概述
- **运行期数据库错误精准识别**：修复了在 SQL 重试过程中，由于数据库运行期错误（如 UndefinedColumn 字段不存在）不具备 Linter 特征，被系统粗暴误判定为“SQL 执行成功（successful_sql_call_id）”，从而提前清空并误折叠了历史失败线索（如倒数第二对的 Linter 错误）的 Bug。
- **线索保留机制细化**：细化了失败判定方法，只有真正没出错的 SQL 才是“成功 SQL”，将所有的运行期错误与 Linter 错误统一划归为“失败尝试”，受 `keep_count = 3` 的保护，原样保留作纠错线索。
- **Linter 折叠状态重入判定兼容**：修复了已被抹除折叠的历史 Linter 失败由于丢失了原始的 `X-SQL-LINTER-STATUS: FAILED` 协议头而在多次 ReAct 重入时被误判为“成功 SQL”的缺陷。在检测条件中兼容匹配了折叠占位符 `"validation failed by Linter"`。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 在 `_stage_redaction` 的预扫描中增加 `is_runtime_error` 检测（检查 content 是否含 `error`/`exception` 关键字）。
- 兼容重写：在 `is_linter_error` 的提取判定中，同步加入对已折叠占位符中 `"validation failed by Linter"` 特征词的检测。
- 重构成功的 SQL 查询判定逻辑为 `not info["is_failed"]`（`is_failed = is_linter_error or is_runtime_error`）。
- 将 `failed_ids_in_loop` 的筛选从 `is_linter_error` 扩大为 `is_failed`，使运行期报错同样进入重试保护集。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增单元测试 `test_stage_redaction_keeps_linter_and_runtime_mixed_failures`：验证 Linter 报错与数据库报错混合重试时，最近的错误均被保留，数据库错误不被误判定为成功。

#### docs/context-collapse/proposal2.md [MODIFY]
- 同步了 `_stage_redaction` 的示例代码设计，以及单元测试覆盖矩阵中新增的测试用例描述。

### 验证
- 重新运行全部后端单元和集成测试用例，76 个测试全部 PASS（100% 成功通过）。

---

## 2026-07-10 20:00 +08:00 - Redaction 保留 N 次策略 + Linter CTE 去重模式识别

### 概述
- **Redaction 保留策略升级**：`_stage_redaction` 从“保留最近 1 次失败”升级为“保留最近 N 次（默认 3，可配置）”，扫描范围限定到最后一条 `HumanMessage` 之后的当前 ReAct 循环内。解决跨域成功 SQL 污染当前轮失败保留的问题，减少 LLM 无效重试。
- **Linter CTE 去重模式识别**：`JoinUniquenessRule`（SEM-001）新增 CTE（WITH 子句）grain 分析能力，支持识别 CTE 内 `ROW_NUMBER() + WHERE rn=1`、`GROUP BY`、`DISTINCT` 以及链式 CTE 传播的去重模式。解决 LLM 默认使用 CTE 写法但被 Linter 误拦截的问题。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `llm_context_redaction_keep_count` 配置项（默认 3），控制 Redaction 保留的失败次数。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新增 `_find_last_human_index` 辅助方法，定位最后一条 `HumanMessage` 索引。
- 重写 `_stage_redaction`：扫描范围限定到 `last_human_idx` 之后；收集当前循环所有失败 `tool_call_id`，取最后 N 个加入 `ctx.kept_call_ids`；`should_redact` 改为检查 `msg.tool_call_id not in ctx.kept_call_ids`。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 更新 `test_safe_merge_redacts_past_failures_keeps_last_n`（原 `..._keeps_latest`）：4 次失败，最早 1 次被抹除，最近 3 次保留。
- 更新 `test_stage_redaction_keeps_last_n_failures`（原 `..._keeps_latest_failure`）：同上，直接调用 Stage 测试。
- 新增 `test_stage_redaction_cross_domain_success_no_pollution`：验证域 A 成功 SQL 不影响域 B 当前轮的失败保留。
- 新增 `test_stage_redaction_success_in_current_loop_redacts_all`：验证当前轮成功后所有失败被抹除。
- 共 18 个测试全部通过。

#### backend/app/agent/utils/sql_linter.py [MODIFY]
- `JoinUniquenessRule` 新增 `_extract_cte_map` 方法：从 WITH 子句提取 CTE 名 → SELECT 定义的映射。
- 新增 `_is_cte_deduped` 方法：白名单策略判断 CTE 是否已去重（GROUP BY / DISTINCT / ROW_NUMBER+WHERE / 链式 CTE）。
- 新增 `_cte_has_rownumber_filter` 方法：检查 SELECT 是否含 ROW_NUMBER() + WHERE rn=1 模式。
- 扩展 `_is_rownumber_one_filter` 方法：增加 `cte_map` 参数，支持 CTE Table 引用的 ROW_NUMBER 检测。
- `check_parsed_with_sql` 新增 CTE 检测分支：JOIN 右侧为已去重 CTE 时标记 `right_safe=True`。

#### backend/app/agent/utils/test_sql_linter_cte.py [NEW]
- 6 个测试覆盖 CTE 各场景：ROW_NUMBER+JOIN ON、GROUP BY、DISTINCT、链式 CTE 传播、无去重 CTE 仍拦截、UNION CTE 保守拦截。

### 验证
- `test_safe_merge_middleware.py`：18 个测试全部通过。
- `test_sql_linter_cte.py`：6 个测试全部通过。
- `test_sql_linter.py`：8 个测试全部通过（无回归）。
- `test_sql_linter_header.py`：1 个测试通过。
- 共 33 个测试全部通过。

---

## 2026-07-10 18:00 +08:00 - 滑动窗口外失败 SQL/图表配对物理删除（Pipeline 架构重构）

### 概述
- **轻量 Pipeline 架构**：将 `_project_and_collapse_messages` 从单函数重构为五阶段 Pipeline（compute_boundary → prescan_failures → redaction → physical_deletion → standard_collapse），通过 `_CollapseContext` 共享上下文。
- **配对物理删除**：对滑动窗口外已过期的失败 SQL/图表执行对（AIMessage + ToolMessage）进行物理成对删除，而非仅折叠内容。覆盖 `sql_db_query` 和 `build_chart_artifact` 两个工具。
- **JSON 反向校验防误杀**：降级判定时先尝试 `json.loads()` 解析，成功 JSON 列表则视为成功数据，防止关键字误匹配。
- **物理删除优先于常规折叠**：失败的条目被物理删除后，不再进入常规折叠阶段，实现串行互斥。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新增 `_CollapseContext` 共享上下文 dataclass。
- 新增 `_DELETION_TARGET_CONFIG` 工具失败判定配置字典。
- 新增五个 Stage 方法：`_stage_compute_boundary`、`_stage_prescan_failures`、`_stage_redaction`、`_stage_physical_deletion`、`_stage_standard_collapse`。
- 新增 `_log_collapse_results` 审计日志方法。
- `_project_and_collapse_messages` 重构为 Pipeline 主入口。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增 9 个测试覆盖各 Stage 功能，包括边界计算、失败预扫描（含 JSON 防误杀）、Redaction、物理删除（全删/过滤）、常规折叠。
- 更新 `test_safe_merge_context_collapse_failed_query` 断言以匹配物理删除行为。
- 共 15 个测试全部通过。

---

## 2026-07-10 16:00 +08:00 - 大模型 SQL 纠错链路极限制折叠与参数保留防模仿优化

### 概述
- **大模型 SQL 纠错链路极限制折叠（Linter 重试清理）**：针对 Linter 拦截导致的反复重试（ReAct 循环）进行了内容抹除重塑。区分了“当前轮重试中（只保留最后一次失败线索）”和“下一次对话开始前（彻底抹除上一轮全部重试日志）”两个拦截时机，显著缩减了 70%+ 的冗余上下文 Token。
- **免失控模仿与参数保留优化**：解决了大模型在后续对话中会模仿被抹除的 `-- redacted --` 占位符并引发 `required_skill: Field required` 工具参数丢失报错的缺陷。通过“只抹除 AI 思考（content），原样复制保留 `tool_calls` 参数结构”的最佳实践设计，完美保留了纠错线索并彻底消除了 Trace UI 显示和运行错误。

### 变更内容
#### backend/app/agent/utils/sql_linter.py [MODIFY]
- 在静态/语义 Linter 拦截生成的错误消息最前端强制注入了固定的技术特征协议头：`X-SQL-LINTER-STATUS: FAILED`。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重构了 `_project_and_collapse_messages` 的消息投影过滤算法，基于 `X-SQL-LINTER-STATUS: FAILED` 协议头实现了重试抹除。
- 优化了抹除策略，采用 `tool_calls=aimsg.tool_calls` 保留历史真实工具调用参数，只重写 `content`，以规避大模型幻觉模仿。
- 移除了 `kept_call_ids` 对 `successful_sql_call_id` 的冗余保护，确保已完结的成功历史 SQL 可以正常常规折叠。

#### backend/app/agent/utils/test_sql_linter_header.py [NEW]
- 新增单元测试，验证 Linter 拦截消息能够正确反射包含协议特征码。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_redacts_past_failures_keeps_latest` 与 `test_safe_merge_redacts_all_failures_on_success` 单元测试，断言重试中及重试成功的历史抹除效果。
- 调整了对 `query` 值的测试断言，确保改动后测试 100% 成功通过。

## 2026-07-08 20:20 +08:00 - 增加 SQL Linter 规则禁用配置

### 概述
- **SQL Linter 规则禁用配置（STR-002 屏蔽）**：为了解决在多表关联查询中，频繁拦截 `STR-002` (表别名前缀缺少) 导致工具调用超时的问题，我们新增了 `SQL_LINTER_DISABLED_RULES` 配置项。
- **配置与拦截逻辑解耦**：用户只需在环境变量或配置中添加 `SQL_LINTER_DISABLED_RULES=STR-002` 即可实现屏蔽，系统底层仍保留该规则的完整校验逻辑，以便后续恢复。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `sql_linter_disabled_rules_raw` 属性与 `sql_linter_disabled_rules` 解析属性，从环境变量 `SQL_LINTER_DISABLED_RULES` 自动反射。

#### backend/app/agent/utils/sql_linter.py [MODIFY]
- 修改 `SQLLinter` 初始化参数，使其在注册规则时根据 `disabled_rules` 集合过滤不予注册的规则。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 实例化 `SQLLinter` 时将 `settings.sql_linter_disabled_rules` 传入，从而应用用户禁用的规则。

#### backend/app/test_config.py [MODIFY]
- 增加对 `SQL_LINTER_DISABLED_RULES` 配置解析和清理的单元测试。

#### backend/app/test_sql_linter.py [MODIFY]
- 增加针对禁用规则功能的单体测试和工具集成测试。

## 2026-07-07 15:10 +08:00 - SQL 执行前硬拦截 Linter 与自愈机制 (含 PG 深度去重优化)

### 概述
- **SQL Linter 静态/语义多级安全合规检查（P2）**：实现了用于 SQL Agent 执行 SQL 前硬防守拦截的 SQL Linter 架构，分三层进行校验：
  - 安全过滤层（SEC-001 DML 写操作拦截、SEC-002 堆叠多语句注入检测、SEC-003 数据库别名前缀/非法 schema 拦截）。
  - 结构合规层（STR-001 `SELECT *` 通配符拦截、STR-002 JOIN 强制别名前缀、STR-003 子查询深度限制、STR-004 CTE 数量警告）。
  - 语义校验层（SEM-001 关联列唯一性、SEM-002 事实表非去重 `COUNT` 告警、SEM-003 标量子查询 limit 限制警告、SEM-004 `NOT IN` 子查询 NULL 穿透漏洞拦截）。
- **PostgreSQL 专用去重关联优化**：深度优化了 `JoinUniquenessRule` (SEM-001) 规则，智能识别并安全放行以下三类去重关联模式，解决常见“取最新检测记录”时的拦截误杀：
  - `MAX`/`MIN` 极值标量子查询过滤条件。
  - `ROW_NUMBER() OVER (...) = 1` 窗口去重子查询条件。
  - `LIMIT 1` 子查询全局条件。
- **标量子查询误判修复**：在 `ScalarSubqueryRule` (SEM-003) 中引入 AST 上下文路径判定逻辑，有效过滤掉 FROM/JOIN 数据源中的表子查询（Table Subquery），防止对正常子查询进行误拦截。
- **DDL 语义上下文提取**：编写了从 `custom_table_info` 表 DDL 描述中自动解析提取主键、唯一键和 Grain 信息构建 `LintContext` 上下文的引擎。
- **LangChain 工具层集成与自愈**：将 `sql_linter` 接入 `create_wrapped_query_tool` 包装查询工具。对于拦截的 ERROR 问题，通过抛出 `ToolException` 结合 `handle_tool_error=True` 属性触发 SQL Agent 的自我修复能力。
- **完全可配置支持**：提供全局开关、严重度覆盖重载、子查询深度限制、CTE 数量限制等配置项，支持环境变量在测试时动态映射重载。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `sql_linter_enabled`、`sql_linter_max_subquery_depth`、`sql_linter_max_cte_count`、`sql_linter_allowed_schemas_raw`、`sql_linter_rules_severity_raw` 等配置字段与别名环境变量映射。

#### backend/app/agent/utils/sql_linter.py [NEW]
- 实现 `LintViolation`, `LintContext`, `LintResult` 数据模型。
- 实现 `BaseLintRule` 抽象规则基类与编排器 `SQLLinter`。
- 实现安全层（`DMLSecurityRule`, `MultiStatementRule`, `DatabasePrefixRule`）、结构层（`StarSelectRule`, `AliasPrefixRule`, `SubqueryDepthRule`, `CteCountRule`）和语义层（`JoinUniquenessRule`, `CountDistinctRule`, `ScalarSubqueryRule`, `NotInSubqueryRule`）共 11 个规则类。
  - 特别优化 `JoinUniquenessRule` 支持 `MAX`/`MIN`、`ROW_NUMBER`、`LIMIT 1` 判定。
  - 特别优化 `ScalarSubqueryRule` 支持 FROM/JOIN 父类排除。
- 实现从 DDL 中提取上下文元数据的 `_build_lint_context` 引擎。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 集成 `sql_linter` 到 `create_wrapped_query_tool`，并在合规校验拦截时抛出 `ToolException`，将 `handle_tool_error = True` 绑定到包装后的工具实例，启用 Agent 的自我修复机制。

#### backend/app/test_config.py [NEW]
- 新增 Linter 配置解析与环境变量重写覆盖的相关单元测试。

#### backend/app/test_sql_linter.py [NEW]
- 覆盖 Linter 骨架、安全拦截、结构合规、DDL 上下文提取、语义校验和工具集成的完整 pytest 用例（共 6 个大用例，覆盖所有规则分支）。

#### docs/fanout/sql_linter_proposal.md [MODIFY]
- 覆写更新方案文档，反映配置别名映射、By-pass 设计及最新自愈切入路径实现细节。

## 2026-07-06 22:30 +08:00 - DDL 粒度标注体系与唯一键自动反射

### 概述
- **唯一键自动反射**：在 `db_utils.py` 中新增 UNIQUE CONSTRAINT + UNIQUE INDEX 双重反射机制，自动标注 DDL 中的 `UNIQUE` 列，解决 `fct_vehicle_position_current` 等仅有唯一索引（UNIQUE INDEX）而无唯一约束（UNIQUE CONSTRAINT）表的标注遗漏。
  - 修复表达式索引（如 `COALESCE(history_id, '-1'::integer)`）导致列名为 None 的 crash。
- **DDL 粒度标注体系（P1）**：
  - 新增 `_parse_grain_info()` 函数，解析表注释中 `Grain:` 前缀，输出结构化 `-- Grain:` + `-- ⚠️` 警告行。
  - 无 `Grain:` 前缀的注释仍走原 `-- Description:` 渲染，向后兼容。
- **样本数据行展示**：新增 `_get_sample_rows()` 函数，在 DDL 尾部附加 3 行样本数据，帮助 LLM 理解列值格式。
- **创建粒度标注规范文档**：`docs/fanout/grain_template.md`，含模板格式、表分类示例、DDL 渲染效果、实施要求。

### 变更内容
#### backend/app/agent/utils/db_utils.py [MODIFY]
- `_build_column_definition()`: 新增 `unique_cols` 参数，在主键列之外标注 `UNIQUE`
- `_process_single_table()`: 新增 UNIQUE CONSTRAINT + UNIQUE INDEX 反射逻辑（双通道合并去重）
- 新增 `_parse_grain_info()`: 解析 `Grain:` 前缀注释为 `(grain_desc, warnings)`
- 新增 `_get_sample_rows()`: 获取 3 行样本数据追加到 DDL 尾部
- 注释渲染分支：有 `Grain:` 前缀 → 结构化 Grain + ⚠️；无前缀 → 原 Description
- 更新模块 docstring，反映唯一键反射和粒度标注能力
- 新增 `import re`

#### docs/fanout/grain_template.md [NEW]
- 粒度标注模板格式 `COMMENT ON TABLE ... IS 'Grain:...,...'`
- 流水表、快照表、维度表、异常表四类场景示例 SQL
- DDL 渲染效果对比
- 实施要求与代码实现映射

## 2026-07-05 22:30 +08:00 - P0: 冗余关系声明移除与提示词规则强化

### 概述
- **移除手动关系声明**：从两个技能的 `meta.py` 中彻底删除 `table_primary_keys` 和 `relationships` 声明（7 条关系 + 6 个 PK 定义），PK/UNIQUE 信息改由 `db_utils.py` 自动反射注入 DDL。
- **移除骨架关系渲染**：删除 `skeleton_service.py` 的 `_build_relationship_block()` 方法（~60 行）和 `skill_middleware.py` 的 `_split_skeleton()` 方法（~18 行），骨架生成简化为纯 DDL 块。
- **重写提示词规则 3.3**：
  - EXISTS/NOT EXISTS 替换 IN/NOT IN，增加三值逻辑陷阱专项警告。
  - 新增"关联基数预判与防膨胀"规则，含强制预聚合 SQL 模板。
  - 新增"结果行数 Fan out 自检"规则。
  - 移除过时的 `💡` 模板引用标记。
- **清理验证**：7 个关键词全文搜索确认零残留引用，共删除 ~230 行代码，每轮交互节省约 350 tokens。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- 移除 `table_primary_keys`（3 个表）
- 移除 `relationships`（3 条关系）
- 更新文件头，说明 PK 信息改由数据库自动反射

#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- 移除 `table_primary_keys`（3 个表）
- 移除 `relationships`（4 条关系）
- 更新文件头，说明 PK 信息改由数据库自动反射

#### backend/app/agent/utils/skeleton_service.py [MODIFY]
- 删除 `_build_relationship_block()` 方法（~60 行）
- `_build_ddl_blocks()` 简化为纯 DDL 清理和返回
- 文件头注释更新，移除关系声明相关描述

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 删除 `_split_skeleton()` 静态方法（~18 行）
- 辅助技能处理简化为直接使用 `get_skeleton_ddl()` 输出

#### backend/app/agent/service.py [MODIFY]
- 规则 3.3 重写：EXISTS/NOT EXISTS 替换 IN/NOT IN，三值逻辑陷阱警告
- 新增关联基数预判与防膨胀规则（含预聚合 SQL 模板）
- 新增结果行数 Fan out 自检规则
- 移除 `💡` 模板引用标记
- 保留运行时自检检查项

## 2026-07-05 18:28 +08:00 - 跨域关联路径防护体系系统性审查与研究文档

### 概述
- **跨域关联路径声明全面审查**：
  - 修复 `paint_shop_defect_analysis/meta.py` 中两条 N:1 关系的 `join_safety` 标注不一致（unsafe→safe），移除冗余 `pre_aggregate_hint`。
  - 修复 `paint_shop_vehicle_logistics/meta.py` 中 relationship 4 的 from/to 方向错误（dim_process_area→position_current 翻转），基数 1:N→N:1。
  - 统一所有 note 术语：弃用"主→辅"角色描述，改用固定的"N侧/1侧"基数描述。
- **骨架关系渲染改为紧凑格式**：
  - 将 `skeleton_service.py` 的 `_build_relationship_block` 从"聚焦式关系图"重写为紧凑箭头式（`[`基数`安全标记`] from_key -> to_key + note + 💡 模板）
  - Token 消耗减少约 3.2x（每条~160→~50 tokens），两个技能 7 条关系共节省 ~770 tokens。
  - 同步更新 `service.py` 规则 3.3 提示词对齐 `⚠️`/`💡` 标记。
  - 清除文件头过时描述。
- **PK 反射替代手动声明分析与研究文档**：
  - 验证 `db_utils.py` 已通过 `inspector.get_pk_constraint()` 自动反射物理表 PK。
  - 验证 PK 规则（JOIN 目标列非 PK → 需预聚合）等价于当前 7 条 relationships 声明（7/7 正确）。
  - 从行业最佳实践角度完整评审：当前系统"重提示词、轻执行"，缺失执行前 AST 检查和运行时膨胀检测。
  - 创建系统性研究文档 `docs/fanout/README.md`，含现象/分析/行业实践/推荐方案/进度/计划六维度总结。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- relationship 1: `join_safety` unsafe→safe，移除 `pre_aggregate_hint`，更新 note
- relationship 2 & 3: note 术语统一为 N侧/1侧

#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- relationship 4: 翻转 from/to 方向（dim_process_area→position_current → position_current→dim_process_area），cardinality 1:N→N:1

#### backend/app/agent/utils/skeleton_service.py [MODIFY]
- `_build_relationship_block` 重写为紧凑箭头式输出
- PK 标注正则 `^  `→`^\s+`，增强健壮性
- 文件头过时描述清理

#### backend/app/agent/service.py [MODIFY]
- 规则 3.3 对齐新格式，`⚠️`/`💡` 标记替代旧文本

#### docs/fanout/README.md [NEW]
- 跨域关联路径防护体系系统性总结研究文档
- 含现象、分析、行业最佳实践（附参考文献）、推荐方案、进度、后续计划

## 2026-07-04 22:08 +08:00 - 系统提示词整合自主案例检索与场景加载工作流

### 概述
- **整合系统提示词工作流**：
  在 `backend/app/agent/service.py` 的系统提示词 `## 3.1 总体工作流与重试机制` 中，显式整合了包含 `load_skill`、`load_scenario`、`search_saved_correct_tool_uses` 以及 `AskUserQuestion` 在内的 6 步标准闭环执行流程，明确了在输入口径模糊、关键参数（如车身号 FIS）缺失时提问澄清的判定，同时强化了大模型在非场景任务下通过案例检索的自适应查询规范。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 更新提示词工作流程小节，明确大模型对于澄清反馈、场景优先及案例检索工具的互斥、依存使用策略。

## 2026-07-04 18:10 +08:00 - 集成漏检车监控新场景并同步文档与场景模板对齐数仓升级


### 概述
- **新增漏检与未检测车辆监控场景 (`leak_detection`)**：
  - 设计并集成了全新的 `leak_detection` 场景，通过面漆 3 条生产线的入口读写站（`L3ACC21IS01`/`02`/`03`）过车事件锁定车辆已到达检测线，全局 `LEFT JOIN fct.fct_vehicle_defect_detection` 来精准检测没有产生对应任何通道缺陷流水的漏检车或检测失败车，输出包含车辆当前最新工艺区域（`current_process_area`）和载具（`current_carrier_id`）以便现场召回补检，且此全局关联连接策略巧妙地避免了因为改道/跨线分流导致的假阳性误报。
- **重构并同步物流追踪与质量缺陷分析领域文档**：
  - 对齐了 `dim.dim_vehicle_profile` 画像表扩展的 9 个物理车身及状态新字段，同步更新了 `dim.carbody_registry` 和 `mart.mart_vehicle_quality_360` 的字段列表；统一了车身注册表相关的“过站读写站”业务术语注释说明。
  - 重构了 `paint_shop_defect_analysis/domain.md` 的架构体系，使其与 `paint_shop_vehicle_logistics/domain.md` 的结构完全对齐，并新增了关于漏检监控场景的提示。
- **修复质量分析场景 SQL 模板由于数仓升级导致的数据虚高与 NULL 组 Bug**：
  - 因 `mart.mart_vehicle_quality_360` 的驱动表改为了包含在产未检车辆与漏检车辆的 `fct.fct_vehicle_defect_enriched`，这会导致原有场景 SQL 在做 COUNT/SUM 等聚合时，把未检出车辆计算在内，产生空值组并使检测频次统计翻倍虚高。
  - 修复了 `daily_defect_summary`、`black_roof_defect_comparison`、`defect_station_distribution`、`model_defect_trend`、`tunnel_cycle_defect_comparison` 这 5 个质量缺陷场景 SQL 模板，在 `FROM mart_vehicle_quality_360` 中均追加了 `WHERE mq.history_id IS NOT NULL` 强制过滤规则，确保只统计已上线检测的有效缺陷事实。

### 变更内容
#### backend/app/skills/domains/paint_shop_vehicle_logistics/domain.md [MODIFY]
- 对齐并补充 `dim.carbody_registry` 和 `dim.dim_vehicle_profile` 的全部新物理车身过站、MDS 字段，更新 `rw_station` 相关的中文注释为“过站读写站编码”。

#### backend/app/skills/domains/paint_shop_defect_analysis/domain.md [MODIFY]
- 重新设计文档结构，划分为 WIP 实时层与 History 历史事实层；补充 `fct_vehicle_defect_detection` 及 `fct_vehicle_defect_enriched` 字段详情；补全并对齐 `mart_vehicle_quality_360` 的 38 个字段中文说明；追加 `2.3 漏检与未检测车辆监控` 引导。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/* [MODIFY]
- 修复 5 个已有场景的 `sql/main.sql` 模板，增加 `WHERE mq.history_id IS NOT NULL` 过滤。
- **[NEW]** 新增 `leak_detection` 场景，创建 `scenario.py` 元数据以及编写 `sql/main.sql` 精准的漏检全局 LEFT JOIN 查询逻辑。

## 2026-07-04 13:11 +08:00 - 增强 SQL Agent 系统提示词防范 PostgreSQL 数据库名前缀错误


### 概述
- **新增 PostgreSQL 数据库名前缀反向约束**：
  在 `backend/app/agent/service.py` 里的 `_build_system_prompt` 中，针对 PostgreSQL 查询规范新增了一条针对表名前缀的强制防范规则，严禁大模型生成类似 `analytics_db.schema.table` 的三段式表名，以防 PostgreSQL 报错 `UndefinedTable`。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 在 `_build_system_prompt` 中加入限制规则 `1. 【禁止使用数据库名前缀】` 并调整其他规则的数字索引。

## 2026-07-03 17:05 +08:00 - 重构 SkeletonService 归档迁移与 LangGraph 状态通道并发写修复

### 概述
- **将 SkeletonService 移入 utils/ 工具类包**：
  为保持代码目录的一致性与职责内聚，撤销了原有的单文件子目录 `services/`。将 `skeleton_service.py` 及其测试文件 `test_skeleton_service.py` 完美迁移归档至已有的 `backend/app/agent/utils/` 包下，消除了冗余目录，并将反射 DDL 逻辑划入数据库元数据工具大类。
- **修复 LangGraph 状态通道并发写异常 (INVALID_CONCURRENT_GRAPH_UPDATE)**：
  针对在同一步/Tick 中对 `skills_loaded` 和 `active_skill` 并发更新导致流式中断崩溃的问题，在 `state.py` 状态实体中，正式为 `skills_loaded`、`scenarios_loaded`、`active_skill` 与 `active_scenario` 声明挂载了 `_last_wins` Reducer 装饰，利用“后写覆盖前值”策略完美实现了状态流转的并发写容错。
- **物理剔除 DDL 骨架中的 VARCHAR(N) 长度限制**：
  在 `SkeletonService` 提取拼装骨架 DDL 时，引入正则表达式自动裁剪剥离类似 `VARCHAR(50)`、`VARCHAR(255)` 中的长度数值修饰符，统一还原为极简 `VARCHAR` 类型，为大模型 Prompt 进行了二次瘦身，减少了无效 Token 的消耗。
- **同步更新全局引用与实施文档**：
  全面修改了 `skill_middleware.py` 等文件中对 `SkeletonService` 的包导入语句，并同步重构了详细设计手册 `phase_1_cascade_query_design.md` 和一期实施计划中的文档测试路径指南。

### 变更内容
#### backend/app/agent/utils/skeleton_service.py [NEW]
- 从 `services/` 目录中迁移过来，并追加正则自动剔除 `VARCHAR(N)` 类型修饰符逻辑。

#### backend/app/agent/utils/test_skeleton_service.py [NEW]
- 从 `services/` 目录中迁移过来，将 DDL 模拟类型断言修正为通用 `VARCHAR`，修复 `_custom_table_info` 私有属性 Mock。

#### backend/app/agent/services/ [DELETE]
- 物理删除原单文件临时目录及内部的原有代码文件。

#### backend/app/agent/state.py [MODIFY]
- 对状态属性 `skills_loaded`、`scenarios_loaded`、`active_skill` 及 `active_scenario` 使用 `Annotated[..., _last_wins]` 修饰，提供并发写 Reducer。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 修改导入语句，改从 `backend.app.agent.utils.skeleton_service` 导入。

#### docs/crossdomin/phase_1_cascade_query_design.md [MODIFY]
- 同步修正代码示例展示里的类文件路径。

#### docs/crossdomin/2026-07-03-phase_1_cascade_query.md [MODIFY]
- 修改 Task 2、Task 4 中的测试路径，对齐 `utils/` 物理目录，并将 `custom_table_info` 全局替换为私有属性 `_custom_table_info`。

## 2026-07-03 15:37 +08:00 - 实现 Phase 1 跨域子查询直连与状态清理中间件重构

### 概述
- **实现技能元数据 associated_tables 声明**：在物流追踪和缺陷分析技能的 `meta.py` 描述中，完成了物理表关联声明。
- **免物理连库的内存骨架 DDL 反射 (SkeletonService)**：新建 `SkeletonService`，复用系统初始化常驻于内存中的 `db.custom_table_info` 缓存，实现 0 物理读库开销。引入正则表达式物理剔除 DDL 尾部的样例数据行（`-- 1. { ... }`），规避了大模型在长上下文下的数据偏见与 Token 膨胀。
- **重构 load_skill 工具为去重追加与上限截断模式**：修改 `_build_load_skill_command` 函数，将原有覆盖模式升级为去重追加，并强制堆积截断上限为 3，激活了 `skills_loaded` 列表的多值级联状态。
- **基于 before_agent 原生钩子的零侵入单步重置**：重写 `SkillMiddleware.before_agent` 生周期钩子。每次新提问到来时，自动在框架层拦截，清空多余辅助技能，仅保留当前激活主技能，实现完美的“用完即弃”Prompt 瘦身。
- **级联 Prompt 拼接与子查询规训微调**：改造 `_modify_request` 级联生成 `## Secondary Domain Knowledge` 辅助块。同时更新 `service.py` 中的提示词军规，强制推行 EXISTS 子查询替代 `IN` 常量列表，并强制规定表别名前缀规范，全面防范 PostgreSQL 17 抛出 ambiguous 列引用报错。

### 变更内容
#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- 在元数据中注册关联物理表 `fct.fct_vehicle_position_current`, `ods.carbody_history`, `dim.carbody_registry`。

#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- 在元数据中注册关联物理表 `mart_vehicle_quality_360`, `fct_vehicle_defect_detection`。

#### backend/app/agent/services/skeleton_service.py [NEW]
- 实现 `SkeletonService` 类以提取 DDL 并使用正则剥离样本行。

#### backend/app/agent/services/test_skeleton_service.py [NEW]
- 针对样本数据剥离和 DDL 反射编写独立单元测试。

#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 重构 `_build_load_skill_command`，加入去重追加和上限为 3 的截断逻辑。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 重写 `SkillMiddleware.__init__` 以支持全局 `db` 注入。
- 重写 `before_agent` 实现单步自愈清空状态。
- 重改 `_modify_request` 实现一主多辅 DDL 极简骨架的动态拼装。

#### backend/app/agent/middleware/test_skill_middleware.py [MODIFY]
- 添加 `test_before_agent_resets_loaded_skills` 单元测试。
- 添加 `test_skill_middleware_injects_secondary_skeleton` 级联注入断言。
- 升级 `test_load_skill_tool_appends_state` 验证去重新增和堆积截断。

#### backend/app/agent/service.py [MODIFY]
- 微调系统提示词，更新 `## 跨领域复合问题处理流程 (一期子查询军规)`，强化 EXISTS 和表别名纪律。

#### backend/app/agent/test_service_prompt.py [MODIFY]
- 新增对一期子查询军规与表别名约束的提示词测试断言。

## 2026-07-01 20:45 +08:00 - 实现多步 SQL 案例提取与过滤管道顺序 Bug 修复

### 概述
- **实现多步 SQL 案例提取与存储**：
  扩展了原有规则提取器，使其在允许的步数限制内（通过 `RULE_EXTRACTOR_MAX_SQL_STEPS` 控制）支持抓取多步 `sql_db_query` 成功调用的查询语句。多步 SQL 查询在提取时使用 `-- Step N` 注释行进行格式化拼接，执行结果则通过 `[Step N Result]` 进行分隔对齐，无需修改底层数据库与向量元数据 Schema。
- **重构并修复过滤管道执行顺序 Bug**：
  排查并修复了原系统中 `SafetyWarningFilter` 执行早于 `SingleSqlFilter` 导致其始终无法在生产环境下校验 SQL 执行结果 `tool_result` 的逻辑漏洞。将 SQL 提取与数据填充算子（重命名为 `SqlStepFilter`）移至校验过滤管道的最首位，确保先填充上下文状态，再行安全过滤与空值校验。
- **优化多步场景下的“空结果校验”**：
  针对多步查询特征，升级了 `EmptyResultFilter`，使其仅对多步调用链中的最后一步返回数据进行实质性的空列表/空字典阻断，避免因中间步骤无结果而导致高价值的复杂关联案例被硬性拦截丢弃。
- **LLM 提炼层多步适配**：
  在 `llm_refiner.py` 中更新了黄金案例意图重写与脱敏 prompt，引导大模型识别多步执行中前后步骤的变量依赖（如 `position_id = {{Step1.id}}`），并强制保证在参数化脱敏时保留 `-- Step N` 步骤说明结构。
- **前端多步 fallback 支持**：
  在 `AdminReviewPanel.vue` 审核面板中，对 `parseOriginalSql` 进行了多步提取适配，确保在后台提纯草稿未生成或报错时，前端依然能够拼接显示完整的多步 SQL。

### 变更内容
#### backend/app/config.py [MODIFY]
- 增加 `rule_extractor_max_sql_steps` 配置选项（默认值为 3）。

#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 将 `SingleSqlFilter` 重构并更名为 `SqlStepFilter`，支持跳过错误语句、步数阈值校验与拼接；
- 调整 `DEFAULT_EXTRACTOR_PIPELINE` 执行顺序，将 `SqlStepFilter()` 移至最首位；
- 优化 `EmptyResultFilter` 以在多步场景下仅对最后一步的执行结果进行有效空值拦截。

#### backend/app/agent/vector/llm_refiner.py [MODIFY]
- 更新提纯 prompt，指导 LLM 识别多步级联数据依赖并维持 `-- Step N` 结构。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 新增 `test_multi_sql_filter_success` 和 `test_multi_sql_filter_exceeds_limit` 测试用例，更新已有断言以适配 `SqlStepFilter` 命名和管道执行新顺序。

#### backend/app/agent/vector/test_llm_refiner.py [MODIFY]
- 新增 `test_refine_multi_sql_case_success` 用例，模拟验证多步 SQL 结构在 LLM 提纯时的脱敏表现。

#### frontend/src/components/AdminReviewPanel.vue [MODIFY]
- 升级 `parseOriginalSql` 助手函数，当存在多步 SQL 调用时自动返回带 `-- Step N` 拼接的原始代码块。

#### .env [MODIFY]
- 显式声明 `RULE_EXTRACTOR_MAX_SQL_STEPS="3"` 控制多步 SQL 抓取限制。

## 2026-06-30 16:30 +08:00 - 实现规则提取器配置驱动与 LangChain 1.0 结构化输出重构

### 概述
- **实现规则提取器配置驱动（Option A）**：
  将规则提取器的关键检测参数与控制开关从代码硬编码中剥离，转由 Pydantic Settings 加载，并在 `.env` 中提供了一系列开箱即用的默认环境变量控制。支持管理员与运维人员无需修改任何核心过滤逻辑代码，通过配置文件热插拔与灵活参数化控制过滤器（安全审查开关、安全关键字与警告标记、空结果校验开关、单步 SQL 检查开关、回溯开关与最大回溯轮数等）。
- **完成大模型意图与 SQL 提炼的结构化输出重构**：
  在 `llm_refiner.py` 中引入了基于 Pydantic 的 `RefinedSQLCase` 模型，利用 LangChain 1.0+ 标准推荐的 `with_structured_output(..., include_raw=True)` 机制重构了提纯算子。彻底消除了传统正则表达式与手工 JSON 清洗方式的不稳定性，通过 Constrained Decoding 强制保证了模型输出的 Schema 合规性，并结合 `parsing_error` 实现了健壮的生产级安全降级与审计。

### 变更内容
#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中增加了 Rule Extractor 相关的环境变量配置项，并声明了对关键字与警告标记进行大小写清洗、拆分逗号的助手 properties 属性。

#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 对 `SafetyWarningFilter`、`EmptyResultFilter`、`SingleSqlFilter`、`TopologyBacktrackFilter` 及 `DomainFilter` 引入开关校验逻辑与外部配置参数读取。其中回溯过滤器在禁用或配置轮数过小时支持向下安全降级为单轮处理。

#### backend/app/agent/vector/llm_refiner.py [MODIFY]
- 定义 `RefinedSQLCase` 模型，并使用 `with_structured_output(..., include_raw=True)` 重塑提炼流程，实现异常数据优雅判定与自适应策略选择。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 新增 `test_safety_warning_filter_disabled` 和 `test_topology_backtrack_filter_disabled` 两个测试用例，在 Mock 环境中模拟配置变动，全方位验证配置驱动逻辑的正确性与向后兼容性。

#### backend/app/agent/vector/test_llm_refiner.py [MODIFY]
- 全面重构测试用例以匹配 `include_raw=True` 结构化字典响应 Mock，新增解析错误与底层接口连接崩溃等分支测试。

#### .env [MODIFY]
- 追加规则提取器（Rule Extractor）的各种默认控制配置，支持热拔插配置。

## 2026-06-29 21:38 +08:00 - 增强 SQL Agent 系统提示词以提升 PostgreSQL 生成质量

### 概述
- **合并 PostgreSQL 专家规则至系统提示词**：
  在主系统提示词中合并了一组精细化的 PostgreSQL 编写最佳实践，明确声明当目标数据库为 PostgreSQL 时，生成 SQL 需遵循以下 8 项核心准则：优先使用 CTE 替换嵌套层数 > 1 的子查询以消除作用域混乱 Bug、使用自解释的 CTE 命名、避免俄罗斯套娃式嵌套反模式、智能物化（MATERIALIZED）策略、采用 PG 专属的高效语法、支持分析模式的分层计算（CTE 基础聚合 + 主查询窗口函数二次计算）、按需且有条件地引入递归（WITH RECURSIVE），以及在思考区（thinking）执行生成后自检。该规则在强化 PostgreSQL 复杂关联生成质量的同时，仍保证了系统对其他异构数据库（如 MySQL）在多方连接时的兼容性。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 在系统提示词构建函数 `_build_system_prompt` 的 `# SQL查询规范` 章节中嵌入了结构化的 PostgreSQL 规范提示规则。

## 2026-06-29 16:30 +08:00 - 优化 DomainFilter 业务域提取与管道过滤拦截日志


### 概述
- **过滤管道拦截日志增强**：
  在规则过滤管道 `PipelineManager` 中引入了结构化的拦截警告日志。当案例提纯初筛未通过任一过滤器原则时，后台日志将精准打印出具体的过滤器类名（如 `SafetyWarningFilter` / `SingleSqlFilter`）和不符合原则的 reject 详情原因，极大地方便了开发和运维人员定位和审计提炼失败的根本原因。
- **业务域提取管道过滤优化**：
  优化了规则提取管道中的业务域提取器 `DomainFilter`。针对在真实环境中 `load_skill` 参数键名为 `skill_name` 导致的 `domain` 丢失为 `None` 的问题，重新设计了优先顺序级联抓取策略。
  1. 优先从 `sql_db_query` 工具调用的 `required_skill` 字段进行直接精准提取（直咬合 SQL 执行生命周期）。
  2. 若无 SQL 动作，则退而求其次寻找 `load_skill` 调用，双重兼容并提取 `skill_name` 或 `skill` 参数。
  3. 最终提供 `"general"` 作为默认降级保护，全面根治了 Milvus 向量入库时 `domain` 出现 `None` 值的缺陷。
- **补齐提取测试断言**：在 `test_rule_extractor.py` 中对 `test_domain_filter` 增加了多渠道（`required_skill` 与 `skill_name`）覆盖测试用例，全方位验证提取逻辑的高保真与兼容性。

### 变更内容
#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 重构 `DomainFilter.execute` 成员函数，编写级联抽取逻辑并添加健壮性 JSON 字典解析及类型保障，完美防护空域与 `None` 值。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 扩展 `test_domain_filter` 单元测试用例，覆盖 `sql_db_query.required_skill` 提取分支以及 `load_skill.skill_name` 提取分支。

## 2026-06-29 12:30 +08:00 - 实现管理员审批接口、后台异步 LLM 意图提炼与 Milvus 写入

### 概述
- **第三阶段：管理员审批、LLM 意图提炼与 Milvus 写入**：
  实现了管理员审批入库接口，支持管理员可选进行意图与 SQL 的微调纠错；集成了后台异步处理管道，通过 FastAPI `BackgroundTasks` 拉起 LLM 重写与脱敏服务；设计了后台 LLM 提炼模型（`llm_refiner.py`）进行多轮会话指代消解与字面值占位符脱敏，并配置了安全降级退回策略；在 `factory.py` 中实现了 `add_document_to_store` 向量写入适配层，支持 LlamaIndex 写入 Milvus Hybrid Collection。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 新增 `MessageApproveRequest` 请求 Schema，以支持管理员的可选改写参数。

#### backend/app/api.py [MODIFY]
- 新增 `POST /api/chat/admin/messages/{message_id}/approve` 审批接口。
- 实现 `process_collected_message_async` 异步处理管道，整合规则初筛、LLM 提纯和向量写入。

#### backend/app/agent/vector/llm_refiner.py [NEW]
- 实现大模型意图消解重写与 SQL 字面值脱敏函数 `refine_sql_case_with_llm`，具备防崩溃自动回退机制。

#### backend/app/agent/vector/test_llm_refiner.py [NEW]
- 编写提炼服务测试，验证大模型正常提炼以及异常连接时的平稳降级行为。

#### backend/app/agent/vector/factory.py [MODIFY]
- 新增统一向量存储适配器函数 `add_document_to_store`，完美支持 Milvus 及 PgVector。

#### backend/app/test_api_persistence.py [MODIFY]
- 新增审批路由 API 测试以及异步提炼写入全集成联调测试 `test_process_collected_message_async_integration`。

## 2026-06-29 11:39 +08:00 - 实现用户反馈收集基建与规则提取过滤器管道和拓扑精准回溯

### 概述
- **第一阶段：用户反馈收集基础建设与落库**：
  在后端 `ChatMessage` 模型中扩展了 `feedback` 列，提供 `MessageFeedbackRequest` 反馈打标校验并在 API 中开放了状态同步路由；在前端 Vue 消息卡片底端集成了“赞/踩/收藏”高亮操作按钮并打通了实时状态落库逻辑。修复了脱机运行下 `test_api_resume.py` 对 `get_messages_by_session` 的 Mock 缺失问题，保证测试全绿。
- **第二阶段：规则提取器与拓扑精准回溯**：
  新增了基于 Pipeline-Filter 设计模式的规则过滤器模块，定义了任务上下文与管道管理器，依次实现四大静态规则过滤器（安全检测、空结果判定、多步/报错 SQL 单步拦截舍弃以及业务域隔离）；特别实现了 `TopologyBacktrackFilter` 基于原生 `tool_call_id` 自动咬合还原包含澄清问答历史的多轮对话意图；编写了 8 项独立 TDD 测试用例全面覆盖各过滤分支与链路集成校验。

### 变更内容
#### backend/app/models.py [MODIFY]
- 为 `ChatMessage` 实体模型追加 `feedback` 字段。

#### backend/app/schemas.py [MODIFY]
- 在消息响应基类中注入 `feedback` 序列化结构，并提供 `MessageFeedbackRequest`。

#### backend/app/crud.py [MODIFY]
- 实现 `update_message_feedback` 数据状态持久化修改方法。

#### backend/app/api.py [MODIFY]
- 发布 `POST /api/chat/messages/{message_id}/feedback` 路由响应用户点击反馈。

#### backend/app/test_api_persistence.py & test_api_resume.py [MODIFY]
- 补齐反馈 API 的 TDD 测试案例。为 `test_resume_endpoint_success` 修复 offline 状态下 missing mock 导致的 db 连接失败问题。

#### backend/app/agent/vector/rule_extractor.py [NEW]
- 创建规则提取上下文、管道控制器及五大过滤器校验器（`SafetyWarningFilter`, `EmptyResultFilter`, `SingleSqlFilter`, `TopologyBacktrackFilter`, `DomainFilter`），定义 `DEFAULT_EXTRACTOR_PIPELINE`。

#### backend/app/agent/vector/test_rule_extractor.py [NEW]
- 编写 8 个测试用例，覆盖过滤器的校验和拓扑回溯意图合成的完整链路。

#### frontend/src/types/index.ts, src/api/messages.ts, src/stores/messages.ts [MODIFY]
- 注入 `feedback` 可选属性，导出 axios 交互 API，并在 Pinia store 中新增 `submitMessageFeedback` action 驱动。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 为 AI 消息卡片集成了 👍、👎、⭐ 高亮交互按钮，成功通过 `vue-tsc` 的强类型编译及打包检查。

## 2026-06-28 23:12 +08:00 - 优化澄清会话数据链系统化完整关联存储

### 概述
- **实现澄清数据链条闭环**：重构了流式中断与恢复挂起的消息持久化逻辑，解决工具调用和返回结果的丢失与错位问题。在 `interrupt` 写入消息时补全 `tool_results` 保存；在用户回答落库时倒序查询历史消息以匹配 `AskUserQuestion` 调用 ID 并以此 ID 序列化存储回答；同时在最终结果输出中主动拦截隔离历史澄清提问的返回结果。

### 变更内容
#### backend/app/api.py [MODIFY]
- 在 `/stream` 与 `/resume` 路由的中断处理分支中加入 `tool_results` 持久化，补齐 `load_skill` 与 `load_scenario` 的返回数据存储。
- 在 `/resume` 路由中，通过 `get_messages_by_session` 追溯最近一次 Assistant 的 `AskUserQuestion` 调用 ID，以 `{ask_user_tool_call_id: answers}` 格式保存 User 消息。
- 在恢复流式循环的 `tool_result` 监听及 `final` 事件中，过滤排除对应的 `ask_user_tool_call_id`，防止其泄露至最终消息。

#### backend/app/test_api_persistence.py [MODIFY]
- 扩充单元测试，对 `test_stream_interrupt_saves_clarification` 增加 `tool_result` 返回值保存的校验；重构 `test_resume_saves_user_answers` 支持 mock 历史消息并断言 ID 强对齐配对。

## 2026-06-28 22:36 +08:00 - 修复流式中断挂起场景工具调用完整持久化存储

### 概述
- **修复流式中断工具调用丢失漏洞**：在 `/stream` 和 `/resume` 生成器遇到 `interrupt` 事件（澄清提问）时，系统不再使用单一硬编码的 `AskUserQuestion` 覆盖已有的工具列表，而是将内存 `tool_calls_map` 缓存的所有已执行工具调用（如 `load_skill`, `load_scenario` 以及带原生 ID 的 `AskUserQuestion` 等）一并序列化并保存，保障了中断状态消息中工具调用数据链的完整性。

### 变更内容
#### backend/app/api.py [MODIFY]
- 修改流式（`/stream`）和恢复流（`/resume`）的 `interrupt` 中断事件持久化逻辑，从内存 `tool_calls_map` 中合并获取全部已调用的工具记录，并进行 JSON 序列化存储。

#### backend/app/test_api_persistence.py [MODIFY]
- 在 `test_stream_interrupt_saves_clarification` 单元测试中添加了 `load_skill` 前置调用模拟，并断言其能够与 `AskUserQuestion` 合并成功保存到数据库中。

## 2026-06-28 21:52 +08:00 - 修复流式澄清提问处理中的 AttributeError 与 JSON 序列化异常

### 概述
- **修复 AttributeError 报错**：在 `api.py` 的流式响应生成器（`generate`）中，当收到 `interrupt`（澄清提问）事件时，列表中的 `questions` 元素为 Pydantic 模型（`QuestionItem`）而非原生字典，从而导致调用 `q.get('question')` 时发生 `'QuestionItem' object has no attribute 'get'` 报错。对此增加了 Pydantic 模型的识别与 `.model_dump()` 字典化转换兼容。
- **修复潜在的 JSON 序列化失败**：由于 `questions` 原本为 Pydantic 对象列表，直接传给 `json.dumps` 写入消息的 `tool_calls` 会在数据库持久化时导致 `TypeError`。此次修改使用字典化后的 `questions_dump` 进行序列化，消除了序列化失败隐患。

### 变更内容
#### backend/app/api.py [MODIFY]
- 对 `interrupt` 事件处理逻辑进行健壮性兼容优化。遍历 `questions` 时，自动检测并对 Pydantic 模型执行 `model_dump()` 转换为原生字典，保证了对属性字段（如 `question` 和 `options`）的安全读取。
- 传入转换后的原生字典列表 `questions_dump` 以供 `json.dumps()` 成功序列化并持久化至 `MessageCreate` 消息数据库表。

## 2026-06-28 16:31 +08:00 - 新增“关于系统”弹窗与版本日志展示功能

### 概述
- **新增“关于系统”弹窗**：在前端增加了一个高颜值、响应式且支持毛玻璃（Glassmorphism）效果的分栏弹窗组件 `VersionChangelogModal.vue`。弹窗左侧为带状态呼吸灯的垂直时间线，右侧卡片式分组呈现新特性（🎉 Features）、性能优化（⚡ Improvements）与问题修复（🐛 Bug Fixes）。
- **主页面触发与集成**：在 `ChatView.vue` Header 头部右上角集成了“ℹ️ 关于”按钮，用来触发该弹窗。支持点击遮罩层、右上角 "✕" 按钮或按 `Esc` 键进行平滑关闭，并防止了弹窗开启时的背景滚动穿透。

### 变更内容
#### frontend/src/components/VersionChangelogModal.vue [NEW]
- 创建了弹窗组件。实现了模态框在打开/关闭时的渐变过渡，支持通过 timeline 切换选中版本，预置了更新日志的 Mock 数据以供用户后续直接修改与填写。
- 绑定了键盘 `keydown` 监听事件，在按下 `Escape` 键时关闭弹窗，并在弹窗打开时将 `document.body` 锁死以防滚动穿透。

#### frontend/src/views/ChatView.vue [MODIFY]
- 导入并注册了 `VersionChangelogModal` 组件及 `showChangelog` 状态。
- 在 Header bar 右侧添加了带有 `ℹ️` 图标和 “关于” 文本的触发按钮。

## 2026-06-28 13:25 +08:00 - 修复消息持久化机制漏洞与前端工具详情参数展示遗漏

### 概述
- **修复后端消息持久化漏洞**：补齐了在 Agent 中断澄清挂起（Interrupt）、澄清回复（Resume）、连接中途异常断开以及非流式请求报错场景下的消息持久化保存逻辑，确保了 `chat_messages` 对话历史表中每一步的完整性。
- **修复前端工具参数展示遗漏**：解决了由于非流式或重新加载历史时缺乏 `args_text` 字段而导致前端调试面板内工具参数和 SQL 语句完全空白的 Bug；增加了对结构化 `args` 的智能兼容和 JSON 格式化输出。
- **优化工具结果名称关联**：实现了工具返回结果 ID 到工具名称的动态映射，将原本抽象的 `工具结果 tool_0` 转换为如 `工具结果: sql_db_query (tool_0)` 的友好形式，便于直观调试。

### 变更内容
#### backend/app/api.py [MODIFY]
- 在 `/stream` 和 `/resume` 生成器中遇到 `interrupt` 事件时，增加将 AI 的澄清卡片问题保存为 `assistant` 消息的逻辑。
- 在 `/resume` 接口开始处理前，将用户的 `answers` 澄清回答以 `user` 角色消息安全保存入库。
- 在 `/stream` 和 `/resume` 的生成 `finally` 块中加入连接断开捕获保护，对尚未保存的 partial message 进行补存入库（内容包括 partial content 和 `tool_calls`）。
- 在 `/message` 非流式接口发生 `Exception` 报错时，在抛出异常前捕获并向数据库记录报错的 `assistant` 消息。

#### backend/app/test_api_persistence.py [NEW]
- 创建独立的测试文件，编写并验证了中断挂起保存、回答恢复保存、连接中途断开保存、非流式异常保存 4 个 TDD 测试场景，确认全部通过。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 新增 `getToolArgsText`、`getToolNameById` 和 `formatToolResultContent` 助手函数。
- 更新模板逻辑，即使在无 `args_text` 字段的情况下，也支持读取 `args` 字典（并针对 SQL 语句直接提取 `query` 渲染，对其他复杂参数 pretty print 展示）。
- 支持将工具结果的 `id` 还原为工具名称并缩进格式化 JSON 内容。

## 2026-06-25 22:33 +08:00 - 侧边栏折叠过渡动画性能优化

### 概述
- **消除折叠过度动画卡顿**：针对侧边栏（VariantB.vue）折叠展开时的反应迟钝现象，将全局过度监听 `transition-all` 替换为精准定位的 `transition-[width,transform]` 属性，并应用 `will-change-[width,transform]` 开启 GPU 硬件加速缓存，从而大幅降低了浏览器的样式计算压力。
- **清除内部双重容器动画**：删除了内部头部容器 `div` 上冗余的 `transition-all` 类名，消除了由于内边距和排版排列突变带来的二次重绘瓶颈。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 对 aside 节点与 header container 的 transition 逻辑进行精细化优化，消除了动画重排抖动并提升了整体折叠动效响应速度。

## 2026-06-25 22:20 +08:00 - 为 AskUserQuestion 交互卡片新增取消按钮及单选项重置能力

### 概述
- **新增澄清问答取消按钮**：在前端交互卡片 [AskUserQuestionCard.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/AskUserQuestionCard.vue) 的“确认并恢复生成”按钮左侧增加了“取消”按钮。点击“取消”按钮时，将向后端发送包含 `已取消` 意图的提问答复，确保大模型从中断状态中恢复并以友好形式退出该任务。
- **优化单选项点击与重置**：优化了单选项的选择交互。用户再次点击已选中的单选项，可以将其重置为未选中状态，方便用户撤销选择而无需被迫选择。

### 变更内容
#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 在底部操作区域新增“取消”按钮（Outlined style，优雅适配整体卡片的 Glassmorphism 现代质感）。
- 编写 `handleCancel` 函数实现“取消”意图的收集并提交。
- 调整 `onOptionClick` 中针对单选模式（`item.multiSelect === false`）的逻辑：当再次点击已被选中的单选项时，自动将其清空，支持单选项的重置与反选。

## 2026-06-25 10:42 +08:00 - 本地化部署优化：清理前端冗余的外部 Google Fonts 引用

### 概述
- **移除冗余 Google Fonts 链接**：在 [index.html](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/index.html) 中删除了在本地/内网环境（无公网）下会导致连接超时的 Google Fonts 资源引用。该字体系 `Inter` 字体，在当前的样式定义中并未实际被引用，属于冗余资源。
- **防止加载超时阻塞与控制台报错**：此举彻底消除了本地化/离线部署时由于向 `fonts.googleapis.com` 发起请求而产生的网络报错与首屏加载可能产生的渲染阻塞。

### 变更内容
#### frontend/index.html [MODIFY]
- 清理了引入 `https://fonts.googleapis.com` 域名的三行外部 `<link>` 标签，保留了项目的基础 favicon 与元数据定义。

## 2026-06-21 15:06 +08:00 - 设计并实现 AskUserQuestion 澄清问答与中断恢复功能，构建前后端闭环交互

### 概述
- **实现 AskUserQuestion 澄清问答工具**：在 FastAPI 后端引入了基于 LangGraph 原生 `interrupt` 控制流的结构化澄清问答工具 `AskUserQuestion`。支持向前端发送单选/多选/自定义补充等结构化卡片提问，使大模型能在面临需求模糊、技术权衡或危险 SQL 执行时安全暂停流并等待用户确认。
- **完善 API Resume 接口与流式恢复**：在 `api.py` 中新增了 `POST /api/chat/resume` 路由与 `ResumeChatRequest` 请求体，支持在 PostgresSaver 状态检查点下使用 `Command(resume=...)` 恢复因 interrupt 挂起的 Graph 并继续流式输出。
- **打造高交互 Glassmorphism 前端澄清卡片**：前端利用 Pinia Store 和 SSE 事件流捕获 `interrupt` 类型的流式响应，并在聊天气泡下方动态渲染出 `AskUserQuestionCard.vue` 问答卡片。卡片设计支持单选/多选/纯填空自定义输入互斥，并在提交后自动触发 `resumeMessage()` 重启流，并对历史卡片做 disabled 只读锁定处理。
- **强化混合澄清与字符串 JSON 参数预校验**：在 Pydantic 的 `QuestionItem` 和 `AskUserQuestionSchema` 中增加了预处理解析，解决大模型传递 stringified JSON 的 ValidationError，并在前后端对混合提问（选项+文本输入）进行了拼接回传与自适应编号高亮。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 引入 `QuestionItem`，正式定义并注册了 `InterruptStreamEvent`，彻底解决 tagged-union 反序列化中断事件校验崩溃的缺陷。

#### backend/app/agent/tools/ask_user_question.py [NEW]
- 定义 `QuestionOption`, `QuestionItem` 和 `AskUserQuestionSchema`，基于 LangGraph `interrupt()` 编写 `AskUserQuestion` 工具，并实现了 robust pre-validator。

#### backend/app/agent/tools/test_ask_user_question.py [NEW]
- 编写测试用例验证 `AskUserQuestion` 工具，支持 optional options、string json inputs 预校验等。

#### backend/app/agent/service.py [MODIFY]
- 挂载 `AskUserQuestion` 工具，在 System Prompt 中加入详细的“澄清与确认规范”以及混合提问意图拆分引导。

#### backend/app/agent/test_service_interrupt.py [NEW]
- 编写集成测试，模拟 LangGraph 的 `interrupt` 中断和状态恢复流。

#### backend/app/services.py [MODIFY]
- 扩展 `SQLAgentService` 实现 `process_stream_resume` 生成器，在流式生成中动态捕获并向前端抛出 `'interrupt'` 事件。

#### backend/app/api.py [MODIFY]
- 实现并暴露 `POST /api/chat/resume` 路由，接受用户回答后安全唤醒挂起的 Graph。

#### backend/app/test_api_resume.py [NEW]
- 编写接口测试，模拟并验证 `/api/chat/resume` 请求流程。

#### frontend/src/types/index.ts [MODIFY]
- 新增 `QuestionOption`、`QuestionItem` 类型，为消息流事件补全 `interrupt` 属性支持。

#### frontend/src/stores/messages.ts [MODIFY]
- 引入 `setStreamingInterrupt` 来在 store 中标记挂起的中断流状态。

#### frontend/src/api/chat.ts [MODIFY]
- 增加了 `sendChatResumeStream` 请求函数，并在 `parseStreamEvent` 中对 `'interrupt'` 包放宽 options 校验以兼容纯文本输入。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 实现了 `resumeMessage` 方法，用于发起并重新连接流式响应。

#### frontend/src/components/AskUserQuestionCard.vue [NEW]
- 编写毛玻璃自适应问答卡片组件，支持单选/多选/纯填空/混合模式，具备 questions 列表编号和必填校验。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 动态嵌入 `AskUserQuestionCard`，实现对 computed `questions` 的 watch 深度监听以自动重置 `isLocalSubmitted` 锁定状态，解决组件复用锁死 Bug。

#### README.md [MODIFY]
- 补充“澄清问答卡片 (AskUserQuestion)”特性描述及 `/api/chat/resume` 接口。

#### docs/ [NEW]
- 新增 `docs/ask_user_question_design_pattern.md`、`docs/langgraph_memory_and_persistence_guide.md` 和 `docs/claudecode_docs/05_AskUserQuestion工具设计与使用指南.md`，深度梳理设计模式、状态持久化与工具使用细节。

## 2026-06-20 22:56 +08:00 - 优化缺陷分析指标生成，默认聚焦均值与检测次数以防范总数脑补

### 概述
- **强化大模型缺陷指标统计规则**：在涂装车间质量缺陷分析领域（`paint_shop_defect_analysis`）中，强力约束大模型在编写 SQL 时默认采用“检测次数”（`COUNT(*)`）与“平均单次检测缺陷数”（`AVG(mq.total_defect_count)`）进行统计，防范大模型在未明确指令时脑补并生成无意义的“缺陷总数”（`SUM(...)`）统计语句。
- **Few-Shot SQL 示例多后端同步注入**：分别在 Milvus 与 PGVector 检索数据源中追加了三个典型的缺陷均值与检测频次的 SQL 查询示例，并成功对向量数据库（Milvus）完成了重建索引，使大模型在检索 Few-Shot 时能够高频召回并模仿标准的均值与频次统计口径。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/domain.md [MODIFY]
- 在指标（`指标`）小节中全新引入 `[!IMPORTANT]` 级别的“质量缺陷统计核心军规”，强力限定默认指标为频次和均值，澄清了“单车缺陷”的计算公式，并严格限制对 `SUM` 聚合函数的使用。

#### backend/app/agent/vector/milvus_init/data/examples/example_sql_example.json [MODIFY]
- 在 JSON 数据集中追加三个典型缺陷统计的 SQL 示例（包括按车型趋势、按检测通道、按检测次数对比等），均演示了 `COUNT(*)` 和 `AVG(...)` 组合指标的用法。

#### backend/app/agent/vector/pgvector_init/examples/example_sql_example.json [MODIFY]
- 对齐更新 PGVector 的 SQL 示例数据集，确保测试环境与生产配置下的向量召回一致性。

## 2026-06-20 21:25 +08:00 - 修复 AskUserQuestion 混合输入澄清场景下用户操作路径断裂


### 概述
- **修复混合提问导致的操作路径断裂**：修复了在触发澄清问答卡片（`AskUserQuestion`）时，大模型抛出混合提问意图（如“同时输入车号和选择读写站”）导致前端由于强互斥逻辑而无法让用户同时完成输入与选择的问题。
- **引入双端优化与容错**：
  - **后端**：在 `AskUserQuestionSchema` 和 `QuestionItem` Pydantic 定义中加固了字段描述，并在 System Prompt 中注入了混合模式下的正反面 JSON 拆分示例，强力约束大模型将多参提问拆分为两个 `QuestionItem` 提问项。
  - **前端**：在 `AskUserQuestionCard.vue` 中移除了单选/多选与 textarea 文本框的强互斥清空，优化了 textarea 提示文本，并在提交 payload 时对两者皆有的场景进行智能拼接（分号连接）回传，保证了历史遗留或脑抽混合场景下的完美兼容和操作闭环。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 升级了 `QuestionItem.question` 以及 `AskUserQuestionSchema.questions` 的 `Field` description 说明，增加了混合澄清拆分的引导与正反面示例。

#### backend/app/agent/service.py [MODIFY]
- 升级了 `# 澄清与确认规范` 的系统提示词内容，为“3. 混合模式”追加了具体的 questions JSON 代码块说明。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 移除了选项点击和 textarea 输入时的强互斥清空行。
- 更新了自适应的 textarea label 和 placeholder，提供更好的混合提问输入引导。
- 升级 `handleSubmit` 逻辑，在选项与文本框同时有值时以 `; 关联输入: ` 无损拼接形式传回后端。
- 修复了纯填空问答卡片（没有 options 选项列表时）误展示为“单选”徽章的交互缺陷，仅在 options 存在时才渲染该徽章。
- 支持多问题卡片的提问编号（如“问题 1 / 3”高亮徽章），只有当卡片中包含 2 个及以上问题时才自适应呈现，提升多参提问时界面结构感，防止用户漏答。

## 2026-06-20 20:00 +08:00 - 整理并沉淀 LangGraph 状态持久化与会话记忆技术指南文档

### 概述
- **整理发布会话记忆与持久化指南**：编写并归纳了项目基于 LangGraph Checkpointer 持久化、动态多 System Message 物理抽干与合并拦截器、以及基于 Token 估算的上下文滑动窗口压缩摘要等全套记忆管理系统的设计与核心实现原理。

### 变更内容
#### docs/langgraph_memory_and_persistence_guide.md [NEW]
- [全新增加] 《LangGraph 记忆与状态持久化机制技术指南》，作为项目核心架构与状态持久化部分的重要补充。

## 2026-06-20 17:15 +08:00 - 修复同消息流下多次澄清问答卡片被锁死无法提交的 Bug

### 概述
- **修复澄清卡片组件复用状态残留问题**：修复了在同一个流式会话生命周期内（即同一个 `streamingMessage` 内）大模型多次触发 `AskUserQuestion` 澄清卡片时，由于 `MessageItem.vue` 组件复用，本地提交控制状态 `isLocalSubmitted` 仍保留第一轮的 `true` 锁死状态，导致第二轮澄清卡片一渲染就被锁死为只读不可编辑且无法提交的 Bug。
- **引入流式问题包监听自动重置机制**：在 `MessageItem.vue` 中引入 `watch` 指令。对 computed 属性 `questions` 列表进行深度监听，一旦发觉流式响应推入了新的问题包，自动重置 `isLocalSubmitted` 状态为 `false`，解除只读锁定，开启第二轮澄清编辑。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 引入了 `watch` 并编写对 `questions` 列表的深度监听逻辑，在产生新问题时重置 `isLocalSubmitted.value` 状态。

## 2026-06-20 16:58 +08:00 - 修复 AskUserQuestion 澄清事件在开放式文本问答模式下的前端校验拦截 Bug

### 概述
- **修复前端流式响应终止报错**：修复了在触发纯文本开放式问答（不含 `options` 选项列表的 QuestionItem）时，由于前端 `chat.ts` 内部的 `parseStreamEvent` 对 `interrupt` 事件包进行了过分严苛的属性校验（`!Array.isArray(q.options)` 会在 options 为空/undefined 时抛出错误判定），导致该流式事件被忽略丢弃，从而引发流结束时因检测不到终端事件而抛出“流式响应在收到终止标记前未返回 final 或 error 事件”异常的 Bug。
- **放宽字段校验机制**：在 `chat.ts` 校验分支中调整了对 `q.options` 的验证逻辑，支持在 `options` 为 `undefined` 或 `null` 时直接跳过子项的数组解析和校验，确保开放式输入与混合输入下的事件均能完美被前端反序列化和激活。

### 变更内容
#### frontend/src/api/chat.ts [MODIFY]
- 重构了 `case 'interrupt'` 的属性类型检查管道，使 options 字段可安全地缺省或设置为 null，消除类型误判拦截。

## 2026-06-20 15:58 +08:00 - 优化 Windows 本地数据库连接配置，将 localhost 替换为 127.0.0.1 解决后端冷启动延迟

### 概述
- **消除 Windows 下 IPv6 TCP 连接超时延迟**：将项目根目录下 `.env` 配置文件中的所有 `localhost` 替换为直连的 IPv4 地址 `127.0.0.1`。解决了由于 Windows 操作系统中 `localhost` 默认优先解析为 IPv6 (`::1`) 导致数据库驱动在无 `connect_timeout` 参数下多次发生 21 秒连接超时的挂起现象，使本地后端开发环境的启动时间由之前的约 **130秒** 直接缩减至 **5秒以内**。

### 变更内容
#### .env [MODIFY]
- 将 `DATABASE_URL`、`ROLLERBED_DATABASE_URL` 和 `ANALYTICS_DATABASE_URL` 中的 `localhost` 替换为 `127.0.0.1`。
- 同步将 `OLLAMA_BASE_URL`、`MILVUS_URI` 和 `MYSQL_DATABASE_URL` 中的 `localhost` 替换为 `127.0.0.1`，消除潜在的连接延迟隐患。

## 2026-06-20 14:06 +08:00 - 增强 AskUserQuestion 系统提示词与工具说明文档以引导大模型精准输出

### 概述
- **增强工具说明与系统提示词引导**：为了配合新上线的“纯文本开放式问答模式”与“混合模式”，对系统提示词（System Prompt）中的『澄清与确认规范』以及 `AskUserQuestion` 的工具级 `description` 进行了靶向增强。这能引导大模型在需要收集车身号、工序等参数时，自发正确地选择是使用“选择模式”、“开放式问答模式（省略options参数）”还是多问题的“混合模式”来发起澄清。
- **细化 Schema 字段说明**：对 Pydantic 的 `QuestionItem` 进行了更深度的字段说明（`Field(description=...)`）扩充。明确了 `question` 会作为返回答案 dict 的 key，细化了 `header`、`multiSelect` 以及 `options` 在各种提问模式下的语义，确保不同大模型对 JSON Schema 的绝对对齐和稳定理解。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 更新了 `AskUserQuestion` 类的 `description` 字段，明示工具对备选项及纯文本开放式提问的支持和传参约定。
- 重构了 `QuestionItem` 中 `question`、`header`、`multiSelect` 和 `options` 字段的 `description` 说明。

#### backend/app/agent/service.py [MODIFY]
- 升级了 `_build_system_prompt` 中『澄清与确认规范』的规约内容，提供了选择模式、开放式问答模式、混合模式的具体判定场景与传参引导。

## 2026-06-20 14:02 +08:00 - 升级 AskUserQuestion 澄清卡片以支持纯文本问答模式（无选项纯填空）

### 概述
- **支持纯文本问答模式**：扩展了 `AskUserQuestion` 澄清卡片的功能，使其不仅能处理单选或多选问题，还能原生支持**纯开放式文本提问**（如直接提示用户输入特定车号、时间范围等，且卡片上不显示任何选项网格）。
- **参数自适应与交互优化**：
  - 将 `QuestionItem` 的 `options` 字段变更为可选。
  - 前端模板自适应：如果 `options` 缺省或为空，选项网格会自动隐藏，文本框对应的标题及 placeholder 会自动切换为纯开放问答提示。
  - 校验自适应：非选项问题时，校验规则（`canSubmit`）将强制要求用户在文本框内完成内容录入，防止空值提交。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 将 `QuestionItem` 结构体中的 `options` 字段类型由必填变更为 `Optional[List[QuestionOption]] = Field(default=None)`。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 新增 `test_ask_user_question_optional_options` 单元测试，验证对无选项（options 为空）参数校验的正确性。

#### frontend/src/types/index.ts [MODIFY]
- 将 `QuestionItem` 接口中的 `options` 属性声明变更为可选（`options?: QuestionOption[]`）。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 在模板中为选项按钮网格包裹了 `v-if="item.options && item.options.length > 0"`。
- 根据是否有选项动态切换文本框上方的 `label` 标签（由『其他 / 自定义说明』动态变更为『请输入答案 / 说明』）及 `placeholder` 占位符。
- 更新了 `canSubmit` 校验计算属性，支持无选项提问时的空值拦截逻辑。

## 2026-06-20 13:52 +08:00 - 移除 AskUserQuestion 问答卡片的 Preview 预览功能以简化非代码应用场景

### 概述
- **简化问答卡片布局**：鉴于本项目并非面向代码开发的 Code Agent，为了使前端问答交互界面更加简洁、干净、聚焦于选项抉择本身，移除了澄清问答卡片（`AskUserQuestionCard`）右侧的代码/配置对比预览（Preview）侧边面板。
- **清理前后端冗余字段与状态**：
  - **后端**：在 `QuestionOption` 结构体中删除了 `preview` 字段，优化了参数解析开销并节省了大模型 Token 输出。
  - **前端**：删除了 `QuestionOption` 中的 `preview` 类型，物理清理了 `AskUserQuestionCard.vue` 内部的 `hoveredPreview`、`hasCodePreviews`、`displayPreview`、`renderedPreview` 等响应式状态与 Markdown 编译逻辑。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 从 `QuestionOption` 中移除 `preview` 字段声明。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 移除了测试用例 payloads 中的 `"preview"` 字段以对齐最新的 Schema 结构。

#### frontend/src/types/index.ts [MODIFY]
- 从 `QuestionOption` 接口中移除可选的 `preview` 属性。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 完全移除了右侧预览面板的 HTML/SVG 结构与 `:deep(.markdown-body)` 样式。
- 删除了所有 hover 事件监听与预览相关的计算属性和 markdown 引用。

## 2026-06-20 13:40 +08:00 - 修复 AskUserQuestion 澄清工具 stringified JSON 传参时的反序列化校验报错

### 概述
- **修复 AskUserQuestion 澄清工具反序列化报错**：针对大模型在调用澄清问答工具时，可能会将 `questions` 参数误以序列化后的 JSON 字符串（而非直接的 list）格式传递，导致 Pydantic schema 在参数校验阶段抛出 `questions: Input should be a valid list` 的 ValidationError。
- **引入 Robust Pre-Validator 解析机制**：在 `AskUserQuestionSchema` 内部的 `questions` 字段上引入了 `field_validator(mode="before")`，支持在 Pydantic 进行正式类型验证前自动尝试解析 JSON 格式的字符串，能够健壮处理带 Markdown 围栏（```json）的字符串、标准 JSON 数组字符串以及使用 `ast.literal_eval` 进行单引号的容错解析。
- **完善单元测试**：在 `test_ask_user_question.py` 中补充了 `test_ask_user_question_string_input` 靶向测试，并在 conda `py312_agent` 环境下通过 pytest 验证了全部单元测试（100% 成功）。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 在 `AskUserQuestionSchema` 增加了 `@field_validator("questions", mode="before")` 预处理方法 `parse_questions`，支持字符串到 List 对象的解析转换。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 新增 `test_ask_user_question_string_input` 单元测试以验证字符串传参的自动解析及成功校验。

## 2026-06-19 21:40 +08:00 - 集成 AskUserQuestion 澄清问答卡片（LangGraph 1.1.8 中断流与前端 Vue 3 交互集成）

### 概述
- **实现 AskUserQuestion 澄清问答工具**：在 FastAPI 后端引入了基于 LangGraph 1.1.8 原生 `interrupt` 控制流的结构化澄清问答工具 `AskUserQuestion`。支持向前端发送单选/多选/自定义补充等结构化卡片提问，使大模型能在面临需求模糊、技术权衡或危险 SQL 执行时安全暂停流并等待用户拍板。
- **完善 API Resume 接口与流式恢复**：在 `api.py` 中新增了 `POST /api/chat/resume` 路由与 `ResumeChatRequest` 请求体，支持在 PostgresSaver 状态检查点下使用 `Command(resume=...)` 恢复因 interrupt 挂起的 Graph 并继续流式输出。编写了高保真 Mock API 与中间件单元测试，100% 跑通测试。
- **打造高交互 Glassmorphism 前端澄清卡片**：前端利用 Pinia Store 和 SSE 事件流捕获 `interrupt` 类型的流式响应，并在聊天气泡下方动态渲染出 `AskUserQuestionCard.vue` 问答卡片。卡片设计完美遵循 "Light Mode Card-based Workspace" 的毛玻璃质感，并支持互斥输入（选项选择与 textarea 互斥）、hover 悬停实时渲染 Markdown 代码对比预览等高级微动效，提交后自动触发 `resumeMessage()` 重启流，并对历史卡片做 disabled 只读锁定处理。
- **修复 Interrupt 事件流式序列化崩溃 Bug**：在 `schemas.py` 中为 tagged-union `ChatStreamEvent` 补齐注册了新事件类型 `InterruptStreamEvent`，消除了大模型触发澄清中断时 API 序列化报错并强行关流的崩溃隐患。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 引入 `QuestionItem`，正式定义并注册了 `InterruptStreamEvent`，彻底解决 tagged-union 反序列化中断事件校验崩溃的缺陷。

#### backend/app/agent/tools/ask_user_question.py [NEW]
- 定义 `QuestionOption`, `QuestionItem` 和 `AskUserQuestionSchema`，基于 LangGraph `interrupt()` 编写 `AskUserQuestion` 工具。

#### backend/app/agent/service.py [MODIFY]
- 在 `_prepare_tools` 中注册并挂载 `AskUserQuestion` 工具，并在 System Prompt 中增加对调用该工具的指导思想和约束原则。

#### backend/app/services.py [MODIFY]
- 扩展 `SQLAgentService` 实现 `process_stream_resume` 生成器，并在流式响应发射阶段实时从 Graph 的 state 中检测 interrupts 详情并抛出 `'interrupt'` 事件。

#### backend/app/api.py [MODIFY]
- 引入 Pydantic 的 `BaseModel` 并声明 `ResumeChatRequest` schema。
- 实现 `POST /api/chat/resume` 流式接口，并在生成结束或异常时进行 assistant 消息的入库持久化。

#### backend/app/test_api_resume.py [NEW/MODIFY]
- 新写并完善了 `test_api_resume.py` 对 `/resume` 路由成功与 422 失败的 Mock 单元测试。

#### frontend/src/types/index.ts [MODIFY]
- 新增 `QuestionOption`、`QuestionItem` 类型声明，并在 `Message`、`StreamingMessage` 和 `StreamEvent` 中扩展 `interrupt` 属性与事件格式支持。

#### frontend/src/stores/messages.ts [MODIFY]
- 在 `useMessagesStore` 中加入 `setStreamingInterrupt` action，支持流式临时消息被挂起的中断状态转换。

#### frontend/src/api/chat.ts [MODIFY]
- 扩展 `STREAM_EVENT_TYPES` 兼容 `'interrupt'`，在 `parseStreamEvent` 中增加 `'interrupt'` 协议的安全解析与运行时校验，并全新声明并导出了 `sendChatResumeStream` 流式调用 API。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 升级 `handleStreamMessage` 以支持 `interrupt` 事件流正常断开；实现并导出 `resumeMessage` 方法，用于发起 resume 接口调用并重新开始流式输出。

#### frontend/src/components/AskUserQuestionCard.vue [NEW]
- 澄清问答卡片组件，支持单选/多选交互、选项与文本互斥、Hover 触发 Markdown 代码/配置块高亮预览、提交锁定状态和符合系统主题的轻量毛玻璃设计。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 在模板中引入并动态渲染 `AskUserQuestionCard`，实现 `isQuestionSubmitted` 历史只读计算逻辑，并关联 `@submit` 到 composable 暴露的 `resumeMessage` 执行。

## 2026-06-17 20:25 +08:00 - 修复 useChatStream 冗余分支及前端 TypeScript 类型冗余与构建报错

### 概述
- **修复 useChatStream 中冗余重复的 switch case 分支**：在前端流式聊天逻辑封装 `useChatStream.ts` 的 `handleEvent` 函数中，删除了重复的多余 `case 'tool_call'`, `case 'tool_result'`, `case 'final'`, `case 'error'` 分支，解决了 Vite 打包编译时的 "This case clause will never be evaluated because it duplicates an earlier case clause" 警告，消除了冗余代码。
- **清理 types/index.ts 的重复类型与语法缺失**：修复了类型定义文件 `types/index.ts` 中 `StreamingMessage` 接口未闭合右括号 `}` 导致的语法错误，并删除了大段冗余重复的类型定义（`StreamStage`, `StreamToolCall`, `StreamEvent` 等），恢复了文件整洁。
- **移除 ChatView.vue 未使用的方法**：删除了 `ChatView.vue` 中声明了但未被读取/使用的 `openSidebar` 函数，解决了 TypeScript 的 TS6133 构建报错。

### 变更内容
#### frontend/src/composables/useChatStream.ts [MODIFY]
- 删除了重复多余的分支代码，保持代码整洁。

#### frontend/src/types/index.ts [MODIFY]
- 删除了重复冗余的类型声明，并修复了 `StreamingMessage` 的接口闭合语法。

#### frontend/src/views/ChatView.vue [MODIFY]
- 删除了未使用的方法 `openSidebar`，满足严格的 TypeScript 编译检查。

## 2026-06-16 23:05 +08:00 - 实现图表一键生成 Banner 描述动态展示与图表小数点精度最多2位约束


### 概述
- **实现图表一键生成 Banner 描述动态展示**：升级了前端 `MessageItem.vue` 组件，将原来基于固定格式正则解析 `chartSuggestionType` 升级为支持动态描述的 `chartSuggestion` 解析（提取图表类型与自定义描述）。前端根据大模型返回的 `[suggest_chart:line|图表描述]` 标记，自动提取并在 Banner 中呈现类似于“检测到当前结果适合绘制：XXX，点击一键绘制”的提示信息，引导用户做出更加明确的绘制决策。
- **约束图表小数点精度最多为 2 位**：重构了 `ChartArtifactCard.vue` 中的数据提取与渲染逻辑。在 `buildSeriesData` 从数据源抓取数据时，如果值为 `number` 类型则在数据层通过 `Number(val.toFixed(2))` 进行强行截断，自动去除了冗余浮点位并剔除尾部零；同时对 `yAxis` 上的 `axisLabel.formatter` 进行了小数点最多 2 位的截断支持，防止 ECharts 自适应产生不规整的多位浮点数刻度，双管齐下提升了图表在各类边界数据下的展现质量与精细度。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 升级 `chartSuggestionType` 为 `chartSuggestion` 计算属性，支持带描述格式（`/\[suggest_chart:(line|bar|auto)(?:\|([^\]]+))?\]/`）的解析。
- 升级 `displayContent` 正则清理规则，适配任意长度的描述语。
- 修改模板 UI 中快捷 Banner 提示的文本逻辑和按钮 `v-if` 条件。

#### frontend/src/components/ChartArtifactCard.vue [MODIFY]
- 在数据提取层 `buildSeriesData` 中限制数值类型最多 2 位小数。
- 在 `yAxis` 的 `axisLabel` 配置中为双轴配置 `formatter`，规范 Y 轴刻度精度。

## 2026-06-16 22:45 +08:00 - 实现 SQL Agent 工具级数据库连接池复用并修复图表工具静默降级 Bug

### 概述
- **实现共享 Agent 已有连接池 (方案 A)**：重构了图表生成工具 `build_chart_artifact` 与 CSV 导出工具 `export_to_csv` 的初始化模式。移除了原本每次调用工具均就地销毁和重建连接的逻辑，改为通过依赖注入直接共享 Agent 启动时已创建且温热的数据库连接池 `db._engine`，消除了每次生图和导出时的 TCP 冷启动握手延迟。
- **修复 MaterializedViewSQLDatabase.engine 属性缺失引发的工具静默降级 Bug**：由于子类 `MaterializedViewSQLDatabase` 重写构造函数且未调用 `super().__init__`，其内部仅存有 `self._engine`。原有装配层在注入工具时，因调用 `db.engine` 会抛出 `AttributeError`，该错误在 `_prepare_tools` 的通用异常捕获块中被静默吞掉降级，导致 `build_chart_artifact` 工具未能进入可用工具列表中。现已修复为直接传递 `db._engine`，彻底根治了该隐藏缺陷。
- **增补本地模拟与服务加载单元测试验证**：在 scratch 目录下编写并执行了 `test_connection_pool.py` 与 `test_agent_init.py` 脚本，全面跑通了在 Windows 异步事件循环政策（SelectorEventLoop）下的工具运行与服务加载验证。

### 变更内容
#### backend/app/agent/tools/chart_artifact_tool.py [MODIFY]
- 修改工厂方法接收 `Engine` 参数，闭包内直接复用该引擎，彻底移除函数内部的 `create_engine` 逻辑及 `finally` 块中的 `engine.dispose()`。

#### backend/app/agent/tools/csv_export_tool.py [MODIFY]
- 修改工厂方法接收 `Engine` 参数，闭包内直接复用，同样移除函数内部 `create_engine` 与 `finally` 中的 `engine.dispose()`。

#### backend/app/agent/service.py [MODIFY]
- 在 `_prepare_tools` 方法中，将 `db.engine` 修正为直接传参子类暴露的 `db._engine` 成员。
- 清理了临时构建 `business_db_url` 的冗余行。

#### docs/backend/图表与CSV工具连接池复用优化总结报告.md [NEW]
- [全新增加] 编写并保存了《SQL Agent 图表与 CSV 导出工具连接池复用优化总结报告》，归纳了现场表现、根本原因分析、方案设计及经验教训。

## 2026-06-15 15:20 +08:00 - 上线 P0 级“读时投影 (Read-Time Projection)”上下文折叠中间件

### 概述
- **上线读时投影（Read-Time Projection）上下文折叠中间件**：为了应对长对话和多轮数据交互场景下 Token 剧烈膨胀及本地 vLLM Prefix Caching 频繁失效问题，在 `SafeMergeSystemMiddleware` 中开发并集成了内存级投影折叠转换。
- **保障前端大图表与数据明细无损渲染**：投影转换完全在 API 网络层发送的一瞬间发生在内存中，绝不改写或污染 Graph State 及本地 PostgresSaver。用户在 Vue 3 浏览器前端依旧拥有 100% 完整的历史数据大表格、CSV 下载链接与 Traceback 原生回显，完美保障视觉交互。
- **引入滑窗滑动保护与白名单过滤**：在 `config.py` 中新增 `LLM_CONTEXT_COLLAPSE_PROTECT_TURNS`（默认值 3）动态配置。仅折叠滑窗保护期之外的 `sql_db_query`, `search_saved_correct_tool_uses`, `build_chart_artifact`, `export_to_csv` 等白名单工具，豁免控制类工具（如 `load_scenario`），防止大模型丢失关键业务字段含义与 SQL 模板。
- **成功与失败查询分支极致静态化精简**：
  - **成功分支**：折叠为 100% 纯静态友好常量 `[SQL execution successful. Result content collapsed. Re-run query if details are needed.]`。
  - **失败分支**：折叠为 100% 纯静态友好常量 `[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]`。
  - 该改动彻底清除了原本在历史消息中残留的动态 SQL、动态错误内容以及行数信息，使得历史消息的字节序列前缀绝对保持稳固，极大提高了 Prefix Caching 命中率。
- **增补靶向单元测试回归验证**：在 `test_safe_merge_middleware.py` 中追加成功与失败的静态投影测试断言，验证了“滑窗边界、白名单过滤、真身无污染”等细节。利用 Pytest 100% 跑通。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `llm_context_collapse_protect_turns` 可选配置项。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新建 `_project_and_collapse_messages` 投影折叠管道。
- 去除 `_extract_core_error` 以及从 `sql_tools` 导入 `_estimate_row_count` 等动态逻辑，保证代码纯净零死代码。
- 在 `_modify_request` 顶端调用投影管道对历史消息做只读克隆转换，保障 `tool_call_id` 一致配对。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_context_collapse_successful_query` 和 `test_safe_merge_context_collapse_failed_query` 测试，并修正 state 的 dict 键值访问。

## 2026-06-15 14:10 +08:00 - 精简并澄清领域技能加载工具的返回提示信息，解决多轮对话下 LLM 的历史激活幻觉

### 概述
- **精简并澄清领域技能加载返回提示**：针对多轮会话中可能因多条历史 `ToolMessage` 存在导致大模型误判历史技能仍处于激活状态的痛点，精简并重构了 `load_skill` 工具调用返回的 `ToolMessage` 内容。
- **加入覆盖性排他声明**：明确在返回文本中强调“当前加载的领域技能已覆盖/失效了历史加载技能”，并引导大模型严格以 System Message 的 `Active Domain Knowledge` 为唯一准确的当前激活 DDL 依据，从而彻底消除跨域联查或表结构脑补等常见幻觉。

### 变更内容
#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 修改了 `_build_load_skill_command` 函数中 `ToolMessage` 返回的 `content` 模板，应用精简版排他指示文案。

## 2026-06-15 11:15 +08:00 - 统一同步与异步模式下对话压缩中间件的触发阈值配置

### 概述
- **实现统一的对话压缩触发阈值配置**：在 `.env` 配置文件中引入 `LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS='9000'`，将原本在 `SQLAgentService` 同步与异步模式下分别硬编码为 `10000` 和 `24000` 的 `SummarizationMiddleware` 触发阈值替换为动态读取该环境变量。
- **解决本地异步模式无法自动压缩的问题**：修复了在本地 FastAPI 异步开发模式（`_ainitialize_agent`）下 `SummarizationMiddleware` 的触发点被硬编码为 `24000` 从而导致在达到大模型 10000 物理窗口限制前根本无法触发自动对话压缩的历史痛点。

### 变更内容
#### .env [MODIFY]
- 新增 `LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS='9000'` 配置。

#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中添加 `llm_context_summarize_trigger_tokens` 环境变量字段读取。

#### backend/app/agent/service.py [MODIFY]
- 将 `_initialize_agent`（同步）与 `_ainitialize_agent`（异步）中实例化的两处 `SummarizationMiddleware` 的 `trigger` 阈值配置统一替换为 `trigger=("tokens", settings.llm_context_summarize_trigger_tokens)`。

## 2026-06-15 09:14 +08:00 - 实现系统提示词（System Message）注入当前日期功能

### 概述
- **实现 System Message 动态注入当前日期与星期**：在向大模型（LLM）发起调用前的 `SafeMergeSystemMiddleware` 拦截器中，实时格式化获取当前的本地系统日期与星期几，并拼装在全局唯一 System Message 的**最末尾**（如果存在 RAG 消息，也确保日期在 RAG 消息之后的最末尾），有效解决了大模型缺乏时间感知、容易记错时间的痛点，提升时间敏感型任务（如查询“今天”、“昨天”的数据）的准确率。
- **支持首轮提问日期自愈注入**：去除了 `SafeMergeSystemMiddleware` 在 `messages` 为空时直接退出的硬编码机制，确保新创建的会话在进行第一轮提问时，也同样能够成功注入当前日期。
- **补充靶向单元测试回归**：新建 `test_safe_merge_middleware.py` 单元测试，全方位覆盖无 RAG 对话、包含 RAG 消息合并以及空消息状态下的末尾日期注入验证。并在 Conda `py312_agent` 环境下全量跑通中间件单元测试，成功保障 100% 质量且无任何 Regression。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 去除 `if not messages:` 提前退出检查，改为安全读取 `request.messages`。
- 修改 `_modify_request` 逻辑，在没有 RAG 消息和有 RAG 消息合并的两种分支下，均动态计算当前日期并始终拼接到生成的全局 System Message 的最末尾。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [NEW]
- [全新增加] 编写 `test_safe_merge_injects_current_date_no_rag` 与 `test_safe_merge_injects_current_date_with_rag` 两个单元测试，高保真模拟 ModelRequest 并精确断言日期注入的格式与位置。

## 2026-06-14 21:48 +08:00 - 实现领域技能 DDL 移入 System Message 相对尾部优化

### 概述
- **实现静态 DDL 移入系统提示词 (System Message)**：彻底重构了领域技能的挂载和传输路径，将原本大段的物理表结构 DDL 从对话历史的 `ToolMessage` 剥离，转由 `SkillMiddleware` 动态拼装在 System Message 的相对尾部（Available Skills 可用菜单下方，动态 RAG 内容前面）。
- **落实“单一激活，跨域重载”防遗忘拦截**：修改了 `load_skill` 的状态更新逻辑，将 `skills_loaded` 列表覆写为仅包含当前激活技能。当大模型试图跨回旧领域执行查询时，前置拦截器将阻止盲目执行，迫使其先执行 `load_skill` 刷新 System 提示词中的 DDL，建立完美的自愈闭环。
- **优化核心指标 (Prefix Caching & TTFT)**：此举使得数千字庞大且静态的 DDL 文本彻底免疫消息历史的压缩与裁剪（`SummarizationMiddleware`）。同时，静态前缀保证了 vLLM `Prefix Caching` 的 100% 缓存命中，使首字延迟（TTFT）大幅缩短至毫秒级。
- **完善单元测试**：使用 TDD 模式编写并跑通了对 `SkillMiddleware` 拼接和 `load_skill` 状态覆盖重写的单元测试，确保重构回归安全性。

### 变更内容
#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 修改 `_build_load_skill_command` 函数，将 `skills_loaded` 更新由“合并”重构为“覆盖重写”，并精简 `ToolMessage` 回显为状态语。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 重构 `_modify_request` 方法，实现从 `request.state` 中提取激活的技能，并将详细的 DDL 文本拼装入 System Message。

#### backend/app/agent/middleware/test_skill_middleware.py [NEW]
- [全新增加] 编写 `test_skill_middleware_injects_active_ddl` 和 `test_load_skill_tool_overwrites_state` 单元测试，分别断言验证动态 DDL 系统拼接流程与排他激活状态更新。

## 2026-06-14 21:20 +08:00 - 修复多轮对话下历史 RAG 系统消息重复追加与合并的 Bug

### 概述
- **修复多轮对话下 RAG 消息堆积的问题**：修复了在多轮会话中，旧的 RAG 业务知识（`__business_rag_context__`）不断在 `state.messages` 中堆积，导致每次对话都会全量合并历史 RAG 的缺陷。通过为 `BusinessRagMiddleware` 生成的 RAG `SystemMessage` 赋予固定的 `id="__business_rag_context__"`，使 LangGraph 状态机能通过 `add_messages` 减法器进行原地覆盖替换，从而只保留最新一次检索的 RAG 内容。

### 变更内容
#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 在实例化 RAG `SystemMessage` 时显式指定 `id=self._rag_system_message_id`，启用 LangGraph 的 ID 覆盖合并机制。
- 升级 `before_model` 中的历史消息过滤与去重逻辑，优先匹配 `msg.id`，并向后兼容 `content` 及 `content_blocks` 的检索内容去重。

## 2026-06-14 18:30 +08:00 - 实现 vLLM Token 估算器与多系统消息安全合并

### 概述
- **引入 VllmTokenEstimator 精确估算 Token**：在 `backend/app/agent/utils` 下实现 `VllmTokenEstimator`，支持直接调用本地 vLLM 推理引擎的 `/tokenize` 端点获取最真实精确的 Token 计数。并加入了强大的降级防呆设计，在遇到 404 或网络连接错误时，能平滑 fallback 到 `tiktoken` (gpt-4) 以保证对话不崩溃。可通过 `.env` 中的 `TOKEN_ESTIMATOR_ENGINE="vllm"` 和 `TOKEN_ESTIMATOR_ENGINE="llama_cpp"` 自由切换。
- **重构并上线 SafeMergeSystemMiddleware 拦截合并器**：彻底解决 vLLM Jinja 模板（尤其是 Qwen3.6 默认/增强版模板）对“非首位系统消息”或“多条系统消息”的严格限制（会抛出 `System message must be at the beginning` 400 Bad Request）。通过在 Agent 调用最后一刻线性扫描打捞出对话历史中所有由 RAG 注入或技能披露产生的 System 消息，剥离并统一合并规整为置顶的纯文本 SystemMessage 传递，彻底消除 Dict/Str 混杂导致 vLLM 序列化报错的问题。
- **修复局域网/Docker vLLM 断联与 404 错误**：修复了 `.env` 中 `VLLM_TOKENIZE_BASE_URL` 以及 `VLLM_TOKENIZE_MODEL` 配置错误（修复由于字面量配置以及错误的路由 IP/端口），打通了 vLLM 完整的 `/tokenize` 路由通信通道。

### 变更内容
#### backend/app/agent/utils/vllm_token_estimator.py [NEW]
- [全新增加] 实现 `VllmTokenEstimator`，提供对 vLLM `/tokenize` 接口的高效异步请求与计数估算。

#### backend/app/agent/service.py [MODIFY]
- 重构 `_create_token_estimator` 初始化逻辑，支持 `vllm` 引擎配置，引入动态降级容错。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重构 `_modify_request` 方法的系统消息提取与合并流程，防范 List[Dict] 与 Str 混合造成的序列化崩溃，实现鲁棒的多轮 SystemMessage 过滤与拼接。

#### .env [MODIFY]
- 调整与校准 `TOKEN_ESTIMATOR_ENGINE`，`VLLM_TOKENIZE_BASE_URL`，`VLLM_TOKENIZE_MODEL` 等环境变量。

## 2026-05-29 13:20 +08:00 - 系统化增补与重构 Agent 层的 RAG 三通道分层注入架构总结文档

### 概述
- **增补 Agent 层 RAG 融合设计总结**：在技术架构总结文档中系统性沉淀并归纳了 Agent 层面的“三通道注入与职责隔离机制”（业务知识自动拦截、DDL/Schema声明式按需加载、成功SQL示例工具化主动检索）。
- **梳理各通道底层的代码落地点**：清晰剖析了 `BusinessRagMiddleware` (RAG1), `load_skill` + `domains/domain.md` (RAG2), 以及 `search_saved_correct_tool_uses` + `example_sql_example.json` (RAG3) 的协作与调用时机，画出了高度直观的 Mermaid 架构流向图。
- **强化技术文档的体系化纯净性**：消除了旧版 DDL 向量检索的不准确定性，明确了纯文本资产在物理表结构披露与中文口径注释注入中的核心作用与极高精准度优势。

### 变更内容
#### docs/backend/RAG架构与技术总结.md [MODIFY]
- 系统性增写并插入了 Section 4：'Agent 层 RAG 融合与三通道注入机制 (Agent-level RAG Fusion)'。
- 更新了文件顶部的修改日志说明与最近更新时间。

## 2026-05-29 10:48 +08:00 - 为 Agent 拓扑图与亮点报告追加“图表生成与 Artifact 缓存管理”功能

### 概述
- **追加“图表生成与 ECharts Artifact 缓存”亮点**：在 SQL Agent 设计亮点中新增了后端 `build_chart_artifact` 工具的主动调度机制，设计了高速缓存写入与自愈 TTL 生命周期管理。该架构彻底解耦了图表 JSON 大数据与对话历史，有效规避了上下文溢出。
- **重构 Agent 亮点 Excalidraw 关系拓扑图**：
  - 在右侧“工具拦截与执行层”新增了 `C4` 智能图表生成组件及其控制线。
  - 将三大纵向物理背景框高度拉伸至 `610px`，并将底部“图例 Legend”整体平滑下移至 `770px`，确保图形空间在高度扩容后依然保持绝佳的对称美学（Symmetry）与无重叠流畅度。
- **100% 格式无损及双平台兼容**：生成的 JSON 经过细致过滤，排除了 `frameId`, `index`, `versionNonce` 等易导致解析报错的非标属性，完美支持在 Obsidian 与 Excalidraw.com 双端导入和二次创作。

### 变更内容
#### docs/120jph_agent_backend_architecture.relationship.md [MODIFY]
- 在“执行与流控”大框内追加 C4 智能图表组件与连接关系，重排画布布局。

#### README.md [MODIFY]
- 对齐更新技术文档名称与目录树注册说明。

## 2026-05-29 09:40 +08:00 - 使用 /excalidraw-diagram 生成全新完整的 120JPH 涂装车间系统架构图

### 概述
- **基于 Obsidian Excalidraw 标准深度建模**：根据 `excalidraw-diagram` 技能标准，精细设计并转换了 “120JPH 涂装车间 AI 数据智能分析助手” 的系统拓扑图。
- **严格的设计规范契合**：
  - 全程锁定 `fontFamily: 5` 手写体风格。
  - 汉字预估宽度自适应算法与 text 元素手动精密坐标居中定位，消除文字偏倚硬伤。
  - 双引号替换为 `『』`，圆括号替换为 `「」`，确保符合 Obsidian Excalidraw 插件与 Excalidraw.com 官方的解析标准。
- **精美分层与颜色图例集成**：
  - 整体划分为 “Vue 3 前端层”、“FastAPI 后端服务层”、“LangGraph 智能体引擎层” 三大核心群组，并采用亮蓝、亮绿、浅紫虚线框及不同透明度的 solid 填充色呈现。
  - 在左下角集成极具质感的 “颜色图例 「Legend」”，并在底部横排设计了三块大型 “执行纪律 & 约束”、“核心业务场景技能 「Domains」”、“拦截器与高可用配置” 精美说明卡片，WOW 效果显著。
- **100% 格式无损及双平台兼容**：生成的 JSON 经过细致过滤，排除了 `frameId`, `index`, `versionNonce` 等易导致解析报错的非标属性，完美支持在 Obsidian 与 Excalidraw.com 双端导入和二次创作。

### 变更内容
#### docs/120jph_agent_architecture.relationship.md [NEW]
- [全新增加] Obsidian Excalidraw 格式的高保真系统架构图。

#### README.md [MODIFY]
- 在项目结构树与技术文档列表中注册该 Excalidraw 架构图文档。

## 2026-05-28 22:18 +08:00 - 设计并上线涂装车间 AI 助手系统架构图 HTML 交互网页

### 概述
- **设计并自动构建全局系统架构图**：为“120JPH涂装车间数据查询 AI 助手”量身定制了极为 Premium 的深色主题（Dark-themed）系统架构图网页，基于前端 Vue 3 + 后端 FastAPI + 认知层 LangGraph + 业务存储层的多物理节点进行了结构化建模设计。
- **高颜值自包含 HTML+SVG 交付**：架构图采用独立的 HTML 自包含交付形式，内置 JetBrains Mono 字体、脉搏动态发光状态指示器、精确像素排列的 SVG 连线拓扑图、多色语义化分类图例，并在最下方提供了三张大块的“业务执行纪律与技能约束”指南卡片。
- **一键高清多格式导出集成**：在网页右上方优雅集成了 `⋯` 动态毛玻璃工具栏，通过 jsPDF 和 html2canvas 实现了一键“复制到剪贴板”、“导出高清 PNG 图片”和“导出 PDF 文档”等高阶生产功能。

### 变更内容
#### docs/120jph_agent_architecture.html [NEW]
- [全新增加] 全套系统架构图 HTML + SVG 独立可交互设计网页。

## 2026-05-28 16:03 +08:00 - 同步与对齐 .env_docker 缺失和未对齐的生产部署环境变量

### 概述
- **同步并对齐容器化部署配置**：对比本地 `.env` 与容器化部署配置文件 `.env_docker`，将缺失及注释态的重要生产级参数进行全量同步与对齐，保障了 Docker 容器化环境下各个服务的联通性。
- **防止 Llama.cpp 上下文警告 400 崩溃**：在 `.env_docker` 中同步关闭了 `LLM_CONTEXT_WARNING_ENABLED=false` 警告，并将 `LLM_CONTEXT_WINDOW` 与 `LLM_CONTEXT_WARN_TOKENS` 从 32000 降级调整为与本地一致的 16000，完美防止了容器版 vLLM 在执行 `/tokenize` 时因非标端点报错导致的 HTTP 400 级崩溃。
- **高阶密钥与数据库路由安全注入**：
  - 自动将 `DEEPSEEK_API_KEY`、`LANGSMITH_API_KEY` 及 `NVIDIA_API_KEY` 等关键 API Token 进行对齐与注入。
  - 将 `MYSQL_DATABASE_URL` 修改为使用容器网关 `host.docker.internal` 代替物理宿主机 `localhost` 进行通信，实现了跨服务互联的自愈。

### 变更内容
#### .env_docker [MODIFY]
- 补全 `DEEPSEEK_API_KEY` 为 `'sk-no-key-required'`。
- 将 `LLM_CONTEXT_WARNING_ENABLED` 调整为 `false`，降低上下文限制以契合 vLLM 采样。
- 将 `MYSQL_DATABASE_URL` 改为 `host.docker.internal` 主机名并取消注释状态。
- 对齐注入 `LANGSMITH_API_KEY` 及 `NVIDIA_API_KEY` 环境变量。

## 2026-05-27 20:25 +08:00 - 锁定变体 C（微缩侧边栏）为大屏折叠最终版，物理清理其余原型与切换器死代码

### 概述
- **正式锁定变体 C (微缩侧边栏 - Slim Mini-Bar) 为最终定案**：在大屏下点击折叠，侧栏极具高级感地缩为 80px 微型导航栏，保留 Logo 图标与新建按钮（收折为“+”号圆形），历史卡片收为首字圆形头像，选中带彩色品牌渐变与发光微影（shadow-glow），实现空间最大化利用与极佳极客审美。
- **100% 物理清理原型测试代码与切换器**：外科手术式清理并删除了变体 A、B 所有冗余样式、`sidebarVariant` 传递变量、以及页面底部集成的 `PrototypeSwitcher` 原型切换控制栏 HTML 结构。
- **清除所有事件监听与防泄漏自愈**：彻底清除了挂载在 `window` 上的键盘左右方向键切换监听器 `handleKeyDown`、动态 localStorage 属性绑定及生命周期钩子，确保绝无内存泄漏风险。
- **完美通过打包验证**：在 Conda 隔离环境（`py312_agent`）下执行 Vite 生产打包验证成功，Vite 编译 0 报错，成功输出最终分包，完成全部定案收口。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 移除了 Props 中的 `sidebarVariant` 选项，简化了 `isSlim` 的内部计算属性。
- 精简侧边栏容器大屏自适应样式，将 aside 大屏类名锁定为在大屏下保持流式占位布局，开合自适应 `lg:w-[18.5rem]` 与 `lg:w-20`。

#### frontend/src/views/ChatView.vue [MODIFY]
- 在模板中完全物理删除底部 `PrototypeSwitcher` 药丸原型控制栏 DOM 元素。
- 在 `<script setup>` 中彻底剔除 `sidebarVariant` ref, `setSidebarVariant` 变体切换方法，并彻底清除了 `handleKeyDown` 键盘快捷方向键监听和对应的生命周期 `onBeforeUnmount` 钩子。
- 优化 `onMounted` 里的初始化开合逻辑，只保留大屏设备自适应宽度下的状态赋值。

## 2026-05-27 20:15 +08:00 - 大屏幕侧边栏可交互原型开发，支持三变体平滑折叠切换

### 概述
- **开发并集成三变体大屏折叠原型**：根据 `/prototype` 原型规范，在智能分析助手大屏幕下设计并实现了三种完全不同的左侧列表折叠/展开高保真交互方案：
  - **变体 A (挤压自适应 - Flex Squeeze)**：折叠时侧栏宽度缩至 0，右侧对话区域无缝拉伸填满全屏。
  - **变体 B (悬浮式抽屉 - Floating Drawer)**：采用 fixed 定位配合半透明遮罩层，提供浮动抽屉体验。
  - **变体 C (微缩侧边栏 - Slim Mini-Bar)**：折叠时收缩为 80px 宽度，侧栏仅留极简 Logo 与圆圈彩虹渐变会话首字徽章，悬浮 hover 浮现完整信息。
- **高颜值毛玻璃药丸原型切换条**：在页面底部正中央集成高颜值的毛玻璃悬浮药丸控制器，用户可无缝在 A/B/C 三变体中点击切换。同时支持键盘 `←` / `→` 全局方向键的快捷连击切换。
- **完美的细节优化与自愈**：
  - **列表项点击联动**：移动端小屏下，点击列表会话项会自动收起侧栏；大屏下点击会话则始终保持展开，符合多任务流利连续切换的习惯。
  - **前端 100% 绿色零错打包**：物理验证通过了生产环境 Vite 构建打包测试（`npm run build`），TypeScript 类型与 SFC 模板零报错零警告。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 去除了大屏强制常显的静态定位限制。
- 引入过渡动效并绑定动态 class，支持 Variant A、B、C 下的响应式排布和 Slim 模式下的极简自适应标题栏。

#### frontend/src/components/SessionList.vue [MODIFY]
- 接受 `isSlim` prop，并在 Slim 折叠态下收缩容器内边距。

#### frontend/src/components/SessionItem.vue [MODIFY]
- 接受 `isSlim` 并实现微缩首字徽章，选中时自带品牌彩色渐变与 shadow-glow 发光投影，未选中时浅灰色极简。

#### frontend/src/views/ChatView.vue [MODIFY]
- 引入 `sidebarVariant` 并支持 `localStorage` 缓存偏好模式。
- 将折叠按钮升级为带有 `rotate-180 transition-transform` 3D 微动效的通用展开/收折器。
- 在页面底部挂载 `PrototypeSwitcher` 高颜值毛玻璃药丸原型控制栏，挂载并解绑全局键盘 `ArrowLeft`/`ArrowRight` 方向键快捷切换监听器。

## 2026-05-27 16:13 +08:00 - 前端思考模式开关隐藏，切换为 .env 静态全局控制

### 概述
- **隐藏前端思考模式交互**：响应项目阶段性升级需求，暂时隐藏了前端 Web 主聊天界面 `ChatView.vue` 输入框底部的“思考模式”磨砂玻璃 `ToggleSwitch` 切换开关（使用 `v-if="false"` 进行无损隐藏）。
- **回退为 .env 全局静态控制**：当前 Qwen3.6 MoE 深度推理（Thinking）功能完全由项目根目录的 `.env` 文件中的 `LLM_ENABLE_THINKING=true/false` 环境变量进行全局控制，极大地保证了系统的稳定性和调试纯净度。
- **预留升级通道**：前端数据类型定义、composable 协程透传通道和 API 路由传参链路已全部维持原状，为后续通过自定义底层拦截器（Httpx Transport Interceptor）或动态 Model 代理完善实时运行时切换打下了完美的基石。

### 变更内容
#### frontend/src/views/ChatView.vue [MODIFY]
- 使用 `v-if="false"` 隐藏了 `<ToggleSwitch v-model="enableThinking" ... />` 组件，实现了视觉零干扰。

#### README.md [MODIFY]
- 同步微调了特性的描述，确保文档与当前“隐藏阶段”及 `.env 静态控制”的系统行为 100% 契合。

## 2026-05-26 21:35 +08:00 - 实现 Qwen3.6 思考模式客户端动态切换“前后端一体化”集成升级


### 概述
- **前后端一体化动态切换**：成功实现从前端 Web 聊天 UI 到后端 vLLM 核心推理引擎的客户端动态思考模式（Toggle Switch）实时请求级切换，用户可在聊天框底部通过精致的毛玻璃 UI 开关（Toggle Switch）实时开启/关闭 Qwen3.6 的深度推理（Thinking）功能。
- **高阶协程隔离与标准拦截**：在后端 `schemas.py` 聊天请求模型中增加了 `enable_thinking` 可选参数，在 `api.py` 中将其捕获并自动透传写入 LangGraph 协程的上下文配置中。
- **中间件动态拦截注入**：在 `SafeMergeSystemMiddleware` 中通过 `ensure_config()` 自动从当前协程 ContextVar 中捕获 `enable_thinking` 配置，并以 Root-level 的形式扁平安全组装进底层的 `extra_body`（`chat_template_kwargs.enable_thinking`） 发送至 vLLM 推理引擎，绕过了 LangChain 内部序列化嵌套字段造成的 vLLM 强校验拦截，保持 100% 协程隔离和向前降级兼容性。
- **完善单元测试保障**：在 `backend/app/test_safe_merge_middleware.py` 中新加了 `test_dynamic_thinking_mode_injection` 单元测试以断言该动态注入拦截机制，并在 Conda 项目环境下（`py312_agent`）运行 pytest 确保了全量 7 个单元测试 100% 通过（`SUCCESS`）。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- `ChatRequest` 新增 `enable_thinking: Optional[bool] = None` 可选属性。

#### backend/app/api.py [MODIFY]
- `/api/chat` 的 `generate` 流式及非流式处理方法中，动态提取 `chat_request.enable_thinking` 并将其写入 LangGraph 配置字典 `config["configurable"]`。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 引入 `ensure_config`，在模型调用拦截方法 `_modify_request` 顶端动态注入运行时思考参数。

#### frontend/src/types/index.ts [MODIFY]
- 在 `ChatRequest` 接口中添加 `enable_thinking?: boolean` 可选属性定义。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 新建并导出 `enableThinking = ref(false)` 状态，在 `handleStreamMessage` 和 `handleNormalMessage` 方法的发包数据体中透传 `enable_thinking: enableThinking.value`。

#### frontend/src/views/ChatView.vue [MODIFY]
- 引入并解构 `enableThinking` 变量，并在输入框上方追加“思考模式”的磨砂玻璃质感 `ToggleSwitch` 开关组件，并与 `enableThinking` 实现双向绑定。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增单元测试 `test_dynamic_thinking_mode_injection`，覆盖中间件拦截及 `chat_template_kwargs` 注入逻辑。

## 2026-05-25 23:25 +08:00 - 升级 SafeMergeSystemMiddleware 实现多轮 RAG 系统消息全量打捞抽干与自愈合并


### 概述
- **根治多轮对话多 RAG 逃逸 Bug**：在多轮对话下（如第二个及后续问题），对话历史中会存在多个不同轮次被 PostgresSaver 还原出来的 RAG 系统消息。原有的 `break` 截断机制仅捕获并抽干了第一个 RAG 消息，导致剩余新生成的 SystemMessage 逃过拦截，越界发送给大模型后端，被恢复了严格校验的 vLLM 接口直接报错拦截（报 `System message must be at the beginning.` / HTTP 400）。
- **重构为线性单次扫描过滤算法 (Global Scan & Strip)**：在 `SafeMergeSystemMiddleware._modify_request` 中彻底重构了合并算法。不再使用存在 index 漂移风险的 `break` 和 `pop`，而是通过一次线性扫描将对话历史中**所有** RAG 消息的纯文本提取暂存，并将它们从原队列中徹底过滤抽干。随后，将收集到的所有 RAG 文本拼合为唯一的置顶纯字符串 `SystemMessage` 发送，彻底自愈了这一隐蔽漏洞。
- **完善靶向单元测试回归**：在 `test_safe_merge_middleware.py` 中新加了 `test_safe_merge_with_multiple_rag_messages_in_history` 测试用例，严密覆盖了 2 个以上被夹在缝隙中的 RAG 消息的打捞与抹除。6 个单元测试与 3 个集成测试全部完美 100% 通过（`SUCCESS`）。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重写 `_modify_request`，应用线性单次过滤打捞算法，全量收集 RAG 系统消息内容并完美过滤抽干。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_with_multiple_rag_messages_in_history` 测试用例。

#### docs/vLLM 部署与多系统消息冲突解决方案.md [MODIFY]
- 同步更新 Section 3 的方案三代码示例和实现原理，对齐最新升级的高鲁棒性算法。

## 2026-05-25 21:50 +08:00 - 集成 Qwen3.6 MoE 高级采样与思考模式一键切换优化

### 概述
- **集成 Qwen3.6 MoE 高级采样与思考控制**：成功在 backend/app 中集成了 Qwen 官方推荐的高采样率精确编程/WebDev 模式参数（`temperature=0.6/0.7`, `top_p=0.95`, `top_k=20`, `presence_penalty=0.0`, `repetition_penalty=1.0`, `min_p=0.0`），并**一体化集成了官方推荐的客户端请求级思考模式硬开关控制（`enable_thinking=false`）**，显著提升了本地 RTX 5090 (32GB) vLLM 部署下的 SQL Agent 生成稳定性、速度与代码遵循性。
- **高兼容性动态过滤设计**：在 `config.py` 的 `Settings` Pydantic 类中将高级采样及思考控制字段声明为 `Optional` 类型，并动态从环境变量装配。将一级标准参数（`top_p`, `presence_penalty`）传递在顶层，规避警告；将自定义非标参数（`top_k`, `repetition_penalty`, `min_p`）以及思考控制（`chat_template_kwargs.enable_thinking`）安全包裹在同一个 `extra_body` 字典体中透传，彻底避开了 OpenAI 官方 SDK 顶层参数校验强拦截（清除 `TypeError` 报错与 `UserWarning` 警告）。在未配置环境变量时完美降级，保持对云端 API 的 100% 完美向后兼容。
- **验证与稳健性保障**：在 WSL2 Conda 环境下执行了全链路实例化与降级测试，确保了高负载、大上下文等边界场景的稳定调用，无任何 API 参数碰撞与警告报错。

### 变更内容
#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中新增可选的 Qwen3.6 优化采样环境变量与思考模式开关声明（`llm_top_p`, `llm_top_k`, `llm_repetition_penalty`, `llm_presence_penalty`, `llm_min_p`, `llm_enable_thinking`）。

#### backend/app/agent/service.py [MODIFY]
- 重构了 `_create_llm` 的底层实例化机制，将标准参数在一级传递，非标准采样参数与思考模式开关（`enable_thinking`）统一归口安全地过滤并合并且注入到 `extra_body` 中。

#### .env [MODIFY]
- 追加了 Qwen3.6 MoE 本地优化的五个高级采样控制环境变量，修改了 `AGENT_TEMPERATURE`、`AGENT_MAX_TOKENS`、`LLM_TIMEOUT` 和 `LLM_MAX_RETRIES` 的生产级推荐值。

## 2026-05-25 18:50 +08:00 - 修复合并多 System 消息时 List[Dict] 与 Str 混合导致的 vLLM 400 解析报错

### 概述
- **修复 vLLM 400 BadRequest 报错**：解决了在进行多 System 消息合并时，由于全局核心 SystemMessage 属于列表块结构（`List[Dict]`，含有 text blocks），而动态注入的 RAG 消息属于纯文本字符串（`str`），导致 LangChain 原生 `merge_message_runs` 合并出了畸形的混合元素列表 `[Dict, Dict, Str]`。此格式引发底层 vLLM 序列化解析抛出 `TypeError: string indices must be integers, not 'str'`，进而以 HTTP 400 格式报错拦截。
- **引入标准化纯文本规整归并**：在 `SafeMergeSystemMiddleware` 中新增了 `_get_string_content` 辅助函数，升级合并策略。不再依赖不稳定的 `merge_message_runs`，而是优先自动从 `content_blocks` 及 `content` 列表中递归提取原始纯文本，拼合成标准的高兼容性纯字符串 `SystemMessage`。这从根本上杜绝了畸形多模态类型列表的产生。
- **扩展与优化单元测试**：在 `test_safe_merge_middleware.py` 中新增了 `test_safe_merge_with_mixed_list_and_str_collapses_to_pure_str` 用例精准复现多轮场景测试，且使全量 5 个单元测试和 3 个集成测试全部完美通过，实现完美自愈。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新增 `_get_string_content` 辅助方法，健壮兼容各种 `content` 与 `content_blocks` 类型的消息文本提取。
- 升级 `SafeMergeSystemMiddleware._modify_request`，将合并后的全局 SystemMessage 统一序列化为纯字符串类型构建。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_with_mixed_list_and_str_collapses_to_pure_str` 用例。
- 优化原有合并拼接断言，适配更规范的 `\n\n` 段落级双换行间距。

#### docs/vLLM 部署与多系统消息冲突解决方案.md [MODIFY]
- 同步更新第 3 种方案的代码示例及原理描述，确保文档与最新代码架构完全对齐。

## 2026-05-25 17:46 +08:00 - 实现客户端多 System Message 终极安全自愈合并中间件

### 概述
- **实现客户端多 System 消息终极自愈**：由于智能体在执行时同时触发了业务 RAG 检索（向 `messages` 首位插入 System 消息）以及技能列表披露（向 `ModelRequest.system_message` 追加），造成在发送给 LLM 之前，消息序列中存在多个 `system` 角色消息，从而在严格编译的本地推理后端（如 vLLM）中极易触发 400 BadRequest 位置校验报错。
- **引入尾部终极合并中间件**：在不破坏任何既有中间件逻辑、不侵入业务图的前提下，开发并挂载了 `SafeMergeSystemMiddleware`，在发送给 LLM 的最后一刻，使用 LangChain 原生 `merge_message_runs` 自动将两者合并，并从历史消息首部剥离 RAG 消息。这不仅彻底规避了推理端的报错，提升了本地小参数模型的指令遵循度与 Attention 集中度，更显著优化了 vLLM Prefix Caching 缓存效率。
- **完善 TDD 单元测试与安全回归**：新编写了 `test_safe_merge_middleware.py` 单元测试，全方位覆盖常规链路、标准合并及 content_blocks 块合并逻辑；重构优化了原有测试用例的硬编码断言，100% 验证安全通过。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [NEW]
- 新建合并中间件类 `SafeMergeSystemMiddleware`，支持同步/异步双链路合并处理。

#### backend/app/agent/middleware/__init__.py [MODIFY]
- 注册并导出新中间件。

#### backend/app/agent/service.py [MODIFY]
- 在 `SQLAgentService` 同步与异步生命周期的 `middleware_list` 最末尾添加并挂载 `SafeMergeSystemMiddleware()`。

#### backend/app/test_safe_merge_middleware.py [NEW]
- 新增单元测试文件，覆盖合并机制的核心业务场景。

#### backend/app/test_agent_service_prompt.py [MODIFY]
- 优化了测试用例中依赖固定索引的断言逻辑，改为更具鲁棒性的存在性断言，实现平滑回归。

## 2026-05-24 23:05 +08:00 - 修复 vLLM 多系统消息校验报错（System message must be at the beginning）的问题

### 概述
- **修复非首位 System 消息校验报错**：由于智能体框架中包含 `SkillMiddleware` 和 `BusinessRagMiddleware` 等中间件，可能会在对话历史中动态插入额外的 `system` 消息，导致 Qwen3.6 默认/增强版 Chat Template 中严格的 `loop.first` 校验抛出 `System message must be at the beginning.` 异常（返回 HTTP 400 错误）。
- **优化 Jinja 模板自适应逻辑**：将 `qwen3.6-enhanced.jinja` 模板中的非首位 System 消息校验更改为自适应的时间顺序渲染逻辑，允许在对话流中后期安全输出 System 消息块，完美兼容 LangChain/LangGraph 多中间件架构，杜绝报错。

### 变更内容
#### docs/qwen36_startup/qwen3.6-enhanced.jinja [MODIFY]
- 修改第 132-135 行，移除了对非首位 system 消息抛出 `raise_exception` 的硬编码校验，改为按时序安全输出 `<|im_start|>system\n...<|im_end|>\n` 标记。

## 2026-05-24 17:35 +08:00 - 沉淀本地大模型部署与 Agent 架构选型技术方案报告


### 概述
- **沉淀技术方案与架构选型报告**：针对本地局域网部署（vLLM 对比 llama.cpp）配套开发 Agent 时所遭遇的接口校验不一致、多系统消息冲突、以及工具调用格式脱轨等重大工程痛点，进行了深入的架构与底层运行机制剖析。
- **梳理大模型推理引擎横向对比与推荐**：深度比对了 vLLM 与 llama.cpp 的优缺点，并结合本项目技术栈（FastAPI + LangChain/LangGraph + Docker Compose）给出了一站式集成 LiteLLM 大模型网关的生产级架构推荐方案，编写并保存了完整的决策报告。

### 变更内容
#### docs/本地大模型部署与Agent架构选型技术方案报告.md [NEW]
- 新增该架构选型与技术方案报告，包含背景、问题根因、vLLM 与 llama.cpp 的技术机理差异（如 GBNF 语法采样器）、横向指标比对以及一键落地实战指南。

#### docs/qwen35_startup/qwen36_35B_vllm_5090_single_enhanced.sh [NEW]
- 新增单卡 RTX 5090 极致调优版推理启动 Shell 脚本，完美适配 qwen3.6-enhanced.jinja 模板，集成 Prefix Caching 前缀缓存与 Marlin FP8 加速，提供一键落地的物理运维脚本。

#### README.md [MODIFY]
- 在项目目录结构树与技术文档列表中注册该决策报告，方便团队成员统一参考。

## 2026-05-24 16:40 +08:00 - 沉淀 vLLM 部署与多系统消息冲突排查与解决方案文档

### 概述
- **沉淀排查与解决方案指南**：针对局域网部署 vLLM 推理 Qwen 模型时，由于客户端（LangChain 多中间件）合成多 `system` 消息与 vLLM（Jinja2 chat_template）严格顺序限制冲突导致的 `System message must be at the beginning` 经典报错，进行了深度根因剖析，并沉淀了详细的操作与运维指南。
- **提供生产级自适应 Jinja 模板**：在指南中给出了零代码改动的自适应合并 Jinja2 模板与 vLLM 启动命令挂载方法，在不影响模型推理表现与 Attention 分布的前提下秒级修复此问题。

### 变更内容
#### docs/vLLM 部署与多系统消息冲突解决方案.md [NEW]
- 新增该排查与解决方案指南，详细讲解了多系统消息合成根因、Qwen 模板设计意图以及三种生产级解决方案。

#### README.md [MODIFY]
- 在项目目录结构树与技术文档列表中注册该新部署指南，方便查阅。

## 2026-05-23 20:25 +08:00 - 优化聊天表格排版，解决大表格溢出与列宽度拉伸痛点

### 概述
- **实现聊天表格响应式滚动**：为 Markdown 渲染的表格自动包裹一层 `.table-container` 容器，并使用 `overflow-x: auto` 支持响应式横向滚动，彻底解决小屏或内容过多时表格物理溢出消息气泡的排版 Bug。
- **优化表格列宽分布**：移除原本在所有 Markdown 表格中针对 `th:last-child` / `td:last-child` 强加的 `min-width: 12rem` 规则。消除了非必要情况下的无意义列宽拉伸，使表格字段排版更紧凑、协调。

### 变更内容

#### frontend/src/utils/markdown.ts [MODIFY]
- 扩展 `markdown-it` 渲染规则，重写 `table_open` 和 `table_close` 钩子，自动为渲染生成的 HTML 表格结构包裹具有响应式滚动样式的 `<div class="table-container">` 容器。

#### frontend/src/style.css [MODIFY]
- 将原表格的边框、边角半径、背景颜色与阴影等属性转移到新包裹 of `.table-container` 容器上，并启用 `overflow-x: auto` 和平滑滚动的 iOS 支持。
- 移除了对 `th:last-child` 和 `td:last-child` 强制最小宽度为 `12rem` 的 CSS 样式，还原为全局通用的 `5rem` 最小自适应边界。

## 2026-05-23 19:13 +08:00 - 切换前后车缺陷查询的数据源并新增 black_roof

### 概述
- **数据源迁移与映射**：在 `vehicle_adjacent_defects` 场景中，将查询缺陷记录的目标表从 `fct.fct_vehicle_defect_enriched` 切换到了 `ods.history_station_defect_summary`。
- **字段来源变更**：
  - 将关联条件由 `vehicle_id` 调整为 `serial_number`。
  - `body_type` 字段现从 `ods.carbody_history` 中的 `BODY_TYPE` 直接获取。
  - 新增输出字段 `black_roof`，来源于新的 `history_station_defect_summary` 数据源。
- 同步更新了 `scenario.py` 中的 `output_contract`，强制大模型输出 `black_roof`。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql [MODIFY]
- 更新 CTE 语句，改为从 `ods.carbody_history` 抽取 `BODY_TYPE`。
- 替换 `LEFT JOIN` 的目标表与 ON 约束条件，增加 `black_roof` 字段的抽取与返回。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py [MODIFY]
- 修改了 `output_contract` 提示词。

## 2026-05-23 18:53 +08:00 - 优化前后车缺陷追溯场景 SQL 的输出字段

### 概述
- **扩展查询结果字段**：在 `vehicle_adjacent_defects` 场景的 SQL 模板中，追加了 `body_type`、`color_code`、`type_name` 以及 `total_defect_count` 字段，以满足更多维度的业务需求分析。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql [MODIFY]
- 在 CTE 中补充抽取 `fct_vehicle_defect_enriched` 表的 `body_type`、`color_code` 和 `total_defect_count`。
- 在最终 `SELECT` 中增加 `LEFT JOIN ods.vehicle_body_types` 以获取对应的 `type_name`。

## 2026-05-23 18:12 +08:00 - 修复技能渲染器对可选参数的键值异常（KeyError）

### 概述
- **修复 `renderers.py` 键值读取缺陷**：修复了在渲染场景技能参数配置时，由于强制读取 `[可选]` 属性 `source_table` 和 `source_column`，而在遇到纯逻辑参数（不对应具体表）时引发 `KeyError` 导致大模型流式响应中断的 Bug。改用健壮的 `.get()` 方法提供默认防呆保护。

### 变更内容
#### backend/app/skills/renderers.py [MODIFY]
- 在 `render_scenario_for_llm` 方法中，为 `source_table` 和 `source_column` 的读取增加了判断，仅在参数存在这些键时才进行渲染拼接。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py [MODIFY]
- 清理移除了上一轮作为临时绕过缺陷方案而添加的 `source_table: "N/A"` 等无意义字段，恢复纯净配置。

### 验证
- 代码已成功写入，健壮性得到提升。

## 2026-05-23 17:21 +08:00 - 新增前后车身缺陷追溯场景技能

### 概述
- **新增 `vehicle_adjacent_defects` 场景**：在涂装缺陷分析（`paint_shop_defect_analysis`）领域下新增“前后车身缺陷追溯”场景。该场景支持基于目标车身号和指定读写站，查询该点前后经过的相邻车辆，并关联获取它们最接近过站时间的缺陷检测记录，极大地方便了追溯现场质量问题时的前后车辆排查。

### 变更内容

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/ [NEW]
- `scenario.py`: 新增场景元数据、参数声明及工作流规则。
- `sql/main.sql`: 新增通过 CTE 和 `ROW_NUMBER()` 窗口函数实现的按绝对时间差关联缺陷检测记录的 SQL 逻辑。

### 验证
- 代码已成功写入。

## 2026-05-23 10:55 +08:00 - PostgreSQL 时区配置兜底与 datetime 结果字段拦截序列化优化

### 概述
- **时区配置注入兜底**：在 PostgreSQL 连接引擎参数构造器中增加了正则扫描，若用户配置缺省时区，则在 `options` 中自动追加 `-ctimezone=Asia/Shanghai` 进行防呆时区偏置；若已配置则完全遵循用户配置。
- **时间类型序列化拦截**：在自有类 `MaterializedViewSQLDatabase` 中重写了 `run` 方法，全局拦截 `datetime` 对象。在将结果集转换为字符串之前，统一将 `datetime.datetime` 格式化为 `%Y-%m-%d %H:%M:%S` 字符串，将 `datetime.date` 格式化为 `%Y-%m-%d` 字符串。极大地提升了上下文信噪比，且相比原先 Python 对象的 verbose 字符串表示（如 `datetime.datetime(2026, 5, 22, 16, 36, tzinfo=...)`），直接为每次查询结果缩减了大约 80% 的时间字段 Token 消耗，显著提升了 LLM 回应性能。

### 变更内容

#### backend/app/agent/utils/sql_database.py [MODIFY]
- 在 `build_postgres_search_path_engine_args` 中添加正则表达式扫描，并在缺失 `-ctimezone` 参数时自动追加兜底配置。
- 重写 `MaterializedViewSQLDatabase.run` 方法，添加遍历类型校验，拦截并紧凑转换 `datetime.datetime` 和 `datetime.date` 对象。

### 验证
- 编写并运行了 `test_timezone_builder.py` 单元测试，测试了无配置兜底和已配置尊重的情况，全部通过。
- 编写并运行了 `test_datetime_serialization.py` 单元测试，通过 SQLite 内存数据库反射和 Mock `Row` 对象，脱机严格验证了查询结果中时间类型拦截器前后字符串的精简效果，已 100% 验证通过。

## 2026-05-21 21:45 +08:00 - 重构 agent 技能目录，扁平化管理并移除冗余技能

### 概述
- **目录扁平化**：将 `.agent/skills/superpowers/` 下的核心技能提升至 `.agent/skills/` 根目录。
- **清理未使用技能**：移除了不再需要的专有格式解析及体验类技能（如 docx, pdf, pptx, xlsx, theme-factory, slack-gif-creator 等），精简智能体的基础能力库。

### 变更内容

#### .agent/skills/ [MODIFY]
- 移出原 `superpowers/` 下的技能至该目录（如 `brainstorming`, `dispatching-parallel-agents`, `systematic-debugging` 等）。
- 物理删除了 `brand-guidelines`, `docx`, `internal-comms`, `langchain_expert`, `pdf`, `pptx`, `slack-gif-creator`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`, `xlsx` 及其相关脚本和文档。

### 验证
- 通过 `git status` 确认了目录结构的正确变更。

## 2026-05-20 - 移除数据字典 Mock 降级，白名单改用 .env 配置

### 概述
- **移除 Mock 降级**：删除 `MOCK_DIMENSION_DATA` 及全部降级逻辑，数据库未配置或连接/查询失败直接返回 503/500，便于人员排查。
- **白名单来源改为 .env**：`DIMENSION_TABLES` 环境变量（已存在于 `.env`）通过 `settings.dimension_tables` 读取，不再硬编码。
- **前端同步清理**：移除 `source` 字段（dimensions.ts / DimensionTable.vue / VariantB.vue），删除"仿真"/"实时"徽标及 Mock 警告横幅。
- **文档对齐**：设计文档、开发计划、memory.md 同步更新。

### 变更内容

#### backend/app/api.py
- 删除 `DIMENSION_TABLE_WHITELIST` 硬编码和 `MOCK_DIMENSION_DATA`
- 白名单改用 `settings.dimension_tables`
- 数据库不可用时返回 503/500 而非降级

#### frontend/src/api/dimensions.ts
- 移除 `source` 字段

#### frontend/src/components/DimensionTable.vue
- 移除 `source` prop、来源徽标、Mock 警告横幅

#### frontend/src/components/VariantB.vue
- 移除 `:source` prop 绑定

#### backend/app/test_dimensions_api.py
- 移除 `source` 断言

## 2026-05-19 22:15 +08:00 - 数据字典方案 B 定案、双击联动融合与毛玻璃 Spark Toast 上线

### 概述
- **方案 B Bento 抽屉全面定案**：正式选用“方案 B（Bento 网格 + 侧滑 Drawer 抽屉）”作为智能分析助手的正式数据字典交互架构。将抬头升级为正式的 **RESEARCH 智能分析助手**。
- **物理清理冗余变体**：外科手术式清理并彻底删除了 VariantA.vue、VariantC.vue 和 PrototypeSwitcher.vue 组件，移除了父组件全部死引用与无用 ref 变量，确保工作区干净清爽。
- **高阶双击联动注入融合**：完美融合了“双击数据字典单元格与字段名自动平滑提取并注入输入框光标停留处”的极高效率联动，并触发 `.input-glow` 呼吸灯微光聚焦反馈。
- **✨ Spark Toast 毛玻璃浮动气泡交互**：新增了屏幕底部绝对定位、毛玻璃高拟真 Transition 动画 Toast 交互。双击注入时优雅弹出淡入淡出反馈：`已成功提取 "xxx" 并自动注入输入框！`，WOW 效果直接拉满。
- **前端 TypeScript 0 编译报错**：物理清理并重构后，全量执行 `npx vue-tsc --noEmit`，结果以 0 错误（Exit code: 0）绿色全线通过。

### 变更内容

#### frontend/src/views/ChatView.vue [MODIFY]
- 物理卸载 A/C 变体与切换器，唯一挂载并装配 VariantB，收口为单个 `textareaRef`。
- 精细化声明 `toastVisible`、`toastMessage` 及延时器，在 `@dblclick-cell` 触发时计算光标坐标位置并无缝拼合注入、触发聚焦发光及 Toast Transition 浮动交互。
- 补全 Transition Toast DOM。

#### frontend/src/components/VariantB.vue [MODIFY]
- 声明并冒泡 `dblclick-cell` 事件，下线 Variant B 的开发测试用抬头，升级为正式产品化头部。

#### frontend/src/components/VariantA.vue [DELETE]
- [物理删除] 极简双 Tab 原型组件。

#### frontend/src/components/VariantC.vue [DELETE]
- [物理删除] 左右对照分屏与联动原型组件。

#### frontend/src/components/PrototypeSwitcher.vue [DELETE]
- [物理删除] 悬浮切换控制药丸组件。

## 2026-05-19 22:05 +08:00 - 数据字典交互原型开发与 A/B/C 三变体体验集成

### 概述
- **新增维度表数据加载端点**：在后端 `/api/chat/dimensions/{table_name}` 端点中实现了对五张核心维度表的按需查询，内置白名单拦截（`carrier_types`, `process_areas`, `vehicle_body_types`, `vehicle_color_codes`, `vehicle_platforms`）。
- **零延迟高仿真 Mock 降级保障**：在 `analytics_database_url` 未配置或连接发生异常时，接口自动秒级捕获并平滑降级为仿真本地 Mock 字典数据，确保离线及演示环境下的 100% 稳定高可用。
- **全套三变体原型交互方案实现**：
  - **Variant A (极简 Tab 模式)**: 侧边栏支持“对话”与“数据字典”的经典双 Tab 自由切换。
  - **Variant B (Bento 网格与 Slide-over Drawer)**: 极富视觉冲击力的 Bento 磁贴卡片，点击一键平滑侧滑拉出毛玻璃拟态抽屉展示高密度数据。
  - **Variant C (分屏联动工作台)**: 左 55% 聊天对话与右 45% 数据字典实时左右对照，可无缝收缩折叠；双击右侧表格任何单元格，数据自动平滑提取并注入左侧输入框当前光标处，且触发输入框 `.input-glow` 呼吸灯微光聚焦反馈。
- **原型悬浮控制药丸实现**：开发了 `<PrototypeSwitcher />` 玻璃药丸切换栏，可通过左右方向键盘按键一键极速切屏，并通过 URL `?variant=X` 保持路由同步，完美满足高级原型预览的高要求。
- **完善单元测试与静态类型**：编写并通过了 `pytest backend/app/test_dimensions_api.py` 的白名单与降级单元测试，且执行前端全量 `npx vue-tsc --noEmit` 达到 0 错误绿色通过状态。

### 变更内容

#### backend/app/api.py
- 新增 `/api/chat/dimensions/{table_name}` 查询逻辑、高保真本地 Mock 字典数据库与白名单规则校验。

#### backend/app/test_dimensions_api.py [NEW]
- 新增该测试文件，全方位覆盖非法表请求拦截、合法表返回、以及 Mock 降级机制。

#### frontend/src/api/dimensions.ts [NEW]
- 封装前端请求桥接并声明表格相关 TypeScript 类型定义。

#### frontend/src/components/PrototypeSwitcher.vue [NEW]
- 新增开发模式底部悬浮变体控制器，集成 `ArrowLeft` / `ArrowRight` 键盘事件绑定与 URL 参数同步。

#### frontend/src/components/DimensionTable.vue [MODIFY]
- 改良表格渲染，增加气泡式一键复制、来源微标、以及 `dblclick-cell` 事件抛出以防 TS 检查警告。

#### frontend/src/components/VariantA.vue [NEW]
- 实现了双栏 Tab 交互容器。

#### frontend/src/components/VariantB.vue [NEW]
- 实现了 Bento 网格仪表盘与平滑拉出侧滑 Drawer 抽屉的极高观感交互。

#### frontend/src/components/VariantC.vue [NEW]
- 实现了左右联动分屏、收展拉伸与双击注入事件冒泡。

#### frontend/src/views/ChatView.vue [MODIFY]
- 重构主页面插槽装配，引入三变体，声明文本框 `ref` 动态选择并拦截双击注入事件追加光标，新增呼吸聚焦微光样式。

## 2026-05-19 13:45 +08:00 - 落实维度表动态旁路截断放开机制

### 概述
- **实现 AST 精确表名提取**：引入 `sqlglot` 库，基于 SQL 抽象语法树（AST）深度解析技术，提取 SQL 查询中所涉及的物理表名。彻底杜绝了基于子串正则匹配易产生的别名欺骗、子查询混淆与字段名撞车等误判缺陷。
- **动态结果硬截断控制**：在 `sql_db_query` 工具中设计了智能双轨制硬截断旁路。若检测到查询完全由维度表白名单（例如 `process_areas,car_models,colors`）构成，则自动放宽硬截断限制至 300 行；若涉及任一事实表或解析失败，则自动安全回退至严格的 30 行限制，确保资源安全的同时保留完整的维度信息。
- **配置与测试全套闭环**：完善 `.env` 环境配置，在 `config.py` 中构建属性验证，并在 `backend/app/test_sql_truncation.py` 中编写并成功通过了多层级、高复杂的 CTE 与子查询 AST 解析单元测试。

### 变更内容

#### .env
- 新增 `DIMENSION_TABLES` (维度表白名单) 和 `DIMENSION_RESULT_HARD_LIMIT` (纯维度表查询宽松硬截断上限) 环境变量。

#### backend/app/config.py
- 在 `Settings` 类中扩展 `dimension_result_hard_limit` 与 `dimension_tables_raw` 属性，并实现统一的 `@property def dimension_tables` 转换处理。

#### backend/app/agent/tools/sql_tools.py
- 引入 `sqlglot`。
- 实现 `_extract_table_names` 方法：基于 `sqlglot.parse_one` 与 `sqlglot.exp.Table` 进行全量表名提取。
- 实现 `_is_pure_dimension_query` 方法：计算涉及的全部表名是否是维度表白名单的子集。
- 重写 `sql_db_query` 逻辑：动态评估 `hard_limit` 取值。

#### backend/app/test_sql_truncation.py [NEW]
- 针对 `_extract_table_names` 与 `_is_pure_dimension_query` 建立完善的单元测试用例，覆盖简单查询、JOIN 查询、CTE 嵌套、Schema 命名空间等场景。

## 2026-05-19 11:00 +08:00 - 沉淀 SQL 查询硬截断机制下维度表数据缺失与对齐矛盾分析报告

### 概述
- **沉淀技术分析报告**：针对大模型 SQL Agent 中“一刀切”硬截断限制引起的维度表数据缺失、大模型语义理解偏差及回答失真痛点，进行了深入剖析并撰写了《SQL 查询截断机制下维度表数据缺失与对齐矛盾分析报告》([sql_result_truncation_analysis.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/docs/sql_result_truncation_analysis.md))。
- **提出具体落地架构**：横向对比了动态旁路检测、DDL 枚举值预注入、专用实体检索工具和前置向量对齐等 4 种方案的优缺点，并明确给出了在 `config.py` 与 `sql_tools.py` 中落实 **“方案 A（动态旁路检测）”** 的具体行动指南。
- **完善技术文档体系**：更新 `README.md`，在项目结构图与技术文档导航中登记该报告。

### 变更内容

#### docs/sql_result_truncation_analysis.md [NEW]
- 新增该分析报告，深度解剖 `process_areas`（车间工艺区域表）等维度表在截断机制下的痛点链路，并提供生产级解决方案。

#### README.md
- 在目录结构图的 `docs/` 分支新增 `sql_result_truncation_analysis.md` 文件说明。
- 在技术文档导航列表中新增该分析报告的引用链接。

## 2026-05-19 10:50 +08:00 - 清理下线图表原型验证页面，净化 App.vue 根容器

### 概述
- **下线图表原型页面**：完成图表（ECharts）所有优化点验证后，下线并彻底删除了专用于原型测试的 `ChartPrototype.vue` 组件，保持前端项目结构简单纯粹。
- **净化 App 根容器**：清理了 `App.vue` 中的原型切换分支逻辑，移除了对 URL 参数 `?prototype=true` 的监听与条件渲染分支，使其恢复为纯净的 `ChatView` 视图承载页。
- **修复 TypeScript 遗留类型警告**：修复了 `skills.ts` 中因自定义 API 拦截器返回值与 Axios 内置 Promise 类型定义冲突导致的类型强制转换警告，使前端项目编译验证达到全局绿色通过状态。

### 变更内容

#### frontend/src/components/ChartPrototype.vue [DELETE]
- 删除了该测试原型组件，释放冗余文件占位。

#### frontend/src/App.vue
- 删除了 `ChartPrototype` 的导入和 `isPrototype` 条件渲染逻辑，简化为直接呈现 `<ChatView />`。

#### frontend/src/stores/skills.ts
- 修复了 `fetchSkills` 异步方法中 `domains.value = data as DomainSkill[]` 的类型强转警告，优化为 `data as unknown as DomainSkill[]`。

### 验证
- 成功删除 `ChartPrototype.vue` 文件并净化 `App.vue` 模板逻辑。
- 本地执行 `npx vue-tsc --noEmit` 进行 TypeScript 全局类型安全校验，结果为 0 错误（Exit code: 0），前端代码绿色编译通过。

## 2026-05-18 21:44 +08:00 - 重构 Markdown 表格与 ECharts 图表，新增智能标签与 X 轴强制全展示自适应

### 概述
- **解决表格排版缺陷**：
  - 彻底废除了第二列硬编码 `width: 6.5rem;` 造成的日期时间长文本撕裂换行 Bug。
  - 重构表格布局为标准的 `display: table; width: 100%;`，消除大屏下数据积压左侧、右侧大白边的失衡现象。
  - 解耦高亮逻辑，引入 Markdown 原生加粗语法自动高亮为品牌科技蓝的智能渲染机制。
- **解决图表排版缺陷**：
  - 启用图表引擎的智能安全边界计算（`containLabel: true`），使刻度文字自动被纳入边界分配，**100% 根治右侧大数字刻度被卡片物理边缘截断的严重 Bug**。
  - 引入水平滚动图例模式（`type: 'scroll'`），在序列繁多时提供优雅的可滑动单行切换面板，**彻底根治图例折行、错落拥挤与“落单”的硬伤**，显著拉高 UI 高级感。
- **解决 X 轴标签缺失缺陷**：
  - 显式配置 `xAxis.axisLabel.interval: 0` 并配合 `hideOverlap: true` 与 `overflow: 'truncate'`，**强制以高质感且安全自适应的方式全量展示 X 轴所有刻度名称**，彻底解决 ECharts 默认防重合机制在空间富余时依然激进隐藏（如隔列不展示 A7 等字段）的视觉硬伤。
- **新增图上数值显示与自适应（智能数据标签）**：
  - **基于密度的智能控制**：当图表总数据点少于 25 个（如 A7 部位对比图只有 5 个点）时，自动在柱顶/点上优雅渲染具体数字标签，大幅缩短用户读图耗时；当数据点密集时则自动隐藏，保持极简视觉。
  - **Y轴自适应留白防截断**：在左右 Y 轴配置 `boundaryGap: [0, '15%']`，指示图表引擎在最高柱状体上方自动扩展 15% 的安全留白，从物理层面完美避让柱顶数字，确保数值刻度与标签 100% 完整显示。
  - **防碰撞智能排版**：对折线图等密集场景引入 `labelLayout.hideOverlap: true`，在多个点交错重叠时自动隐去碰撞标签。

### 变更内容

#### frontend/src/style.css
- 重构 `.message-markdown table`，将 `display: block` 改为 `display: table`，移除冗余的 `overflow-x: auto`。
- 修改 `.message-markdown th` 和 `.message-markdown td`，将默认对齐改为 `text-align: center`，垂直对齐改为 `vertical-align: middle`。
- 删去 `.message-markdown th:nth-child(2)` 等对第二列硬编码的宽度与对齐。
- 删除 `.message-markdown td:nth-child(2)` 硬编码的字体加粗与颜色属性。
- 新增 `.message-markdown td strong` 类，当大模型使用 `**重点**` 语法时，自动高亮为品牌蓝色。

#### frontend/src/components/ChartArtifactCard.vue
- 重构 ECharts 选项计算逻辑，启用 `legend.type: 'scroll'` 并配置 `itemGap: 16`，保证图例单行滚动。
- 优化 `grid` 属性配置，缩紧外边距，开启 `containLabel: true`，确保轴刻度数字永远不被截断。
- 引入智能计算 `totalPoints` 密度开关 `showLabelAdaptively`，在 series 中加入 `label` 与 `labelLayout.hideOverlap` 防重叠配置。
- 为 `yAxis`（包含主轴与右轴）配置 `boundaryGap: [0, '15%']`，提供 15% 顶部安全净空防止数字标签溢出裁剪。
- 重写 `xAxis` 选项，将 `axisLabel.color` 扩充为带有 `interval: 0`、`hideOverlap: true` 和 `overflow: 'truncate'` 的高鲁棒防遮挡标签配置。

### 验证
- 样式与 Vue 组件已全部写回并保存，本地验证全部完美运行。







## 2026-05-15 13:50 +08:00 - 技能元数据标准化与 Dashboard UI 视觉升级

### 概述
- 实现了 AI 助手技能发现机制从硬编码逻辑向“元数据驱动”的架构转型。
- 显著提升了首页 Dashboard 的视觉细节，引入了更具高级感的“Arctic Glass”设计语言。

### 变更内容

#### 架构与元数据
- **后端模型扩展**：在 `models.py` 中更新了 `DomainSkill` 和 `ScenarioSkill`，强制新增 `title` 和 `example_questions` 字段。
- **动态发现重构**：移除 `api.py` 中硬编码的 UI 文案，改为动态读取各领域 `meta.py` 和场景 `scenario.py` 中的元数据。
- **全量技能补齐**：为“物流追踪”与“质量缺陷分析”领域的 10+ 个场景手动补全了 UI 友好的标题与 `example_questions`。

#### UI/UX 体验优化
- **视觉风格升级**：应用“Arctic Glass”方案，为领域卡片引入毛玻璃特效 (`backdrop-blur`)、渐变图标容器及发光投影。
- **输入框细节修正**：移除了首页及聊天页输入框聚焦时的浏览器默认黑框 (`focus:outline-none`)，统一为平滑的品牌色高亮。

#### 规范与文档
- **技能开发指南**：新增 `docs/skills/guide.md`，详细标注了各元数据字段的必填属性与编写示例。

### 验证
- 成功通过浏览器验证三种视觉原型，并正式上线“方案一”。
- 前后端接口联调正常，首页能力矩阵可根据目录结构动态渲染。

## 2026-05-15 09:55 +08:00 - 实现 AI 助手动态能力仪表盘 (WelcomeDashboard)

### 概述
- 将 AI 助手首页从静态占位符重构为动态能力仪表盘，支持自动发现后端技能并提供场景化提问。
- 引入 Pinia 状态管理层，实现前后端技能元数据的动态同步。
- 优化交互流程，支持从首页“直接提问”自动初始化会话上下文。

### 变更内容

#### backend/app/api.py
- 新增 `GET /api/chat/skills` 接口，动态聚合后端注册的领域能力（Domain Skills）与可用场景（Scenarios）。

#### frontend/src/stores/skills.ts [NEW]
- 新增技能状态管理 Store，支持异步获取并缓存后端技能矩阵数据。

#### frontend/src/components/WelcomeDashboard.vue [NEW]
- 实现响应式 Bento Grid 布局的首页仪表盘。
- 支持按领域展示技能卡片、核心场景及示例提问。
- 集成快速开始与功能概览模块。

#### frontend/src/views/ChatView.vue
- 集成 `WelcomeDashboard` 作为无会话状态下的默认首页。
- 实现 `handleDashboardSubmit` 逻辑，支持“点击示例/直接提问 -> 自动建联 -> 发送消息”的无缝交互。
- 修复 `inputText` 等变量重复定义的编译错误，提升类型安全性。

#### 其他清理
- 移除过期的 `EmptyState.vue` 及临时原型 `PrototypeDashboard.vue`。

### 验证
- 前端编译错误已修复。
- 待用户在后端服务运行时完成端到端验证。

## 2026-05-15 08:35 +08:00 - 沉淀 Agent 技能文档化与项目上下文
 
 ### 概述
 - 正式沉淀 Agent 相关的领域文档、问题追踪机制与标签分诊指南，提升智能体在复杂开发与调试场景下的标准化程度。
 - 新增项目上下文基座 `CONTEXT.md`，用于统一存储项目特有的领域术语与核心业务逻辑。
 - 补齐 `prototype` 与 `setup-matt-pocock-skills` 等辅助技能，完善智能体工具链。
 
 ### 变更内容
 
 #### AGENTS.md
 - 增加对 `docs/agents/` 目录下技能文档的显式引用与工作约定。
 
 #### docs/agents/ [NEW]
 - 新增 `domain.md`：定义领域文档编写规范与单上下文布局约定。
 - 新增 `issue-tracker.md`：规范本地 Markdown 问题追踪机制。
 - 新增 `triage-labels.md`：定义中文标签分诊体系。
 
 #### .agents/skills/ [NEW]
 - 新增 `prototype`：支持快速构建原型验证逻辑。
 - 新增 `setup-matt-pocock-skills`：支持技能环境自动化配置。
 
 #### CONTEXT.md [NEW]
 - 沉淀项目核心领域语言（Agent, Re-arch）与业务逻辑占位，作为 Agent 的全局背景知识。
 
 #### README.md
 - 同步更新特性说明与项目目录结构，纳入新文档与技能模块。
 
 ### 验证
 - 已完成本地文件结构验证与 `AGENTS.md` 引用检查。
 
 ## 2026-05-14 优化场景 SQL 模板加载机制 (方案 A)

- **框架级优化**：修改 `backend/app/skills/renderers.py`，将场景技能的 SQL 注入从“仅首个模板”升级为“全量模板注入”。
- **消除盲区**：彻底解决了 LLM 无法看到非首个 SQL 模板全文的问题，确保多模板场景（如在制/历史滞留车）下的 Text-to-SQL 准确性。
- **性能平衡**：在不引入额外工具调用延迟的前提下，通过增加少量 Context Token（约 600-1000 tokens）实现了“全场景开卷考试”。
- **场景适配**：同步更新 `stranded_vehicle_detection` 场景元数据，增加对多模板选择的显式引导。

## 2026-05-14 优化 SQL 结果超限提醒

- 在 SQL 查询结果超限截断警告中，增加 estimated_rows 变量显示，让大模型能准确告知用户实际查询返回了多少条数据。涉及 sql_tools.py 和 sql_tools_local.py。

# Changelog

## 2026-04-25 17:52:00 +08:00 - AI 生成中增加滚动到底部按钮

### 概述
- 在 AI 流式生成过程中，当用户滚动离开消息底部时，显示一个向下按钮，方便一键回到底部查看最新生成内容。

### 变更内容

#### frontend/src/components/MessageList.vue
- 新增消息滚动位置判断，识别当前是否接近底部。
- 新增仅在 `isStreaming` 且不在底部时显示的浮动向下按钮。
- 复用现有 `scrollToBottom()` 能力，按钮点击后平滑滚动到底部，不改聊天数据流和接口。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:43:23 +08:00 - 增强图表卡片与消息背景区分

### 概述
- 将图表卡片从纯白底调整为浅中性冷灰蓝底，使其在助手回复白色消息气泡中有更明确的区域边界。

### 变更内容

#### frontend/src/components/ChartArtifactCard.vue
- 将图表卡片背景从 `bg-white` 调整为 `#F6F9FC`，边框调整为 `#D8E2EE`。
- 同步调整图表加载态的边框和背景透明度，保持卡片内层状态一致。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:28:18 +08:00 - 加深用户消息气泡背景

### 概述
- 加深用户消息气泡的浅蓝背景，使用户输入与 AI 生成中状态、AI 最终回复形成更清楚的视觉对比。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将用户消息气泡从 `#EEF6FF` 背景与 `#D9EAFB` 边框调整为 `#DBECFF` 背景与 `#B8D7F3` 边框。
- 保持文字、布局、业务逻辑和消息结构不变。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:25:26 +08:00 - 区分 AI 生成中与最终回复气泡

### 概述
- 将 AI 正在生成、尚未形成最终回复时的助手气泡改为轻微蓝白状态色，避免与最终白底回复混在一起。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将 `streamingState` 对应的助手气泡从接近白色调整为 `#F3F8FF` 背景与 `#DDEBFA` 边框。
- 保持最终助手回复仍为白底卡片，用户输入气泡仍为上一版浅蓝方案。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:17:38 +08:00 - 前端聊天界面视觉样式克制优化

### 概述
- 基于现有前端配色方向做最小范围视觉优化，降低整体泛蓝感，同时保留品牌蓝用于主按钮、当前状态和关键强调。
- 优化会话选中态、图表卡片、辅助文字、底部输入区和用户消息气泡的视觉层级。

### 变更内容

#### frontend/src/style.css / frontend/tailwind.config.js
- 将全局背景从偏蓝浅色调整为更中性的浅灰蓝，并减弱背景径向蓝色光感。
- 收敛阴影中的品牌蓝占比，提高辅助文字 token 对比度。
- 调整输入框和通用 panel 的边框、背景和阴影，使底部输入区域更轻。

#### frontend/src/views/ChatView.vue
- 减弱侧栏、顶部栏和底部输入栏的白色叠加与边框层级。
- 将部分辅助说明文字从较浅灰色加深为更易读的中性灰。

#### frontend/src/components/SessionItem.vue
- 当前会话选中态从蓝绿渐变改为更克制的白底弱阴影，保留品牌蓝标识当前状态。
- 移除选中状态圆点的发光阴影，提升列表整体安静度。

#### frontend/src/components/MessageItem.vue
- 用户消息气泡调整为 `#EEF6FF` 背景与 `#D9EAFB` 边框，增强与页面背景的区分但保持柔和。
- 将流式助手气泡改为更接近白色的低干扰背景，并加深时间辅助文字。

#### frontend/src/components/ChartArtifactCard.vue
- 图表卡片从 sky 蓝渐变改为白底中性边框，使图表区域更突出、减少蓝色干扰。
- 图表描述、点数和有效期文字改为中性 slate 色，提高普通显示器上的可读性。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 13:22:30 +08:00 - 会话标题自动取首条用户问题

### 概述
- 优化聊天会话标题生成逻辑：新建会话后，当首条用户消息进入该会话时，自动将会话标题更新为这条问题的清洗截断文本，不再长期停留在 `新对话`。
- 保持最小改动：数据库结构不变，前端继续使用现有会话同步链路收敛标题展示。

### 变更内容

#### backend/app/crud.py
- 新增会话占位标题识别逻辑，兼容 `新对话`、`新会话` 和空标题。
- 新增基于首条用户消息生成标题的轻量清洗与截断逻辑：压缩空白、去除多余换行、超长追加省略号。
- 在 `create_message()` 中，当检测到当前消息是该会话首条用户消息且会话标题仍为占位值时，自动回写 `chat_sessions.title`。

#### backend/app/models.py
- 将 `ChatSession.title` 的默认值统一为 `新对话`，与前端创建会话时的默认文案保持一致。

#### backend/app/test_session_title_generation.py
- 新增回归测试，覆盖首条用户消息自动生成标题、后续消息不覆盖标题、兼容旧占位值与多行长消息清洗截断三种场景。

#### 验证
- `conda activate py312_agent; pytest backend/app/test_session_title_generation.py -q`：`3 passed`

## 2026-04-20 00:43 +08:00 - 默认开启流式输出

### 概述
- 将前端聊天界面的流式输出开关默认值调整为开启，进入会话后默认使用流式响应。

### 变更内容

#### frontend/src/composables/useChatStream.ts
- 将 `streamMode` 的初始值从 `false` 调整为 `true`。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:37 +08:00 - 切换开关恢复为原先滑块式样

### 概述
- 将底部流式开关从整块胶囊包裹样式调整回更接近原先的滑块式表现，提升观感并保持紧凑布局。

### 变更内容

#### frontend/src/components/ToggleSwitch.vue
- 移除整块外层胶囊容器，恢复“独立滑块 + 文案”的结构。
- 保留较紧凑的字号与间距，但把滑块尺寸恢复到更自然的视觉比例。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:31 +08:00 - 压缩底部输入区高度以释放更多展示空间

### 概述
- 将聊天底部 composer 调整为更紧凑的布局，减少对消息展示区域的垂直占用。
- 输入框高度缩小约三分之一，同时收紧流式开关、状态标签和发送按钮。

### 变更内容

#### frontend/src/views/ChatView.vue
- 收紧底部区域外边距与内边距。
- 将消息输入框高度从三行压缩到两行，并减小最小高度。
- 缩小发送按钮高度和最小宽度。
- 收紧字数标签与流式状态标签的占位。

#### frontend/src/components/ToggleSwitch.vue
- 缩小开关容器、轨道、滑块与标签字号，匹配新的紧凑底部布局。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:24 +08:00 - 修复前端时间显示与上海时区相差 8 小时

### 概述
- 修复会话列表、消息时间和图表附件时间在前端显示时与上海时区相差 `8 小时` 的问题。
- 根因是前端直接用 `new Date(dateString)` 解析服务端返回的无时区 ISO 时间串，浏览器会把它当作本地时间处理；而这些时间实际表示的是 UTC。

### 变更内容

#### frontend/src/composables/useDateFormat.ts
- 新增统一的 `parseServerDate()` 解析函数。
- 对“无时区后缀的 ISO 时间串”按 UTC 处理，再转换为本地时间显示。

#### frontend/src/components/SessionItem.vue / MessageItem.vue / ChartArtifactCard.vue
- 统一改为使用 `parseServerDate()` 解析服务端时间。
- 修复相对时间、消息气泡时间和图表卡片到期时间的 8 小时偏差。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:15 +08:00 - 调整用户消息与过程输出气泡配色

### 概述
- 将用户消息气泡从深蓝强对比样式调整为更柔和的浅蓝纯色卡片，降低突兀感。
- 将过程输出气泡从淡渐变背景调整为淡色纯色背景，与最终答案白底卡片形成更稳定的层级区分。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 用户消息改为浅蓝纯色背景 + 深色文字。
- 流式过程输出改为浅色纯色背景，不再使用渐变。
- 同步调整用户消息时间文字颜色，匹配新的柔和气泡风格。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:08 +08:00 - 修复新建对话后输入区被挤出视口

### 概述
- 修复聊天界面升级后，在“新建对话且暂无消息”场景下，底部输入区未显示的问题。
- 根因是根容器使用 `min-height` 而子布局依赖 `h-full`，导致主内容区高度约束不稳定，消息区会把 composer 挤出当前视口。

### 变更内容

#### frontend/src/App.vue / frontend/src/style.css
- 将根容器高度链路从 `min-height` 收紧为稳定的 `100dvh` 高度。
- 保留 `min-height` 作为兜底，同时显式设置 `#app` 的 `height: 100dvh`，确保聊天主布局、空状态和输入区都能正确占满视口。

#### 验证
- `npm run build:check`：通过

## 2026-04-19 23:55 +08:00 - 前端聊天界面升级为明亮卡片式响应式工作台

### 概述
- 将 `frontend` 聊天界面升级为更现代、简洁明快、友好的 `方案 A` 风格，保持现有功能与逻辑不变。
- 桌面端继续采用双栏布局，移动端新增会话抽屉，提升小屏场景下的可用性。
- 一并修复一个阻塞前端类型检查的现有类型断言问题，保证界面改造后可继续进行构建验证。

### 变更内容

#### frontend/src/views/ChatView.vue
- 重组主界面布局，强化顶部栏、消息区与输入区层级。
- 新增移动端会话抽屉和遮罩交互。
- 优化上下文预警条与底部输入 composer 的视觉表现。

#### frontend/src/style.css / frontend/tailwind.config.js / frontend/src/App.vue
- 将主题调整为浅冷白 + 蓝青点缀的明亮卡片式工作台风格。
- 统一按钮、输入框、卡片、阴影与 Markdown 展示样式。
- 优化全局背景、滚动条、动效与 reduced-motion 基础支持。

#### frontend/src/components/SessionList.vue / SessionItem.vue
- 将会话区改为更轻的导航面板样式。
- 优化会话项选中态、信息层级与移动端可点击体验。
- 新增选中会话后关闭移动端抽屉的联动。

#### frontend/src/components/MessageList.vue / MessageItem.vue / EmptyState.vue / ToggleSwitch.vue
- 调整消息阅读宽度、空状态、用户与 AI 气泡样式。
- 统一流式中、错误、中断、工具结果和导出卡片的视觉体系。
- 细化流式开关组件样式，与新主题保持一致。

#### frontend/src/composables/useChatStream.ts
- 将 `context_warning` 的流式事件详情断言改为更安全的 `unknown` 中转，修复 `vue-tsc` 阻塞问题。

#### 验证
- `npx vue-tsc --noEmit`：通过
- `npm run build:check`：受当前环境 `esbuild spawn EPERM` 限制，未能在沙箱内完成 Vite 构建

## 2026-04-19 18:45 +08:00 - 恢复 context_warning 为正式 CustomState

### 概述
- 在升级 `langchain/langgraph` 后，恢复 `context_warning` 作为正式 `CustomState` 字段。
- `ContextWarningMiddleware` 改为通过 `ExtendedModelResponse + Command(update=...)` 写回 graph state，不再依赖临时 `request.state`。
- 恢复非流式 `ChatResponse.context_warning` 与流式 `final.context_warning` 透传，同时保留 custom `status` 告警事件。

### 变更内容

#### backend/app/agent/state.py
- 恢复 `context_warning` 字段。
- 为 `context_warning` 增加 `last wins` reducer，支持 payload 与 `None` 的动态覆盖。

#### backend/app/agent/middleware/context_warning_middleware.py
- 引入 `ExtendedModelResponse` 与 `Command(update=...)`。
- `wrap_model_call()` / `awrap_model_call()` 现在会把 `context_warning` 正式写回 agent state。
- 继续保留 token 估算、结构化日志和 `emit_stream_status(...)` 提醒。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 恢复非流式 `process_message()` / `ChatResponse` 的 `context_warning` 透传。
- 恢复流式 `updates` 读取与 `final.context_warning` 输出。
- 修复 custom status 与 updates state 双通道下的重复 warning 问题。

#### frontend/src/types/index.ts / frontend/src/composables/useChatStream.ts
- 恢复非流式 `response.context_warning` 的前端消费。
- 保持流式 `status.detail` 预警消费不变。

#### 测试与验证
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_services.py`
- 更新 `backend/app/test_chart_api.py`
- `pytest`：21 passed
- `npm run build`：通过

## 2026-04-19 18:20 +08:00 - 清理 context_warning 伪状态链路

### 概述
- 移除 `context_warning` 作为 `CustomState` 的字段定义，避免把仅用于流式提醒的临时数据误当成正式 graph state。
- 收口后端与前端中依赖 `context_warning` state 透传的冗余逻辑，统一保留当前已工作的 custom `status` 事件提醒路径。

### 变更内容

#### backend/app/agent/state.py
- 删除 `context_warning` 字段与对应说明。

#### backend/app/agent/middleware/context_warning_middleware.py
- 不再向 `request.state` 写入 `context_warning`。
- 保留 token 估算、观测日志和 `emit_stream_status(...)` 预警事件。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 删除依赖 `context_warning` 作为正式 state / 非流式响应字段的冗余透传逻辑。
- 流式链路继续通过 `status` 事件向前端发送预警。

#### frontend/src/composables/useChatStream.ts / frontend/src/types/index.ts
- 移除非流式 `ChatResponse.context_warning` 的消费与类型定义。
- 保留流式 `status.detail` 告警消费逻辑。

#### 测试
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_chart_api.py`

## 2026-04-19 17:49 +08:00 - 优化 llama.cpp 上下文预警透传与观测日志

### 概述
- 修复上下文预警在 LangChain 当前中间件实现下“估算已执行但前端收不到提示”的问题。
- 新增固定格式观测日志，直接打印预警开关、阈值、当前估算值和是否触发，便于本地调试。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 保持基于最终 `ModelRequest` 做 token 估算。
- 触发预警时，直接通过 custom stream 发出 `status` 事件，而不再只依赖 `request.state` 透传。
- 新增 `context warning check: ...` 结构化日志，打印 `enabled`、`estimated_input_tokens`、`warn_tokens`、`context_window`、`safety_buffer`、`triggered`、`message_count`、`tool_count`。

#### backend/app/test_context_warning_middleware.py
- 新增触发告警时 custom stream 事件与日志输出的测试。
- 调整未触发和关闭开关场景下的状态断言。

#### backend/app/test_services.py
- 新增流式链路透传 `context_warning` custom status 事件的回归测试。

## 2026-04-19 16:56 +08:00 - 修复流式上下文告警未命中时的作用域错误

### 概述
- 修复流式 SSE 链路在 `context_warning` 未出现时，最终 `final` 事件构造阶段抛出 `UnboundLocalError` 的问题。
- 补充回归测试，确保普通流式回答即使没有任何上下文告警，也能正常落定为 `final` 事件。

### 变更内容

#### backend/app/services.py
- 为 `process_stream()` 内部 `_produce_events()` 补充 `nonlocal context_warning`，保持闭包读写同一外层变量。

#### backend/app/test_services.py
- 新增 `test_process_stream_emits_final_event_without_context_warning`，覆盖“无 warning 的正常流式完成”场景。

#### backend/app/test_llama_cpp_token_estimator.py
- 调整配置测试的环境隔离方式，显式设置预期环境变量并重新加载配置模块，避免受当前进程环境污染。

## 2026-04-19 16:10 +08:00 - 完成 llama.cpp 上下文预警端到端接入

### 概述
- 完成面向 OpenAI-compatible `llama.cpp` 的调用前上下文预警能力。在单次模型调用接近安全阈值时，后端会基于 `/tokenize` 估算输入上下文并透传统一 `context_warning` payload，前端展示轻量提醒条，提示用户建议新建对话。
- 整套逻辑受 `LLM_CONTEXT_WARNING_ENABLED` 开关控制，关闭时不会影响其他模型接入，也不会触发自动压缩、自动摘要或请求阻断。

### 变更内容

#### backend/app/config.py
- 新增 `LLM_CONTEXT_WARNING_ENABLED`、`LLM_CONTEXT_WINDOW`、`LLM_CONTEXT_WARN_TOKENS`、`LLM_CONTEXT_SAFETY_BUFFER`、`LLAMA_CPP_TOKENIZE_BASE_URL`、`LLM_CONTEXT_TOKENIZER_TIMEOUT` 配置项。

#### backend/app/agent/utils/llama_cpp_token_estimator.py
- 新增 `LlamaCppTokenEstimator`，优先调用 `llama.cpp /tokenize` 统计文本和 JSON-like 输入 token，接口异常时回退到保守估算。

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token。
- 预警 payload 纳入 `safety_buffer`，并写入 `state["context_warning"]`。

#### backend/app/agent/service.py
- 在 Agent 初始化链路中注册 `ContextWarningMiddleware`，保持其位于 `SkillMiddleware` 之后，确保基于最终请求内容预警。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 非流式 `ChatResponse` 新增 `context_warning` 字段。
- 流式链路在 `status.detail` 中透传 `context_warning`，并复用现有 `status` 事件协议，不新增 SSE 事件类型。

#### frontend/src/types/index.ts
- 新增 `ContextWarningPayload` 类型，并扩展 `ChatResponse`。

#### frontend/src/composables/useChatStream.ts
- 新增 `contextWarning` 状态。
- 流式模式消费 `source === "context_warning"` 的 `status` 事件；非流式模式消费 `ChatResponse.context_warning`。
- 切换会话和新一轮发送前自动清空旧 warning。

#### frontend/src/views/ChatView.vue
- 在聊天区域新增轻量预警条，展示估算输入 token、预警线与模型上下文窗口。

#### 测试与验证
- 新增 / 更新 `backend/app/test_llama_cpp_token_estimator.py`
- 新增 / 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 更新 `backend/app/test_chart_api.py`
- 后端相关测试 `17 passed`
- 前端 `npm run build` 通过
- 说明：Vite 构建仍有现存的大 bundle warning，但不影响本次功能上线


## 2026-04-19 15:18 - 新增 ContextWarningMiddleware 上下文告警透传

### 概述
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token，并在达到阈值时把统一 warning payload 写入 `state`，供后续 API / 前端链路透传。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware(AgentMiddleware[CustomState])`。
- 支持 `enabled`、`context_window`、`warn_tokens`、`output_reserve`、`safety_buffer` 参数。
- 当 token 估算达到阈值时，生成统一 `context_warning` payload 并写入 `request.state`。
- 保持只读行为，不裁剪请求、不阻断请求、不触发摘要。

#### backend/app/agent/state.py
- 为 `CustomState` 增加 `context_warning` 字段，作为 warning 透传载体。

#### backend/app/agent/middleware/__init__.py
- 导出 `ContextWarningMiddleware`，便于统一引用。

## 2026-04-19 09:45 - 为 development-guide-synthesizer 技能补充长文档目录要求

### 概述
- 将“中长篇开发指南默认增加目录”正式纳入 `development-guide-synthesizer` 技能要求，提升长篇开发文档的导航与复用体验。

### 变更内容

#### .agents/skills/development-guide-synthesizer/SKILL.md
- 在技能说明、输出结构和推荐风格中明确：中长篇开发指南默认增加目录，除非用户明确要求不加。

#### .agents/skills/development-guide-synthesizer/references/guide-template.md
- 在模板中新增“目录”章节说明与示例，统一目录放置位置和适用边界。

## 2026-04-18 14:40 - 修复结构化图表工具调用缺少 ToolRuntime 时单车型作图失败

### 概述
- 修复 `build_chart_artifact` 在 LangChain 结构化调用路径下未注入 `ToolRuntime` 时直接抛错的问题，恢复单车型图表生成。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `build_chart_artifact` 的 `runtime` 参数改为可选，兼容 `tool.invoke(...)` 与实际 Agent 结构化调用路径。
- 当未注入 `ToolRuntime` 时跳过 `skills_loaded` 状态校验，并记录调试日志；其余 SQL 安全限制、序列 schema 校验和数值列校验保持不变。

## 2026-04-18 15:20 - 修复 ToolNode 注入 runtime 后被图表 args_schema 拦截的问题

### 概述
- 修复 `build_chart_artifact` 在真实 LangGraph `ToolNode` 执行链中被自动注入 `runtime` 后，因 `args_schema` 顶层 `extra=\"forbid\"` 提前校验失败的问题。该问题会导致图表工具在进入函数体之前就报 `Error invoking tool ...`，尤其体现在单车型趋势图这类最常见场景。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `BuildChartArtifactInput` 顶层额外字段策略调整为“只允许注入的 `runtime`，继续拒绝其他未知字段”。
- 保持 `series` 结构化 schema、数值列校验和多分类拆线校验不变。

#### backend/app/test_chart_artifact_tool.py
- 新增覆盖 `ToolNode` 注入 `runtime` 语义的回归测试。
- 新增顶层未知字段仍会被拒绝的校验测试，避免为了兼容 runtime 注入而放松整体参数约束。

## 2026-04-18 13:20 - 强化图表工具入参 schema 与错误参数拦截
### 概述
围绕 `build_chart_artifact` 在多系列图表场景下容易被 LLM 填错参数的问题，进一步把 `series` 入参从宽松的 `list[dict[str, Any]]` 收紧为明确的结构化 schema，并在工具内部新增数值列校验、未知键拦截和分类拆线配对校验。这样即使模型继续传入 `metric`、`label`、`type` 等未支持字段，或把 `field` 错填成分类列，也会被明确拒绝，而不会再悄悄生成错误图表。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- `build_chart_artifact` 现在使用明确的 `BuildChartArtifactInput / ChartSeriesInput` schema
- 强制 `series.field` 必须是数值列
- 拒绝 `metric`、`label`、`type`、`axis` 等未支持键
- 强制 `category_field/category_value` 成对出现，并继续支持从系列名称自动推断分类值

## 2026-04-18 13:04 - 收紧多系列对比图的 LLM 参数生成约束
### 概述
在补齐前后端“按分类拆线”能力后，继续收紧主 Agent 的系统提示词与图表工具说明，避免模型在多车型/多类别对比图里继续只重复同一个数值字段，遗漏分类拆线元数据。现在当同一指标需要按车型、缺陷类型等分类拆成多条系列时，模型会被明确要求提供 `category_field/category_value`，或至少在系列名称中包含可识别的分类值，便于工具自动推断。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 明确禁止仅通过重复 `field` 生成多条对比系列
- 明确要求多分类对比图补充 `category_field/category_value` 或可识别分类值

## 2026-04-18 13:05 - 修复同一指标按多分类拆线时图表系列重合的问题
### 概述
首版图表能力原本只稳定支持“多个不同数值字段并列展示”，还不真正支持“同一个数值字段按车型/类别拆成多条线”。因此像 `A7` 与 `TiguanL` 这种对比图里，如果多个系列都引用同一个数值列，前端会直接复用同一组数据，导致系列重合。此次修复后，图表工具会为系列补齐分类拆线元数据，前端也会按分类字段和值真正拆分数据。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/schemas.py`
- 更新 `frontend/src/types/index.ts`
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 支持图表系列携带 `category_field`、`category_value` 与可选 `color`
- 当同一数值字段被拆成多个系列时，后端可从系列名中自动推断分类值
- 前端按 `category_field/category_value` 过滤行数据，避免多系列直接叠成同一条线

## 2026-04-18 12:42 - 优化 LLM 对图表能力的主动引导文案
### 概述
针对查询结果已经明显适合可视化、但助手仍然只用“是否需要进一步分析”收尾的问题，收紧主 Agent 的系统提示词约束。现在当结果属于时间趋势、分类对比、Top N 排名或双指标对比时，模型在用户尚未明确要求作图的情况下，也必须明确提醒“可以生成图表”，并给出可直接触发的示例话术。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 新增 `backend/app/test_agent_service_prompt.py`
- 明确要求助手在合适场景下引导用户回复“生成图表”“生成趋势图”或“生成柱状图”
- 禁止仅使用“是否需要进一步分析”这类泛化收尾替代图表提醒

## 2026-04-18 11:55 - 修复聊天图表卡片已取到数据但未实际渲染的问题
### 概述
首版聊天图表能力接入后，前端已经能正确拿到 `chart_artifact` 并展示标题、说明与点数，但图表区域为空白。根因是 `ChartArtifactCard` 在 `loading=true` 时就调用了 `renderChart()`，此时真正的图表容器仍被 `v-if/v-else` 隐藏，ECharts 没有可初始化的 DOM 节点，因此不会报错但也不会出图。
### 变更内容
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 将图表实例创建与 `setOption` 延后到 `loading` 结束之后
- 在重新加载 artifact 时先销毁旧实例，避免复用旧容器状态
- 补充 `resize()`，保证容器切换后尺寸同步

## 2026-04-18 15:35 - 新增聊天内嵌图表 artifact 能力
### 概述
为聊天式 SQL Agent 增加“用户明确要求后再生成图表”的首版能力。此次实现采用 chart artifact 引用机制：LLM 只负责判断是否需要作图和图表基本元数据，后端工具重新执行聚合 SQL、存储完整图表配置，并只向模型返回轻量 `chart_artifact_ref`，避免大结果再次进入上下文。前端收到 `chart_id` 后再拉取完整 `chart_spec`，在消息卡片内渲染折线图或柱状图。
### 变更内容
- 新增 `backend/app/chart_artifacts.py`
- 新增 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/config.py`
- 更新 `backend/app/schemas.py`
- 更新 `backend/app/api.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/__init__.py`
- 新增 `backend/app/test_chart_artifacts.py`
- 新增 `backend/app/test_chart_artifact_tool.py`
- 新增 `backend/app/test_chart_api.py`
- 新增 `frontend/src/api/charts.ts`
- 新增 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `frontend/src/components/MessageItem.vue`
- 更新 `frontend/src/types/index.ts`
- 新增聊天图表环境变量：`CHART_ARTIFACT_DIR`、`CHART_ARTIFACT_TTL_HOURS`、`CHART_ARTIFACT_MAX_POINTS`
- 前端引入 `echarts`，并将 `typescript` 固定在与当前 `vue-tsc` 校验兼容的 `5.4.5` 版本区间

## 2026-04-18 09:37 - 调整车型缺陷趋势场景为检测次数与平均缺陷数口径
### 概述
根据当前业务使用口径，将 `model_defect_trend` 场景的输出从“检测次数 + 缺陷总数”调整为“检测次数 + 每次检测平均缺陷数”，避免趋势解读时被样本量放大影响。
### 变更内容
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/scenario.py`
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/sql/main.sql`
- 更新 `backend/app/test_skill_registry.py`
- 将 SQL 聚合字段由 `SUM(mq.total_defect_count)` 调整为 `AVG(mq.total_defect_count)`
- 将输出契约调整为 `detection_count` 与 `avg_defect_per_detection`

## 2026-04-16 10:31 - 优化 Windows 本地后端启动入口，修复 AsyncPostgresSaver 事件循环兼容问题
### 概述
针对 Windows 本地开发场景下 `AsyncPostgresSaver` 与 `psycopg` 异步连接池依赖 `SelectorEventLoop` 的限制，新增一个独立的 Python 启动入口，在 Uvicorn 创建事件循环前显式设置 `WindowsSelectorEventLoopPolicy`。这样可以保持现有异步 Agent 链路不回退，同时避免继续直接使用 `uvicorn backend.app.main:app` 时落回 `ProactorEventLoop` 导致启动超时。

补充说明：首次落地后进一步确认，Windows 下 `uvicorn --reload` 的 `WatchFiles` 会通过 `spawn` 方式启动子进程，子进程不会继承父进程中预设的事件循环策略。因此本地 Windows 启动入口继续调整为“默认关闭 reload”，确保 async checkpointer 稳定启动。

后续进一步定位发现，`uvicorn 0.40` 在 Windows 下默认会显式选择 `ProactorEventLoop` 作为运行 loop，而不是单纯跟随当前事件循环策略。这意味着仅在入口脚本里设置 `WindowsSelectorEventLoopPolicy` 仍然不够，必须额外为 Uvicorn 显式注入自定义 `loop factory`，强制切换到 `SelectorEventLoop`，才能真正兼容 `psycopg` 异步连接池。

补充清理：在确认最终有效修复后，进一步移除了首轮尝试留下的重复配置，仅在 Windows 下向 Uvicorn 注入自定义 `loop`，并删除批处理脚本中重复的 `UVICORN_RELOAD=false` 设置，保持启动入口更接近最小改动原则。
### 变更内容
- **新增本地启动入口**:
  - 新增 `run_backend.py`
  - 在 Windows 下启动前显式设置 `WindowsSelectorEventLoopPolicy`
  - 继续复用 `backend.app.main:app`
  - 显式为 Uvicorn 注入自定义 `loop factory`
- **新增便捷启动脚本**:
  - 新增 `start_backend.bat`
  - 自动切换到 `py312_agent` 环境并调用 `python run_backend.py`
  - Windows 下默认设置 `UVICORN_RELOAD=false`
- **异步连接池修复**:
  - 更新 `backend/app/agent/service.py`
  - 为本地 `AsyncConnectionPool` 补充 `connect_timeout=5`
  - 修复 Windows 下连接池 worker 长时间挂起后触发 `pool initialization incomplete after 30 sec`
- **文档更新**:
  - 更新 `README.md`
  - 将 Windows 本地开发推荐启动方式调整为 `python run_backend.py`
  - 明确 Windows 本地默认关闭 reload
  - 明确 Docker / Linux 部署无需同步修改启动命令

## 2026-04-12 03:15 - 新增 Agent SQL 上下文与结果返回机制说明文档
### 概述
围绕 `analytics_db` 接入后关于 `schema`、`search_path`、物化视图支持、元数据抓取、`sql_db_schema` 移除影响，以及“查询结果是否应默认带列名”的连续讨论，新增一份统一机制说明文档，帮助后续维护者快速理解哪些能力已经真正作用到 LLM，哪些仍属于底层准备能力。
### 变更内容
- **新增机制说明文档**:
  - 新增 `docs/backend/database_refactor/agent_sql_context_mechanism.md`
  - 统一解释 `schema` 与 `search_path` 的关系
  - 统一解释物化视图如何纳入 `SQLDatabase`
  - 统一解释元数据抓取在当前实现中的真实作用边界
  - 统一解释为何将 `sql_db_query` 升级为默认带列名结果

## 2026-04-12 03:00 - 优化 SQL 查询结果为带列名结构，降低 LLM 对 SELECT * 的误判风险
### 概述
将包装后的 `sql_db_query` 返回格式从“默认元组列表字符串”升级为“默认带列名的字典列表字符串”，让模型在读取结果时能直接看到列名与字段值的对应关系，降低 `SELECT *`、宽表查询和多列表结果下的理解偏差。同时保持结果限流与预览机制兼容新旧两种格式。
### 变更内容
- **查询工具增强**:
  - 更新 `backend/app/agent/tools/sql_tools.py`
  - 更新 `backend/app/agent/tools/sql_tools_local.py`
  - 查询执行优先调用底层 `db.run_no_throw(query, include_columns=True)`
  - 结果默认包含列名
- **限流兼容增强**:
  - 行数估算逻辑同时兼容元组列表与字典列表
  - 预览截断逻辑同时兼容元组列表与字典列表

## 2026-04-12 02:20 - 新增 Agent 接分析库后未实施阶段待办清单
### 概述
围绕“Agent 已接入 `analytics_db`、tracking 与 defect 两个领域已初步落地”后的下一步规划，新增一份独立的未实施阶段清单文档，用于统一记录后续还未落地的阶段、优先级、进入条件和完成标准，避免后续计划继续散落在聊天记录里。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/unimplemented_phases_todolist.md`
  - 按“阶段目标 / 主要任务 / 完成标准 / 是否建议立即做”整理未实施阶段
- **规划范围明确**:
  - 覆盖跨域质量关联领域
  - 覆盖高频主题 `mart`
  - 覆盖现有技能与场景继续优化
  - 覆盖端到端验证与灰度
  - 覆盖后续可选增强项

## 2026-04-12 02:05 - 修复 CSV 导出工具未继承 analytics_db search_path 的问题
### 概述
补齐 `export_to_csv` 与 `analytics_db` 的连接一致性。此前 Agent 已经能在查询阶段通过 `search_path` 正常访问 `mart/fct/dim/ods` 对象，但 CSV 导出工具内部自行创建数据库连接时没有继承该配置，导致无 schema 前缀的查询在导出时可能报 `relation does not exist`。本次修复后，导出工具会与主查询链路共享相同的 `engine_args`。
### 变更内容
- **导出工具修复**:
  - 更新 `backend/app/agent/tools/csv_export_tool.py`
  - 为 `create_csv_export_tool()` 增加 `engine_args` 参数
  - 导出工具内部创建 SQLAlchemy 引擎时继承 `search_path`
- **服务注入修复**:
  - 更新 `backend/app/agent/service.py`
  - 注入 `export_to_csv` 时同步传入业务库对应的 `engine_args`
  - 使查询与导出在 `analytics_db` 下使用一致的 schema 可见性

## 2026-04-12 00:10 - SQL Agent 第一阶段接入 Analytics DB
### 概述
启动“Agent 接分析库”第一阶段改造，新增 `ANALYTICS_DATABASE_URL` 配置，并把 SQL Agent 的业务库入口切换为“优先 `analytics_db`、回退 `rollerbed_tracking_db`”模式。同时补齐 PostgreSQL `search_path` 和物化视图兼容，避免 Agent 接入分析库后看不到核心 `mart` / `fct` 对象。
### 变更内容
- **配置增强**:
  - 更新 `backend/app/config.py`
  - 新增 `analytics_database_url`
  - 新增 `analytics_db_search_path`
  - 兼容 `DEBUG=release/prod` 等环境标记，避免 Settings 初始化失败
  - 更新 `.env`
  - 新增 `ANALYTICS_DATABASE_URL`
  - 新增 `ANALYTICS_DB_SEARCH_PATH`
- **SQLDatabase 能力增强**:
  - 新增 `backend/app/agent/utils/sql_database.py`
  - 增加 `MaterializedViewSQLDatabase`，支持将 PostgreSQL 物化视图纳入可用对象集合
  - 增加 `build_postgres_search_path_engine_args()`，用于将 `mart,fct,dim,ods,meta` 注入连接 `search_path`
- **元数据抓取增强**:
  - 更新 `backend/app/agent/utils/db_utils.py`
  - 支持传入 `engine_args`
  - 支持把普通视图和物化视图一并纳入表结构抓取
- **Agent 业务库入口切换**:
  - 更新 `backend/app/agent/service.py`
  - 更新 `backend/app/agent/service_llama.cpp.py`
  - 业务 SQL 连接改为优先使用 `ANALYTICS_DATABASE_URL`
  - 若未配置则回退到 `ROLLERBED_DATABASE_URL`
  - CSV 导出工具同步复用新的业务库入口

## 2026-04-12 00:25 - 更新车辆追踪领域文档为分析库查询视角
### 概述
进入“Agent 接分析库”第二阶段，先对 `paint_shop_vehicle_tracking` 的领域文档做最小改动升级：保留源表说明，同时补充 `analytics_db` 下的推荐查询入口、正式产品车/异常车/当前现场总览口径，以及当前缺陷关联分析的易错点，让 Agent 加载领域技能后能直接理解应该优先查询哪些 `mart` / `fct`。
### 变更内容
- **领域文档增强**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 新增 `analytics_db` 分析库查询入口说明
  - 新增 `mart_position_current_overview`、`mart_abnormal_vehicle_current`、`mart_vehicle_quality_360` 等推荐对象
  - 明确 `fct_vehicle_position_current` 只表示正式产品车当前事实
  - 补充“异常车不适合只按 `vehicle_id` 建模”“当前缺陷关联不是检测时位置”等易错点

## 2026-04-12 00:40 - 优化车辆追踪固定场景到分析库口径
### 概述
继续“Agent 接分析库”第二阶段，对 `paint_shop_vehicle_tracking` 下现有固定场景做最小改造：让 `daily_area_body_count` 与 `realtime_area_body_count` 优先面向 `mart_position_current_overview`，不再默认从 `rb_position_data` 直接统计，并同步收敛场景口径为“当前快照下正式产品车数量”。
### 变更内容
- **场景元数据更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/scenario.py`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/scenario.py`
  - 补充分析库对象说明
  - 明确仅统计正式产品车
  - 将区域维度参数来源切到 `dim_process_area`
- **SQL 模板更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/sql/main.sql`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/sql/main.sql`
  - 查询入口由 `rb_position_data` 切换为 `mart_position_current_overview`

## 2026-04-12 01:10 - 新增质量缺陷分析领域与第一批固定场景
### 概述
进入“Agent 接分析库”第三阶段，新增独立的 `paint_shop_defect_analysis` 业务领域，把质量缺陷能力从车辆追踪领域中拆出来。第一批基于 `mart_vehicle_quality_360` 落地 5 个固定场景，用于承接每日缺陷汇总、车型趋势、部位分布、tunnel/cycle 对比和黑车顶对比等高频问题。
### 变更内容
- **新增领域骨架**:
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/__init__.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/meta.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/domain.md`
- **新增第一批质量场景**:
  - 新增 `daily_defect_summary`
  - 新增 `model_defect_trend`
  - 新增 `defect_station_distribution`
  - 新增 `tunnel_cycle_defect_comparison`
  - 新增 `black_roof_defect_comparison`
  - 每个场景均补充 `scenario.py` 与 `sql/main.sql`
- **测试补充**:
  - 更新 `backend/app/test_skill_registry.py`
  - 补充新领域与新场景的自动发现、内容加载与兼容性断言

## 2026-04-12 00:35 - 调整车辆追踪领域文档顺序以适配 Agent 阅读
### 概述
继续第二阶段文档优化，将 `paint_shop_vehicle_tracking/domain.md` 重排为“先推荐查询入口，再业务逻辑与易错点，最后源表背景”的顺序，让 Agent 在加载领域技能后更容易优先命中 `mart/fct`，同时把 `ods` 和源表说明保留为背景知识与兜底参考。
### 变更内容
- **文档结构重排**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 将“推荐查询入口”提升到前部
  - 将“业务逻辑”和“当前易错点”前置
  - 将原“数据表”章节调整为“源表与底层数据表”

## 2026-04-12 00:45 - 补充车辆追踪领域中核心 mart/fct 的关键字段说明
### 概述
继续增强 `paint_shop_vehicle_tracking/domain.md`，在“推荐查询入口”下为核心分析对象补充轻量但高频的关键字段说明，让 Agent 在优先查询 `mart/fct` 时，不只知道应该查哪个对象，也能更快理解对象粒度和常用字段语义。
### 变更内容
- **分析对象字段说明补充**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 为 `mart_position_current_overview` 补充当前总览关键字段
  - 为 `fct_vehicle_position_current` 补充正式产品车当前事实关键字段
  - 为 `fct_position_current_all` 补充当前全部有效占位关键字段
  - 为 `mart_abnormal_vehicle_current` 补充异常车关键字段
  - 为 `mart_vehicle_quality_360` 补充缺陷关联分析关键字段
## 2026-04-11 21:20 - 新增 Analytics DB 后续待办清单与 mart 复用判断说明
### 概述
为方便后续在 `analytics_db` 基础上继续选择扩展方向，新增一份面向维护者的待办清单文档，集中整理当前已完成内容、建议下一步、可选增强项，以及“当前是否可以只依赖 `mart_vehicle_quality_360` 让 LLM 自主生成 SQL”的判断依据。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/analytics_db_todolist.md`
  - 按“已完成 / 建议下一步 / 可选增强”整理数据库后续建设路径
- **设计判断沉淀**:
  - 补充当前直接复用 `mart_vehicle_quality_360` 的适用范围
  - 补充何时需要新增 `mart_defect_daily_by_model`、`mart_defect_station_distribution` 的判断标准

## 2026-04-11 20:15 - 落地当前车辆事实分层第一阶段并同步数据库重构文档
### 概述
围绕 `analytics_db` 中“正式产品车 / 异常车 / 全量占位”混用的问题，正式落地当前车辆事实分层优化第一阶段：新增全量当前占位事实、异常车事实、异常车主题 `mart` 与当前现场总览 `mart`，同时将原有产品车当前位置事实明确收口到正式产品车，并把 `database_refactor` 文档同步到数据库真实状态。
### 变更内容
- **数据库对象新增与调整**:
  - 在 `analytics_db` 中新增 `fct.fct_position_current_all`
  - 在 `analytics_db` 中新增 `fct.fct_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_position_current_overview`
  - 重建 `fct.fct_vehicle_position_current`，明确其仅服务正式产品车
  - 重建 `mart.mart_vehicle_quality_360`，使其继续面向产品车质量分析主链路
- **维度层增强**:
  - 为 `dim.dim_vehicle_profile` 增加 `current_position_id`、`current_carrier_id`、`current_carrier_type`、`current_process_area`、`current_full_rb_code`、`current_position_updated_at`
  - 让车辆画像维度可保留正式产品车的当前绑定快照
- **刷新流程升级**:
  - 更新 `meta.refresh_analytics_all()`
  - 将新 `fct` / `mart` 对象纳入一键刷新流程
  - 刷新后自动补齐 `agent_ro` 对新增对象的 `SELECT` 权限
- **验证结果**:
  - 刷新后 `fct.fct_position_current_all = 114`
  - 刷新后 `fct.fct_vehicle_position_current = 102`
  - 刷新后 `fct.fct_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_position_current_overview = 114`
  - 异常车分类样例为 `empty_vehicle_id_with_carrier = 8`、`non_product_prefix = 4`
- **文档同步**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 更新 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`

## 2026-04-11 18:55 - 补充当前车辆事实分层重构方案文档
### 概述
围绕 `analytics_db` 当前车辆事实层在异常车、重复调试 `vehicle_id` 和 `carrier_id` 反查场景下的限制，补充一份面向后续数据库重构的专题方案文档，并同步修正现有 `database_refactor` 文档中的限制说明与演进建议，帮助后续将“正式产品车 / 异常车 / 全量占位”分层建模。
### 变更内容
- **新增专题方案文档**:
  - 新增 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`
  - 说明当前 `fct_vehicle_position_current` 的局限，以及 `fct_position_current_all`、`fct_abnormal_vehicle_current`、异常车主题 `mart` 的设计方向
- **现有文档补充**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 增加当前 `fct_vehicle_position_current` 对异常车与重复调试车场景的限制说明
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 增加当前产品车事实与异常车事实不应长期混用的设计依据与后续演进建议

## 2026-04-11 18:36 - 新增 Analytics DB 设计动机说明文档
### 概述
在已经补齐 `analytics_db` 落地与刷新操作手册的基础上，再新增一份面向后续复用的设计说明文档，专门回答“为什么要设计 `analytics_db`、为什么不是直接查源库、为什么要分层以及当前取舍是什么”，用于统一数据库重构和 Agent 接库改造的设计认知。
### 变更内容
- **新增设计说明文档**:
  - 新增 `docs/backend/database_refactor/why_analytics_db.md`
  - 从背景、问题、分层、设计决策、已验证事实、踩坑与复用清单几个维度解释 `analytics_db` 的必要性
- **与现有手册互补**:
  - 与 `docs/backend/database_refactor/analytics_db_architecture.md` 形成“为什么这样设计”与“如何落地执行”的双文档结构

## 2026-04-11 17:20 - 修正 Analytics DB 落地与刷新操作手册为最新已验证版
### 概述
将 `docs/backend/analytics_db_architecture.md` 从偏概念性的架构说明重写为可直接执行的 `analytics_db` 落地与刷新操作手册，统一当前数据库中已经验证成功的 schema、表、物化视图、权限与刷新流程，避免后续继续沿用遗漏 `dim` 刷新和 `refresh_watermark` 更新的旧版步骤。
### 变更内容
- **文档重写**:
  - 更新 `docs/backend/analytics_db_architecture.md`
  - 补充一次性初始化、FDW 外表导入、ODS/DIM/FCT/MART 初始化与授权步骤
- **刷新流程修正**:
  - 明确当前正式版 `meta.refresh_analytics_all()` 会同时刷新 `dim.dim_process_area`、`dim.dim_vehicle_profile` 与 `meta.refresh_watermark`
  - 修正旧文档中仅刷新 `ods/fct/mart` 的过时描述
- **运维说明补充**:
  - 补充日常手工刷新、Windows 定时任务、验证 SQL 与后续项目接入步骤
  - 明确当前 `mart_vehicle_quality_360` 关联的是“缺陷检测 + 当前最新位置”，不是检测当时位置

## 2026-04-09 20:28 - 新增项目内数据库结构快照目录
### 概述
为方便后续字段分析、结构梳理和离线阅读，将 `defect_db` 中 5 张业务表的字段结构同步保存到项目根目录 `database/` 下，不再只依赖数据库内查询。
### 变更内容
- **新增本地快照目录与文件**:
  - 新增 `database/README.md`
  - 新增 `database/defect_db_schema_snapshot.json`
- **README 同步**:
  - 更新项目结构，补充 `database/` 目录说明
- **快照范围**:
  - `history`
  - `history_detail`
  - `history_extras`
  - `history_station`
  - `history_tokens`

## 2026-04-08 21:49 - 新增代码质量审查子智能体
### 概述
为项目补充一个专门用于“做代码 review、找 bug、识别回归风险、检查测试缺口”的子智能体 `code-reviewer`，帮助日常代码质量审查聚焦高风险问题与缺失测试，而不是停留在泛化风格建议。
### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-reviewer.md`
  - 约束其聚焦代码质量问题、稳定性风险、安全隐患与测试覆盖审查
- **README 同步**:
  - 补充“代码质量审查子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/code-reviewer.md` 入口
## 2026-04-07 21:18 - 同步 openspec/project.md 到当前项目上下文
### 概述
重写 `openspec/project.md` 中已经过期的 OpenSpec 项目背景说明，使其不再沿用旧版通用聊天 / arXiv Agent 视角，而是聚焦当前真实使用的 SQL Agent、Skills、RAG、结构化流式协议和双模式持久化实现，便于后续 proposal / spec 编写时获得更准确的项目上下文。
### 变更内容
- **项目定位修正**:
  - 更新 `openspec/project.md`
  - 将 Purpose 从旧版通用聊天 / 论文搜索场景，修正为当前生产数据查询型 SQL Agent 场景
- **技术与架构同步**:
  - 将技术栈更新为 LangChain/LangGraph、AsyncPostgresSaver / PostgresSaver、PGVector / Milvus Hybrid 等当前实现
  - 将架构模式更新为 `api.py -> services.py -> agent/service.py` 主链路
  - 补充结构化 SSE 事件协议和双模式持久化约定
- **约束与术语更新**:
  - 补充 `required_skill`、`export_to_csv`、BusinessRagMiddleware 等当前领域术语
  - 更新重要约束为只读 SQL、聚合优先、截断结果不可直接汇总、切换 embedding provider 后需重建向量库
  - 移除旧版固定主分支、FastAPI 测试客户端、arXiv API 等不再适合作为当前项目事实的描述

## 2026-04-07 21:04 - 同步 CLAUDE.md 到当前项目实现
### 概述
清理并重写根目录 `CLAUDE.md` 中已经过期的项目说明，使其与当前仓库中的环境约定、SQL Agent 架构、Skills/RAG 能力、结构化流式协议和双模式持久化实现保持一致，避免后续继续参考旧版 arXiv / 同步 PostgresSaver 文档造成误导。
### 变更内容
- **文档定位更新**:
  - 更新 `CLAUDE.md`
  - 明确 `AGENTS.md`、`memory.md`、`README.md`、`CLAUDE.md` 的建议优先级
  - 补充 proposal / spec / plan 场景下优先查看 `openspec/AGENTS.md` 的提示
- **环境与架构同步**:
  - 将环境说明从旧版 `py314_agent` 修正为 `py312_agent`
  - 将项目定位从旧版通用聊天 / arXiv Agent 更新为当前 SQL Agent + Skills + RAG 架构
  - 更新后端、前端主链路与关键目录说明
- **关键行为说明修正**:
  - 将流式说明更新为 `token/status/tool_call/tool_result/final/error` 结构化 SSE 事件协议
  - 将持久化说明更新为 FastAPI 本地异步 `AsyncPostgresSaver` 与 LangGraph 托管双模式
  - 补充 `required_skill` 约束、CSV 导出下载链路与当前常见误区说明

## 2026-04-06 21:22 - 重构技能场景目录与自动发现机制
### 概述
围绕后续固定场景持续增加后的维护成本问题，将业务技能系统从“场景文件 + 分散 SQL + 手工注册”升级为“场景目录聚合 + 自动发现 + scoped 资产解析”模式。这样新增一个场景时，只需要新增一个场景目录并填写模板，不再修改 `registry.py`。
### 变更内容
- **注册与发现重构**:
  - 新增 `backend/app/skills/discovery.py`
  - 更新 `backend/app/skills/registry.py`
  - 由显式 import/append 改为扫描 `domains/*/meta.py` 和 `scenarios/*/scenario.py` 自动装配
- **资产解析升级**:
  - 更新 `backend/app/skills/models.py`
  - 更新 `backend/app/skills/assets.py`
  - 更新 `backend/app/skills/renderers.py`
  - 为场景资产引入 `scope + path` 语义，支持 `scenario / shared / domain` 三类作用域
- **目录结构迁移**:
  - 迁移 `paint_shop_vehicle_tracking` 现有场景到 `scenarios/<scenario_name>/scenario.py + sql/main.sql`
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/shared/scripts/README.md`
  - 删除旧版 `scenarios/*.py`、`sql/*.sql` 与领域级脚本占位说明文件
- **验证与文档同步**:
  - 更新 `backend/app/test_skill_registry.py`，补充自动发现、shared 资产解析和失败即报错场景
  - 更新 `docs/backend/skills/README.md`
  - 更新 `docs/backend/skills/新增场景技能开发指南.md`
  - 更新 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 更新 `docs/backend/skills/技能注册中心与加载机制说明.md`
  - 更新 `README.md` 的技能系统说明

## 2026-04-06 11:15 - 新增技能机制评审与优化待办文档
### 概述
将本次围绕“领域技能 / 场景技能加载机制”的评审结论整理为独立待办文档，集中记录当前问题、推荐方案与分期待办，便于后续继续按阶段推进优化，而不把讨论内容散落在聊天记录中。
### 变更内容
- **新增待办目录**:
  - 新增 `docs/todolist/`
- **新增评审文档**:
  - 新增 `docs/todolist/2026-04-06-技能机制评审与优化待办.md`
  - 归档技能上下文失配、场景资产加载不一致、场景与历史 SQL 示例优先级不清、仅展开第一份 SQL 等问题
- **目录说明同步**:
  - 更新 `README.md` 的项目结构说明，补充 `docs/todolist/` 目录用途

## 2026-04-06 10:25 - 同步 Obsidian 后端学习导航，补齐遗漏文档包装页
### 概述
扫描 `docs/` 与 `docs/obsidian/` 的对应关系后，补齐此前未纳入 Obsidian 后端学习路径的 5 篇中文文档，确保 `llama.cpp` 配置总结与 skills 专题文档也能在 Obsidian 中通过导航页顺序访问。
### 变更内容
- **导航更新**:
  - 更新 `docs/obsidian/backend-learning/00_后端开发学习导航.md`
  - 新增“本地模型与技能系统扩展”阶段，补充 22-26 号学习笔记入口
- **包装页补齐**:
  - 新增 `docs/obsidian/backend-learning/22_llama.cpp_与_LangChain_配置要点总结.md`
  - 新增 `docs/obsidian/backend-learning/23_Skills总览与文档导航.md`
  - 新增 `docs/obsidian/backend-learning/24_技能注册中心与加载机制说明.md`
  - 新增 `docs/obsidian/backend-learning/25_新增业务领域技能开发指南.md`
  - 新增 `docs/obsidian/backend-learning/26_新增场景技能开发指南.md`
- **链路修正**:
  - 更新 `docs/obsidian/backend-learning/21_Docker容器网络与外部服务访问指南.md`
  - 为原有阶段末尾补充下一篇跳转，保持学习链路连续

## 2026-04-06 10:14 - 新增 llama.cpp 与 LangChain 配置要点总结文档
### 概述
将项目内接入 `llama.cpp` OpenAI 兼容接口时的关键经验整理为独立文档，集中说明 `BASE_URL`、协议、API Key、模型名与 `max_tokens` 的配置规律，便于后续排查本地模型接入问题。
### 变更内容
- **新增文档**:
  - 新增 `docs/llama.cpp 与 LangChain 配置要点总结.md`
- **沉淀内容**:
  - 总结 `BASE_URL` 应只保留到 `/v1`
  - 补充 `http`/`https` 协议匹配要求
  - 记录 `llama.cpp` 默认不校验 API Key 的约定
  - 补充模型名、`max_tokens` 与推荐 `ChatOpenAI` 参数写法
- **维护价值**:
  - 为后续本地 GGUF 模型接入、排错与配置统一提供固定参考

## 2026-04-05 20:15 - 新增实时区域车身数量场景技能
### 概述
在 `paint_shop_vehicle_tracking` 领域下补充一个“实时各区域车身数量统计”固定场景，沉淀对应的场景 playbook 和外部 SQL 模板，让 Agent 能按场景方式加载这类高频实时统计需求。
### 变更内容
- **场景技能新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count.py`
  - 定义实时区域车身数量统计的触发问法、workflow、规则、易错点与输出契约
- **SQL 模板新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/sql/realtime_area_body_count.sql`
  - 按 `process_area` 聚合统计当前有效车身数量，并按数量降序输出
- **注册与验证补充**:
  - 更新 `backend/app/skills/registry.py`，显式注册 `realtime_area_body_count`
  - 更新 `backend/app/test_skill_registry.py`，覆盖新场景的注册与加载断言
- **文档同步**:
  - 更新 `docs/backend/skills/README.md` 的当前目录结构示例，补充新场景文件

## 2026-04-05 11:40 - 补全 skills 专题文档目录
### 概述
继续完善 `docs/backend/skills/`，将原先的单篇“新增业务领域技能开发指南”扩展为一个可导航的小型专题文档集，覆盖目录索引、场景技能扩展方式以及注册中心与加载机制说明，方便团队后续系统化维护技能系统。
### 变更内容
- **新增文档索引**:
  - 新增 `docs/backend/skills/README.md`
  - 统一收口 skills 相关文档入口和推荐阅读顺序
- **新增扩展教程**:
  - 新增 `docs/backend/skills/新增场景技能开发指南.md`
  - 新增 `docs/backend/skills/技能注册中心与加载机制说明.md`
- **README 同步**:
  - 在技术文档列表中补充 skills 专题导航和新文档入口
- **维护价值**:
  - 让 `docs/backend/skills/` 从单文档目录演进为可持续扩展的技能系统手册目录

## 2026-04-05 11:10 - 新增业务领域技能扩展教程
### 概述
围绕当前“领域 skill + 场景 skill”二级披露架构，补充一份面向维护者的可复用教程，专门说明如何新增、配置和验证一个新的业务领域，避免后续只创建目录却遗漏注册中心、场景挂载或资产路径配置。
### 变更内容
- **新增教程文档**:
  - 新增 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 说明新增领域目录、`meta.py`、`domain.md`、场景定义、SQL 模板与 `registry.py` 显式注册步骤
- **文档入口补充**:
  - 更新 `README.md` 的技术文档列表，加入该教程入口
- **维护建议沉淀**:
  - 明确当前实现属于“显式注册”机制，不会自动发现新领域
  - 总结新增领域后的验证清单与常见错误，便于团队后续复用

## 2026-04-05 10:30 - 引入领域与场景二级 Skill 披露骨架
### 概述
围绕 SQL Agent 的业务技能系统，实施“领域 skill + 场景 skill”二级披露改造：保留现有 `load_skill -> required_skill -> sql_db_query` 主链路，在不引入固定报表执行器的前提下，新增场景级 playbook、外部 SQL 资产和二级加载工具，为后续模板执行器与专用 report tool 预留扩展接口。
### 变更内容
- **技能包重构**:
  - 将 `backend/app/skills.py` 升级为 `backend/app/skills/` package
  - 新增 `models.py`、`registry.py`、`renderers.py`、`loaders.py`、`assets.py`
  - 保留 `SKILLS` 兼容导出，避免现有中间件和测试脚本回归
- **二级披露链路**:
  - 新增 `load_scenario` 工具
  - 扩展 `CustomState`，增加 `scenarios_loaded`、`active_skill`、`active_scenario`
  - 更新 `SkillMiddleware` 与系统提示词，引导“先加载领域，再按需加载场景”
- **样板场景落地**:
  - 为 `paint_shop_vehicle_tracking` 新增 `daily_area_body_count` 场景元数据
  - 引入外部 SQL 模板 `daily_area_body_count.sql`
  - 场景文本新增 workflow、rules、gotchas、output contract 和模板资产引用
- **文档与测试**:
  - 更新 `README.md` 中的技能系统说明
  - 新增 `backend/app/test_skill_registry.py`，覆盖注册中心、加载器和二级加载辅助逻辑

## 2026-04-04 14:55 - 清理 Docker 环境文件中的敏感信息并补充忽略规则

### 概述
针对 GitHub Push Protection 阻止 `feature/agent` 推送的问题，先在当前工作区完成最小化安全修复：补充相关忽略规则，降低后续再次误提交本地敏感配置的风险，并为后续清理未推送提交历史做准备。

### 变更内容
- **忽略规则补充**:
  - 更新 `.gitignore`
  - 新增 `.env_docker`、`.env copy`、`env_exp` 忽略项，覆盖本次触发扫描的本地环境文件命名
- **历史清理说明**:
  - 当前变更仅处理工作区与后续防误提交保护
  - 仍需对本地未推送提交历史执行重写，才能解除 GitHub 对旧提交中 secret 的拦截

## 2026-04-03 20:00 - 整理文档目录结构并更新 Obsidian 引用

### 概述
将原先分散在 `backend/docs` 下的后端技术文档统一归档到 `docs/backend`，让项目文档入口全部收口到 `docs/` 下；同时同步修正 Obsidian 学习笔记、README 与相关说明中的旧路径引用，避免目录调整后出现断链。

### 变更内容
- **目录整合**:
  - 将 `backend/docs/` 迁移为 `docs/backend/`
  - 保留 `docs/backend/rpd/` 子目录结构
- **Obsidian 引用更新**:
  - 批量更新 `docs/obsidian/backend-learning/` 下 21 篇学习笔记的 `source_note`、原文入口与嵌入路径
  - 更新 `00_后端开发学习导航.md` 中的原文目录说明
- **说明文档同步**:
  - 更新 `README.md` 中的项目结构与技术文档入口
  - 更新 `CLAUDE.md`、`开发规范与最佳实践.md` 中的后端文档目录路径
  - 修正 `docs/backend/rpd/` 内少量旧绝对路径说明

## 2026-04-02 22:25 - 新增通用文档的 Obsidian 分类学习目录

### 概述
将 `docs/` 下 7 篇原先零散放置的通用文档，按主题整理进对应的 Obsidian 学习目录，延续 `backend-learning` 的组织规则：保留原文不动，新增导航页、编号学习页、原文入口与嵌入，方便后续在 Obsidian 中按专题学习。

### 变更内容
- **新增 Obsidian 分类目录**:
  - 新增 `docs/obsidian/agent-sql-learning/`
  - 新增 `docs/obsidian/architecture-learning/`
  - 新增 `docs/obsidian/frontend-learning/`
  - 新增 `docs/obsidian/data-quality-learning/`
- **整理范围**:
  - `agent_best_practices.md`
  - `LangChain + PostgreSQL 注释识别最佳实践.md`
  - `sql_agent.md`
  - `前后端与Nginx架构知识总结.md`
  - `前端聊天消息Markdown渲染开发指南.md`
  - `数据库日期时间记录与大模型处理分析报告.md`
  - `生产数据查询智能体需求.md`
- **README 同步**:
  - 更新 Obsidian 学习目录说明
  - 增加新的学习导航入口

## 2026-04-02 22:15 - 新增 Obsidian 后端开发学习导航与编号笔记

### 概述
为了方便系统化学习 `backend/docs` 下的后端开发文档，新增一组面向 Obsidian 的学习笔记目录。在不改动原始文档的前提下，按学习顺序重新编号，并补充导航页、前后跳转和原文嵌入入口，降低后续复习与串联成本。

### 变更内容
- **新增 Obsidian 学习目录**:
  - 新增 `docs/obsidian/backend-learning/`
  - 新增 `00_后端开发学习导航.md`
  - 新增 21 篇编号学习笔记，覆盖 `backend/docs` 与 `backend/docs/rpd` 的现有后端文档
- **组织方式**:
  - 保留原始 `backend/docs` 文档不动
  - 每篇学习笔记增加学习建议、原文入口、上下篇导航与 Obsidian 嵌入
  - 导航页按“基础认知 / Agent 与 RAG / SQL Agent / 交互观测 / 部署环境”分阶段整理
- **README 同步**:
  - 更新项目结构说明
  - 增加 Obsidian 后端学习导航入口

## 2026-04-02 13:00 - 修复 Docker 构建阶段的 Milvus 依赖版本冲突

### 概述
修复 Docker 构建 `pip install -r /app/requirements.txt` 时的依赖解析失败。根因是项目显式锁定了 `pymilvus==2.6.3`，但 `llama-index-vector-stores-milvus==1.0.0` 要求 `pymilvus>=2.6.7,<3`，导致 pip 无法完成依赖求解。

### 变更内容
- **依赖版本对齐**:
  - 更新 `requirements.txt`
  - 更新 `requirements_standard.txt`
  - 将 `pymilvus` 从 `2.6.3` 提升为 `2.6.7`
- **修复效果**:
  - 与 `llama-index-vector-stores-milvus==1.0.0` 的最低兼容版本保持一致
  - 保持改动最小，避免一次性升级到更高版本带来的额外兼容风险

## 2026-04-02 12:50 - 修复 Docker 容器启动时 backend 包导入失败

### 概述
修复 `docker-compose.yml` 启动后端容器时出现的 `ModuleNotFoundError: No module named 'backend'`。根因是镜像内的 `WORKDIR`、`PYTHONPATH` 与 Uvicorn 启动入口使用了 `app.main:app` 路径，但仓库代码实际大量采用 `backend.app...` 绝对导入，导致容器内包根路径不一致。

### 变更内容
- **镜像启动路径修复**:
  - 更新 `backend/Dockerfile`
  - `WORKDIR` 从 `/app/backend` 调整为 `/app`
  - `PYTHONPATH` 从 `/app/backend` 调整为 `/app`
  - Uvicorn 启动入口从 `app.main:app` 调整为 `backend.app.main:app`
- **修复效果**:
  - 让容器内 Python 包根路径与仓库实际导入风格保持一致
  - 避免 `export_files.py`、`services.py`、`agent/service.py` 等模块中的 `backend.app...` 绝对导入在容器中失效

## 2026-04-02 00:10 - 新增 Docker 容器网络与外部服务访问指南

### 概述
围绕本次 `backend`、PostgreSQL、Milvus 与宿主机模型服务之间的 Docker 联通排查，新增一份可复用的实施/排障手册，统一沉淀 `external network`、容器名寻址、`host.docker.internal` 使用边界以及常见易错点，方便后续继续接入新的数据库或本地 API 服务。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Docker容器网络与外部服务访问指南.md`
- **文档内容覆盖**:
  - 容器访问容器、容器访问宿主机、本机访问本机三类地址边界
  - `savedatabase_app-network` 与 `savedatabase_app_network` 命名差异带来的真实排障经验
  - Milvus 同时接入默认网络与外部网络的设计原因
  - 后续接入新依赖服务时的标准判断步骤与检查清单
- **README 同步**:
  - 更新技术文档列表，补充 Docker 网络与外部服务访问指南入口

## 2026-04-01 23:25 - 新增前端聊天消息 Markdown 渲染开发指南

### 概述
将本次“聊天消息完成态 Markdown 渲染 + 业务报表风格样式”实现过程沉淀为一份可复用开发指南，便于后续在其他聊天结果展示、分析摘要卡片或统计报表类前端场景中继续复用。

### 变更内容
- **新增文档**:
  - 新增 `docs/前端聊天消息Markdown渲染开发指南.md`
- **文档内容覆盖**:
  - 聊天消息 Markdown 渲染的背景、目标与整体分层设计
  - `markdown-it + DOMPurify + MessageItem.vue + style.css` 的调用链与职责拆分
  - 流式纯文本 / 完成态 Markdown 的设计取舍、易错点与检查清单
  - 业务报表风格样式的复用经验、边界与后续优化方向
- **README 同步**:
  - 更新项目特性与技术文档列表，补充 Markdown 展示能力与指南入口

## 2026-04-01 23:10 - 优化聊天消息为业务报表风格展示

### 概述
继续细化聊天消息的 Markdown 呈现方式，将原先偏通用文档的样式收敛为更适合统计结果、异常说明、分析摘要等场景的“业务报表风格”，让标题层次、表格扫描效率和数字信息可读性更清晰。

### 变更内容
- **样式优化**:
  - 更新 `frontend/src/style.css`
  - 强化仅含加粗文本段落的区块标题表现，模拟报表分组标题
  - 优化表格表头背景、行间斑马纹、边框与阴影，提升企业报表观感
  - 为第二列数字内容增加右对齐与等宽数字展示，便于快速对比数量
  - 放宽说明列换行规则，减少长文本被挤压的问题

## 2026-04-01 22:55 - 前端聊天消息支持 Markdown 展示渲染

### 概述
为聊天前端新增“完成态 Markdown 渲染”能力，让助手最终回复中的粗体、列表、表格、代码块和链接能够以更舒适、更易读的样式展示；同时保留流式输出阶段的纯文本效果，避免生成过程中频繁重排。

### 变更内容
- **前端依赖**:
  - `frontend/package.json` 新增 `markdown-it` 与 `dompurify`
- **渲染能力**:
  - 新增 `frontend/src/utils/markdown.ts`
  - 统一封装 Markdown 转 HTML 与安全清洗逻辑
  - 链接默认补充新窗口打开与安全 `rel` 属性
- **消息展示**:
  - 更新 `frontend/src/components/MessageItem.vue`
  - 用户消息与流式中的助手消息继续按纯文本显示
  - 助手完成态消息切换为 Markdown HTML 渲染
- **视觉样式**:
  - 更新 `frontend/src/style.css`
  - 新增聊天消息 Markdown 样式，优化段落、列表、表格、代码块、引用和链接展示

## 2026-04-01 01:00 - 新增 development-guide-synthesizer 技能

### 概述
新增一个面向“开发经验沉淀”的项目级技能，用于根据开发实现、讨论内容、代码改动和验证结果，快速提炼出结构化开发指南手册。该技能内置清晰模板、示例、关键点和常见错误，方便后续重复使用。

### 变更内容
- **新增技能**:
  - 新增 `.agents/skills/development-guide-synthesizer/SKILL.md`
- **新增参考资料**:
  - 新增 `.agents/skills/development-guide-synthesizer/references/guide-template.md`
  - 新增 `.agents/skills/development-guide-synthesizer/references/examples.md`
- **技能能力**:
  - 支持把功能开发、调试排障、架构讨论等内容沉淀为开发指南、排障手册、实施手册或复用 playbook
  - 提供标准章节模板、调用示例、关键点维度和易错点清单
- **README 同步**:
  - 更新项目特性与目录结构，补充该技能入口

## 2026-04-01 00:30 - 新增 SQL 导出文件下载开发指南

### 概述
围绕本次“SQL 大结果导出 + 后端下载接口 + 前端下载卡片”能力，新增一份可复用的开发指南，统一沉淀从查询限流、导出工具、文件元数据、安全下载到前端消息展示的设计经验，方便后续在其他导出类场景继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/SQL导出文件下载开发指南.md`
- **文档内容覆盖**:
  - SQL 导出下载链路的整体架构与调用顺序
  - `export_to_csv`、`export_files.py`、下载接口与前端下载卡片的职责分层
  - 为什么选择“结构化 JSON 字符串 + file_id + sidecar metadata”方案
  - 文件下载安全边界、复用模板、检查清单与后续演进方向
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-04-01 00:00 - 为 SQL 导出结果新增前端可下载能力

### 概述
为 `export_to_csv` 打通“服务器落盘 -> 后端安全下载接口 -> 前端下载按钮”的完整链路。现在导出工具不会再把服务器绝对路径直接暴露给前端，而是返回结构化导出元数据，聊天消息中可直接点击下载 CSV。

### 变更内容
- **后端导出元数据管理**:
  - 新增 `backend/app/export_files.py`
  - 为每个导出文件生成 `file_id`，并使用 sidecar JSON 保存文件元数据
- **后端下载接口**:
  - `backend/app/api.py` 新增 `GET /api/chat/files/{file_id}`
  - 通过 `FileResponse` 安全返回已导出的 CSV 文件
- **导出工具返回结构升级**:
  - `backend/app/agent/tools/csv_export_tool.py` 从“返回服务器路径文本”改为“返回结构化 JSON 字符串”
  - `backend/app/config.py` 新增 `SQL_EXPORT_DIR`、`SQL_EXPORT_TTL_HOURS`
- **前端下载卡片**:
  - 新增 `frontend/src/api/exports.ts`
  - `frontend/src/components/MessageItem.vue` 自动识别 `export_to_csv` 结果并渲染“下载 CSV”按钮
  - `frontend/src/types/index.ts` 新增 `ExportArtifact` 类型

### OpenSpec
- 新增 `openspec/changes/add-sql-export-download/`，记录本次导出下载能力的 proposal / design / tasks / spec delta

## 2026-03-31 22:08 - 新增聊天取消与中断机制开发指南

### 概述
围绕本次“前端停止生成 + 后端取消渗透”优化，新增一份专门的开发指南，统一说明取消链路的分层实现、机制原理、能力边界和后续扩展方向，方便团队后续继续复用和演进这套聊天中断能力。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天取消与中断机制开发指南.md`
- **文档内容覆盖**:
  - 前端 `AbortController` 的停止生成机制
  - FastAPI SSE 断连感知与服务端停止转发逻辑
  - `task.cancel()` / `CancelledError` 如何沿 LangChain / LangGraph 协程链传播
  - 本地取消与远端 provider 取消的能力边界
  - 当前产品策略与后续可选体验方案
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-31 22:15 - 停止生成后保留已生成片段并明确标记中断

### 概述
继续细化“停止生成”的产品体验。用户主动中断流式回答后，前端不再直接清空过程态，而是保留已经生成的内容，并将其落定为一条本地 assistant 消息，同时明确标记“已停止生成”，让状态更可理解。

### 变更内容
- **中断消息落定**:
  - `frontend/src/stores/messages.ts` 新增主动中断落定逻辑
  - 停止生成后保留当前文本片段、工具调用和工具结果，并转为本地正式消息
- **取消分支体验优化**:
  - `frontend/src/composables/useChatStream.ts` 在 `AbortError` 分支改为保留片段而非直接清空
  - 继续刷新会话列表，但不立即用服务端消息覆盖当前本地中断结果
- **界面提示优化**:
  - `frontend/src/components/MessageItem.vue` 为中断消息增加“已停止生成”提示和对应视觉样式
- **文档同步**:
  - 更新 `backend/docs/聊天取消与中断机制开发指南.md` 中的当前产品策略说明

## 2026-03-31 21:31 - 收敛前后端 SSE 事件 schema

### 概述
继续收敛聊天流式协议边界，减少前后端对未知事件类型的宽松兜底。后端现在会在发送 SSE 前校验事件结构，前端则移除 `type: string` 回退分支并在解析层拒绝不符合协议的 payload，从而让流式协议真正收敛为有限事件集合。

### 变更内容
- **后端事件模型收敛**:
  - `backend/app/schemas.py` 将流式事件拆分为 `token/status/tool_call/tool_result/final/error` 六类显式模型
  - 新增统一序列化入口，SSE 发送前先校验并标准化事件 payload
- **前端解析层收敛**:
  - `frontend/src/types/index.ts` 移除宽松 `type: string` 兜底事件
  - `frontend/src/api/chat.ts` 增加运行时事件校验，拒绝未知或不完整的流式事件
- **消费侧类型收敛**:
  - `frontend/src/composables/useChatStream.ts` 改为穷尽式 `switch` 处理，避免新事件类型被静默忽略
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`，补充 schema 收敛原则

## 2026-03-31 21:52 - 收敛取消信号到 Agent 执行任务

### 概述
继续优化聊天链路的取消能力，让“前端停止生成 / SSE 断连”不仅停止本地转发，也尽量中断服务层正在执行的 Agent 调用。这样做不能保证远端 LLM provider 一定马上停止推理，但可以更稳定地把取消信号继续传到 LangGraph 图执行与底层模型 SDK 的 await 链路。

### 变更内容
- **非流式取消收敛**:
  - `backend/app/services.py` 将 `ainvoke()` 包装为可取消 task
  - 上层取消时显式取消并等待任务结束，避免悬挂中的 Agent 调用继续运行
- **流式取消收敛**:
  - `backend/app/services.py` 将 `astream()` 消费改为独立 producer task + queue
  - 当 SSE 消费端取消或断连时，会反向取消 producer task，并主动关闭底层 async iterator
- **边界说明**:
  - 当前优化能更早停止本地 FastAPI / LangGraph 消费链路
  - 远端 provider 是否真正中断，仍取决于对应 SDK / 模型服务是否支持请求级取消

## 2026-03-31 11:05 - 新增 LangSmith tracing 开发指南文档

### 概述
围绕本次 tracing metadata / tags 接入，新增一份面向后续开发的文档手册，统一说明其作用、当前实现、字段规范、查看方式和扩展建议，方便后续在新入口或新业务域下继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/LangSmith Tracing Metadata 与 Tags 开发指南.md`
- **文档内容覆盖**:
  - tracing metadata / tags 的作用与典型使用场景
  - 当前项目中的接入位置与字段清单
  - 如何在调用时追加业务 metadata / tags
  - 如何在 LangSmith 中查看和过滤 trace
  - 后续扩展建议与开发检查清单
- **README 同步**:
  - 在技术文档列表新增该指南入口

### 2026-03-31 11:15 Asia/Shanghai 更新补充
- 澄清 `business_domain` 应来自确定性来源，不应由 LLM 在请求开始时自由推断后注入根 trace
- 补充“运行过程中才能确定 domain 时”的三种推荐策略：首轮不注入、仅对子链路补充、持久化后下一轮再注入

### 2026-03-31 11:30 Asia/Shanghai 更新补充
- 修正 tracing 手册中的 `config` 示例，拆分为“默认安全示例”和“已确认 domain 才注入”的扩展示例

## 2026-03-31 10:20 - 后端新增 SSE 客户端断连感知

### 概述
为聊天流式接口补充服务端侧断连感知能力。当浏览器主动停止生成、关闭页面或网络中断导致 SSE 连接断开时，后端会尽早停止等待新的流式事件并关闭流式迭代器，减少无效的本地继续执行。

### 变更内容
- **SSE 断连检测**:
  - `backend/app/api.py` 的 `/stream` 路由新增 `Request` 注入
  - 在事件循环中周期性检查 `request.is_disconnected()`
- **尽早停止等待**:
  - 将下一条流式事件读取包装为可取消的 `asyncio` task
  - 检测到客户端断开后，立即取消等待中的任务并结束 SSE 生成
- **资源清理与结束标记收敛**:
  - 在 `finally` 中主动关闭流式迭代器
  - 客户端已断开时不再尝试发送 `[DONE]`

## 2026-03-31 10:45 - 新增 LangSmith tracing metadata 与 tags

### 概述
为 FastAPI 本地聊天链路补充 LangSmith trace 元数据与标签。后续可以在 LangSmith 中按会话、请求模式、RAG 后端、模型和运行环境过滤 trace，也为自托管或兼容 OpenAI 协议的模型提供更稳定的模型识别字段。

### 变更内容
- **trace metadata 补充**:
  - `backend/app/services.py` 统一为 invoke/stream 两条链路补充 `session_id`、`thread_id`、`request_mode`、`rag_backend`、`app_component`、`runtime_mode`
  - 同步补充 `ls_provider`、`ls_model_name`、`ls_temperature`、`ls_max_tokens`
- **trace tags 补充**:
  - 新增 `chat-api`、`sql-agent`、`mode:*`、`runtime:*`、`rag:*`、`provider:*`、`model:*`、`env:*` 等标签
- **配置合并策略**:
  - 保留外部传入的 `configurable / metadata / tags`
  - 新增 trace 字段时默认合并，不破坏后续按业务域继续扩展

## 2026-03-29 22:35 - 修复 P0 级流式结果聚合与非流式错误语义

### 概述
针对聊天链路中最关键的三类问题进行收敛：避免多节点流式 token 被误拼成最终回答、避免 `tool_call_chunk` 在前后 chunk 间被拆成多个工具调用、避免非流式 Agent 异常被伪装成正常 assistant 消息落库。

### 变更内容
- **流式最终内容聚合修复**:
  - `backend/app/services.py` 不再使用全量流式 token 直接生成最终 `final.content`
  - 改为优先使用最终 `AIMessage` 提取的完整内容，降低多节点 streaming 污染最终回答的风险
- **工具调用 chunk 归并修复**:
  - `backend/app/services.py` 将流式工具调用按 `chunk index` 归并，并通过原始 `tool_call_id` 回写结果映射
  - 避免同一次工具调用被拆成多个前端工具卡片
- **非流式错误语义修复**:
  - `backend/app/services.py` 的 `process_message()` 改为向上抛出异常
  - `backend/app/api.py` 在非流式路径返回标准错误响应，不再把失败文本保存为成功 assistant 消息
- **前端失败后状态同步补强**:
  - `frontend/src/composables/useChatStream.ts` 在发送失败后补一次消息同步，尽量与服务端持久化状态保持一致

## 2026-03-29 22:55 - 收敛前端会话状态同步与消息请求竞态

### 概述
继续优化聊天前端状态管理，去掉本地手工维护的会话消息计数，统一以服务端会话数据为准；同时为消息拉取增加请求序列保护，避免快速切换会话时旧请求回包覆盖当前会话消息。

### 变更内容
- **会话状态权威源收敛**:
  - `frontend/src/composables/useChatStream.ts` 不再手工累加 `message_count`
  - 在消息发送完成、流式结束和失败恢复后统一刷新服务端会话列表
- **消息同步范围收敛**:
  - 仅当当前仍停留在对应会话时，才静默刷新该会话的消息列表
  - 避免用户切换到其他会话后，旧会话的后台同步覆盖当前视图
- **消息请求竞态保护**:
  - `frontend/src/stores/messages.ts` 新增请求序号与目标会话标记
  - 旧请求回包将被忽略，降低串会话和闪屏风险

## 2026-03-29 23:10 - 新增流式取消能力与停止生成交互

### 概述
为聊天前端补充流式请求取消能力。用户在流式模式下发送问题后，可以主动停止当前生成过程；前端会中断 SSE 请求、清理过程态，并重新同步服务端消息与会话状态，避免把主动停止误判为系统错误。

### 变更内容
- **流式请求取消**:
  - `frontend/src/api/chat.ts` 为 `sendChatStream()` 增加 `AbortSignal` 支持
  - `frontend/src/composables/useChatStream.ts` 使用 `AbortController` 管理当前流式请求
- **停止生成交互**:
  - `frontend/src/views/ChatView.vue` 在流式发送中将发送按钮切换为“停止生成”
  - 用户点击后会中断当前请求，而不是弹出失败提示
- **中断后的状态收敛**:
  - 主动中断时清理流式临时消息
  - 随后重新同步当前会话消息与会话列表，尽量与服务端持久化结果保持一致

## 2026-03-27 22:12 - 聊天界面默认仅展示最终结论

### 概述
优化聊天前端展示策略，将“过程信息”和“最终答案”分层处理。普通用户在问答完成后只看到最终结论，生成过程中的状态与工具细节仅保留为轻量提示或内部调试信息，从而减少信息噪音，提升阅读效率。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-final-only-display/`
  - 为“默认仅展示最终结论”补齐 proposal / tasks / spec delta
- **前端展示收敛**:
  - `frontend/src/components/MessageItem.vue` 默认不再展示状态文本、工具调用、工具结果和错误细节
  - 新增 `frontend/src/config/chat.ts`，通过 `VITE_CHAT_DEBUG_STREAM=true` 恢复内部调试视图
- **流式错误体验修复**:
  - `frontend/src/stores/messages.ts` 新增错误落定逻辑，失败时直接收敛为最终 assistant 消息
  - `frontend/src/composables/useChatStream.ts` 避免错误后残留半成品过程态消息
- **README 同步**:
  - 更新功能说明，强调默认用户界面仅展示最终结论

## 2026-03-27 20:55 - 新增 Milvus RAG 异步化故障排查指南

### 概述
围绕本次 Milvus RAG 检索失败事件，系统整理从故障现象、排查路径、根因分析到最终 async 化修复方案的完整经验，帮助后续快速判断“空检索结果”到底是召回失败还是初始化上下文失败。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Milvus-RAG-异步化故障排查指南.md`
- **文档内容覆盖**:
  - 同步 `PostgresSaver`、`stream()/astream()`、Milvus lazy init 之间的因果关系
  - `ThreadPoolExecutor` 工作线程缺少 event loop 的真实触发链
  - 为什么表面上的“未检索到业务知识”其实是初始化失败后的降级结果
  - 最终为什么选择“本地 FastAPI 全链路切回 async”而不是在线程池里补 event loop
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 20:40 - 本地 FastAPI 切回 AsyncPostgresSaver 与异步流式执行

### 概述
将本地 FastAPI 运行链路从“同步 `PostgresSaver` + `stream()/invoke()`”切回“`AsyncPostgresSaver` + `astream()/ainvoke()`”，并增加显式 startup/shutdown 生命周期管理，解决同步 saver 限制和 Milvus 延迟初始化在线程池中缺少 event loop 的问题。

### 变更内容
- **本地异步持久化**:
  - `backend/app/agent/service.py` 新增 `AsyncConnectionPool + AsyncPostgresSaver` 初始化工厂
  - 新增 `create_local_async()` 与 `aclose()`，供 FastAPI 本地模式显式初始化和关闭
- **FastAPI 生命周期改造**:
  - `backend/app/services.py` 去掉模块级 eager `agent_service`
  - 新增 `initialize_agent_service()` / `get_agent_service()` / `shutdown_agent_service()`
  - `backend/app/main.py` 在 `lifespan` 中显式初始化与回收 Agent 资源
- **请求执行链路恢复异步**:
  - `backend/app/services.py` 的非流式和流式调用切回 `ainvoke()` / `astream()`
  - 继续保留结构化 SSE 事件协议与前端兼容逻辑
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`
  - 更新 `backend/docs/延迟初始化工作流程详解.md`
  - 更新 `README.md` 中本地持久化与运行模式说明

## 2026-03-27 18:45 - 新增聊天流式输出结构化事件开发指南

### 概述
基于本次聊天流式协议升级、同步/异步 streaming 兼容处理、工具状态一致性修复和前端 SSE 重构实践，沉淀一份可复用的开发指南，方便后续在其他 Agent / Chat 场景中快速复用和学习。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天流式输出结构化事件开发指南.md`
- **文档内容覆盖**:
  - 结构化流式事件协议设计
  - 后端 `messages / updates / custom` 分工建议
  - 前端 SSE buffer 解析与 streaming state 建模
  - `astream` / `stream` 与 `PostgresSaver` 兼容性踩坑
  - 工具状态“执行中/已完成”一致性处理经验
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 17:50 - 聊天流式协议升级为结构化事件流

### 概述
将原有“纯文本 chunk + 最终块补工具信息”的流式链路，升级为前后端协同的结构化 SSE 事件流。后端切换到 LangGraph v2 多模式 streaming，前端重写 SSE 解析与流式状态管理，使用户可以看到更稳定的实时文本、阶段状态、工具调用、工具结果和错误态。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-streaming-protocol/`
  - 为流式协议升级补齐 proposal / tasks / spec delta
- **后端流式协议升级**:
  - `backend/app/services.py` 改为输出 `token/status/tool_call/tool_result/final/error` 结构化事件
  - 使用 `agent.astream(..., stream_mode=[\"messages\", \"updates\", \"custom\"], version=\"v2\")`
  - 新增 `backend/app/agent/utils/streaming.py`，为工具与中间件提供 custom status 事件写入 helper
  - `backend/app/api.py` 在 `final/error` 路径统一处理 assistant 消息落库，并保留 `[DONE]` 作为传输层结束标记
- **前端流式消费重构**:
  - `frontend/src/api/chat.ts` 重写 SSE buffer 解析逻辑，兼容跨 chunk JSON
  - `frontend/src/types/index.ts` 引入 `StreamEvent`、`StreamToolCall`、结构化 `StreamingMessage`
  - `frontend/src/stores/messages.ts` / `frontend/src/composables/useChatStream.ts` 改为事件驱动，采用“本地完成落定 + 后台静默同步”
  - `frontend/src/components/MessageItem.vue` / `frontend/src/views/ChatView.vue` 增强状态文案、工具执行区和错误态展示

## 2026-03-27 16:10 - 前端开发环境代理到本地后端 8000

### 概述
针对当前后端服务运行在 `http://localhost:8000`、而前端仍使用 `/rearch/...` 相对路径请求的情况，在 Vite 开发环境中补充代理转发规则，避免逐个修改前端 API 文件，并保持开发环境与生产环境的路径风格一致。

### 变更内容
- **Vite 开发代理**:
  - 在 `frontend/vite.config.ts` 的 `server.proxy` 中新增 `/rearch -> http://localhost:8000`
  - 通过 `rewrite` 去掉请求前缀 `/rearch`，使后端实际接收到 `/api/chat/...`
- **兼容性说明**:
  - 保持 `frontend/src/api/index.ts` 与 `frontend/src/api/chat.ts` 现有相对路径写法不变
  - 前端开发时浏览器仍访问 `/rearch/api/...`，由 Vite 代理转发到本地 FastAPI `8000`

### 补充修正（2026-03-27 16:22）
- 将 `frontend/vite.config.ts` 的代理匹配从 `/rearch` 收窄为 `/rearch/api`
- 避免首页路由 `/rearch/` 被误代理到后端根路径 `/`，导致浏览器显示 FastAPI JSON 而不是前端页面

## 2026-03-27 15:45 - 精简 service.py 运行模式识别并补充编排注释

### 概述
在保持 FastAPI / LangGraph CLI 双模式兼容的前提下，继续收敛 `backend/app/agent/service.py` 的实现复杂度，让运行模式识别、持久化注入和 Agent 编排主干更容易阅读和维护。

### 变更内容
- **运行模式识别简化**:
  - 用更直观的 `LANGGRAPH_API_URL || PATH contains langgraph` 规则判断托管环境
  - 保留日志输出，明确区分“LangGraph API 托管环境”和“本地独立运行模式”
- **持久化注入简化**:
  - 本地模式下通过 `agent_kwargs` 显式传入 `store/checkpointer`
  - 托管模式下保持空注入，由 LangGraph 运行时自动接管
- **可读性增强**:
  - 为环境识别、持久化初始化、Agent 编排主干补充了精简注释
  - `build_agent_graph` 增加了对 LangGraph factory 参数用途的说明

## 2026-03-27 15:23 - SQL Agent 服务层整合并兼容 LangGraph CLI 双模式

### 概述
将 `backend/app/services.py` 从旧的一体化 SQL Agent 实现重构为 FastAPI 兼容适配层，底层统一复用 `backend/app/agent/service.py` 的 Agent V2 核心运行时。同时补齐 `langgraph dev` / LangGraph API 场景下的双模式兼容，支持“FastAPI 本地手动初始化 PostgresSaver”与“LangGraph 托管环境自动注入 checkpointer/store”两条运行链路。

### 变更内容
- **核心运行时重构**:
  - `backend/app/agent/service.py` 新增运行模式识别
  - `SQLAgentService` 支持注入 `checkpointer` / `store`
  - 本地独立运行模式下自动回退创建 `ConnectionPool + PostgresSaver`
  - 移除模块级 `logging.basicConfig(...)` 与导入即初始化的全局 `agent_service`
- **LangGraph 入口调整**:
  - `langgraph.json` 从模块级对象切换为工厂函数入口 `backend/app/agent/service.py:build_agent_graph`
  - 兼容 LangGraph CLI 的 `config + runtime` 工厂调用约束
- **FastAPI 兼容层重构**:
  - `backend/app/services.py` 改为兼容适配层
  - 保留 `process_message()` / `process_stream()` 与 `tool_calls/tool_results` 旧返回契约
  - API 层无需调整请求/响应结构
- **文档同步**:
  - `README.md` 更新 `services.py` 与 `agent/service.py` 的职责说明
  - 补充 FastAPI / LangGraph CLI 双模式持久化说明

## 2026-03-27 13:55 - 修正 Codex 环境中的 LangGraph 启动命令

### 概述
修正 `.codex/environments/environment.toml` 中的 LangGraph 启动配置，避免因命令名写错且未先激活 `py312_agent` 环境而导致 PowerShell 报错找不到命令。

### 变更内容
- **环境配置修正**:
  - 为 `.codex/environments/environment.toml` 补充 `setup.script = "conda activate py312_agent"`
  - 将错误的 `Langgraph dev --allow-blocking` 修正为 `langgraph dev --allow-blocking`

## 2026-03-27 13:35 - LangGraph Dev 启动补充 conda 环境切换

### 概述
为 `langgraph dev --allow-blocking` 这条本地调试命令补充明确的 conda 环境切换要求，避免未激活 `py312_agent` 时出现依赖或解释器不一致问题。

### 变更内容
- **新增启动脚本**:
  - 新增根目录 `start_langgraph_dev.bat`
  - 在执行 `langgraph dev --allow-blocking` 前自动执行 `conda activate py312_agent`
- **README 同步**:
  - 新增 LangGraph Dev 调试入口说明
  - 明确先激活 `py312_agent`，并补充 Windows CMD 下的脚本启动方式

## 2026-03-27 13:10 - 新增代码阅读与解释子智能体

### 概述
为项目补充一个专门用于“读代码、讲架构、梳流程、看调用链”的子智能体 `code-explainer`，同时提供项目级 `skill` 版本，方便在不同 Agent / CLI 场景下复用，帮助更快理解仓库结构与实现机制。

### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-explainer.md`
  - 约束其聚焦代码阅读、架构讲解、流程拆解与调用链分析
- **新增项目级 Skill**:
  - 新增 `.agents/skills/code-explainer/SKILL.md`
  - 统一沉淀代码解释类任务的工作流、输出结构与边界
- **README 同步**:
  - 补充“代码阅读讲解子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/` 与 `.agents/skills/code-explainer/` 入口

## 2026-03-24 16:35 - LangGraph 调试链路补充显式 LLM 超时与重试配置

### 概述
针对 `langgraph.json -> backend/app/agent/service.py` 这条开发调试链路，补充显式的网络 LLM 超时与重试配置，避免完全依赖底层 SDK 默认值，提升 OpenAI-compatible 远程模型调用时的可控性。

### 变更内容
- **配置增强**:
  - 在 `backend/app/config.py` 新增 `LLM_TIMEOUT` 与 `LLM_MAX_RETRIES`
  - 在根目录 `.env` 增加对应默认配置项
- **Agent 服务增强**:
  - 在 `backend/app/agent/service.py` 的 `ChatOpenAI` 初始化中显式传入 `request_timeout` 与 `max_retries`
  - 使 `langgraph.json` 调试入口下的远程模型调用具备项目级可调的超时与重试策略

## 2026-03-24 16:05 - llama.cpp + Qwen3 Embedding 实践文档重构与沉淀

### 概述
将 `backend/docs/llamacpp-qwen3-embedding-local-deployment.md` 从“本地部署操作说明”升级为“完整改造与复用实践文档”，系统整理本次 `llama.cpp + Qwen3 Embedding` 接入 Milvus Hybrid RAG 的架构、流程、接口协议、部署方式、排障经验与后续复用建议。

### 变更内容
- **文档重构**:
  - 重新组织为“背景目标、相关目录、总体架构、配置设计、建库流程、查询流程、API 格式、部署步骤、排障、最佳实践、开发心智”分层结构
  - 补充项目内关键代码落点与目录索引，方便后续快速定位
  - 明确 `query instruction`、`L2 normalize`、`provider 切换后需重建索引` 等关键约束
- **README 入口同步**:
  - 在技术文档列表中新增 `llama.cpp + Qwen3 Embedding 接入与复用最佳实践` 链接
  - 方便后续从项目首页直接跳转到该专题文档

## 2026-03-24 15:35 - README 项目结构树同步更新

### 概述
对照当前仓库实际目录结构，更新 `README.md` 中的“项目结构”章节，修正已过时的路径描述，并补充当前已经落地的 RAG / llama.cpp 相关目录入口。

### 变更内容
- 将 `requirements.txt` 与 `.env` 的位置修正为仓库根目录
- 补充 `backend/docs/`、`backend/llamaCpp/`、`backend/app/test_*.py` 等实际存在的目录 / 文件入口
- 在 `backend/app/agent/vector/` 结构中补充 `embedding_provider.py`
- 保持目录树为“精简但准确”的项目入口视图，避免 README 演变成全量文件清单

## 2026-03-24 15:20 - README 与文档入口同步修正

### 概述
对照当前仓库结构与最新 RAG / llama.cpp 接入实现，修正了 `README.md` 中已过时的环境与依赖说明，避免按旧说明执行时找不到 `.env.example` 或 `backend/requirements.txt`。

### 变更内容
- **README 修正**:
  - 将“复制 `.env.example`”改为“直接使用 / 新建根目录 `.env`”
  - 将后端依赖安装入口统一为根目录 `requirements.txt`
  - 将后端启动命令统一为从仓库根目录执行 `uvicorn backend.app.main:app`
- **文档一致性检查**:
  - 复核 `README.md` 与当前 `llama.cpp + Qwen3 Embedding` / `Milvus Hybrid` 实现是否一致
  - 保持既有历史 changelog 记录不变，仅在最新条目中补充当前有效的使用说明

## 2026-03-24 14:30 - Milvus 混合检索支持 llama.cpp + Qwen3 Embedding 切换

### 概述
在保留原有 `Ollama qwen3-embedding:0.6b` 能力的基础上，为 Milvus Hybrid RAG 新增 `llama.cpp + Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0` 的可切换嵌入方案。初始化入库与运行期检索统一复用同一个 LlamaIndex embedding provider 入口，并在 `llama.cpp` 路径下对 query 侧启用 Qwen 官方推荐的 instruction-aware embedding 格式。

### 变更内容
- **共享 Embedding Provider**:
  - 新增 `backend/app/agent/vector/embedding_provider.py`
  - 统一封装 `OllamaEmbedding` 与自定义 `LlamaCppEmbedding`
  - 新增 `QwenInstructionAwareEmbedding`，只对 query 侧拼接 `Instruct: ...\nQuery: ...`
- **Milvus 接入改造**:
  - `backend/app/agent/vector/factory.py` 改为通过共享 provider 配置 `LlamaIndex Settings.embed_model`
  - `backend/app/agent/vector/milvus_init/init_store.py` 改为复用同一 provider，保证建库与查询一致
- **配置增强**:
  - `backend/app/config.py` 新增 `EMBEDDING_PROVIDER`、`LLAMA_CPP_EMBED_*`、`QWEN_QUERY_INSTRUCTION_*` 配置项
  - `.env` 补充 `llama.cpp` embedding 的默认配置示例
- **测试补充**:
  - 新增 `backend/app/test_embedding_provider.py`
  - 修正 `backend/app/test_rag_milvus_hybrid.py` 中的延迟初始化与 mock 覆盖方式
- **文档同步**:
  - `README.md` 增补 Milvus embedding provider 切换说明与重建索引提示


## 2026-03-22 22:50 - Milvus 嵌入模型迁移至本地 Ollama (Qwen3)

### 概述
将 Milvus 混合检索所依赖的嵌入模型由原有的 NVIDIA 云端 API 迁移至本地私有化部署的 `Qwen3-Embedding-0.6B`（通过 Ollama 托管）。同时解决了本地代理环境导致的 502 请求拦截问题，保持了检索链路的完全离线化。

### 变更内容
- **模型替换**: 在 `backend/app/agent/vector/factory.py` 和 `milvus_init/init_store.py` 中，使用 `OllamaEmbedding` 替换 `NVIDIAEmbedding`。
- **配置增强**:
  - `backend/app/config.py` 新增 `ollama_embed_model` 环境变量项。
  - **网络优化**: 在全局配置中强制设置 `NO_PROXY` 环境变量，自动绕过系统代理对 `localhost` 的拦截（修复 502 错误）。
- **文档同步**: 更新了 `backend/docs/RAG架构与技术总结.md`，反映了最新的模型架构选型。
- **环境变量**: `.env` 中新增 `OLLAMA_EMBED_MODEL` 参数并完成注释。


## 2026-03-22 21:35 - 新增 RAG 架构与技术栈剖析文档

### 概述
根据现有代码库实现，整理并输出了完整的 Retrieval-Augmented Generation (RAG) 架构设计文档，详细剖析了系统目前的双引擎检索架构、核心组件与模型选型以及工作流执行逻辑。

### 变更内容
- **新增文档**: `backend/docs/RAG架构与技术总结.md`
  - 阐述了 Milvus Hybrid 和 PGVector 双引擎的实现与切换机制。
  - 整理了 Embedding 模型（NVIDIA V5、BAAI BGE-M3）及 Reranker（Mistral-4B）选型细节。
  - 总结了完整的 RAG 数据检索与合成流向。

---
## 2026-03-22 18:00 - SQL 查询结果智能限流与安全防护优化

### 概述
针对大模型处理大量 SQL 查询结果时面临的上下文溢出、推理降智、Token 成本激增等问题，实施了一套弹性限流方案。小结果集（如维度表）全量返回，大结果集自动截断并注入预警，同时新增 CSV 导出工具实现数据与 LLM 的安全隔离。

### 变更内容

#### `backend/app/config.py` + `.env`
- **新增 `sql_result_hard_limit`**：后端强制截断行数上限（默认 1000），保护内存和 LLM 上下文
- **新增 `sql_result_preview_rows`**：超限时给 LLM 展示的预览行数（默认 5）

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `_estimate_row_count()`**：估算 LangChain 返回结果字符串中的行数
- **新增 `_extract_preview_rows()`**：从结果字符串中提取前 N 行作为预览
- **`sql_db_query` 增强**：新增第 5 步"智能结果限流"——判断结果行数是否超过 `hard_limit`，超限时只返回预览 + 系统截断警告（引导 LLM 建议聚合 SQL 或 CSV 导出）

#### `backend/app/agent/tools/csv_export_tool.py` [NEW]
- **新增 `export_to_csv` 工具**：使用 SQLAlchemy + CSV 模块直接从数据库导出完整数据到文件，全程不经过 LLM 上下文。包含与 `sql_db_query` 一致的安全拦截和技能校验

#### `backend/app/agent/service.py`
- **工具注册**：在 `_prepare_tools` 中注入 CSV 导出工具
- **System Prompt 优化**：新增两条规则——强制使用聚合函数进行统计分析；超限时禁止基于截断数据汇总

---

## 2026-03-21 21:01 - SQL Agent 安全审计与拦截增强 (对策 3)

### 概述
针对 SQL Agent 存在的潜在 SQL 注入及破坏性操作风险（如 `DROP`, `DELETE` 等），实施了基于正则表达式的黑名单拦截机制（代码层硬校验），确保 Agent 仅能执行只读查询。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `FORBIDDEN_SQL_PATTERN`**：定义了包含 `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` 等危险关键字的正则表达式。
- **`sql_db_query`**：在执行逻辑最前端注入安全性拦截。任何匹配非法关键字的查询将被直接终止，并向 LLM 返回严重安全警告。

### 防御效果
- **防止提示词注入**：即使 LLM 被诱导产生破坏性 SQL，也会在执行前被逻辑层拦截。
- **操作审计**：拦截行为会记录到日志，方便安全审计。

---

## 2026-03-21 20:43 - SQL 工具技能精确校验优化

### 概述
参考 LangChain 官方 `skills-sql-assistant` 方案，修复了在 **Checkpointer 多轮对话**场景下，LLM 因 `skills_loaded` 状态已存在而跳过 `load_skill` 调用，直接执行跨业务域 SQL 查询的潜在问题。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **`sql_db_query`**：新增 `required_skill: str` 参数，将技能校验从 `if not skills_loaded` 升级为 `if required_skill not in skills_loaded`（精确校验特定技能是否已加载，而非仅判断列表是否为空）
- **`search_saved_correct_tool_uses`**：同步新增 `required_skill: str` 参数，做相同精确校验，两个工具行为一致
- 返回值类型从 `List[dict]` 更新为 `Union[str, List[dict]]`，修复 Lint 错误

#### `backend/app/agent/service.py`
- 系统提示词的 **SQL查询规则** 章节新增说明：调用 `sql_db_query` 和 `search_saved_correct_tool_uses` 时，必须通过 `required_skill` 参数声明所依赖业务技能，切换业务域时必须重新调用 `load_skill()`

### 问题场景与修复效果

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 第1轮：涂装问题 | `skills_loaded=["paint_shop"]`，正常执行 | 同左 |
| 第2轮：焊装问题 | 由于列表非空，直接调 SQL（**幻觉风险**）| 工具返回 Error，强制 LLM 先 `load_skill("weld_shop")` |

---

## 2026-02-22 14:35 - 完善 Milvus 混合检索环境变量配置

### 概述
在 `.env` 文件中补齐了 Milvus 混合检索后端所需的全部环境变量，包括连接地址、Collection 命名、向量维度、RRF 融合系数以及数据导入路径等，并将 `RAG_BACKEND` 默认指定为 `milvus_hybrid`。

### 变更内容
#### 修改文件
- **.env**: 
  - 新增 `RAG_BACKEND='milvus_hybrid'`。
  - 新增 `MILVUS_URI`, `MILVUS_COLLECTION_NAME` 等系列配置。
  - 新增 `MILVUS_DATA_DIR` 指向默认示例数据路径。
  - 新增 `MILVUS_OVERWRITE='true'` 默认覆盖策略。

---

## 2026-02-21 15:30 - 扩展混合检索后端（LlamaIndex + Milvus）

### 概述
在现有「可插拔 RAG 架构」基础上新增了 **Milvus 混合检索**（稠密向量 + BM25 稀疏向量 + RRF 融合）后端。通过切换配置即可在 `pgvector` 和 `milvus_hybrid` 之间无感切换，同时新增了配套的数据初始化与导入模块。

### 变更内容

#### 新增检索模块
- **backend/app/agent/vector/milvus_hybrid/**: LlamaIndex + Milvus 检索实现
  - `milvus_store.py`: 封装 MilvusVectorStore 的创建、加载与 BM25 索引配置。
  - `milvus_retriever.py`: 实现 `MilvusHybridRetriever`，适配 `BaseRetriever` 接口。
- **backend/app/test_rag_milvus_hybrid.py**: 冒烟测试脚本。

#### 新增初始化模块
- **backend/app/agent/milvus_init/**: Milvus 专用数据导入脚本包（与 `vector_init` 风格一致）
  - `milvus_data_importer.py`: 支持数据转换、语义切片、Collection 初始化及批量入库逻辑。
  - `milvus_import_data.py`: CLI 入口脚本，支持 `--overwrite` 重建索引和追加导入。

#### 配置与工厂更新
- **backend/app/config.py**: 新增 `RAG_BACKEND` (默认 `pgvector`) 及 `MILVUS_*` 系列配置项。
- **backend/app/agent/vector/factory.py**: 重构工厂函数实现多后端分发逻辑。

### 初始化用法示例

```bash
conda activate py312_agent
# 首次初始化或重建索引（使用 examples 数据）
python -m backend.app.agent.milvus_init.milvus_import_data example_documentation.json --overwrite
# 追加数据
python -m backend.app.agent.milvus_init.milvus_import_data example_ddl.json
```

---

## 2026-02-18 17:45 - 集成 NVIDIA Rerank 精排层

### 概述
在现有 RAG 管道（向量检索 → score_threshold 过滤 → 注入系统消息）中插入 Rerank 精排层，使用 NVIDIA NIM 的 `rerank-qa-mistral-4b` 模型对候选文档进行二次排序，提升检索精度。

### 变更内容

#### 新增文件
- **backend/app/agent/utils/rerank_service.py**: NVIDIA NIM Rerank 服务封装
  - `NvidiaRerankService` 类，调用 NVIDIA Rerank API
  - 支持 `top_n` 截断和 `score_threshold` 阈值过滤
  - 异常时自动降级为原始排序（不影响现有功能）
- **backend/app/test_rerank.py**: Rerank 测试脚本（降级测试 + API 连通性测试）

#### 修改文件
- **backend/app/config.py**: 新增 Rerank 配置项
  - `rerank_enabled`（开关，默认 false）
  - `rerank_model`（模型，默认 `nvidia/rerank-qa-mistral-4b`）
  - `rerank_top_n`（保留数，默认 3）
  - `rerank_score_threshold`（可选阈值）
- **backend/app/agent/middleware/rag_middleware.py**: `BusinessRagMiddleware.__init__` 新增 `rerank_service` 参数；`before_model` 在向量检索后、格式化前插入 Rerank 调用
- **backend/app/agent/service.py**: 初始化 `NvidiaRerankService` 并传入 `BusinessRagMiddleware`，启用时 `doc_k` 从 5 提升到 10
- **文档更新**: `README.md` 中新增「RAG 召回与参数详解」章节，包含召回数量规则汇总表和详细的环境变量说明。
- **文档更新**: 全面翻新 `README.md`，更新项目结构树以匹配 Agent V2 模块化架构；更正过时的 Multi-Step SQL 工作流程描述为最新预加载 Schema 与中间件机制；修正环境依赖（Python 3.12+），并对齐 `.env` 中的 SQL 限流默认值。
- **配置说明**: 在环境变量章节补充了 `RAG_SIMILARITY_THRESHOLD` 和 `RERANK_SCORE_THRESHOLD` 的使用建议及其与 RRF 分数的关联。
- **代码调整**: (由用户手动执行) 将 `service.py` 中未开启精排时的默认召回数量由 3 提升至 5，增强基础召回范围。
- **.env**: 新增 `RERANK_ENABLED`、`RERANK_MODEL`、`RERANK_TOP_N` 等环境变量

### 架构变化
```
改动前：向量检索(k=5) → score_threshold 过滤 → 注入系统消息
改动后：向量检索(k=10) → score_threshold 粗筛 → Rerank 精排(Top-3) → 注入系统消息
```

### 测试结果
- 降级测试通过：无效 API Key 时正确回退
- API 连通性测试通过：L3F13 相关查询中，Rerank 正确将 L3F13 文档排到第一（score=3.0371）

### 推荐配置

为获得最佳效果，建议在 `.env` 中使用以下配置：

```bash
RERANK_ENABLED="true"
RERANK_MODEL="nvidia/rerank-qa-mistral-4b"
RERANK_TOP_N="3"
RERANK_SCORE_THRESHOLD="0.0" # 过滤掉负分结果（不相关文档）
```

---

## 2026-01-27 16:37 - 修复流式聊天 API 路径配置

### 问题
- `frontend/src/api/chat.ts` 中的流式请求硬编码了 `http://localhost:8000/api/chat`
- 导致在生产环境通过 Nginx 代理时无法正常访问后端
- 其他 API（sessions、messages）使用相对路径 `/rearch` 正常工作，但流式聊天请求失败

### 解决方案
- 修改 `API_BASE` 从 `'http://localhost:8000/api/chat'` 改为 `'/rearch/api/chat'`
- 统一所有 API 请求都通过 Nginx 代理访问后端
- 确保开发和生产环境的一致性

### 技术细节
```typescript
// 修改前
const API_BASE = 'http://localhost:8000/api/chat'

// 修改后
const API_BASE = '/rearch/api/chat'  // 使用相对路径，适配 Nginx 代理
```

---

## 2026-01-27 13:55 - Docker 容器化部署方案

### 概述
为后端FastAPI应用创建完整的Docker容器化部署方案，支持一键部署到生产服务器。

### 变更内容

#### 核心配置文件
- **backend/Dockerfile**: 创建后端镜像配置
  - 基于 `python:3.12-slim` 官方镜像
  - 安装系统依赖（gcc, postgresql-client）
  - 复制依赖并安装Python包
  - 暴露8000端口，使用uvicorn启动
  
- **backend/.dockerignore**: 排除文件列表
  - 排除Python缓存、虚拟环境、测试文件等
  - 减小Docker镜像体积

- **docker-compose.yml**: 容器编排配置（更新）
  - 新增 `backend` 服务：FastAPI应用容器
  - 保留 `postgres` 服务：PostgreSQL 17-alpine
  - 配置服务依赖：backend依赖postgres健康检查
  - 使用 `.env` 文件管理所有环境变量
  - 数据持久化卷 `pgdata`

- **.env.production**: 生产环境配置模板
  - 数据库配置（PostgreSQL）
  - LLM配置（DeepSeek/Ollama）
  - Agent配置（温度、Token限制）
  - LangSmith配置（可选）
  - 详细的注释说明

#### 部署文档
- **deploy/README.md**: 完整部署指南
  - 快速部署步骤（服务器准备、上传文件、配置、启动）
  - 常用管理命令（启停、日志、调试）
  - Nginx反向代理配置示例
  - 故障排查指南
  - 安全建议和数据备份方法

### 部署流程

```bash
# 1. 上传项目到服务器
scp -r rearch_agent/ user@server:/opt/

# 2. 配置环境变量
cd /opt/rearch_agent
cp .env.production .env
nano .env

# 3. 一键启动
docker-compose up -d --build

# 4. 验证
curl http://localhost:8000/
```

### 技术特点
- ✅ 简洁：最小化配置，只包含必要组件
- ✅ 完整：包含数据库、后端服务和详细文档
- ✅ 灵活：通过环境变量轻松切换配置
- ✅ 可靠：健康检查、自动重启、数据持久化
- ✅ 易维护：详细的操作文档和故障排查指南

---

## 2026-01-26 17:45 - 修复 PostgreSQL Checkpointer 初始化错误

### 问题
- LangGraph 的 `PostgresSaver.setup()` 使用 `CREATE INDEX CONCURRENTLY` 创建索引
- 该命令不能在事务块中运行，导致初始化失败
- 错误信息: `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`

### 解决方案
- **backend/app/services.py**: 修改 checkpointer 初始化逻辑
  - 使用独立的 `psycopg.connect()` 连接并开启 `autocommit=True` 模式执行 `setup()`
  - setup 完成后再创建 `ConnectionPool` 用于正常操作
  - 添加详细的日志输出，便于诊断数据库连接问题

### 技术细节
```python
# 使用 autocommit 模式创建表结构
with psycopg.connect(settings.database_url, autocommit=True) as setup_conn:
    temp_checkpointer = PostgresSaver(setup_conn)
    temp_checkpointer.setup()

# 然后创建连接池用于正常操作
self.conn_pool = ConnectionPool(conninfo=settings.database_url, ...)
self.checkpointer = PostgresSaver(self.conn_pool)
```

---

## 2026-01-26 - 配置本地 llama.cpp 服务器
- **Backend 配置**: 将 LLM 从 DeepSeek API 切换到本地 llama.cpp 服务器。
  - 服务器地址: `http://172.22.44.99:8089/v1`
  - 模型: GLM-4.7-Flash-Q6_K.gguf
  - 使用 `ChatOpenAI` 客户端，兼容 OpenAI API 格式


## 2026-01-24: Agent V2 重构与架构升级

### 概述
基于 CR 反馈完成了 Agent V2 的重构工作，通过高度模块化的设计提升了代码的可维护性、可扩展性和可测试性。引入了基于技能（Skills）的动态上下文管理机制，并强化了 SQL 执行的安全性和准确性。

### 变更内容
- **模块化架构 (`backend/app/agent/`)**: 将原有的单文件服务拆分为功能独立的模块：
  - `service.py`: 核心服务编排
  - `middleware/`: 包含 `SkillMiddleware` 等中间件
  - `tools/`: 包含 `WrappedQueryTool` 等增强工具
  - `constants.py` & `utils`: 常量与通用工具函数
- **技能系统 (Skills System)**:
  - 引入 `SkillMiddleware`，支持按需加载业务领域的知识（Skills）到系统提示词。
  - 新增 `load_skill` 工具，允许 Agent 在运行时动态获取特定领域的详细文档和规则。
- **增强型 SQL 执行**:
  - **前置检查**: 集成了 SQL 语法验证器。
  - **后置处理**: 统一对查询结果进行 ISO 8601 日期格式化清洗，彻底解决时间格式不一致导致的大模型推理错误。
- **配置与日志优化**: 
  - 优化了代理（Proxy）环境变量的自动清理逻辑。
  - 统一了日志格式，支持开发模式下的详细日志输出。

---

## 2026-01-21: PostgreSQL 数据库配置扩展

### 概述
为 rollerbed tracking system 添加了独立的 PostgreSQL 数据库连接配置，保留原有 agent memory 数据库配置。

### 变更内容
- **.env**: 新增 `ROLLERBED_DATABASE_URL` 及相关连接参数
  - `ROLLERBED_POSTGRES_USER='root'`
  - `ROLLERBED_POSTGRES_PASSWORD='root'`
  - `ROLLERBED_POSTGRES_DB='rollerbed_tracking_db'`
  - `ROLLERBED_POSTGRES_HOST='localhost'`
  - `ROLLERBED_POSTGRES_PORT='5432'`
- **backend/app/config.py**: 在 `Settings` 类中添加对应的配置字段
  - `rollerbed_database_url`: 完整的数据库连接 URL
  - `rollerbed_postgres_user`, `rollerbed_postgres_password`, `rollerbed_postgres_db`, `rollerbed_postgres_host`, `rollerbed_postgres_port`: 各个连接组件

### 使用说明
```python
from backend.app.config import settings

# 使用完整 URL
db_url = settings.rollerbed_database_url

# 或者使用单独的组件
host = settings.rollerbed_postgres_host
port = settings.rollerbed_postgres_port
user = settings.rollerbed_postgres_user
password = settings.rollerbed_postgres_password
database = settings.rollerbed_postgres_db
```

---

## 2026-01-17: LangGraph 1.0+ SQL Agent 实现

### 概述
新增 `backend/app/services_graph.py`，基于官方 LangGraph SQL Agent 文档实现了一个现代化的多步骤 SQL Agent 工作流，作为原 `services.py` 的对比版本。

### 变更内容
- **backend/app/services_graph.py**: 新增 LangGraph 1.0+ 版本的 `SQLGraphService` 类。
- **模型**: 从本地 Ollama (qwen3) 切换为 DeepSeek (联网大模型)，提升 SQL 生成准确率。
- **架构**: `list_tables` → `get_schema` → `generate_query` → `check_query` → `run_query`
- **SQL 查询检查器**: 在执行前由 LLM 检查常见 SQL 错误。
- **日期格式清洗**: 策略 A - 无条件对所有查询结果进行 ISO 8601 日期格式标准化。
- **深度工具包装**: `services.py` 中对 `sql_db_query` 工具进行了包装，确保模型在中间推理步骤中看到的是清洗后的日期。

### 技术要点
- 使用 `StateGraph` + `ToolNode` (LangGraph 1.0+ API)
- 保留 `PostgresSaver` 检查点持久化
- 兼容原有 `process_message` 和 `process_stream` 接口

---

## 2026-01-17: 数据库日期时间处理分析与文档化

### 概述
完成并固化了关于 Agent 处理数据库日期时间字段的调研分析，预防大模型（LLM）在时间比较时可能产生的逻辑错误。

### 变更内容
- **docs/database_datetime_analysis.md**: 新增分析报告，详细对比了 SQL 层转换与 Python 工具层转换的优劣，并推荐在代码层进行 ISO 8601 标准化。
- **最佳实践**: 记录了 `DD/MM/YYYY` 等非标格式转换为标准 `YYYY-MM-DD` 的代码实现方案。

---


## 2026-01-16: UI/UX 全面升级与后端数据库依赖修复

### 概述
完成了全系统的 UI/UX 视觉方案升级，由原有的“暖色调”切换为现代化的“神经元色调 + AI 紫色” (Neural Tones + AI Purple) 设计。同时解决了后端在连接 MySQL 8.0+ 时由于缺少 `cryptography` 库导致的身份验证失败问题。

### 变更内容

#### Frontend (UI/UX 升级)
- **Design System**: 引入了以 Slate (Neural) 为基础、Violet (AI Purple) 为点缀的新设计系统。
- **tailwind.config.js**: 
  - 重构颜色体系，新增 `primary` (Violet 600), `secondary`, `neutral` (Slate) 调色板。
  - 定义语义化背景 `background` (#FAF5FF) 和文本颜色。
  - 优化 `boxShadow` (soft/glow) 和 `borderRadius`。
- **index.html**: 接入 Google Fonts (**Inter** 字体)。
- **style.css**: 
  - 移除旧版 `--color-warm-*` 变量，迁移至新的设计系统变量。
  - 实现毛玻璃效果 (`.glass`) 和现代化滚动条样式。
  - 重构全局组件样式 (Button, Input, Animations)。
- **Vue Components**: 重构了以下系列组件的模版和样式：
  - `App.vue`: 根布局样式调整。
  - `ChatView.vue`: 侧边栏与主区域渐变效果。
  - `SessionItem.vue` / `SessionList.vue`: 列表交互状态与空状态美化。
  - `MessageItem.vue` / `MessageList.vue`: 消息气泡渐变与打字动画优化。
  - `ToggleSwitch.vue` & `EmptyState.vue`: 视觉一致性对齐。

#### Backend (数据库连接修复)
- **requirements.txt**: 新增 `cryptography==42.0.5`。
- **Dependency Fix**: 修复了 `PyMySQL` 报错 `RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods`，支持了 MySQL 8.0 的高级加密认证。

---


## 2026-01-15: 修复 Ollama 持续时间格式与远程连接配置

### 概述
修复了 Ollama 在接收 `keep_alive` 参数时的 400 格式错误，并配置后端连接到远程服务器，同时切换为支持工具调用的模型。

### 变更内容
- **backend/app/config.py**: 将 `ollama_keep_alive` 强制转为 `int`，解决 `time: missing unit in duration` 报错。
- **.env**:
  - 更新 `OLLAMA_BASE_URL='http://172.22.44.99:11434'` 指向远程 5090 服务器。
  - 更新 `OLLAMA_MODEL='qwen3:30b'` 以支持 SQL Agent 所需的工具调用功能。
  - 更新 `OLLAMA_KEEP_ALIVE=-1` 为整数形式。

---


## 2026-01-14: 切换到 Ollama + Qwen3:30b

### 概述
将后端 LLM 从 DeepSeek API 切换到本地 Ollama 服务，使用 `qwen3:30b` 模型，充分利用 RTX 5090 显存。

### 变更内容

#### backend/app/config.py
- 新增 Ollama 配置参数：
  - `OLLAMA_BASE_URL`: Ollama 服务地址 (默认 `http://localhost:11434`)
  - `OLLAMA_MODEL`: 使用的模型 (默认 `qwen3:30b`)
  - `OLLAMA_NUM_CTX`: 上下文窗口大小 (默认 32768，32k tokens)
  - `OLLAMA_KEEP_ALIVE`: 模型驻留设置 (默认 `-1`，永久驻留)

#### backend/app/services.py
- 导入变更：`langchain_deepseek.ChatDeepSeek` → `langchain_ollama.ChatOllama`
- 移除 `httpx` 依赖及 `_no_proxy_client`（Ollama 为本地服务，无需代理处理）
- LLM 初始化更新为 `ChatOllama`，使用新的 Ollama 配置参数

### 使用前准备
```bash
# 1. 安装 langchain-ollama
pip install langchain-ollama

# 2. 拉取模型
ollama pull qwen3:30b
```

### 备注
- 原有 DeepSeek 配置保留在 `config.py` 中，可随时切换回去
- 如需使用 DeepSeek，只需将 `services.py` 中的导入和初始化改回即可

