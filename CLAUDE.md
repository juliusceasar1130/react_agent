# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个**大模型聊天会话管理系统**，采用前后端分离架构。

### 技术栈

| 层 | 技术 |
|----|------|
| **后端** | FastAPI + SQLAlchemy + SQLite + LangChain |
| **前端** | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| **AI** | DeepSeek + LangChain Agent |

### 核心功能

- 多会话管理（创建、删除、切换）
- 流式/非流式聊天输出
- LangChain Agent 工具调用（arXiv 论文搜索）
- 对话历史持久化

## 环境

```bash
conda activate py314_agent
```

## 启动命令

```bash
# 启动后端服务
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端开发服务器
cd frontend
npm run dev

# 后端 API 文档
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

## 项目结构

```
backend/app/              # 后端应用核心
├── main.py              # FastAPI 应用入口，lifespan 管理器
├── api.py               # RESTful API 路由（/api/chat）
├── crud.py              # 数据库 CRUD 操作层
├── models.py            # SQLAlchemy ORM 模型
├── schemas.py           # Pydantic 数据验证 Schema
├── database.py          # SQLite 数据库连接
├── config.py            # 配置管理（环境变量）
├── services.py          # LangChain Agent 服务层
└── test.py              # 测试文件

backend/docs/            # 技术文档

frontend/                # Vue 3 前端应用
├── src/
│   ├── api/             # API 请求封装
│   │   ├── index.ts     # Axios 实例配置
│   │   ├── sessions.ts  # 会话 API
│   │   ├── messages.ts  # 消息 API
│   │   └── chat.ts      # 聊天 API（流式/非流式）
│   ├── components/      # Vue 组件
│   │   ├── SessionList.vue    # 会话列表
│   │   ├── SessionItem.vue    # 单个会话项
│   │   ├── MessageList.vue    # 消息列表
│   │   ├── MessageItem.vue    # 单条消息
│   │   └── EmptyState.vue     # 空状态提示
│   ├── views/           # 页面组件
│   │   └── ChatView.vue       # 聊天主界面
│   ├── stores/          # Pinia 状态管理
│   │   ├── sessions.ts        # 会话状态
│   │   └── messages.ts        # 消息状态（含流式支持）
│   ├── composables/     # 组合式函数
│   │   ├── useChatStream.ts   # 流式聊天逻辑
│   │   ├── useDateFormat.ts   # 日期格式化
│   │   └── useConfirmation.ts # 确认对话框
│   ├── types/           # TypeScript 类型定义
│   │   └── index.ts     # Session, Message 等类型
│   ├── main.ts          # 应用入口
│   └── App.vue          # 根组件
├── index.html           # HTML 模板
├── vite.config.ts       # Vite 配置
├── tailwind.config.js   # Tailwind CSS 配置
└── package.json         # 依赖管理
```

## 架构设计

### 后端架构

```
┌─────────────────────────────────────────────────┐
│         API Layer (api.py)                      │
│  - FastAPI 路由                                  │
│  - HTTP 状态码管理                                │
│  - SSE 流式响应                                   │
└─────────────────┬───────────────────────────────┘
                  │ Depends(get_db)
┌─────────────────▼───────────────────────────────┐
│         CRUD Layer (crud.py)                     │
│  - 数据库业务逻辑                                 │
└─────────────────┬───────────────────────────────┘
                  │ ORM 操作
┌─────────────────▼───────────────────────────────┐
│      Database Layer (database.py, models.py)     │
│  - SQLAlchemy ORM                                │
│  - SQLite 数据库                                  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│      Agent Service Layer (services.py)           │
│  - LangChain Agent 初始化                        │
│  - 流式/非流式消息处理                            │
│  - 工具调用（arXiv）                              │
└─────────────────────────────────────────────────┘
```

### 前端架构

```
┌─────────────────────────────────────────────────┐
│         View Layer (ChatView.vue)                │
│  - 页面布局                                       │
│  - 事件处理                                       │
└─────────────────┬───────────────────────────────┘
                  │ use
