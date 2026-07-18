# SQL Agent 主动纠偏工具链与自愈重写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当 SQL Agent 执行 SQL 返回结果为空或表结构认知缺失时，自发通过 Milvus 向量物理词典进行列值、行实体、表结构的自查纠偏，实现大模型层面的“自愈”重试。

**Architecture:**
1. 在 [backend/app/agent/tools/sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/sql_lexicon_tools.py) 中新增三个向量物理词典纠偏与探索工具。这些工具直接接收 `lexicon_retriever` 对象进行初始化，内部不设置 `required_skill` 拦截，保证模型自主查询能力。
2. 在 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py) 中复用 `BusinessRagMiddleware` 初始化时产生的 `DatabaseLexiconRetriever` 实例，将该单例传入 `_prepare_tools` 函数进行新工具挂载。
3. 在 [backend/app/agent/middleware/prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py) 的 `COLLAPSIBLE_TOOLS` 集合中加入新增的三个工具名，实现滑动窗口外的 ToolMessage 内容折叠。
4. 微调系统提示词 [base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/prompts/base_system_prompt.md)，引入空结果反思与 DDL 缺失自愈纠偏机制规范。
5. 编写针对物理词典纠偏工具的单元测试，并在测试环境中打通回归验证。

**Tech Stack:** `Python`, `LangChain`, `Pytest`, `LlamaIndex`, `Milvus`

---

## 任务分解清单

### Task 1: 创建三个物理词典纠偏与探索工具

**Files:**
- Create: [backend/app/agent/tools/sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/sql_lexicon_tools.py)
- Modify: [backend/app/agent/tools/__init__.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/__init__.py)

