# Agent SQL 上下文与结果返回机制说明

修改时间：2026-04-12 Asia/Shanghai

主要修改内容：
- 整理从 `PostgreSQL search_path` 与物化视图支持开始的一整段设计讨论
- 说明 `schema`、`search_path`、物化视图纳入、元数据抓取、`sql_db_schema` 移除后的实际影响
- 说明为什么将 `sql_db_query` 结果升级为默认带列名结构
- 总结当前实现中哪些能力真正对 LLM 生效，哪些只是底层准备能力

## 1. 背景

在 Agent 切换到 `analytics_db` 之后，我们引入了两类底层能力：

1. PostgreSQL `search_path`
2. 物化视图（materialized view）支持

后来又围绕这两个能力继续讨论了几个关键问题：

- `schema` 到底是什么
- `search_path` 会不会把 `rb_position_data` 自动变成 `mart.rb_position_data`
- 移除了 `sql_db_schema` 工具以后，元数据抓取还有没有意义
- 如果查询结果没有列名，会不会影响 LLM 对结果的判断
- 是否应该把 `sql_db_query` 改成默认返回带列名的结构

这份文档把这些点统一整理，避免后续继续散落在聊天记录里。

## 2. 这个机制主要解决什么问题

`analytics_db` 不是单一 `public` schema，而是分层数据库：

- `mart`
- `fct`
- `dim`
- `ods`
- `meta`
- `public`

同时，Agent 现在优先依赖：

- `mart_*`
- `fct_*`

而不是直接面对源表或底层 `ods` 表。

因此我们需要解决 3 类问题：

1. LLM 写无 schema SQL 时，数据库如何正确找到对象
2. LangChain 的 `SQLDatabase` 如何识别 `mart` / `fct` 里的物化视图
3. LLM 在拿到查询结果后，如何尽量稳地理解列和值的对应关系

## 3. `schema` 是什么

在 PostgreSQL 里，`schema` 可以理解成数据库内部的“命名空间”或“分层文件夹”。

例如：

- `ods.rb_position_data`
- `fct.fct_vehicle_position_current`
- `mart.mart_vehicle_quality_360`

其中：

- `analytics_db` 是数据库
- `ods`、`fct`、`mart` 是 schema
- `rb_position_data`、`fct_vehicle_position_current`、`mart_vehicle_quality_360` 是具体对象

所以：

- 数据库 = 大仓库
- schema = 仓库里的分区
- 表 / 视图 / 物化视图 = 分区里的对象

## 4. `search_path` 的原理

### 4.1 基本原理

当 SQL 没有显式写 schema 时，例如：

```sql
SELECT id, plc, tag FROM rb_position_data;
```

PostgreSQL 会按 `search_path` 顺序去各个 schema 里找同名对象。

当前配置是：

```text
mart, fct, dim, ods, meta, public
```

也就是说数据库会按这个顺序查找：

1. `mart.rb_position_data`
2. `fct.rb_position_data`
3. `dim.rb_position_data`
4. `ods.rb_position_data`
5. `meta.rb_position_data`
6. `public.rb_position_data`

找到第一个存在的对象就停止。

### 4.2 这不等于“自动改名”

`search_path` 不是把 `rb_position_data` 自动变成 `mart.rb_position_data`。

它只是告诉 PostgreSQL：

- “当用户没写 schema 时，按这个优先顺序去找”

当前设计里：

- `rb_position_data` 只存在于 `ods`
- 所以 `SELECT * FROM rb_position_data` 最终命中的是 `ods.rb_position_data`

### 4.3 为什么顺序要设成 `mart -> fct -> dim -> ods`

这是一个有意识的产品化设计，而不是随便排的：

- 优先命中 `mart`，让模型更容易查高层稳定分析对象
- 再命中 `fct`，用于事实层补充
- 再看 `dim`
- 最后才回到底层 `ods`

这样做的目的是尽量减少模型直接碰底层表。

## 5. 项目里 `search_path` 是怎么接上的

### 5.1 配置入口

在 [config.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py) 中增加了：

