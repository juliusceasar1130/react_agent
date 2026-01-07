# Research Agent - 大模型聊天会话管理系统

一个功能完整的大模型聊天应用，支持多会话管理、流式输出、工具调用和状态持久化。

## 特性

- **多会话管理** - 创建、删除、切换聊天会话
- **流式/非流式输出** - 支持 SSE 实时流式响应
- **LangChain Agent** - 集成 arXiv 论文搜索工具
- **状态持久化** - PostgresSaver 自动管理 Agent 状态
- **自动摘要** - SummarizationMiddleware 压缩长对话
- **前后端分离** - FastAPI + Vue 3 + TypeScript

## 技术栈

### 后端

| 技术           | 说明                              |
| -------------- | --------------------------------- |
| FastAPI        | 高性能异步 Web 框架                |
| SQLAlchemy     | Python ORM                         |
| PostgreSQL     | 关系型数据库                       |
| LangChain      | LLM 应用开发框架                   |
| DeepSeek       | 大语言模型                         |
| PostgresSaver  | Agent 状态持久化                   |
| psycopg_pool   | PostgreSQL 连接池                  |

### 前端

| 技术          | 说明                  |
| ------------- | --------------------- |
| Vue 3         | 渐进式 JavaScript 框架 |
| TypeScript    | 类型安全              |
| Vite          | 前端构建工具          |
| Pinia         | 状态管理              |
| Tailwind CSS  | CSS 框架              |
| Axios         | HTTP 客户端           |

## 快速开始

### 前置要求

- Python 3.14+
- Node.js 18+
- PostgreSQL 14+

### 1. 克隆项目

```bash
git clone <repository-url>
cd rearch_agent
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
# .env
DATABASE_URL='postgresql://用户名:密码@localhost:5432/rearch_agent'
DEEPSEEK_API_KEY='your-deepseek-api-key'
DEEPSEEK_BASE_URL='https://api.deepseek.com'
DEEPSEEK_MODEL='deepseek-chat'
AGENT_TEMPERATURE=0.7
AGENT_MAX_TOKENS=2000
```

### 3. 安装依赖

**后端依赖**：
```bash
cd backend
pip install -r requirements.txt
```

或手动安装核心依赖：
```bash
pip install fastapi uvicorn sqlalchemy psycopg[binary,pool]
pip install langchain langchain-deepseek langgraph-checkpoint-postgres
```

**前端依赖**：
```bash
cd frontend
npm install
```

### 4. 初始化数据库

```bash
# 创建数据库
createdb rearch_agent

# 启动后端服务（会自动创建表）
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm run dev
```

### 6. 访问应用

- 前端界面：http://localhost:5173
- 后端 API 文档：http://localhost:8000/docs
- ReDoc 文档：http://localhost:8000/redoc

## 项目结构

```
rearch_agent/
├── backend/                 # 后端应用
│   ├── app/
│   │   ├── main.py         # FastAPI 应用入口
│   │   ├── api.py          # RESTful API 路由
│   │   ├── crud.py         # 数据库 CRUD 操作
│   │   ├── models.py       # SQLAlchemy ORM 模型
│   │   ├── schemas.py      # Pydantic Schema
│   │   ├── database.py     # 数据库连接
│   │   ├── config.py       # 配置管理
│   │   └── services.py     # LangChain Agent 服务
│   ├── docs/               # 技术文档
│   └── requirements.txt    # Python 依赖
│
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── api/            # API 请求封装
│   │   ├── components/     # Vue 组件
│   │   ├── views/          # 页面组件
│   │   ├── stores/         # Pinia 状态管理
│   │   └── types/          # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
│
├── .env                    # 环境变量
├── .env.example            # 环境变量示例
├── CLAUDE.md               # Claude Code 开发指南
└── README.md               # 本文件
```

## API 端点

### 会话管理

| 方法   | 路径                     | 功能               |
| ------ | ------------------------ | ------------------ |
| POST   | `/api/chat/sessions`     | 创建会话           |
| GET    | `/api/chat/sessions`     | 获取所有会话       |
| GET    | `/api/chat/sessions/{id}` | 获取单个会话       |
| PUT    | `/api/chat/sessions/{id}` | 更新会话           |
| DELETE | `/api/chat/sessions/{id}` | 删除会话           |