- [ ] **Step 1: 新建工具模块文件**
  
  在 [backend/app/agent/tools/sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/sql_lexicon_tools.py) 中写入三个工具工厂方法及具体的 tool 实现：
  
  ```python
  # backend/app/agent/tools/sql_lexicon_tools.py
  import logging
  import re
  from typing import Any
  
  from langchain.tools import ToolRuntime, tool as langchain_tool
  
  from backend.app.agent.utils import emit_stream_status
  
  logger = logging.getLogger(__name__)
  
  
  def create_db_value_lexicon_tool(lexicon_retriever: Any) -> Any:
      """
      创建列值语义纠偏工具。
      """
  
      @langchain_tool
      def search_db_value_lexicon(query: str, runtime: ToolRuntime) -> str:
          """
          通过语义相似度在去重列值字典中检索数据库字段物理真实值。
          
          当你发现 SQL 执行结果为空 (Empty Result)，怀疑是过滤条件值拼写、别名、或别称不匹配时调用。
          例如：用户问“电泳二期”，若数据库实际存“前道电泳二区”，使用此工具做模糊匹配可以找到正确值。
          
          Args:
              query: 待检索列值的模糊文本或关键字。
          """
          if lexicon_retriever is None:
              return "Error: Database lexicon retriever is not initialized or disabled."
          try:
              emit_stream_status(
                  f"正在进行列值检索纠偏: {query}",
                  stage="retrieving",
                  source="search_db_value_lexicon",
              )
              nodes = lexicon_retriever.value_retriever.retrieve(query)
              if not nodes:
                  return f"未在列值词典中找到与 '{query}' 相关的物理真实值。"
              
              lines = [
                  "已找到相似的真实物理列值映射参考：\n",
                  "| 数据表 | 目标列名 | 真实物理字段值 (SQL Literal) | 相似度得分 |",
                  "| :--- | :--- | :--- | :--- |"
              ]
              for n in nodes[:5]:
                  meta = n.node.metadata
                  t_name = meta.get("table_name", "")
                  c_name = meta.get("column_name", "")
                  val = meta.get("exact_value", "")
                  score = getattr(n, "score", 0.0)
                  lines.append(f"| `{t_name}` | `{c_name}` | `'{val}'` | {score:.4f} |")
                  
              return "\n".join(lines)
          except Exception as e:
              logger.error(f"Error retrieving value lexicon: {e}", exc_info=True)
              return f"Error retrieving value lexicon: {str(e)}"
  
      return search_db_value_lexicon
  
  
  def create_db_row_lexicon_tool(lexicon_retriever: Any) -> Any:
      """
      创建行级实体对齐工具。
      """
  
      @langchain_tool
      def search_db_row_lexicon(query: str, runtime: ToolRuntime) -> str:
          """
          通过语义相似度在行实体字典中检索对应记录的主键及核心属性描述。
          
          当你需要根据模糊实体名/属性（如某个特定的设备名称、工位别名）定位表中的主键 ID 时调用。
          
          Args:
              query: 待检索行实体（如工位、工艺区域、设备等）的名称或别名。
          """
          if lexicon_retriever is None:
              return "Error: Database lexicon retriever is not initialized or disabled."
          try:
              emit_stream_status(
                  f"正在进行行级实体检索对齐: {query}",
                  stage="retrieving",
                  source="search_db_row_lexicon",
              )
              nodes = lexicon_retriever.row_retriever.retrieve(query)
              if not nodes:
                  return f"未在行实体词典中找到与 '{query}' 相关的记录。"
              
              lines = [
                  "已找到相似的数据库行记录映射参考：\n",
                  "| 数据表 | 主键列 | 真实主键值 | 关联行核心属性描述 | 相似度得分 |",
                  "| :--- | :--- | :--- | :--- | :--- |"
              ]
              for n in nodes[:5]:
                  meta = n.node.metadata
                  t_name = meta.get("table_name", "")
                  pk_col = meta.get("primary_key_column", "")
                  pk_val = meta.get("primary_key_val", "")
                  row_content = meta.get("row_content", "")
                  score = getattr(n, "score", 0.0)
                  lines.append(f"| `{t_name}` | `{pk_col}` | `'{pk_val}'` | {row_content} | {score:.4f} |")
                  
              return "\n".join(lines)
          except Exception as e:
              logger.error(f"Error retrieving row lexicon: {e}", exc_info=True)
              return f"Error retrieving row lexicon: {str(e)}"
  
      return search_db_row_lexicon
  
  
  def create_db_table_schema_tool(lexicon_retriever: Any) -> Any:
      """
      创建表结构补充探索工具。
      """
  
      @langchain_tool
      def search_db_table_schema(query: str, runtime: ToolRuntime) -> str:
          """
          通过语义相似度在表结构字典中检索最相关的 DDL 表定义详情。
          
          当你对某张表的字段名、字段类型不确定，或者遇到 SQL 报错（如列不存在）时调用。
          
          Args:
              query: 与目标表相关的自然语言描述。
          """
          if lexicon_retriever is None:
              return "Error: Database lexicon retriever is not initialized or disabled."
          try:
              emit_stream_status(
                  f"正在进行表结构 DDL 检索: {query}",
                  stage="retrieving",
                  source="search_db_table_schema",
              )
              nodes = lexicon_retriever.schema_retriever.retrieve(query)
              if not nodes:
                  return f"未找到与 '{query}' 相关的表结构定义。"
              
              lines = ["已找到以下最相关的表 DDL 定义：\n"]
              for n in nodes[:2]:
                  meta = n.node.metadata
                  t_name = meta.get("table_name", "")
                  score = getattr(n, "score", 0.0)
                  ddl = n.node.text
                  
                  # 剥离注释中的样本数据
                  clean_ddl = re.sub(r"-- \d+\. \{.*?\}", "", ddl, flags=re.DOTALL).strip()
                  clean_ddl = re.sub(r"VARCHAR\(\d+\)", "VARCHAR", clean_ddl, flags=re.IGNORECASE)
                  
                  lines.append(f"### 表: {t_name} (相似度得分: {score:.4f})")
                  lines.append(f"```sql\n{clean_ddl}\n```\n")
                  
              return "\n".join(lines)
          except Exception as e:
              logger.error(f"Error retrieving table schema lexicon: {e}", exc_info=True)
              return f"Error retrieving table schema lexicon: {str(e)}"
  
      return search_db_table_schema
  ```

- [ ] **Step 2: 在 `tools/__init__.py` 中统一导出**
  
  修改 [backend/app/agent/tools/__init__.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/__init__.py)，在 `__all__` 和 import 列表中加入三个工具创建方法：
  
  ```python
  from .sql_lexicon_tools import (
      create_db_value_lexicon_tool,
      create_db_row_lexicon_tool,
      create_db_table_schema_tool,
  )
  ```
  同时将这三项追加至 `__all__`。

- [ ] **Step 3: 验证编译**
  
  运行：
  `conda run -n py312_agent python -c "from backend.app.agent.tools import create_db_value_lexicon_tool, create_db_row_lexicon_tool, create_db_table_schema_tool; print('sql_lexicon_tools compiled successfully')"`
  Expected: Success without syntax error

---

### Task 2: 服务层工具挂载与单例复用

