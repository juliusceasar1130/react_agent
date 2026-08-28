针对您在 LangChain 中连接 PostgreSQL 并希望大模型理解表/字段注释的需求，以下是整合后的**最佳实践指导方案**。

---

## LangChain + PostgreSQL 注释识别最佳实践

### 1. 核心原理：静态注入 (Custom Table Info)

LangChain 默认的 `sql_db_schema` 工具只能抓取表名和列名。要让模型看到注释，必须通过 `custom_table_info` 参数，将包含注释的 DDL 语句手动“喂”给 `SQLDatabase` 对象。

### 2. 标准实施流程

#### 第一步：编写元数据提取函数

利用 SQLAlchemy 的 `inspect` 模块，从 PostgreSQL 系统表中提取 `COMMENT` 信息，并拼接成带注释的伪 DDL。

```python
from sqlalchemy import create_engine, inspect

def get_annotated_schema(uri: str):
    engine = create_engine(uri)
    inspector = inspect(engine)
    custom_info = {}
    
    # 获取表和视图
    for table in inspector.get_table_names() + inspector.get_view_names():
        table_comment = inspector.get_table_comment(table).get('text')
        columns = inspector.get_columns(table)
        
        # 构造增强版 DDL
        ddl = f"-- Table: {table}\n"
        if table_comment:
            ddl += f"-- Table Comment: {table_comment}\n"
        ddl += f"CREATE TABLE {table} (\n"
        
        col_defs = []
        for col in columns:
            line = f"  {col['name']} {col['type']}"
            if col.get('comment'):
                line += f" -- {col['comment']}" # 注入列注释
            col_defs.append(line)
        
        ddl += ",\n".join(col_defs) + "\n);"
        custom_info[table] = ddl
    
    engine.dispose()
    return custom_info

```

#### 第二步：初始化数据库对象

在服务启动时运行一次提取函数，并将结果传入 `from_uri`。

```python
custom_info = get_annotated_schema(settings.rollerbed_database_url)

db = SQLDatabase.from_uri(
    settings.rollerbed_database_url,
    view_support=True,
    custom_table_info=custom_info  # 关键：这会让 sql_db_schema 工具直接读取这段文本
)

```

### 3. 处理大规模表（如 100+ 表）的策略

当数据库规模较大时，为了防止 Token 溢出并提高查询准确性，请遵循以下原则：

* **按需加载 (Lazy Loading)**：LangChain Agent 的原生逻辑是：`sql_db_list_tables` (看表名) -> `sql_db_schema` (选定 2-3 个表看详情)。因此，即便 `custom_table_info` 存了 100 个表，模型每次只会消耗它选中的那几个表的 Token。
* **黑白名单机制**：如果数据库中包含大量日志表或无关表，使用 `include_tables` 或 `ignore_tables` 进行过滤。
* **表名语义化**：确保表名具有辨识度（如 `t_prod_record` 而不是 `t1`），否则模型在第一步 `list_tables` 时就无法选出正确的表。

### 4. System Prompt 的配合调整

在 System Message 中明确引导模型参考注释：

> **指令：** "在编写 SQL 之前，请务必调用 `sql_db_schema` 查看相关表的详细信息。注意：表结构中以 `--` 开头的内容是字段的中文业务注释，必须严格参考注释来识别字段含义（例如处理日期格式或状态码）。"

---

### 5. 常见坑点排查

1. **视图 (Views) 支持**：如果业务逻辑在视图里，`view_support=True` 必须开启。
2. **驱动兼容性**：确保使用 `psycopg2` 或 `pg8000` 驱动，以便 SQLAlchemy 能够顺利读取 PostgreSQL 的元数据。
3. **刷新机制**：如果数据库增加了新字段或注释，`SQLAgentService` 需要重启或重新实例化 `db` 对象，因为 `custom_table_info` 是静态注入的。

---

**下一步建议：**
您可以先尝试为您最核心的 2-3 个表手动编写 `custom_table_info` 进行测试，观察大模型在生成 SQL 时是否能够准确引用注释中的业务逻辑。如果您需要自动化程度更高的**动态 DDL 注入**方案（针对表结构经常变动的情况），我可以为您提供更进阶的代码。