# 阶段 4：主动纠偏工具链挂载与 SQL Agent 自愈重写详细设计规格 (Spec)

本设计规格详细规定了 LlamaIndex 检索思想与本项目双轨融合设计报告中“阶段 4”的落地实施方案。该阶段的核心目标是当 SQL Agent 执行 SQL 返回结果为空时，自发通过 Milvus 向量物理词典进行列值或行实体纠偏，实现大模型层面的“自愈”重试。

---

## 一、 架构设计与协作关系

在“数据库物理词典 (DB Lexicon)”体系下，RAG 阶段（在线三路并发检索）与大模型自主微调纠错（工具调用阶段）共享同一个物理词典存储，但它们拥有不同的职责边界：

*   **RAG 阶段 (BusinessRagMiddleware)**：
    *   在首轮用户消息时，进行前置的宽检索。
    *   其目的是**为大模型提供背景知识**，将最相似的表 DDL、去重列值、行实体以 System Message 形式带入，让大模型在第一轮决策时就尽量写出正确的 SQL。
*   **工具调用与自愈阶段 (sql_db_query & 纠偏/探索工具)**：
    *   当大模型第一轮生成的 SQL 因为拼写误差等原因，导致在数据库中执行结果为**空结果集 (`[]`)**，或者遇到对某张表结构认知不足时，大模型反思后主动触发检索。
    *   大模型自主调用 `search_db_value_lexicon` 或 `search_db_row_lexicon` 获取准确的真实列值或实体主键；调用 `search_db_table_schema` 补充 DDL。
    *   纠偏完成后，重新生成 SQL 并再次调用 `sql_db_query` 执行。

为了保证效率和连接复用，`DatabaseLexiconRetriever` 在服务生命周期中作为**单例对象**存在，同时注入给 RAG 中间件与工具。

---

## 二、 详细设计规格

### 2.1 物理词典纠偏与探索工具设计 (Backend Tools)

为了将纠偏与结构探索能力暴露给大模型，我们需要在后端定义三个全新工具。工具放置在独立的新建模块中：
`backend/app/agent/tools/sql_lexicon_tools.py`

#### 1. 列值语义纠偏工具 (`search_db_value_lexicon`)
*   **工具命名**：`search_db_value_lexicon`
*   **输入参数**：
    *   `query` (str): 待检索模糊值的自然语言文本（例如：“电泳二期”）。
*   **核心逻辑**：
    1.  **向量匹配检索**：调用 `lexicon_retriever.value_retriever.retrieve(query)`。
    2.  **结果格式化输出**：如果检索到结果，将其渲染为整齐的 Markdown 表格：
        ```markdown
        | 数据库表 | 目标列名 | 真实物理字段值 (SQL Literal) | 相似度得分 |
        | :--- | :--- | :--- | :--- |
        | dim.dim_process_area | process_area_name | 前道电泳二区 | 0.9532 |
        ```
        若未命中，返回固定的提示字符串。

#### 2. 行级实体对齐工具 (`search_db_row_lexicon`)
*   **工具命名**：`search_db_row_lexicon`
*   **输入参数**：
    *   `query` (str): 待检索行实体（如工位、工艺区域、设备等）的名称或别名。
*   **核心逻辑**：
    1.  **向量匹配检索**：调用 `lexicon_retriever.row_retriever.retrieve(query)`。
    2.  **结果格式化输出**：如果检索到结果，将其渲染为 Markdown 表格返回给大模型：
        ```markdown
        | 数据库表 | 主键列 | 真实主键值 | 关联行核心属性描述 | 相似度得分 |
        | :--- | :--- | :--- | :--- | :--- |
        | dim.dim_process_area | id | 1002 | area_name=前道电泳二区 | 0.9248 |
        ```

#### 3. 表结构补充探索工具 (`search_db_table_schema`)
*   **工具命名**：`search_db_table_schema`
*   **输入参数**：
    *   `query` (str): 与目标表相关的自然语言描述，例如“在制车辆工位追踪”。