**Files:**
- Modify: [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py)

- [ ] **Step 1: 修改 `_prepare_tools` 函数签名与注入**
  
  在 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py#L305-L310) 处，修改 `_prepare_tools` 的定义，支持 `lexicon_retriever` 传入：
  
  ```python
  def _prepare_tools(
      db: MaterializedViewSQLDatabase,
      llm: Any,
      retriever: Optional[BaseRetriever] = None,
      lexicon_retriever: Optional[Any] = None,
  ) -> list:
  ```

- [ ] **Step 2: 在 `_prepare_tools` 尾部挂载新工具**
  
  在 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py#L379) 的 `return tools` 之前，插入挂载新工具的逻辑：
  
  ```python
      if lexicon_retriever is not None:
          try:
              from backend.app.agent.tools.sql_lexicon_tools import (
                  create_db_value_lexicon_tool,
                  create_db_row_lexicon_tool,
                  create_db_table_schema_tool,
              )
              tools.append(create_db_value_lexicon_tool(lexicon_retriever))
              tools.append(create_db_row_lexicon_tool(lexicon_retriever))
              tools.append(create_db_table_schema_tool(lexicon_retriever))
              logger.info("已注入物理词典纠偏/探索工具集 (search_db_value_lexicon, search_db_row_lexicon, search_db_table_schema)")
          except Exception as exc:
              logger.warning("注入物理词典工具失败: %s", exc)
  ```

- [ ] **Step 3: 提取 `rag_middleware` 内部的 `lexicon_retriever` 单例并传入**
  
  在 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py#L569) 处，将原来直接调用 `_prepare_tools` 升级为支持单例传入：
  
  ```python
              lexicon_retriever = rag_middleware.lexicon_retriever if rag_middleware else None
              tools = _prepare_tools(db, llm, retriever=retriever, lexicon_retriever=lexicon_retriever)
  ```

- [ ] **Step 4: 验证编译**
  
  运行：
  `conda run -n py312_agent python -c "from backend.app.agent.service import SQLAgentService; print('service.py compiled successfully')"`
  Expected: Success without syntax error

---

### Task 3: 中间件折叠白名单维护

**Files:**
- Modify: [backend/app/agent/middleware/prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)

