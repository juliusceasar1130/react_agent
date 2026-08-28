# SQL Agent 开发文档

> 创建日期：2025-01-11
> 文档描述：基于 LangChain 创建 SQL 数据库智能体开发指南

## 概述

本文档介绍如何基于 LangChain 创建一个 SQL 数据库智能体（SQL Agent），使其能够通过自然语言与数据库进行交互，执行查询并返回结果。

## 1. 环境配置与初始化

### 1.1 安装依赖

```bash
pip install langchain langchain-community langchain-core python-dotenv
```

### 1.2 加载环境变量

```python
import dotenv
import os

dotenv.load_dotenv()  # 加载当前目录下的 .env 文件
```

### 1.3 初始化大语言模型

```python
from langchain.chat_models import init_chat_model

llm = init_chat_model(
    model="deepseek-chat",
    model_provider="deepseek",
    api_key=os.environ.get("OPENAI_API_KEY"),
)
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `model` | 模型名称，支持 deepseek-chat、gpt-4、claude-3 等 |
| `model_provider` | 模型提供商标识 |
| `api_key` | API 密钥，从环境变量读取 |

---

## 2. 数据库配置

### 2.1 连接数据库

LangChain 提供了 `SQLDatabase` 工具来连接各种数据库。

```python
from langchain_community.utilities import SQLDatabase

# MySQL 连接示例
db = SQLDatabase.from_uri(
    "mysql+pymysql://root:root@localhost:3306/changepoint?charset=utf8mb4"
)

# SQLite 连接示例
# db = SQLDatabase.from_uri("sqlite:///Chinook.db")
```

### 2.2 获取数据库信息

```python
print(f"Dialect: {db.dialect}")
print(f"Available tables: {db.get_usable_table_names()}")
print(f'Sample output: {db.run("SELECT * FROM emos_web_data LIMIT 5;")}')
```

**输出示例：**
```
Dialect: mysql
Available tables: ['emos_web_data', 'equipment_ioitem_map']
```

---

## 3. 数据库交互工具

### 3.1 创建工具包

LangChain 提供了 `SQLDatabaseToolkit` 来自动生成 SQL 相关的工具。

```python
from langchain_community.agent_toolkits import SQLDatabaseToolkit

toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()
```

### 3.2 工具列表

| 工具名称 | 描述 |
|---------|------|
| `sql_db_query` | 执行 SQL 查询，返回数据库结果 |
| `sql_db_schema` | 查询指定表的结构和示例数据 |
| `sql_db_list_tables` | 列出数据库中所有可用的表 |
| `sql_db_query_checker` | 检查 SQL 查询的语法正确性 |

---

## 4. 创建 Agent

### 4.1 定义 System Prompt

```python
system_prompt = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most {top_k} results.

You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

You MUST double check your query before executing it. If you get an error while
executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
database.

To start you should ALWAYS look at the tables in the database to see what you
can query. Do NOT skip this step.

Then you should query the schema of the most relevant tables.
""".format(
    dialect=db.dialect,
    top_k=5,
)
```

### 4.2 创建 Agent 实例

```python
from langchain.agents import create_agent

agent = create_agent(
    llm,
    tools,
    system_prompt=system_prompt,
)
```

---

## 5. 运行 Agent

### 5.1 基本查询

```python
question = "3线工艺最近一次是谁修改的点位?"

for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    stream_mode="values",
):
    step["messages"][-1].pretty_print()
```

**执行流程：**
1. Agent 接收自然语言问题
2. 分析问题意图，确定需要查询的表
3. 查看数据库表结构
4. 生成 SQL 查询语句
5. 执行查询并返回结果

---

## 6. 人机交互审核（Human-in-the-Loop）

在生产环境中，建议对敏感操作（如数据库查询）添加人工审核机制。

### 6.1 创建带审核的 Agent

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    llm,
    tools,
    system_prompt=system_prompt,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"sql_db_query": True},  # 在执行查询前中断
            description_prefix="Tool execution pending approval",
        ),
    ],
    checkpointer=InMemorySaver(),  # 允许暂停和恢复执行
)
```

### 6.2 执行查询（带审核）

```python
from langgraph.types import Command

question = "注蜡有几个点位?"
config = {"configurable": {"thread_id": "1"}}

# 第一步：执行到审核点
for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    config,
    stream_mode="values",
):
    if "messages" in step:
        step["messages"][-1].pretty_print()
    elif "__interrupt__" in step:
        print("INTERRUPTED:")
        interrupt = step["__interrupt__"][0]
        for request in interrupt.value["action_requests"]:
            print(request["description"])

# 第二步：批准执行
for step in agent.stream(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config,
    stream_mode="values",
):
    if "messages" in step:
        step["messages"][-1].pretty_print()
```

**执行流程：**
1. Agent 生成 SQL 查询
2. 在执行查询前暂停，触发中断
3. 显示待执行的查询请求
4. 用户批准后继续执行查询
5. 返回查询结果

---

## 7. 完整代码示例

```python
import dotenv
import os
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

# 1. 加载环境变量
dotenv.load_dotenv()

# 2. 初始化模型
llm = init_chat_model(
    model="deepseek-chat",
    model_provider="deepseek",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# 3. 连接数据库
db = SQLDatabase.from_uri(
    "mysql+pymysql://root:root@localhost:3306/changepoint?charset=utf8mb4"
)

# 4. 创建工具包
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# 5. 定义系统提示
system_prompt = """..."""

# 6. 创建 Agent
agent = create_agent(
    llm,
    tools,
    system_prompt=system_prompt,
    checkpointer=InMemorySaver(),
)

# 7. 执行查询
question = "注蜡有几个点位?"
for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    stream_mode="values",
):
    step["messages"][-1].pretty_print()
```

---

## 8. 注意事项

1. **安全限制**：Agent 默认禁止执行 DML 语句（INSERT、UPDATE、DELETE、DROP）
2. **查询限制**：默认限制返回最多 5 条结果，可通过 `top_k` 参数调整
3. **错误处理**：SQL 执行出错时会自动重写查询并重试
4. **数据库支持**：支持 MySQL、PostgreSQL、SQLite、Oracle 等主流数据库
5. **审核机制**：生产环境建议启用 Human-in-the-Loop 审核

---

## 9. 常见问题

**Q: 如何连接其他数据库？**

```python
# PostgreSQL
db = SQLDatabase.from_uri("postgresql+psycopg2://user:password@host/dbname")

# Oracle
db = SQLDatabase.from_uri("oracle+cx_oracle://user:password@host:1521/service")

# SQL Server
db = SQLDatabase.from_uri("mssql+pyodbc://user:password@host/dbname?driver=ODBC+Driver+17+for+SQL+Server")
```

**Q: 如何修改返回结果数量？**

在 `system_prompt` 中修改 `top_k` 参数值。

**Q: Agent 返回 "Unknown column" 错误怎么办？**

Agent 会自动调用 `sql_db_schema` 工具重新获取表结构，如果仍有问题请检查数据库连接和表权限。
