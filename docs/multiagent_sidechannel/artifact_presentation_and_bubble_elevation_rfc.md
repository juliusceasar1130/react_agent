# 多智能体工件展示与主气泡透出（Artifact Bubble-Up）架构研究报告与 RFC

> **文档版本**：v1.0  
> **文档位置**：`docs/multiagent_sidechannel/artifact_presentation_and_bubble_elevation_rfc.md`  
> **归属专区**：`docs/multiagent_sidechannel/`（多智能体侧信道与工件体系架构知识库）  
> **面向受众**：系统架构师、前端开发工程师、LLM/Agent 算法工程师、产品体验设计师  
> **核心议题**：解决多智能体（Supervisor-Worker）分层架构下，子智能体产出的图表、CSV 下载文件及数据表格被深埋在子卡片内部导致的用户体验与交互摩擦问题，确立行业级工件展示范式。

---

## 1. 问题背景与需求深度对齐

### 1.1 现象还原与核心痛点
在当前多智能体协同（Supervisor + Worker）架构中，用户发起“请帮我统计上周各车型缺陷并画出趋势图”、“导出 CSV 数据文件”等指令：
1. **调度链路**：主智能体（Supervisor）将任务路由派发给 SQL 子智能体（`sql_domain_agent`）；
2. **执行链路**：子智能体调用 `sql_db_query`、`build_chart_artifact` 或 `export_to_csv` 完成业务计算与落盘；
3. **前端渲染层级（当前设计）**：
   - 前端通过 `subagentsList` 将子智能体的思考、工具调用与产生的工件统一打包渲染在 `SubagentCard.vue` 内部；
   - 主气泡 `MessageItem.vue` 中设置了 `v-if="subagentsList.length === 0 && chartSpecsList.length > 0"` 和 `v-if="subagentsList.length === 0 && fileExportsList.length > 0"` 的硬性排他条件；
   - **直接后果**：一旦派发了子智能体，生成的图表、CSV 下载卡片在主消息气泡中**完全不显示**，用户必须手动点击“展开详情”、向下翻阅工具调用链才能找到图表和下载按钮。

```
【当前层级（存在 UX 摩擦）】                     【期望层级（行业最佳实践）】
┌──────────────────────────────────────┐        ┌──────────────────────────────────────┐
│  主消息气泡 (MessageItem)             │        │  主消息气泡 (MessageItem)             │
│  - 主 Agent 总结性文本回复           │        │  - 主 Agent 总结性文本回复           │
│                                      │        │                                      │
│  ┌────────────────────────────────┐  │        │  ★ 核心交付物 (第一视口直达)          │
│  │ 子智能体折叠卡片 (SubagentCard) │  │        │  - 📊 交互式 ECharts 图表卡片        │
│  │  - 思考链 (Reasoning)          │  │        │  - 📥 CSV 下载按钮 / 预览卡片        │
│  │  - 工具调用序列 (Tool Calls)   │  │        │  - 📋 SQL 数据表格 (默认折叠)        │
│  │    ├─ sql_db_query             │  │        │                                      │
│  │    ├─ build_chart_artifact     │  │        │  ┌────────────────────────────────┐  │
│  │    │   └─ [图表埋在里面] ❌     │  │        │  │ 执行过程与调试溯源 (按需展开)    │  │
│  │    └─ export_to_csv            │  │        │  │ - 子智能体调度与工具链 Trace   │  │
│  │        └─ [下载按钮埋在里面] ❌ │  │        │  └────────────────────────────────┘  │
│  └────────────────────────────────┘  │        └──────────────────────────────────────┘
└──────────────────────────────────────┘
```

### 1.2 用户心智模型（Mental Model）与概念区分
用户在使用智能体时，对界面元素有着明确的**认知分层**：