- `analytics_database_url`
- `analytics_db_search_path`

默认值是：

```text
mart,fct,dim,ods,meta,public
```

### 5.2 SQLAlchemy 引擎参数构造

在 [sql_database.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/sql_database.py) 中：

- `build_postgres_search_path_engine_args()`

会把 `search_path` 转成 SQLAlchemy 的 `connect_args`：

```python
{
    "connect_args": {
        "options": "-csearch_path=mart,fct,dim,ods,meta,public"
    }
}
```

也就是说，每次连接 `analytics_db` 时，session 一建立就自带这个 schema 搜索顺序。

### 5.3 在服务里接入

在 [service.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py) 中：

- `_get_business_database_url()`：优先取 `analytics_db`
- `_get_business_database_engine_args()`：如果是 `analytics_db`，就补 `search_path`
- `_create_database_connection()`：用带 `engine_args` 的数据库连接初始化 SQLDatabase

CSV 导出工具也已经补齐同样逻辑，所以查询和导出现在使用同一套 `search_path`。

## 6. 为什么要支持物化视图

`analytics_db` 里给 Agent 暴露的很多核心对象不是普通表，而是物化视图，例如：

- `mart_vehicle_quality_360`
- `mart_abnormal_vehicle_current`
- `mart_position_current_overview`

这些对象的价值在于：

- 预先把高频复杂查询算好
- 提供更稳定的分析口径
- 让模型尽量查单表或低复杂度对象

问题在于，LangChain 原生 `SQLDatabase` 默认并不稳定覆盖 PostgreSQL 物化视图。

如果不做扩展，就会出现：

- 数据库里明明有 `mart_*`
- 但 Agent 的可用对象集合里看不到它们

## 7. 项目里物化视图是怎么纳入的

在 [sql_database.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/sql_database.py) 中新增了：

- `MaterializedViewSQLDatabase`

它在初始化时会收集：

1. 普通表：`get_table_names()`
2. 普通视图：`get_view_names()`
3. 物化视图：`get_materialized_view_names()`

然后统一放进 `_all_tables`。

这样对 Agent 来说：

- `mart_vehicle_quality_360`
- `mart_abnormal_vehicle_current`
- `mart_position_current_overview`

都变成了“可见对象”。

## 8. 元数据抓取到底有什么用

这里要区分两个概念：

### 8.1 运行时工具：`sql_db_schema`

这是 LangChain 默认的 schema 查看工具。  
它已经在当前项目里被移除了，见：

- [constants.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/constants.py)

原因是当前项目希望：

- 强制先走 `load_skill()`
- 不让模型在运行时自由扫库

### 8.2 启动时元数据抓取

这部分由 [db_utils.py](/f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/db_utils.py) 中的：

- `fetch_table_definitions_with_comments()`

负责。

它会抓：

- 表
- 普通视图
- 物化视图
- 字段注释

然后作为 `custom_table_info` 交给 `SQLDatabase`。

## 9. 一个关键澄清：这些元数据当前有没有真正“告诉” LLM

### 9.1 讨论后的结论

**当前并没有直接注入到 system prompt 或 user message。**

也就是说：

- 服务启动时确实抓了这些结构信息
- 但当前 `system_prompt` 没有显式拼接 `db.get_context()`
- `sql_db_schema` 也已经移除了

所以从“LLM 能否直接读到这段结构文本”来说，答案是：

**当前不能直接读到。**

### 9.2 那元数据抓取还有没有意义

有，但意义要拆开看：

#### 有直接意义的部分

- 让 `SQLDatabase` 正确认出物化视图
- 让底层数据库对象集合完整

#### 当前对 LLM 直接帮助有限的部分

- 字段注释和表结构摘要本身

因为这部分现在还没有被显式注入模型上下文。

### 9.3 结论

当前实现中，真正直接作用于 LLM 的主要还是：

- `load_skill()` 载入的领域知识
- 工具描述与参数说明
- 可调用的工具集合
- `search_path` 带来的“无 schema SQL 更容易跑通”

