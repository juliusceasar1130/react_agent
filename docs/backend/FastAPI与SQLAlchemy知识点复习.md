# FastAPI + SQLAlchemy 知识点复习

## 目录
1. [CRUD 操作](#1-crud-操作)
2. [同步 vs 异步](#2-同步-vs-异步)
3. [依赖注入 Depends](#3-依赖注入-depends)
4. [数据库模型与 Schema 转换](#4-数据库模型与-schema-转换)
5. [response_model 工作原理](#5-response_model-工作原理)
6. [字段名匹配机制](#6-字段名匹配机制)
7. [SQLAlchemy 关系与懒加载](#7-sqlalchemy-关系与懒加载)
8. [ORM 与 Pydantic 对象转换](#8-orm-与-pydantic-对象转换)

---

## 1. CRUD 操作

### 基本 CRUD 方法

| 方法 | 说明 |
|------|------|
| `create()` | 创建新记录 |
| `get()` | 根据 ID 查询单条 |
| `get_all()` / `list()` | 查询所有记录（支持分页） |
| `update()` | 更新记录 |
| `delete()` | 删除记录 |

### 更新操作最佳实践

```python
# ✅ 推荐：动态过滤 None 值
def update_session(db: Session, session_id: str, session_update: SessionUpdate):
    update_data = session_update.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in update_data.items():
        setattr(db_session, field, value)

# model_dump 参数说明
# exclude_unset=True  → 排除未设置的字段
# exclude_none=True   → 排除值为 None 的字段
```

### 创建消息前检查关联

```python
# ✅ 复用已有函数检查
def create_message(db: Session, message: MessageCreate):
    db_session = get_session(db, message.session_id)
    if not db_session:
        raise ValueError(f"会话不存在")
    # ... 创建消息
```

---

## 2. 同步 vs 异步

### 同步架构（当前）

```python
# API 层
def endpoint(db: Session = Depends(get_db)):
    return create_session(db, session)

# CRUD 层
def create_session(db: Session, session: SessionCreate):
    db.add(db_session)
    db.commit()  # 同步阻塞
```

### 异步架构（高并发优化）

```python
# 需要改造的范围
┌─────────────────────────────────────────────────────┐
│  1. API 层     →  async def endpoint()              │
│  2. CRUD 层    →  async def create_session()        │
│  3. 数据库层   →  AsyncSession + async引擎          │
│  4. 驱动       →  aiosqlite / aiomysql             │
└─────────────────────────────────────────────────────┘
```

| 方式 | 驱动 | 适用场景 |
|------|------|----------|
| 同步 | PyMySQL / sqlite3 | 一般业务，并发 < 100 |
| 异步 | aiomysql / aiosqlite | 高并发，调用外部 API |

**建议**：保持同步即可，除非有明确的高并发需求。

---

## 3. 依赖注入 Depends

### 工作原理

```python
# 1. 定义依赖函数
def get_db():
    db = SessionLocal()     # 创建会话
    try:
        yield db            # 传给接口使用
    finally:
        db.close()          # 用完自动关闭

# 2. 接口中使用
def endpoint(db: Session = Depends(get_db)):
    # FastAPI 自动调用 get_db()
    return get_sessions(db)
```

### 执行流程

```
请求到达
    ↓
FastAPI 调用 get_db()
    ↓
yield db  ───────────────────┐
    ↓                         ↓
接口使用 db 操作数据库    请求结束后
    ↓                         ↓
返回响应              finally: db.close()
```

### 好处

| 好处 | 说明 |
|------|------|
| 自动管理 | 无需手动创建/关闭会话 |
| 复用代码 | 每个接口不用重复写 `db = SessionLocal()` |
| 安全 | 确保 `db.close()` 一定执行 |

---

## 4. 数据库模型与 Schema 转换

### 两层模型

```python
# models.py - SQLAlchemy ORM（数据库层）
class ChatSession(Base):
    id: str
    title: str
    created_at: DateTime
    messages: List[ChatMessage]  # relationship

# schemas.py - Pydantic（API 层）
class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: List[MessageResponse] = []
```

### 转换流程

```
CRUD 返回 ChatSession (数据库模型)
    ↓
FastAPI 根据 response_model=SessionResponse
    ↓
通过字段名匹配，自动转换
    ↓
SessionResponse (Pydantic Schema)
    ↓
JSON 响应给客户端
```

### 关键配置

```python
# schemas.py
class SessionResponse(SessionBase):
    model_config = ConfigDict(from_attributes=True)  # ← 允许从 ORM 模型转换
```

---

## 5. response_model 工作原理

### API 返回的是数据库模型

```python
@router.post("/sessions", response_model=SessionResponse)
def create_session_endpoint(...):
    db_session = create_session(db, session)  # 返回 ChatSession
    return db_session  # ← FastAPI 自动转换为 SessionResponse
```

### 新建会话时的 messages

```python
# SessionResponse 有 messages 字段
class SessionResponse:
    messages: List[MessageResponse] = []  # 默认空列表

# 新会话没有消息，返回：
{
  "id": "abc-123",
  "title": "我的对话",
  "messages": []  # ← 空数组，正常
}
```

---

## 6. 字段名匹配机制

### 通过字段名（非位置）匹配

```python
# ✅ 正确：字段名一致
class ChatSession:
    title: str

class SessionResponse:
    title: str  # 同名，自动映射

# ❌ 错误：字段名不一致
class ChatSession:
    title: str

class SessionResponse:
    name: str  # 不同名，无法映射
```

### 别名映射（如需不同名）

```python
from pydantic import Field

class SessionResponse:
    name: str = Field(alias="title")  # Schema 用 name，映射到模型的 title
```

---

## 7. SQLAlchemy 关系与懒加载

### Relationship 配置

```python
class ChatSession(Base):
    messages = relationship("ChatMessage", back_populates="session")  # 默认 lazy="select"
```

### 懒加载机制

```python
# 步骤 1: 查询会话（还没加载 messages）
db_session = db.query(ChatSession).first()

# 步骤 2: 访问 messages 时，自动触发额外查询
messages = db_session.messages  # ← 此时才执行 SELECT * FROM chat_messages ...
```

### FastAPI 自动触发加载

```python
@router.get("/sessions/{id}", response_model=SessionResponse)
def get_session_endpoint(...):
    db_session = get_session(db, id)
    return db_session  # ← FastAPI 序列化时访问所有字段，包括 messages
                      #   触发懒加载，自动查询消息
```

### 性能问题 - N+1 查询

```python
# 问题：1 次查会话 + N 次查消息
sessions = get_sessions(db)  # 1 次查询
for s in sessions:
    print(s.messages)        # N 次查询（每个会话触发一次）
```

### 优化方案（预加载）

```python
from sqlalchemy.orm import joinedload

# 一次性查询会话和消息（JOIN）
db.query(ChatSession).options(joinedload(ChatSession.messages)).all()
```

---

## 8. ORM 与 Pydantic 对象转换

### 8.1 两层模型架构

```python
# models.py - SQLAlchemy ORM（数据库层）
from sqlalchemy.orm import relationship

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True)
    title = Column(String(255))
    created_at = Column(DateTime)
    # relationship 自动关联 ChatMessage
    messages = relationship("ChatMessage", back_populates="session")


# schemas.py - Pydantic（API 层）
from pydantic import BaseModel, ConfigDict

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int = 0
    messages: List[MessageResponse] = []

    # ← 关键配置：允许从 ORM 对象创建 Pydantic 模型
    model_config = ConfigDict(from_attributes=True)
```

### 8.2 `from_attributes=True` 的作用

#### 配置前（无法自动转换）

```python
# 假设没有 from_attributes=True
class SessionResponse(BaseModel):
    id: str
    title: str

# CRUD 返回 SQLAlchemy ORM 对象
db_session = ChatSession(id="123", title="我的对话")

# ✗ 错误：无法直接从 ORM 对象创建
response = SessionResponse.model_validate(db_session)
# ValidationError: Input should be a valid dictionary or ORM object
```

#### 配置后（自动提取属性）

```python
class SessionResponse(BaseModel):
    id: str
    title: str

    model_config = ConfigDict(from_attributes=True)  # ← 开启自动转换

# ✓ 正确：自动从 ORM 对象提取属性
db_session = ChatSession(id="123", title="我的对话")
response = SessionResponse.model_validate(db_session)
print(response.title)  # "我的对话"
```

### 8.3 对象转换流程

```
┌─────────────────────────────────────────────────────────────┐
│  CRUD 层返回 ORM 对象                                         │
│                                                              │
│  db_session = ChatSession(                                  │
│      id="abc-123",                                          │
│      title="我的对话",                                       │
│      created_at=datetime(...)                               │
│  )                                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FastAPI 根据 response_model 自动转换                         │
│                                                              │
│  @router.get("/sessions", response_model=SessionResponse)   │
│  def get_sessions():                                         │
│      return get_sessions(db)  # ORM 对象列表                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Pydantic 提取字段，匹配同名属性                               │
│                                                              │
│  SessionResponse = {                                        │
│      "id": "abc-123",         ← 从 ORM.id 提取               │
│      "title": "我的对话",      ← 从 ORM.title 提取            │
│      "created_at": "2025-..." ← 从 ORM.created_at 提取       │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  序列化为 JSON 返回给前端                                      │
│                                                              │
│  application/json                                          │
│  {                                                          │
│    "id": "abc-123",                                        │
│    "title": "我的对话",                                     │
│    "created_at": "2025-01-01T10:00:00"                     │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 8.4 嵌套模型的转换

#### 场景：`ChatResponse` 包含 `MessageResponse`

```python
class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse      # ← 嵌套 Pydantic 模型
    is_complete: bool = True

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    # ← 只有 MessageResponse 有 from_attributes=True
    model_config = ConfigDict(from_attributes=True)
```

#### API 层返回

```python
@router.post("/message", response_model=ChatResponse)
def send_message(...):
    # assistant_message 是 SQLAlchemy ORM 对象
    assistant_message = crud.create_message(...)

    return ChatResponse(
        session_id=session_id,
        message=assistant_message,  # ← ORM 对象自动转换为 MessageResponse
        is_complete=True
    )
```

#### 为什么 `ChatResponse` 不需要 `from_attributes=True`？

| 模型 | 是否需要配置 | 原因 |
|------|--------------|------|
| `MessageResponse` | ✅ 需要 | 直接从 ORM 对象创建 |
| `ChatResponse` | ❌ 不需要 | 它包含的 `MessageResponse` 已配置 |

**关键**：FastAPI 序列化 `ChatResponse` 时，会递归处理 `message` 字段，此时 `MessageResponse` 的 `from_attributes=True` 生效。

### 8.5 `model_config` 的其他常用配置

```python
from pydantic import ConfigDict, Field

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str

    # 配置字典
    model_config = ConfigDict(
        from_attributes=True,     # 允许从 ORM 对象创建
        populate_by_name=True,     # 使用字段名而非别名填充
        str_strip_whitespace=True, # 自动去除字符串两端空格
        validate_assignment=True,  # 赋值时进行验证
        extra='ignore'             # 忽略额外字段（不报错）
    )
```

### 8.6 常见问题

#### Q1: 为什么不直接返回字典？

```python
# ✗ 方式 A：手动构造字典
return {
    "session_id": session_id,
    "message": {
        "id": assistant_message.id,
        "role": assistant_message.role,
        # ... 需要手动列出每个字段
    }
}

# ✓ 方式 B：使用 Pydantic（推荐）
return ChatResponse(
    session_id=session_id,
    message=assistant_message  # 自动提取所有字段
)
```

**优势**：
- 自动类型验证
- 字段名自动补全
- 生成 OpenAPI 文档
- 代码更简洁

#### Q2: `from_orm` 和 `from_attributes` 的区别？

| 版本 | 方法 | 说明 |
|------|------|------|
| Pydantic v1 | `.from_orm()` | 旧方法，已废弃 |
| Pydantic v2 | `model_config = ConfigDict(from_attributes=True)` | 新方法 |

**迁移指南**：
```python
# Pydantic v1（旧）
class UserResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True  # ← v1 配置

# Pydantic v2（新）
class UserResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)  # ← v2 配置
```

#### Q3: 字段名不一致怎么办？

```python
# ORM 模型字段名
class ChatSession:
    title: str  # 数据库字段名

# API 需要返回不同字段名
class SessionResponse(BaseModel):
    name: str = Field(alias="title")  # API 用 name，映射到 title

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True  # 使用字段名 title 填充
    )
```

### 8.7 最佳实践总结

| 场景 | 推荐做法 | 原因 |
|------|---------|------|
| CRUD 返回单条 ORM | 直接返回 | FastAPI + Pydantic 自动转换 |
| 返回自定义结构 | `dict()` 或 Pydantic | 灵循类型安全 |
| 嵌套模型 | 子模型配置 `from_attributes=True` | 递归自动转换 |
| 字段名不一致 | 使用 `Field(alias=...)` | 兼容不同命名约定 |

---

## 总结对比表

| 概念 | 当前实现 | 高级实现 |
|------|----------|----------|
| API 类型 | 同步 `def` | 异步 `async def` |
| 数据库驱动 | sqlite3 | aiosqlite / aiomysql |
| 加载方式 | 懒加载 | 预加载 `joinedload` |
| ORM 转换 | `from_attributes=True` | 手动映射（特殊场景） |

**当前设计已满足大多数场景，按需优化即可。**
