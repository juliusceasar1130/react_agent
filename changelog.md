# Changelog

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