而不是 `custom_table_info` 本身。

## 10. 为什么后来还要改查询结果返回格式

在继续讨论时，我们又发现一个实际问题：

- 即使 SQL 能跑通
- 如果 `sql_db_query` 返回给模型的是“只有值、没有列名”的元组列表
- 那 LLM 在解释结果时仍然容易出错

特别是下面几类情况：

- `SELECT *`
- 宽表
- 多表 join
- 字段含义接近的结果集

## 11. 原来的返回格式有什么问题

LangChain 的 `SQLDatabase.run()` 默认是：

- `include_columns=False`

这意味着结果会被转成：

```python
[('val1', 'val2'), ('val3', 'val4')]
```

也就是：

- 只有值
- 没有列名

如果查询是：

```sql
SELECT vehicle_id, process_area, carrier_id
FROM mart_position_current_overview
```

模型还能勉强根据自己刚写的列顺序去猜。

但如果是：

```sql
SELECT * FROM mart_vehicle_quality_360
```

模型拿到结果时，基本不知道每个值对应什么字段。

## 12. 结果带列名为什么更接近最佳实践

对于 SQL Agent 来说，更好的做法是：

- 仍然约束 LLM 尽量不要 `SELECT *`
- 但即使它写了，也尽量让返回结果带列名

这样做的优点：

1. 列和值一一对应，模型更容易理解结果
2. 宽表和多表结果可读性明显更高
3. 后续做总结、解释、二次判断时更稳
4. 更接近真实分析场景里“看结构化结果”的方式

因此，当前项目已将 `sql_db_query` 改为优先走：

```python
db.run_no_throw(query, include_columns=True)
```

现在返回结果更接近：

```python
[{'vehicle_id': '782026...', 'process_area': 'L2面漆储存线', 'carrier_id': '1281'}]
```

## 13. 配套做了哪些兼容处理

因为历史上结果格式是元组列表，当前改造还同步兼容了两种格式：

- 老格式：`[('a', 'b')]`
- 新格式：`[{'col1': 'a', 'col2': 'b'}]`

对应改造点在：

- `_estimate_row_count()`
- `_extract_preview_rows()`

这样结果限流和预览机制不会因为返回结构升级而失效。

## 14. 当前实现的关键结论

### 14.1 已经真正生效的能力

- `analytics_db` 连接优先级切换
- PostgreSQL `search_path`
- 物化视图纳入 SQLDatabase
- CSV 导出与查询共享 `search_path`
- 查询结果默认带列名

### 14.2 当前还没有真正发挥完全价值的能力

- 启动时抓到的 `custom_table_info`
- 字段注释与表结构摘要

原因是：

- 这些内容还没有显式进入模型上下文

## 15. 后续如果继续优化，建议往哪走

### 15.1 优先建议

继续保留当前结果带列名方案，不回退到元组格式。

### 15.2 下一步值得考虑的增强

可以在不放开 `sql_db_schema` 的前提下，做一种“受控的结构摘要注入”，例如：

- 只把核心 `mart/fct` 的轻量结构摘要注入 prompt
- 而不是让模型自由扫库

### 15.3 不建议的方向

不建议重新完全放开 `sql_db_schema` 和 `sql_db_list_tables`，否则容易和当前技能系统产生冲突：

- skills 负责业务口径
- 数据库对象只应作为受控执行面

## 16. 复用检查清单

如果以后别的分析库也要接入 Agent，可以用下面清单复用：

- 数据库是否存在多 schema 分层
- 是否需要通过 `search_path` 让无 schema SQL 跑通
- 是否使用了普通视图或物化视图作为核心消费对象
- `SQLDatabase` 是否能识别这些对象
- 是否真的把结构摘要注入给了模型，还是只是底层抓了但没用上
- 查询结果是否带列名
- 限流逻辑是否兼容当前返回格式

## 17. 一句话总结

这轮优化的本质，是把“数据库能找到对象”升级成“Agent 能更稳地用对象”，而真正让模型判断更稳的关键一步，是让查询结果默认带上列名。