*   **核心逻辑**：
    1.  **向量匹配检索**：调用 `lexicon_retriever.schema_retriever.retrieve(query)`。限制 `top_k=2`。
    2.  **结果格式化输出**：如果检索到结果，剥离附加的 sample_rows 信息，保留精简的列/类型/注释 DDL，使用 Markdown 的 ````sql` 块进行包裹后返回。

---

### 2.2 服务层工具挂载与单例复用

为了在不产生网络/连接开销的前提下，平滑共享物理词典检索器，我们需要在服务初始化链复用现有的单例：

1.  **复用 RAG 检索器对象**：
    *   `BusinessRagMiddleware` 初始化时内部已经实例化了 `DatabaseLexiconRetriever`（暴露为 `lexicon_retriever`）。
2.  **工具列表挂载**：
    *   修改 `_prepare_tools` 函数签名，支持传入 `lexicon_retriever`。
    *   在 `service.py` 的 `_initialize_agent` 中，从 `rag_middleware` 取出 `lexicon_retriever` 传递给 `_prepare_tools`。
    *   在 `_prepare_tools` 内部，若 `lexicon_retriever` 不为空，调用工厂方法构建上述三个工具，并 `append` 到 `tools` 列表中。

---

### 2.3 系统提示词 (Prompt) 自愈规约微调

为了强引导大模型在 SQL 执行为空时自发调用纠偏工具，必须微调系统提示词。

*   **修改文件**：[base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/prompts/base_system_prompt.md)
*   **修改位置**：`## 3.1 总体工作流与重试机制` 下的“错误处理与重试”上方。
*   **追加规约内容**：
    > - **空结果反思与自愈纠偏**：如果调用 `sql_db_query` 执行后返回结果集为空（形如 `[]`），你必须启动反思机制，怀疑是否因为过滤条件中使用的专有名词、名称、类型、别名或参数值与数据库内真实存储的值存在偏差。此时你必须自发调用 `search_db_value_lexicon` 工具进行列值相似度检索，或调用 `search_db_row_lexicon` 工具进行实体主键对齐检索，获取正确的物理值并进行条件替换。如果是因为你对特定表的列结构认知缺失导致报错，你应当调用 `search_db_table_schema` 检索相关表结构，重写 SQL 再次执行。

---

## 三、 验证与保障计划

### 3.1 自动化测试规格

在 [test_sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/agent/tools/test_sql_lexicon_tools.py) 中实现针对新工具的回归防护：

1.  **测试点 A (工具纯净性)**：
    *   调用工具，断言验证它仅需要 `query` 参数，不再受 `required_skill` 的加载拦截限制。
2.  **测试点 B (正常检索输出格式)**：
    *   Mock `DatabaseLexiconRetriever` 的检索响应。
    *   调用工具，断言验证返回文本是规范的 Markdown 表格和 SQL 代码块。
3.  **测试点 C (工具挂载验证)**：
    *   实例化 `SQLAgentService`，断言验证服务暴露的 `tools` 列表中确实存在 `search_db_value_lexicon`、`search_db_row_lexicon` 和 `search_db_table_schema` 工具。

### 3.2 手动联调验证用例

1.  **前置条件**：确保 Milvus 中的三层向量 Collections (`table_schema_store`, `db_value_lexicon`, `db_row_lexicon`) 均已物理覆盖初始化并导入了物流领域的元数据及去重数据。
2.  **执行操作**：在对话中输入：
    *   *“看下在制车辆中工艺区域属于‘电泳二期’的有几台？”*
3.  **时序验证 (自愈检查)**：
    *   大模型在首轮决策中，通过静态/动态 XML 装配信息，判定属于物流追踪领域，发送工具调用：`load_skill("paint_shop_vehicle_logistics")`。
    *   次轮大模型因为没有从 RAG 得到最新的 `电泳二期` 对齐（因该数据在 Milvus 同步中尚未及时录入），写出带有 `WHERE process_area = '电泳二期'` 的 SQL 并执行。
    *   SQL 正常返回为 `[]`。
    *   **核心断言点**：大模型不能直接回答没有车辆，而是触发反思，发出工具调用：`search_db_value_lexicon(query="电泳二期")`。
    *   物理列值词典通过语义检索返回匹配表：`dim.dim_process_area` 中的真实列值为 `前道电泳二区`。
    *   大模型捕获此输出后，重写 SQL 为 `WHERE process_area = '前道电泳二区'` 并二次执行。
    *   执行成功，得出正确数字，且在最终回复中正确标注数据源和查询时间。