- [ ] **Step 1: 在 `COLLAPSIBLE_TOOLS` 集合中追加新工具名**
  
  修改 [backend/app/agent/middleware/prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py#L37-L43) 中的 `COLLAPSIBLE_TOOLS` 定义：
  
  ```python
  # 定义需折叠替换的白名单工具名
  COLLAPSIBLE_TOOLS = {
      "sql_db_query",
      "search_saved_correct_tool_uses",
      "build_chart_artifact",
      "export_to_csv",
      "export_query_to_csv",
      "search_db_value_lexicon",
      "search_db_row_lexicon",
      "search_db_table_schema"
  }
  ```

- [ ] **Step 2: 验证编译**
  
  运行：
  `conda run -n py312_agent python -c "from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware; print('prompt_compiler_middleware.py compiled successfully')"`
  Expected: Success

---

### Task 4: 系统提示词自愈规约微调

**Files:**
- Modify: [backend/app/agent/prompts/base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/prompts/base_system_prompt.md)

- [ ] **Step 1: 追加空结果与结构自愈反思约束规则**
  
  修改 [backend/app/agent/prompts/base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/prompts/base_system_prompt.md#L60) 处，在 `**错误处理与重试**：` 上方追加“空结果反思与自愈纠偏”小节：
  
  ```markdown
  **空结果反思与自愈纠偏**：
  - 若 `sql_db_query` 执行返回结果集为空（形如 `[]`），你必须启动反思机制，怀疑是否因为过滤条件中使用的专有名词、名称、类型、别名或参数值与数据库内真实存储的值存在偏差。此时你必须自发调用 `search_db_value_lexicon` 工具进行列值相似度检索，或调用 `search_db_row_lexicon` 工具进行实体主键对齐检索，获取正确的物理值并进行条件替换。
  - 如果因为你对特定表的列结构或字段名认知缺失（例如 SQL 报错列不存在），你应当调用 `search_db_table_schema` 检索相关表结构，补充 DDL 认知后重写 SQL 再次执行。
  ```

---

### Task 5: 编写工具单元测试与验证

**Files:**
- Create: [backend/tests/agent/tools/test_sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/agent/tools/test_sql_lexicon_tools.py)

- [ ] **Step 1: 编写单元测试脚本**
  
  在 [backend/tests/agent/tools/test_sql_lexicon_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/agent/tools/test_sql_lexicon_tools.py) 中，使用 mock 覆盖三个工具的返回逻辑与格式输出测试：
  
  ```python
  # backend/tests/agent/tools/test_sql_lexicon_tools.py
  import pytest
  from unittest.mock import MagicMock
  from langchain.tools import ToolRuntime
  
  from backend.app.agent.tools.sql_lexicon_tools import (
      create_db_value_lexicon_tool,
      create_db_row_lexicon_tool,
      create_db_table_schema_tool,
  )
  
  
  def test_db_value_lexicon_tool():
      # 1. Mock 物理词典检索器
      mock_retriever = MagicMock()
      mock_node = MagicMock()
      mock_node.node.metadata = {
          "table_name": "dim.dim_process_area",
          "column_name": "process_area_name",
          "exact_value": "前道电泳二区"
      }
      mock_node.score = 0.9532
      mock_retriever.value_retriever.retrieve.return_value = [mock_node]
  
      # 2. 实例化并运行工具
      tool = create_db_value_lexicon_tool(mock_retriever)
      runtime = MagicMock(spec=ToolRuntime)
      result = tool.run({"query": "电泳二期"}, runtime=runtime)
  
      # 3. 断言验证 Markdown 格式输出与参数纯净性
      assert "| 数据表 | 目标列名 | 真实物理字段值 (SQL Literal) | 相似度得分 |" in result
      assert "`dim.dim_process_area`" in result
      assert "`process_area_name`" in result
      assert "`'前道电泳二区'`" in result
      assert "0.9532" in result
  
  
  def test_db_row_lexicon_tool():
      # 1. Mock
      mock_retriever = MagicMock()
      mock_node = MagicMock()
      mock_node.node.metadata = {
          "table_name": "dim.dim_process_area",
          "primary_key_column": "id",
          "primary_key_val": "1002",
          "row_content": "area_name=前道电泳二区"
      }
      mock_node.score = 0.9248
      mock_retriever.row_retriever.retrieve.return_value = [mock_node]
  
      # 2. 运行工具
      tool = create_db_row_lexicon_tool(mock_retriever)
      runtime = MagicMock(spec=ToolRuntime)
      result = tool.run({"query": "前道电泳二区"}, runtime=runtime)
  
      # 3. 断言验证
      assert "| 数据表 | 主键列 | 真实主键值 | 关联行核心属性描述 | 相似度得分 |" in result
      assert "`dim.dim_process_area`" in result
      assert "`id`" in result
      assert "`'1002'`" in result
      assert "area_name=前道电泳二区" in result
      assert "0.9248" in result
  
  
  def test_db_table_schema_tool():
      # 1. Mock
      mock_retriever = MagicMock()
      mock_node = MagicMock()
      mock_node.node.metadata = {
          "table_name": "dim.dim_process_area"
      }
      mock_node.node.text = (
          "CREATE TABLE dim.dim_process_area (\n"
          "  id INTEGER,\n"
          "  process_area_name VARCHAR(50)\n"
          ");\n"
          "-- 1. {'id': 1, 'process_area_name': '电泳一区'}"
      )
      mock_node.score = 0.8876
      mock_retriever.schema_retriever.retrieve.return_value = [mock_node]
  
      # 2. 运行工具
      tool = create_db_table_schema_tool(mock_retriever)
      runtime = MagicMock(spec=ToolRuntime)
      result = tool.run({"query": "工艺区域表"}, runtime=runtime)
  
      # 3. 断言验证样本行剥离与 VARCHAR 规范化
      assert "### 表: dim.dim_process_area (相似度得分: 0.8876)" in result
      assert "VARCHAR" in result
      assert "VARCHAR(50)" not in result
      assert "-- 1." not in result
      assert "CREATE TABLE dim.dim_process_area" in result
  ```

- [ ] **Step 2: 运行单元测试并验证输出**
  
  运行测试命令：
  `conda run -n py312_agent pytest backend/tests/agent/tools/test_sql_lexicon_tools.py -v`
  
  Expected:
  - 3 个用例全部通过 (PASS)。
  
- [ ] **Step 3: 运行全量回归测试**
  
  运行整体测试命令以确保无副作用破坏：
  `conda run -n py312_agent pytest backend/tests/agent/test_persistence_integration.py -v`
  
  Expected:
  - 单元测试运行通过 (PASS)。