| 维度 | 过程溯源（Process Trace） | 最终交付物（Deliverable Artifact） |
| :--- | :--- | :--- |
| **典型载体** | 思维链（CoT）、工具入参、中间 SQL、调试信息 | ECharts 图表、CSV 导出文件、清洗后的聚合数据表 |
| **用户关注点** | “它是怎么算出来的”（仅在怀疑结果或排查时关心） | “算出来的结论是什么、文件在哪下载”（最核心关注点） |
| **视觉呈现要求** | 默认收起、低饱和度、紧凑排版、辅助定位 | **第一视口直接呈现、高交互性、免翻找、直达操作** |
| **当前状态** | 占据外层子卡片主体 | 被嵌套在过程内部，层级被倒置 |

> **核心诉求总结**：**“过程归过程（收起），交付归交付（透出）”**。用户无需探索子智能体内部的执行细节，即可在主气泡的第一视口直接看到图表、点击下载 CSV 或预览数据。

---

## 2. 行业顶级 Agent 系统工件展现模式深度对比

我们对业界主流的大模型对话与多智能体系统（OpenAI、Anthropic、Perplexity、Microsoft Copilot 等）进行了横向对比：

| 平台 / 系统 | 架构协同方式 | 过程信息呈现（Trace） | 核心工件呈现（Artifact） | 用户心智与交互流 |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI ChatGPT**<br>*(Code Interpreter / ADA)* | 单/多工具调用（Python 执行环境） | 胶囊按钮 `[>_ Analyzed]` 紧凑收起，点击展开代码与终端输出 | 生成的图表（Matplotlib/Plotly）与生成的 CSV/Excel 下载链接**直接浮现在主回答气泡正文下方** | 极其流畅：用户只看正文与图表，想看 Python 代码才去点胶囊 |
| **Anthropic Claude**<br>*(Claude Artifacts)* | 单/多 Agent 工具产出 | 思考块（Thinking Block）与 Tool Call 折叠在消息正文内 | 屏幕右侧独立开辟 **Artifact 宽屏工作台（Dual-Pane）**，左侧对话仅放交互引用微卡 | 生产力极高：图表/代码/文档在右侧独立交互、导出、编辑 |
| **Perplexity Pro**<br>*(Computational Engine)* | 检索 + 计算多步骤 Agent | 顶部横向进度条 `[Searched 5 sources → Generated query]` 渐进式折叠 | 结构化对比表、可视化图表及下载入口**直接作为主答案的一部分呈现** | 极低认知负担：结论与核心资产优先，过程作为背景证据 |
| **Microsoft Copilot**<br>*(Excel / BI Agent)* | Planner-Executor 分层智能体 | “正在分析您的工作表...” 瞬态加载，步骤收起于过程折叠区 | 生成的 PivotTable、图表组件直接卡片化置于回答首部或尾部，并提供一键插入/导出 | 强调业务成果驱动，工具链作为透明后端 |
| **LangGraph Studio / Open Canvas** | Supervisor-Worker 多图协同 | 节点状态图与 Checkpoint 历史在抽屉/调试区展示 | 状态中的全局 `tool_artifact` 提升到 Canvas 或主消息流最外层直接挂载 | 过程可观测性强，主交互保持清爽 |

---

## 3. 架构方案探索与权衡对比（Three Architectural Options）

针对本系统的业务场景与技术栈（FastAPI + LangGraph + Vue 3），我们提出 3 种架构演进方案进行评估：

```
                              架构演进可选方案全景
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     ▼                                 ▼                                 ▼
【方案 A：双轨透出与就近提升】       【方案 B：纯后端状态晋升】        【方案 C：独立右侧工件工作台】
  (Dual-Projection & Bubble-Up)     (State Elevation to Parent)       (Dual-Pane Artifact Drawer)
  - 前端工件池全局提权               - 修改后端 State Reducer         - 类似 Claude Artifacts
  - 主气泡直接透出交付物             - 子图结束将工件合入父图         - 右侧开辟独立预览工作台
  - 子卡片保留轻量操作日志           - 前端仅认父图 State             - 对大宽屏体验极佳
  - 改动小、零破坏、收益极大         - 需修改 LangGraph 图接线        - 前端改造体量大
```

### 详细方案对比矩阵

