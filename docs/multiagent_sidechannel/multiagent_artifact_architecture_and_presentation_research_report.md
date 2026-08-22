# 多智能体架构下工件（Artifacts）生命周期、呈现范式与主气泡透出综合研究报告

> **文档版本**：v1.0 (权威完整版)  
> **文档位置**：`docs/multiagent_sidechannel/multiagent_artifact_architecture_and_presentation_research_report.md`  
> **归属专区**：`docs/multiagent_sidechannel/`（多智能体侧信道与工件体系架构知识库）  
> **参考源码库**：LobeHub/LobeChat (`F:\000_dev\github\lobehub`)、Anthropic Claude Artifacts、OpenAI Advanced Data Analysis (ADA)  
> **面向受众**：系统架构师、前端专家、Agent 研发工程师、数据产品经理  
> **研究主题**：解决多智能体（Supervisor-Worker）分层架构下，子智能体（如 SQL 专家）产出的图表、CSV 下载文件及数据表格被深埋在子卡片内部导致的用户体验与交互摩擦问题，深度结合开源与商业顶级架构，确立企业级工件交付最佳实践。

---

## 目录（Table of Contents）

- [1. 执行摘要与背景痛点（Executive Summary & Context）](#1-执行摘要与背景痛点)
  - [1.1 现状还原与核心矛盾](#11-现状还原与核心矛盾)
  - [1.2 用户心智模型：过程溯源 vs 最终交付物](#12-用户心智模型过程溯源-vs-最终交付物)
  - [1.3 研究目标与报告价值](#13-研究目标与报告价值)
- [2. 行业顶级系统工件架构横向全景调研（Industry Benchmarking）](#2-行业顶级系统工件架构横向全景调研)
  - [2.1 LobeHub (LobeChat) 源码级深度剖析](#21-lobehub-lobechat-源码级深度剖析)
  - [2.2 Anthropic Claude Artifacts（双栏工作台范式）](#22-anthropic-claude-artifacts双栏工作台范式)
  - [2.3 OpenAI ChatGPT (Code Interpreter / ADA / Canvas)](#23-openai-chatgpt-code-interpreter--ada--canvas)
  - [2.4 Perplexity Pro 与 Microsoft Copilot](#24-perplexity-pro-与-microsoft-copilot)
  - [2.5 行业主流架构多维横向对比矩阵](#25-行业主流架构多维横向对比矩阵)
- [3. 核心机制与架构原语解耦（Architectural Primitives）](#3-核心机制与架构原语解耦)
  - [3.1 资产分类：过程 Trace vs 交付 Artifact](#31-资产分类过程-trace-vs-交付-artifact)
  - [3.2 通信拓扑：带内主信道 + 带外侧信道 + Claim-Check 存储](#32-通信拓扑带内主信道--带外侧信道--claim-check-存储)
  - [3.3 多智能体下的工件全局提权机制（Bubble-Up Mechanism）](#33-多智能体下的工件全局提权机制bubble-up-mechanism)
- [4. 三大架构演进方案深度剖析与权衡（Three Architectural Options）](#4-三大架构演进方案深度剖析与权衡)
  - [4.1 方案 A：双轨透出与主气泡工件全局提升（Dual-Projection & Bubble-Up）🌟](#41-方案-a双轨透出与主气泡工件全局提升dual-projection--bubble-up-)
  - [4.2 方案 B：父图状态显式晋升（Parent State Elevation）](#42-方案-b父图状态显式晋升parent-state-elevation)
  - [4.3 方案 C：独立右侧工件工作台 / Portal 抽屉（Dual-Pane Workspace）](#43-方案-c独立右侧工件工作台--portal-抽屉dual-pane-workspace)
  - [4.4 方案决策打分与综合裁决](#44-方案决策打分与综合裁决)
- [5. 推荐方案（方案 A）详细技术设计（Detailed Engineering Design）](#5-推荐方案方案-a详细技术设计)
  - [5.1 前端组件职责解耦与层级重构](#51-前端组件职责解耦与层级重构)
  - [5.2 视觉动线与布局层级编排（Visual Hierarchy）](#52-视觉动线与布局层级编排visual-hierarchy)
  - [5.3 流式首屏直推与 F5 刷新秒开机制](#53-流式首屏直推与-f5-刷新秒开机制)
  - [5.4 进阶路线：借鉴 LobeChat 引入 `identifier` 连续图表迭代](#54-进阶路线借鉴-lobechat-引入-identifier-连续图表迭代)
- [6. 实施路径、风险评估与验收标准（Roadmap & Verification）](#6-实施路径风险评估与验收标准)
  - [6.1 阶段化实施路径](#61-阶段化实施路径)
  - [6.2 风险评估与防御策略](#62-风险评估与防御策略)
  - [6.3 验收标准与测试规范](#63-验收标准与测试规范)

---

## 1. 执行摘要与背景痛点

### 1.1 现状还原与核心矛盾
在面向生产数据查询与分析的场景中，本项目构建了基于 **Supervisor-Worker（主智能体调度 + SQL/技能子智能体执行）** 的多智能体协同系统。在过去的演进中（Phase 2），系统建立了统一工件存储底座（`ArtifactStore`）以及就近内嵌于子智能体卡片（`SubagentCard.vue`）的展示形态。

然而，在真实业务使用过程中暴露了显著的 **交互层级错配（Hierarchy Inversion）** 痛点：

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

#### 关键技术根因剖析：
1. **排他渲染锁**：前端 [`MessageItem.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/chat/MessageItem.vue) 在外层工件挂载区域硬编码了 `subagentsList.length === 0` 的排他判断。其原意是“如果派发了子智能体，由子智能体卡片自行呈现工件；未派发子智能体时才由外层兜底呈现”；
2. **用户路径阻塞**：一旦主智能体派发了 SQL 子智能体，生成的趋势图表和 CSV 下载按钮被强制锁死在 `SubagentCard` 内部。由于子智能体卡片默认紧凑收起，用户看到的对话主气泡**只有一段文本解释，核心图表和下载链接完全不可见**；
3. **高操作摩擦（Friction）**：用户必须：**① 识别子卡片 -> ② 点击“展开详情” -> ③ 滚动跳过深度思考与工具入参 -> ④ 翻找具体的工具调用项**，才能完成下载或查看图表。

---

### 1.2 用户心智模型：过程溯源 vs 最终交付物

在人机协同与数据分析中，用户的心智模型天然区分为两个不同维度的资产：

```
                    用户心智模型与界面资产双层解耦
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     ▼                                                       ▼
【过程溯源 (Process Trace)】                           【最终交付物 (Deliverable Artifact)】
- 载体：思维链 (CoT)、SQL 语句、工具入参、调试信息       - 载体：ECharts 图表、CSV 导出文件、清洗后的汇总数据
- 目标：“它是怎么算出来的”（排查/审计时关心）           - 目标：“结论是什么、文件在哪下载”（业务核心关心点）
- 交互特征：默认紧凑收起、低饱和度、按需探索             - 交互特征：第一视口直达、高对比度、免翻找、一键交互
```

> **设计公理**：**“过程归过程（收起），交付归交付（透出）”**。用户无需探索子智能体内部的执行细节，即可在主气泡第一视口直接获得业务成果。

---

### 1.3 研究目标与报告价值
本报告旨在：
1. 深入调研以 **LobeHub (LobeChat)**、**Anthropic Claude**、**OpenAI ChatGPT** 为代表的行业顶级系统工件设计范式；
2. 系统解耦多智能体系统下的 **带内主信道（In-Band）**、**带外侧信道（Out-of-Band State）** 与 **Claim-Check 存储凭证**；
3. 提出零后端破坏、极简优雅且兼顾高扩展性的 **主气泡工件全局提升（Bubble-Up Elevating）** 落地架构。

---

## 2. 行业顶级系统工件架构横向全景调研

### 2.1 LobeHub (LobeChat) 源码级深度剖析

通过对本地源码库 [`F:\000_dev\github\lobehub`](file:///F:/000_dev/github/lobehub) 的实地代码审计，LobeChat 的 Artifacts 架构涵盖四大核心层次：

```
                                LobeHub Artifacts 架构全景
                                             │
      ┌───────────────────┬──────────────────┴───────────────────┬───────────────────┐
      ▼                   ▼                                      ▼                   ▼
【1. 技能协议层】     【2. 消息流解析层】                   【3. 状态管理层】     【4. Portal 工作台层】
 builtin-skills/     Markdown Rehype Plugin                useChatStore/         features/Portal/
 - <artifacts_guides>- 自定义 <lobeArtifact> 标签           - openArtifact()      - 双栏工作台 (Dual-Pane)
 - 判定标准与约束规范  - 主气泡渲染为精致轻量胶囊卡片           - closeArtifact()     - Preview 预览 / Code 源码
 - 跨轮次 identifier - 实时生成时自动唤起侧边栏               - isArtifactTagClosed - 隔离沙箱渲染 (React/SVG/HTML)
```

#### 2.1.1 技能定义与 System Prompt 契约
- **源码位置**：[`packages/builtin-skills/src/artifacts/content.ts`](file:///F:/000_dev/github/lobehub/packages/builtin-skills/src/artifacts/content.ts)
- **核心逻辑**：LobeChat 将 Artifacts 作为全局内置技能（`BuiltinSkill`），向大模型注入 `<artifacts_guides>`。协议要求模型将复杂交付物包裹在自定义 XML 标签中：

```xml
<lobeArtifact identifier="quarterly-defect-trend" type="application/lobe.artifacts.react" title="季度缺陷走势大屏">
  import { LineChart, XAxis, YAxis ... } from "recharts";
  export default function App() { ... }
</lobeArtifact>
```

- **关键规则（Evaluation Criteria）**：
  - **准入规则**：交互组件（React/Recharts）、矢量可视化（SVG）、独立页面（HTML）；
  - **准出规则**：普通代码片段（必须留在 Markdown 内联代码块中）、解释性文本、一次性问答；
  - **跨轮次持久标识（`identifier`）**：模型在后续微调修改时，**必须复用相同的 `identifier`**，实现前端画布的平滑原地覆写，杜绝重复产生垃圾工件。

#### 2.1.2 消息流 Markdown 插件与胶囊微卡
- **源码位置**：[`src/features/Conversation/Markdown/plugins/LobeArtifact/Render/index.tsx`](file:///F:/000_dev/github/lobehub/src/features/Conversation/Markdown/plugins/LobeArtifact/Render/index.tsx)
- **设计哲学**：**“主气泡不做重型渲染，只做高质感交付胶囊”**。
  - 在聊天流中，Rehype 插件将 `<lobeArtifact>` 转换为一个高 64px 的**精致胶囊卡片（Capsule Card）**，包含类型图标、标题、`identifier` 及生成中动画；
  - **自动联动机制**：流式生成过程中检测到新 Artifact 时，`useEffect` 会在首个 chunk 到达时**自动打开右侧 Portal 抽屉（`openArtifactUI()`）**，无需用户手动点击。

#### 2.1.3 Portal 右侧独立工作台（Dual-Pane Workspace）
- **源码位置**：[`src/features/Portal/Artifacts/Title.tsx`](file:///F:/000_dev/github/lobehub/src/features/Portal/Artifacts/Title.tsx)、[`src/features/Portal/Artifacts/Body/index.tsx`](file:///F:/000_dev/github/lobehub/src/features/Portal/Artifacts/Body/index.tsx)
- **核心特性**：
  - **双模式切换**：`Preview`（沙箱实时运行）与 `Code`（语法高亮源码）；
  - **一键导出工具箱**：复制源码、下载 SVG/PNG、全屏沉浸预览；
  - **独立沙箱**：基于 iframe 与 `@lobechat/artifact-template` 动态编译，完全阻断样式与 JS 运行污染。

---

### 2.2 Anthropic Claude Artifacts（双栏工作台范式）
Anthropic 是现代 Artifacts 架构的开创者：
1. **左右分屏（Dual-Pane）**：左侧为标准对话流，右侧为全高（Full-Height）交互式工作台；
2. **会话级一等公民**：无论模型调用了何种工具或进入了何种思考深度，最终形成的 React 组件、SVG 图表、文档均直接推入右侧工作台；
3. **版本化回溯**：右侧顶部支持切换历史版本（`v1`, `v2`, `v3`），支持多轮对话持续演进。

---

### 2.3 OpenAI ChatGPT (Code Interpreter / ADA / Canvas)
OpenAI 在数据分析与编程场景采用了**流内胶囊（In-stream Capsule）+ 结果直接透出**的极简模式：
1. **过程紧凑折叠**：Python 执行环境与代码通过 `[>_ Analyzed]` 灰色胶囊按钮收起；
2. **交付物第一视口置顶**：生成的 Matplotlib/Plotly 图表、计算得到的数据表格、以及 `[Download dataset.csv]` 文件下载链接，**紧随在助手回复下方直接渲染**；
3. **极低认知负荷**：普通业务用户无需展开 Python 代码，就能直接看图、点链接下载文件。

---

### 2.4 Perplexity Pro 与 Microsoft Copilot
- **Perplexity Pro**：将多步骤检索与 SQL 执行呈现为顶部横向渐进式进度条（`[Searched 5 sources → Cleaned table]`），而对比表和交互图表直接作为主回答卡片的主体呈现；
- **Microsoft Copilot (Excel / BI)**：执行过程以瞬态 Spinner 显示，生成的 PivotTable（透视表）和图表组件直接卡片化置于回答首部，提供“一键插入工作表 / 一键导出”入口。

---

### 2.5 行业主流架构多维横向对比矩阵

| 评估维度 | LobeHub (LobeChat) | Anthropic Claude | OpenAI ChatGPT (ADA) | 本项目当前现状 (Phase 2) | 本项目目标形态 (Target) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **工件载体** | 客户端沙箱即时编译 (React/SVG/HTML) | 客户端沙箱运行 (React/SVG/Doc) | 服务端执行产物 (PNG/HTML/CSV) | 服务端 Claim-Check (ECharts/CSV/SQL表) | 服务端生成 + 前端交互工件 (ECharts/CSV/SQL表) |
| **工件归属** | 会话全局一等公民 | 会话全局一等公民 | 消息轮次核心交付物 | **被深埋在 `SubagentCard` 内部** ❌ | **全面提升至主气泡交付区 (Bubble-Up)** 🌟 |
| **主气泡呈现** | 64px 紧凑胶囊微卡 | 紧凑引用卡片 | 图表直出 + 一键下载按钮 | 仅文字，子智能体执行时工件被隐藏 ❌ | **图表直出 + CSV 一键下载 + 紧凑折叠表** 🌟 |
| **工作台交互** | 右侧 Portal 抽屉 (Preview/Code) | 右侧全高双栏工作台 | 单栏流式直接交互 / Canvas | 仅消息内嵌交互，无右侧工作台 | **主气泡直达交付，支持全屏/多表Tab切换** |
| **过程与结果解耦**| 思考与工具折叠，工件在 Portal | 思考块折叠，工件在右侧 | `[>_ Analyzed]` 胶囊折叠，工件直出 | 过程与结果混杂在 `SubagentCard` ❌ | **过程折叠（按需审计）+ 结果突出（即时消费）** |
| **跨轮次修改** | 强制复用 `identifier` 原地刷新 | 自动版本堆栈 (`v1`->`v2`) | 上下文理解后重新生成 | 生成新 `chart_id`（未做标识符聚合） | 借鉴 `identifier`，支持图表平滑原地刷新 |
| **数据安全与离线**| 客户端渲染，适合公网前端 | 依赖公网平台服务 | 依赖公网平台服务 | **企业级内网/离线部署 + 物理路径脱敏** | **企业级内网/离线部署 + 物理路径脱敏** |

---

## 3. 核心机制与架构原语解耦

为了彻底理顺多智能体系统的工件生命周期，必须在架构层面严格确立三大原语：

```
                              多智能体工件通信拓扑
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     ▼                                 ▼                                 ▼
【1. 带内主信道 (In-Band)】        【2. 带外侧信道 (Out-of-Band)】    【3. Claim-Check 存储凭证】
  (LLM Prompt 上下文)               (LangGraph State / SSE)          (ArtifactStore / PostgreSQL)
  - 极轻量结构化摘要                - 完整渲染 Payload                - 服务端物理落盘 (24h TTL)
  - 避免 Token 膨胀与遗忘           - 前端毫秒级流式直推              - 前端异步下载与 F5 刷新秒开
```

### 3.1 资产分类：过程 Trace vs 交付 Artifact

1. **过程 Trace（Process Trace / Execution Logs）**：
   - **内容**：主子智能体路由决策、思维链（Reasoning CoT）、数据库物理词典检索结果、中间执行的 SQL 语句、SQL Linter 合规拦截记录、工具执行耗时等；
   - **受众与生命周期**：面向开发者、审计员或在结果存疑时供业务人员溯源；生命周期紧随当前执行步；
   - **界面交互约定**：**默认紧凑折叠在 `SubagentCard.vue` 或 `ReasoningAccordion.vue` 中，不干扰主阅读线**。

2. **交付 Artifact（Deliverable Artifact / Business Outcomes）**：
   - **内容**：交互式 ECharts 图表（`chart_spec`）、CSV 导出文件（`file_export`）、结构化数据透视表格（`query_result`）；
   - **受众与生命周期**：面向最终业务用户；生命周期跨越整个会话，具备独立导出、复用、分享与持续修改价值；
   - **界面交互约定**：**必须脱离执行过程的束缚，提权提升（Bubble-Up）至主气泡第一视口，一目了然、一键直达**。

---

### 3.2 通信拓扑：带内主信道 + 带外侧信道 + Claim-Check 存储

本项目三大核心工具（`build_chart_artifact`, `export_to_csv`, `sql_db_query`）采用带内带外分立机制：

```
[Agent LLM] ──(In-Band 仅传摘要 chart_ref)──> [Context 保持轻量]
     │
     └──(Out-of-Band State: tool_artifact)──> [SSE Stream] ──> [前端 ECharts 即刻渲染]
     │
     └──(Claim-Check 落盘)──> [ArtifactStore: /data/artifacts/charts/cht_xxx.json]
```

- **带内主信道（In-Band）**：工具执行后，仅向大模型上下文返回结构化摘要（如 `{"chart_id": "cht_123", "message": "图表已生成"}`），**0 冗余 Token 消耗**；
- **带外侧信道（Out-of-Band）**：通过 `Command(update={"tool_artifact": ...})` 挂载到状态机，由 SSE 流式分发通道（`chat_service.py`）在毫秒级发射给前端，**实现图表与下载卡片比文字打字机更快渲染**；
- **Claim-Check 存储**：文件落盘至 `ArtifactStore`（带 24 小时 TTL 与 GC），前端通过 Claim-Check ID（`file_id` / `chart_id`）实现异步下载与 F5 刷新 0 秒秒开。

---

### 3.3 多智能体下的工件全局提权机制（Bubble-Up Mechanism）

在多智能体分层执行时，工件的产生源自 Worker（如 `sql_domain_agent`），但工件的**最终交付目标是主会话**：

```
┌─────────────────────────────────────────────────────────────┐
│  会话层全局工件池 (Session Artifacts Pool: artifactsMap)     │
│  - 收集本轮所有 Agent (Main + Subagents) 产出的所有工件      │
└──────────────────────────────┬──────────────────────────────┘
                               │ (全局提权 Bubble-Up)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  主消息气泡 (MessageItem) - 核心交付区                       │
│  ├─ 📊 ChartGroupCard (并列呈现所有图表工件)                │
│  ├─ 📥 FileExportCard (直接呈现所有 CSV 下载按钮)            │
│  └─ 📋 QueryResultGroup (紧凑折叠呈现所有 SQL 数据表)        │
└─────────────────────────────────────────────────────────────┘
                               ▲
                               │ (轻量关联引用)
┌──────────────────────────────┴──────────────────────────────┐
│  子智能体过程卡片 (SubagentCard)                             │
│  - 仅作为执行 Trace、审计日志与调试证据链展示               │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 三大架构演进方案深度剖析与权衡

针对本系统的业务场景与技术栈（FastAPI + LangGraph + Vue 3），系统性评估 3 种架构演进方案：

### 4.1 方案 A：双轨透出与主气泡工件全局提升（Dual-Projection & Bubble-Up）🌟

- **核心机制**：
  1. 前端 `artifactsMap` 工件字典池在 `MessageItem.vue` 层面直接提权消费；
  2. 移除 `subagentsList.length === 0` 互斥限制，主气泡正文下方**直接挂载图表、CSV 下载卡片及 SQL 数据表**；
  3. `SubagentCard.vue` 内部保留轻量 Trace 日志（可保留微缩引用），形成外层交付、内层审计的双轨体验。
- **优点**：
  - **用户体验极佳**：0 步直达，首屏直接看到图表与下载按钮；
  - **零后端破坏（Zero Backend Change）**：后端 `ArtifactStore`、持久化表与 SSE 协议 100% 保持不动；
  - **极简改动（Surgical & Minimal）**：仅需调整 `MessageItem.vue` 约 30 行展示逻辑，发布风险几乎为零。
- **缺点**：
  - 若一轮对话生成 5 张以上超大图表，主气泡纵向滚动会变长（已通过 `ChartGroupCard` 栅格化排版对冲）。

---

### 4.2 方案 B：父图状态显式晋升（Parent State Elevation）

- **核心机制**：
  - 在 LangGraph 的子图退出边界上编写状态转换节点，将子图的 `tool_artifact` 显式写入父图 `CustomState`；
  - 前端完全依赖父图 State 中的单一 `tool_artifact` 字段进行渲染。
- **优点**：
  - 逻辑在 Python 状态机层面看起来较为传统。
- **缺点**：
  - **多智能体并发竞态冲刷**：如果多个子智能体并发执行，父图单槽位 `tool_artifact` 会发生后写覆盖（`_last_wins`）；
  - **后端侵入大**：需改动 LangGraph 编排层图结构与 Checkpoint 序列化。

---

### 4.3 方案 C：独立右侧工件工作台 / Portal 抽屉（Dual-Pane Workspace）

- **核心机制**：
  - 深度复刻 Anthropic / LobeChat，在页面右侧开辟可伸缩的 **Portal Artifact Drawer**；
  - 主气泡只放微型胶囊卡片，点击胶囊卡片（或模型生成时自动）在右侧滑出全高工作台，进行大屏 ECharts 交互、数据筛选与 CSV 导出。
- **优点**：
  - 对宽屏、多维复杂数据大屏、专业 BI 用户的交互体验无敌；
  - 对话流保持极致纯净。
- **缺点**：
  - 前端工程改造体量大（需重构整个聊天页面的 Layout 与响应式适配）；
  - 窄屏/移动端需要复杂的抽屉层级管理。

---

### 4.4 方案决策打分与综合裁决

| 评估维度 (权重) | 方案 A：主气泡工件全局提升 🌟 | 方案 B：父图状态显式晋升 | 方案 C：右侧双栏工作台 (Portal) |
| :--- | :---: | :---: | :---: |
| **用户体验与直达率 (30%)** | 9.5 / 10 | 8.0 / 10 | 9.5 / 10 |
| **实现简单性与零过度设计 (25%)** | **10.0 / 10** | 7.0 / 10 | 6.0 / 10 |
| **系统稳定性与零破坏性 (25%)** | **10.0 / 10** | 7.5 / 10 | 8.0 / 10 |
| **多工件/多智能体并发兼容 (20%)** | 9.5 / 10 | 6.0 / 10 | 9.5 / 10 |
| **加权综合得分 (Weighted Score)** | **9.75 (卓越 · 推荐)** | 7.25 (普通) | 8.25 (良好 · 适合远期) |

> **架构裁决**：
> **当前阶段立即落地 方案 A（双轨透出与主气泡工件全局提升）**，以最低风险、最小改动彻底根除当前用户体验摩擦；
> **远期演进（Phase 4）可基于方案 A 的工件池平滑升级为 方案 C（右侧 Portal 双栏工作台）**。

---

## 5. 推荐方案（方案 A）详细技术设计

### 5.1 前端组件职责解耦与层级重构

修改 [`MessageItem.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/chat/MessageItem.vue)，解除三大工件渲染块对 `subagentsList.length === 0` 的非必要排他约束：

```diff
- <!-- 智能 SQL 数据预览表格模块 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="!isUser && subagentsList.length === 0 && sqlQueryResultsList.length > 0">
+ <!-- 智能 SQL 数据预览表格模块 (主气泡全局透出) -->
+ <div v-if="!isUser && sqlQueryResultsList.length > 0" class="mt-3 text-left animate-fade-in">
    <QueryResultGroup :tables="sqlQueryResultsList" />
  </div>

- <!-- 侧信道直达与懒加载图表卡片 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="subagentsList.length === 0 && chartSpecsList.length > 0">
+ <!-- 侧信道直达与懒加载图表卡片 (主气泡全局透出) -->
+ <div v-if="chartSpecsList.length > 0" class="mt-3 space-y-3 animate-fade-in">
    <ChartGroupCard :charts="chartSpecsList" />
  </div>

- <!-- 终态工件 B: CSV 导出卡片列表 (仅在无子智能体时作为外层兜底展示) -->
- <div v-if="!isUser && subagentsList.length === 0 && fileExportsList.length > 0">
+ <!-- 终态工件 B: CSV 导出卡片列表 (主气泡全局透出) -->
+ <div v-if="!isUser && fileExportsList.length > 0" class="space-y-3 px-4 pb-3 animate-fade-in">
```

---

### 5.2 视觉动线与布局层级编排（Visual Hierarchy）

主气泡重构后的自上而下视线动线极其符合认知习惯：

```
┌─────────────────────────────────────────────────────────────┐
│  MessageItem (主消息气泡)                                    │
├─────────────────────────────────────────────────────────────┤
│  1. 思考链折叠区 (ReasoningAccordion)                       │
│     - 深度思考过程 (默认折叠/耗时标注)                       │
│                                                             │
│  2. 子智能体过程卡片 (SubagentCard - 默认折叠)               │
│     - ⚡ SQL 数据专家 (已完成 · 1.2s) [展开详情 ⌄]           │
│       (折叠审计区：具体 SQL 编写、词典命中等技术细节)         │
│                                                             │
│  3. 主回复正文 (Markdown Content)                           │
│     - "已为您完成上周缺陷数据的聚合统计，趋势如下："          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  4. ★ 核心工件交付区 (Artifact Delivery Zone - 第一视口)    │
│                                                             │
│     [ 📊 交互式 ECharts 图表 (ChartGroupCard) ]             │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📈 上周每日缺陷走势 (2026-08-10 ~ 2026-08-16)   │     │
│     │ [折线/柱状图切换 · 数据提示 Tooltip · 图例过滤]  │     │
│     └─────────────────────────────────────────────────┘     │
│                                                             │
│     [ 📥 CSV 导出与下载卡片 (CSV Export Card) ]              │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📄 export_20260821_120000.csv                   │     │
│     │ 共 4 行 × 3 列 · 0.2 KB · 有效期至 2026-08-22   │     │
│     │ [📥 下载 CSV] 按钮 (一键直达)                    │     │
│     └─────────────────────────────────────────────────┘     │
│                                                             │
│     [ 📋 SQL 查询数据表格 (QueryResultGroup - 默认收起) ]    │
│     ┌─────────────────────────────────────────────────┐     │
│     │ 📋 SQL 查询数据预览 (共 4 行 × 3 列)  [展开查看 ⌄]│     │
│     └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.3 流式首屏直推与 F5 刷新秒开机制

1. **流式阶段（Streaming Active）**：
   - 当 `build_chart_artifact` 或 `export_to_csv` 执行完毕时，后端 SSE 立即向前端下发 `type: "tool_artifact"`；
   - 前端 Pinia Store (`useMessagesStore`) 将工件存入内存工件池 `memoryArtifactPool[msgId]`；
   - `MessageItem.vue` 的 `chartSpecsList` 与 `fileExportsList` 响应式计算属性触发，**ECharts 图表和下载按钮即刻在主气泡第一视口渲染，完全无需等待后续总结性打字机文字完成**。

2. **完成态与刷新回放（F5 Refresh / Persistence）**：
   - 消息完成时，后端将全部工件持久化写入 PostgreSQL 的 `chat_messages.tool_artifacts` 列（JSONB / TOAST 存储）；
   - 用户刷新页面后，前端直接反序列化 `message.tool_artifacts`，**0 次额外网络请求、0 秒秒开复原完整图表与下载卡片**。

---

### 5.4 进阶路线：借鉴 LobeChat 引入 `identifier` 连续图表迭代

在后续 Phase 中，可借鉴 LobeChat 的 `identifier` 规范：
1. **工具入参扩展**：在 `build_chart_artifact` 中新增可选参数 `chart_identifier: str = ""`（例如 `defect_weekly_trend`）；
2. **多轮对话平滑更新**：
   - 当用户在第一轮说：“生成上周缺陷趋势折线图” -> 产生 `identifier="defect_weekly_trend"` 的图表；
   - 当用户在第二轮说：“把刚才的图改成柱状图，并加上检测次数” -> 大模型复用 `chart_identifier="defect_weekly_trend"`；
   - 前端工件池检测到相同 `identifier` 时，直接在原图表卡片进行平滑过渡重绘（Chart Re-render），避免对话流中堆积大量过期图表。

---

## 6. 实施路径、风险评估与验收标准

### 6.1 阶段化实施路径

| 阶段 | 实施内容 | 预估耗时 | 交付物 |
| :--- | :--- | :---: | :--- |
| **Phase 1 (即刻实施)** | 修改 `MessageItem.vue`，解除图表、CSV 下载与 SQL 表格的 `subagentsList.length === 0` 排他限制，完成主气泡第一视口直出 | 0.5 天 | 核心工件主气泡直达，0 步点击交互 |
| **Phase 2 (交互微调)** | 优化 `SubagentCard.vue` 内部的工具链展示，将其弱化为轻量 Trace 标签，避免内外部重复占用 DOM | 0.5 天 | 过程收敛、主次分明 |
| **Phase 3 (契约迭代)** | 借鉴 LobeChat 在 `build_chart_artifact` 工具中引入 `chart_identifier`，支持对话式连续修改图表 | 1 天 | 连续对话原地迭代图表 |

### 6.2 风险评估与防御策略
- **风险 1：多子智能体产生多个工件时的布局拥挤**
  - **防御**：已建设 [`ChartGroupCard.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/artifacts/ChartGroupCard.vue) 支持多图表网格自适应排版；[`QueryResultGroup.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/artifacts/QueryResultGroup.vue) 默认紧凑折叠并支持 Tab 分组。
- **风险 2：后端与流式协议兼容性**
  - **防御**：零后端改动，前端状态池 `artifactsMap` 已经天然具备多工件汇聚能力，完全向前向下兼容。

### 6.3 验收标准与测试规范
1. **交互直达验收**：用户输入“查询上周每日缺陷并画图”后，主消息气泡内正文下方直接呈现 ECharts 图表，无需点击展开任何子卡片；
2. **下载一键直达**：用户输入“导出缺陷明细 CSV”后，主消息气泡内直接呈现带有文件名、行数、大小与“下载 CSV”按钮的绿色卡片；
3. **构建与类型安全**：执行 `npm run build:check`（`vue-tsc && vite build`）通过，0 语法与类型错误；
4. **全量后端回归**：`pytest -m "not integration and not smoke"` 82 项测试 100% 保持绿色全通。