┌─────────────────▼───────────────────────────────┐
│      Composable Layer (useChatStream.ts)         │
│  - 流式/非流式逻辑                                │
│  - 乐观更新                                       │
└─────────────────┬───────────────────────────────┘
                  │ use
┌─────────────────▼───────────────────────────────┐
│         Store Layer (Pinia)                      │
│  - sessions store (会话状态)                      │
│  - messages store (消息状态 + 流式状态)           │
└─────────────────┬───────────────────────────────┘
                  │ call
┌─────────────────▼───────────────────────────────┐
│         API Layer (chat.ts)                      │
│  - Axios 请求封装                                 │
│  - SSE 流式响应解析                               │
└─────────────────────────────────────────────────┘
```

## API 端点速查

### Session API（会话管理）

| 方法   | 路径                               | 功能                               |
| ------ | ---------------------------------- | ---------------------------------- |
| POST   | `/api/chat/sessions`               | 创建会话                           |
| GET    | `/api/chat/sessions`               | 获取所有会话（按 updated_at 降序） |
| GET    | `/api/chat/sessions/{session_id}`  | 获取单个会话                       |
| PUT    | `/api/chat/sessions/{session_id}`  | 更新会话                           |
| DELETE | `/api/chat/sessions/{session_id}`  | 删除会话（级联删除消息）           |

### Message API（消息 CRUD）

| 方法   | 路径                                    | 功能                       |
| ------ | --------------------------------------- | -------------------------- |
| POST   | `/api/chat/messages`                    | 创建消息                   |
| GET    | `/api/chat/messages/{message_id}`       | 获取单条消息               |
| GET    | `/api/chat/sessions/{session_id}/messages` | 获取会话的所有消息     |
| DELETE | `/api/chat/messages/{message_id}`      | 删除消息                   |

### Chat API（Agent 聊天）

| 方法   | 路径                  | 功能                   |
| ------ | --------------------- | ---------------------- |
| POST   | `/api/chat/message`   | 发送消息（非流式）      |
| POST   | `/api/chat/stream`    | 发送消息（流式 SSE）    |

#### 非流式请求

```bash
POST /api/chat/message
Content-Type: application/json

{
  "message": "用户消息",
  "session_id": "会话ID",
  "stream": false
}

Response: ChatResponse
{
  "session_id": "...",
  "message": { ... },
  "is_complete": true
}
```

#### 流式请求

```bash
POST /api/chat/stream
Content-Type: application/json

{
  "message": "用户消息",
  "session_id": "会话ID",
  "stream": true
}

Response: SSE (text/event-stream)
data: {"content": "你", "is_final": false}

data: {"content": "好", "is_final": false}

data: {"content": "", "is_final": true, "tool_calls": null}