| 维度 | 方案 A：工件全局提升与双轨透出 (Bubble-Up) 🌟 | 方案 B：父图状态晋升 (Parent State Elevation) | 方案 C：右侧工件抽屉 (Canvas Drawer) |
| :--- | :--- | :--- | :--- |
| **核心机制** | 前端 `artifactsMap` 工件字典池在 `MessageItem` 层面直接提权消费；移除 `subagentsList.length === 0` 互斥限制，主气泡直出工件；子卡片仅保留轻量 Trace | 修改 LangGraph 子图退出节点，将子图的 `tool_artifact` 显式写入父图 `CustomState`，主图 State 直接承载全部工件 | 引入类似 Claude 的两栏布局：左侧为标准对话流，右侧为全高工件工作台，点击任何工件卡片在右侧激活展示 |
| **用户体验** | **★★★★★ (极佳)**<br>用户无需展开任何子卡片，第一视口直接看到图表与 CSV 下载按钮；同时想溯源时仍可在子卡片内看到哪个 Agent 何时调用的 | **★★★★☆ (良好)**<br>主气泡能看到工件，但如果多子智能体产生多个工件，父图 State 容易发生覆盖或冲刷 | **★★★★★ (超强但重型)**<br>图表与多表对比在大屏幕上体验无敌，但在移动端/窄屏下需频繁切换 Tab |
| **后端侵入性** | **零侵入（Zero Backend Change）**<br>后端 Phase 2 的 `ArtifactStore`、`tool_artifacts` 字典池与 SSE 协议保持 100% 不动 | **中等（Medium）**<br>需调整 `SqlSubAgentState` 到 `CustomState` 的状态映射与 Reducer | **低（Low）**<br>后端保持不变，仅前端重构布局 |
| **前端改动量** | **极小（Surgical & Minimal）**<br>仅调整 `MessageItem.vue` 的条件判断与工件提取计算属性（~30 行代码） | **小（Small）**<br>前端调整状态消费路径 | **大（Large）**<br>需重构整个聊天页面的 Layout 与响应式布局 |
| **多工件兼容性** | 完美支持多图表（`ChartGroupCard`）、多 CSV 文件、多数据表（Tab 分组） | 容易受单槽位 `tool_artifact` 覆盖限制 | 完美支持历史工件版本列表与全屏交互 |
| **工件溯源性** | 优秀：工件带有 `created_by` / `tool_call_id` 徽章，清楚标明来自哪个专家智能体 | 良好 | 优秀 |

---

## 4. 推荐方案（方案 A）详细设计与落地规范

综合考虑 **交付敏捷性**、**零后端破坏性**、**最小改动原则（Simplicity First）** 与 **顶级用户体验**，推荐采纳 **方案 A：双轨透出与主气泡工件全局提升（Dual-Projection & Bubble-Up）**。

### 4.1 核心设计理念
1. **工件池（`artifactsMap`）属于当前轮次消息的全局资产**，而非某单个子智能体的私有内部状态；
2. **主气泡承载“最终交付物”**：
   - 无论是否存在子智能体，当前轮次产生的**所有图表（`chartSpecsList`）、所有 CSV 导出（`fileExportsList`）、所有数据表格（`sqlQueryResultsList`）**均在主气泡下方第一视口直接挂载；
   - 带有来源子智能体徽标（如 `由 SQL 数据专家生成`），保障严谨溯源；
3. **子卡片承载“执行过程与审计日志”**：
   - 子卡片内部的工具链依然展示工具调用记录，但其中的图表/CSV 可作为**轻量级缩略摘要或就近引用**，避免深层折叠阻碍用户获取最终成果。

### 4.2 消息视觉层次编排（Layout Hierarchy）

