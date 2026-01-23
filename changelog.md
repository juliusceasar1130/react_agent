# Changelog

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