data: [DONE]
```

## 数据模型

### ChatSession（会话表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(UUID) | 主键 |
| `title` | String(255) | 会话标题 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间（自动更新） |
| `messages` | Relationship | 一对多关联 ChatMessage |

### ChatMessage（消息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(UUID) | 主键 |
| `session_id` | String(FK) | 外键关联 ChatSession（CASCADE） |
| `role` | String | user/assistant/system/tool |
| `content` | Text | 消息内容 |
| `tool_calls` | JSON/NULL | 工具调用信息（JSON 字符串） |
| `tool_results` | JSON/NULL | 工具执行结果（JSON 字符串） |
| `created_at` | DateTime | 创建时间 |

## 代码规范

### 后端规范

#### CRUD 操作
- 函数应返回 `Optional[T]`
- 创建操作返回模型实例
- 更新使用 `model_dump(exclude_unset=True, exclude_none=True)` 过滤 None 值
- 删除操作返回布尔值

#### Schema 定义
- 所有 Response Schema 配置 `model_config = ConfigDict(from_attributes=True)`
- 使用 `model_config` 而非 `Config` 类（Pydantic v2）

#### 数据库操作
- 使用 `Depends(get_db)` 注入数据库会话
- 主键统一使用 UUID 字符串
- 利用级联删除机制

#### Agent 服务
- 工具调用验证：只保存有效的 tool_calls（有 name 和 id）
- 对话历史：不恢复 tool_calls，让 agent 重新决策

### 前端规范

#### 组件开发
- 使用 `<script setup>` 语法
- Props 使用 TypeScript 接口定义
- Emits 使用 TypeScript 泛型定义

#### 状态管理
- 使用 Pinia Setup Stores
- Refs 自动解包，不需要 `.value`
- 删除会话时清除关联的 messages store

#### 流式处理
- 使用乐观更新立即显示用户消息
- 流式完成后重新加载消息列表
- 错误时清理临时状态

#### 样式
- 使用 Tailwind CSS 工具类
- 响应式设计（移动优先）

## 技术文档

详细的技术文档位于 `backend/docs/FastAPI与SQLAlchemy知识点复习.md`，包含：

1. CRUD 操作最佳实践
2. 同步 vs 异步架构对比
3. FastAPI 依赖注入机制
4. response_model 工作原理
5. 字段名匹配机制
6. SQLAlchemy 关系与懒加载
7. N+1 查询问题与优化方案
8. **ORM 与 Pydantic 对象转换**（新增）

## 关键技术点

### 1. 流式输出实现

**后端**：使用 `StreamingResponse` + SSE
```python
async def generate_stream():
    async for chunk in agent_service.process_stream(...):
        yield f"data: {json.dumps(chunk)}\n\n"
return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

**前端**：使用 `EventSource` 或 `TextDecoder` 解析 SSE

### 2. LangChain Agent 工具调用

```python
# 工具调用提取
if hasattr(msg, "tool_calls") and msg.tool_calls:
    for tool_call in msg.tool_calls:
        tool_info = {
            "name": tool_call["name"],
            "args": dict(tool_call["args"]),
            "id": tool_call["id"],
        }
        # 只保存有效的工具调用
        if tool_info["name"] and tool_info["id"]:
            tool_calls.append(tool_info)
```

### 3. 乐观更新

```typescript
// 立即显示用户消息
const tempUserMessage: Message = {
  id: `temp-user-${Date.now()}`,
  session_id: currentSession.id,
  role: 'user',
  content,
  created_at: new Date().toISOString()
}
messagesStore.messages.push(tempUserMessage)
```

### 4. Pinia Setup Store Refs 自动解包

```typescript
// ❌ 错误
messagesStore.messages.value.push(item)

// ✅ 正确
messagesStore.messages.push(item)
```

## 常见问题

### Q: 为什么删除会话后消息还在？

A: 需要在 sessions store 中调用 `messagesStore.clearMessages()`

### Q: 为什么会有重复的用户消息？

A: 后端 `/message` 端点已经创建 user 消息，前端不应该重复调用 `createMessage()`

### Q: 工具调用失败怎么办？

A: 检查 tool_calls 是否有效（有 name 和 id），对话历史不应恢复 tool_calls

### Q: 流式输出卡住怎么办？

A: 确保 `onComplete` 回调中调用 `clearStreamingMessage()`

## 开发工作流

1. 修改 models.py → 重启后端（自动创建表）
2. 修改 crud.py → 重启后端
3. 修改 api.py → 热重载生效
4. 修改 services.py → 重启后端（Agent 重新初始化）
5. 修改前端 → Vite 热更新

## 依赖版本

| 包 | 版本 |
|----|------|
| FastAPI | 最新 |
| SQLAlchemy | 最新 |
| Pydantic | v2 |
| Vue | 3.4+ |
| Pinia | 2.1+ |
| TypeScript | 5.3+ |
| Tailwind CSS | 3.4+ |