```
┌─────────────────────────────────────────────────────────────┐
│  MessageItem (消息主气泡)                                    │
├─────────────────────────────────────────────────────────────┤
│  1. 思考链折叠区 (ReasoningAccordion)                       │
│     - 主智能体的深度思考过程                                  │
│                                                             │
│  2. 子智能体过程卡片 (SubagentCard)                          │
│     - ⚡ SQL 数据专家 (已完成 · 1.2s) [展开详情 ⌄]           │
│       (折叠：SQL 编写、词典检索、合规拦截等技术细节)           │
│                                                             │
│  3. 主回复正文 (Markdown Content)                           │
│     - "已为您完成上周缺陷数据的聚合统计，生成了趋势图并..."      │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  4. ★ 核心工件交付区 (Artifact Delivery Zone - 第一视口)    │
│                                                             │
│     [ 图表工件展示 (ChartGroupCard / ChartArtifactCard) ]   │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📊 上周每日缺陷走势 (2026-08-10 ~ 2026-08-16)   │     │
│     │ [ECharts 折线图渲染区]                           │     │
│     └─────────────────────────────────────────────────┘     │
│                                                             │
│     [ CSV 导出工件展示 (CSV Export Card) ]                   │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📄 export_20260821_120000.csv (4 行 × 3 列)     │     │
│     │ [📥 下载 CSV 按钮]                               │     │
│     └─────────────────────────────────────────────────┘     │
│                                                             │
│     [ SQL 查询数据表格 (QueryResultGroup - 默认收起) ]       │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📋 SQL 查询数据预览 (共 4 行 × 3 列)  [展开查看 ⌄]│     │
│     └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 前端具体代码调整点（Surgical Change）

在 [`MessageItem.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/chat/MessageItem.vue) 中：
- 将原本束缚在 `subagentsList.length === 0` 下的三个工件渲染区域进行**解耦提权**：

```diff
- <!-- 智能 SQL 数据预览表格模块 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="!isUser && subagentsList.length === 0 && sqlQueryResultsList.length > 0">
+ <!-- 智能 SQL 数据预览表格模块 (主气泡全局透出) -->
+ <div v-if="!isUser && sqlQueryResultsList.length > 0">
    <QueryResultGroup :tables="sqlQueryResultsList" />
  </div>

- <!-- 侧信道直达与懒加载图表卡片 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="subagentsList.length === 0 && chartSpecsList.length > 0">
+ <!-- 侧信道直达与懒加载图表卡片 (主气泡全局透出) -->
+ <div v-if="chartSpecsList.length > 0">
    <ChartGroupCard :charts="chartSpecsList" />
  </div>

- <!-- CSV 导出卡片 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="!isUser && subagentsList.length === 0 && fileExportsList.length > 0">
+ <!-- CSV 导出卡片 (主气泡全局透出) -->
+ <div v-if="!isUser && fileExportsList.length > 0">
```

---

## 5. 预期收益与体验提升评估

| 评估维度 | 当前现状（埋在子卡片内） | 实施方案 A 后（主气泡透出） | 提升幅度 |
| :--- | :--- | :--- | :--- |
| **操作步数（Clicks to Value）** | 2~3 步（点击展开子卡片 → 寻找工具项 → 点击操作） | **0 步（首屏直接可见、一键直接下载）** | **降低 100% 认知交互成本** |
| **图表直读性（Readability）** | 默认隐藏在子卡片内，用户常误以为“没生成图表” | 对话流正文下方直接呈现高清图表 | **信息直达率 100%** |
| **过程与结果分离度** | 过程与结果混合在一起，结构混乱 | **过程折叠（按需排查）+ 结果突出（即时消费）** | 符合专业 BI 与 Agent 规范 |
| **多图表/多工件承载力** | 散落在各个子工具步骤下方，无法并列对比 | 在主气泡以 `ChartGroupCard` / Tab 分组并列展示 | 显著提升多表、多图对比分析体验 |
| **代码与系统稳定性** | 无影响 | 零后端变更，纯前端展现层优化 | **极高可靠性与极低发布风险** |

---

## 6. 实施建议与下一步行动

1. **建议决策**：确认采纳 **方案 A（双轨透出与主气泡工件全局提升）**；
2. **执行步骤**：
   - Step 1: 修改 `MessageItem.vue`，解除工件对 `subagentsList.length === 0` 的非必要限制；
   - Step 2: 保持 `SubagentCard.vue` 内部的执行流展示（或将其简化为轻量日志），形成外层交付、内层溯源的双轨体验；
   - Step 3: 执行 `npm run build:check` 验证前端无语法与类型错误；
   - Step 4: 进行端到端交互走通与 Changelog 登记。
