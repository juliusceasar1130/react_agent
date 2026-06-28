---
name: sql-memory-fewshot-evolution-proposal
description: 用户成功 SQL 案例记忆持久化与 Few-Shot 演进方案可行性评估与设计提案
metadata:
  type: project
---

# 用户成功 SQL 案例记忆持久化与 Few-Shot 演进方案

> 创建日期: 2026-06-27
> 状态: 提案阶段

## 一、背景与目标

在大模型聊天会话管理系统（FastAPI + LangChain/LangGraph + Vue 3）中，将"用户提问后成功的案例与生成的 SQL"作为记忆保存，用于：

- **Few-Shot 示例生成**：为 SQL Agent 提供动态、语义相关的历史成功案例参考
- **数据分析**：积累真实使用场景数据，洞察高频查询模式
- **经验沉淀**：形成可复用的领域查询知识库，降低新人上手成本

## 二、可行性评估

在当前技术栈（LangChain/LangGraph + PostgreSQL/PGVector）下，方案具有**极高的可行性**。

### 技术基础（已具备）

| 能力 | 位置 | 状态 |
|------|------|------|
| `search_saved_correct_tool_uses` SQL 示例检索工具 | `backend/app/agent/tools/sql_tools.py:267` | 已存在，Agent 可通过 `doc_type='sql_example'` 检索 |
| PGVector 按元数据过滤检索 | `backend/app/agent/vector/pgvector/pgvector_wrapper.py:135` | 已支持 `type` + `domain` 过滤 |
| `BaseRetriever` 抽象接口 | `backend/app/agent/vector/base.py:33` | 可直接用于新记忆的检索端 |
| PostgreSQL 连接池 | `backend/app/agent/service.py:234` | 已有，无需新增中间件 |
| 对话摘要中间件 | `backend/app/agent/service.py:685` | 可用于方案三的会话复盘 |

### 核心挑战

1. **如何定义"成功"**：SQL 执行成功 ≠ 结果符合用户预期。需采用"规则初筛 + 用户反馈"的多级漏斗
2. **多轮对话上下文消解**：第二轮"那其中华东地区的呢？"需重写为独立问题再配对存储
3. **数值时效性**：包含具体数值的示例（"昨日产量 320 台"）若被注入，与系统 Prompt 的"核心数值纪律"冲突

## 三、现有架构分析

### 项目技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangChain/LangGraph |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| LLM | DeepSeek / OpenAI 兼容接口 / Ollama（可选） |
| 状态持久化 | AsyncPostgresSaver / PostgresSaver |
| 检索增强 | PGVector / Milvus Hybrid + 可选 NVIDIA Rerank |

### 关键现有能力

- `ChatMessage` ORM 模型（`backend/app/models.py:31`）：无 `feedback` 字段
- `MessageItem.vue` 前端组件：无赞/踩/收藏 UI
- 前端已定义 `Message` 和 `StreamingMessage` 类型接口（`frontend/src/types/index.ts`）
- 后端 API 路由 `backend/app/api.py`：有标准 CRUD 模式可扩展
- RAG 检索器工厂 `backend/app/agent/vector/factory.py`：可扩展新的写入能力

### 三层能力定位

| 层级 | 内容 | 检索方式 | 适用场景 |
|------|------|----------|----------|
| Skills | 表结构、字段含义、业务规则 | `load_skill()` 全量加载 | 领域基础认知 |
| Scenario Skills | 预定义 SQL 模板 + 参数 | `load_scenario()` 精确匹配 | 高频固定报表 |
| Few-shot 记忆 | 历史成功问答对 | 向量语义检索 | 长尾/方言/新问题 |

## 四、设计决策

### 方案对比

| 评估维度 | 方案一：显式收集与审核 | 方案二：隐式规则自动落库 | 方案三：LLM 异步复盘 |
|----------|----------------------|----------------------|-------------------|
| 数据精准度 | 极高 | 中等（含噪音） | 高 |
| 自动化程度 | 较低 | 极高 | 高 |
| 开发成本 | 低 | 中等 | 较高 |
| 运行成本 | 极低 | 零额外成本 | 中等 |
| **推荐优先级** | **阶段一** | **不推荐** | **阶段三** |