### 消息管理

| 方法   | 路径                                | 功能                 |
| ------ | ----------------------------------- | -------------------- |
| POST   | `/api/chat/messages`                | 创建消息             |
| GET    | `/api/chat/messages/{id}`           | 获取单条消息         |
| GET    | `/api/chat/sessions/{id}/messages`  | 获取会话的所有消息   |
| DELETE | `/api/chat/messages/{id}`           | 删除消息             |

### Agent 聊天

| 方法 | 路径                | 功能               |
| ---- | ------------------- | ------------------ |
| POST | `/api/chat/message` | 发送消息（非流式） |
| POST | `/api/chat/stream`  | 发送消息（流式）   |

#### 示例请求

**非流式**：
```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "搜索最新的深度学习论文",
    "session_id": "会话ID",
    "stream": false
  }'
```

**流式**：
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "搜索最新的深度学习论文",
    "session_id": "会话ID",
    "stream": true
  }'
```

## 核心功能

### PostgresSaver 状态管理

Agent 的对话状态由 PostgresSaver 自动管理，无需手动加载历史：

```python
# 初始化
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

self.conn_pool = ConnectionPool(conninfo=settings.database_url)
self.checkpointer = PostgresSaver(self.conn_pool)

# 使用
config = {"configurable": {"thread_id": str(session_id)}}
result = agent.invoke({"messages": [...]}, config=config)
```

### SummarizationMiddleware 自动摘要

当对话历史超过 4000 tokens 时，自动生成摘要：

```python
from langchain.agents.middleware import SummarizationMiddleware

middleware = SummarizationMiddleware(
    model=llm,
    trigger=("tokens", 4000),
    keep=("messages", 20)
)
```

### 数据库表结构

**业务表**（用于前端展示）：
- `chat_sessions` - 会话信息
- `chat_messages` - 聊天消息

**检查点表**（PostgresSaver 自动创建）：
- `checkpoints` - Agent 状态存储
- `checkpoint_blobs` - 大型二进制数据
- `checkpoint_writes` - 写入记录

## 开发指南

### 后端开发

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd frontend
npm run dev
```

### 代码规范

详见 [CLAUDE.md](./CLAUDE.md) 文档。

### 技术文档

- [FastAPI 与 SQLAlchemy 知识点](./backend/docs/FastAPI与SQLAlchemy知识点复习.md)
- [PostgresSaver 集成重构总结](./backend/docs/PostgresSaver集成重构总结.md)
- [连接池与上下文管理器详解](./backend/docs/连接池与上下文管理器详解.md)

## 常见问题

### 代理连接错误 (Connection error)

**错误现象**：
```
httpcore.ConnectError: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
connect_tcp.started host='127.0.0.1' port=7890
```

**原因**：OpenAI 客户端（langchain-deepseek 底层使用）自动检测 Windows 系统代理设置，尝试通过 `127.0.0.1:7890` 连接，但代理服务未运行。

**解决方案**：在 `backend/app/services.py` 中创建禁用代理的 HTTP 客户端：

```python
import httpx

# 创建不使用代理的 HTTP 客户端
_no_proxy_client = httpx.Client(
    proxy=None,  # 明确禁用代理
    timeout=60.0
)

# 传递给 ChatDeepSeek
llm = ChatDeepSeek(
    ...,
    http_client=_no_proxy_client,  # 禁用代理
)
```

**修改时间**：2025-01-07

### PostgresSaver 报错

确保使用 `ConnectionPool` 初始化：

```python
# ✅ 正确
self.conn_pool = ConnectionPool(conninfo=DB_URL)
self.checkpointer = PostgresSaver(self.conn_pool)

# ❌ 错误
self.checkpointer = PostgresSaver.from_conn_string(DB_URL)
```

### Agent 不记得对话

检查是否传递了 `config` 参数：

```python
config = {"configurable": {"thread_id": str(session_id)}}
result = agent.invoke({...}, config=config)
```

更多问题请参考 [CLAUDE.md](./CLAUDE.md)。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