### 推荐方案详解

#### 阶段一（第 1-2 周）：显式收集基础建设

**核心思路**：不新建独立记忆库表，利用 PGVector 已有 `rag_store` collection 的 `sql_example` 类型进行存储。

**修改文件清单**：

1. **后端模型层** `backend/app/models.py`
   - `ChatMessage` 表新增 `feedback` 字段（`none` / `like` / `dislike` / `collected`）

2. **后端 Schema 层** `backend/app/schemas.py`
   - 新增 `MessageFeedback` 请求 Schema

3. **后端 CRUD 层** `backend/app/crud.py`
   - 新增 `update_message_feedback()` 方法
   - 新增 `collect_sql_example()` 方法（提取 SQL → 构造 Document → PGVector 写入）

4. **后端 API 层** `backend/app/api.py`
   - 新增 `POST /api/chat/messages/{id}/feedback` 端点

5. **前端类型层** `frontend/src/types/index.ts`
   - `Message` 接口新增 `feedback?: 'none' \| 'like' \| 'dislike' \| 'collected'`

6. **前端组件层** `frontend/src/components/MessageItem.vue`
   - 非流式完成态消息底部增加 👍 / 👎 / ⭐ 按钮

7. **前端 API 层** `frontend/src/api/messages.ts`
   - 新增 `submitFeedback()` 请求方法

**收藏流程**：
```
用户点击 ⭐ → 前端 POST feedback={status: "collected"}
→ 后端解析该消息的 tool_calls/tool_results 提取 SQL 和 question
→ 构造 Document(page_content=question, metadata={type: "sql_example", sql: ..., domain: ...})
→ PGVector.add_documents() 写入 rag_store
→ 现有 search_saved_correct_tool_uses 工具自动能检索到
```

#### 阶段二（第 3-4 周）：动态 Few-shot 注入增强

**核心思路**：将 Few-shot 检索从中介调用改为中间件自动注入，减少 Agent 的 tool call 次数。

**修改文件清单**：

1. **前端增强** `frontend/src/components/MessageItem.vue`
   - ⭐ 收藏时弹出对话框，允许用户编辑/确认 question 文本（人工 Query Rewriting）

2. **后端中间件** `backend/app/agent/middleware/`（新增 `fewshot_middleware.py`）
   - 新增 `FewShotMiddleware`，参考 `BusinessRagMiddleware` 模式
   - 在每轮对话开始时自动检索 Top-3 `sql_example` 注入到 System Prompt 尾部

3. **Agent 组装层** `backend/app/agent/service.py`
   - 在 middleware 列表中注册 `FewShotMiddleware`

#### 阶段三（后续）：质量闭环与自动演进

1. 基于用户反馈数据训练轻量质量分类器（替代昂贵的 LLM 复盘）
2. 引入时效性衰减机制：对超过 N 天的示例降低检索权重
3. 定期清理低质量/过期 Few-shot 样本

## 五、设计原则

- **最小改动**：不新建独立记忆表，复用 PGVector 的 `rag_store` + `sql_example` 类型
- **渐进增强**：阶段一即可独立上线使用，不影响现有 Agent 行为
- **用户驱动**：仅用户主动收藏的案例才进入记忆库，确保数据质量
- **可逆设计**：收藏/取消收藏操作可以互相撤销

## 六、验证方式

- 阶段一：前端收藏后，数据库 `langchain_pg_embedding` 表中出现新行（`type='sql_example'`）
- 阶段二：Agent 响应中出现的 SQL 更贴近收藏案例的查询模式；A/B 测试对比 SQL 生成正确率
- 数据质量：统计收藏案例被检索和使用的频次，追踪低频/低效案例的淘汰

## 七、不纳入范围

- 不引入 Celery 或异步任务队列（阶段三前不需要）
- 不实现管理后台（阶段一仅通过 API 管理）
- 不实现隐式规则自动收集（阶段二不实施）
- 不实现 LLM 自动复盘（推后到阶段三评估）
