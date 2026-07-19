# SQL 检查二元降级优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现配置化的 SQL 检查二元切换机制，支持 `fast`（仅本地 Linter 检查 + 数据库被动纠错，不调用大模型校验）与 `safety`（本地 Linter + 大模型同步阻塞校验）两种模式，以大幅提升 SQL 查询的响应延迟。

**Architecture:**
1. 在 `backend/app/config.py` 与 `.env` 中新增 `sql_checker_mode` 环境变量（默认值为 `fast`）。
2. 在 `backend/app/agent/tools/sql_tools.py` 中，将大模型 SQL 检查工具 `original_checker_tool` 的调用包装在 `settings.sql_checker_mode == "safety"` 逻辑分支中。（注：`sql_tools_local.py` 经证实是死代码已被彻底删除，无须修改）。

**Tech Stack:** Python 3.12, pytest, LangChain Core Tools, Pydantic settings.

---

### Task 1: 编写单元测试用例 (TDD)

**Files:**
- Create: `backend/app/test_sql_checker_mode.py`

- [ ] **Step 1: 创建测试文件并编写模式测试**

写入文件 `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\test_sql_checker_mode.py`。该测试会验证在不同 `sql_checker_mode` 配置下，底层是否正确执行/跳过了 `checker_tool` 的大模型调用。

```python
import pytest
from unittest.mock import MagicMock, patch
from backend.app.agent.tools.sql_tools import create_wrapped_query_tool

def test_sql_checker_mode_fast():
    """测试在 fast 模式下，直接跳过大模型 checker 校验"""
    mock_query_tool = MagicMock()
    mock_query_tool.db.run_no_throw.return_value = "query results"
    mock_checker_tool = MagicMock()
    
    # 模拟 settings.sql_checker_mode 为 "fast"
    with patch("backend.app.agent.tools.sql_tools.settings") as mock_settings:
        mock_settings.sql_checker_mode = "fast"
        mock_settings.sql_linter_enabled = False # 屏蔽 linter
        
        wrapped_tool = create_wrapped_query_tool(mock_query_tool, mock_checker_tool)
        
        mock_runtime = MagicMock()
        mock_runtime.state = {"skills_loaded": ["test_skill"]}
        
        # 运行 sql_db_query
        result = wrapped_tool.func("SELECT 1", "test_skill", runtime=mock_runtime)
        
        # 断言 1: checker 的 invoke 绝没有被调用
        mock_checker_tool.invoke.assert_not_called()
        # 断言 2: 查询工具被调用了
        mock_query_tool.db.run_no_throw.assert_called_once_with("SELECT 1", include_columns=True)
        assert result == "query results"

def test_sql_checker_mode_safety():
    """测试在 safety 模式下，大模型 checker 被同步调用"""
    mock_query_tool = MagicMock()
    mock_query_tool.db.run_no_throw.return_value = "query results"
    mock_checker_tool = MagicMock()
    mock_checker_tool.invoke.return_value = "SQL Safe"
    
    # 模拟 settings.sql_checker_mode 为 "safety"
    with patch("backend.app.agent.tools.sql_tools.settings") as mock_settings:
        mock_settings.sql_checker_mode = "safety"
        mock_settings.sql_linter_enabled = False # 屏蔽 linter
        
        wrapped_tool = create_wrapped_query_tool(mock_query_tool, mock_checker_tool)
        
        mock_runtime = MagicMock()
        mock_runtime.state = {"skills_loaded": ["test_skill"]}
        
        # 运行 sql_db_query
        result = wrapped_tool.func("SELECT 1", "test_skill", runtime=mock_runtime)
        
        # 断言 1: checker 的 invoke 被调用了
        mock_checker_tool.invoke.assert_called_once_with({"query": "SELECT 1"})
```

- [ ] **Step 2: 运行测试并验证其失败**

在终端运行此测试。因为我们目前还没有在 config 中加入 `sql_checker_mode` 字段，且代码尚未增加二元过滤逻辑，测试会直接报错（提示 `settings` 没有 `sql_checker_mode` 属性，或者 `test_sql_checker_mode_fast` 会因为 `mock_checker_tool.invoke` 仍被调用而 assert 失败）。

先激活 conda 环境：
`conda activate py312_agent`

运行测试命令：
`pytest backend/app/test_sql_checker_mode.py -v`

Expected Output:
`FAILED backend/app/test_sql_checker_mode.py`

---

### Task 2: 配置项修改

**Files:**
- Modify: `backend/app/config.py:75-85`
- Modify: `.env:10-25`

- [ ] **Step 1: 修改 config.py**

在 [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py) 中，为 `Settings` 类增加配置字段：

```python
    # SQL Checker 模式：fast(仅本地Linter) | safety(同步checker=当前默认)
    sql_checker_mode: str = os.getenv("SQL_CHECKER_MODE", "fast")
```

- [ ] **Step 2: 修改 .env**

在项目根目录的 [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env) 中新增配置项并注释说明其含义：

```ini
# SQL Checker 模式：fast | safety
# fast   - 仅本地 Linter 检查，跳过大模型 checker，性能最优（推荐）
# safety - 本地 Linter + 同步大模型 checker（当前默认行为，安全安全兜底）
SQL_CHECKER_MODE="fast"
```

---

### Task 3: 实施 SQL 工具二元降级修改

**Files:**
- Modify: `backend/app/agent/tools/sql_tools.py:263-270`
- [已废弃] Modify: `backend/app/agent/tools/sql_tools_local.py:152-160`（该文件已物理删除）

- [ ] **Step 1: 修改 sql_tools.py 语法检查逻辑**

在 [sql_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/tools/sql_tools.py) 中，找到：
```python
        # 3. 自动执行 SQL 语法检查（如果 checker 工具可用）
        if original_checker_tool is not None:
```
将其修改为：
```python
        # 3. 自动执行 SQL 语法检查（如果配置为 safety 模式且 checker 工具可用）
        if settings.sql_checker_mode == "safety" and original_checker_tool is not None:
```

- [x] **Step 2: [已废弃] 修改 sql_tools_local.py 语法检查逻辑**

> **注**：在 2026-07-19 的系统诊断重构中，`sql_tools_local.py` 经核实是 `sql_tools.py` 的死代码分叉副本，已被物理删除，故此步骤直接标记为已完成并废弃。


---

### Task 4: 测试验证与回归验证

**Files:**
- Test: `backend/app/test_sql_checker_mode.py`
- Test: `backend/app/test_services_stream_filtering.py`

- [ ] **Step 1: 运行我们编写的二元检查单元测试**

执行命令：
`pytest backend/app/test_sql_checker_mode.py -v`

Expected Output:
`PASSED backend/app/test_sql_checker_mode.py` (包含 fast 模式和 safety 模式两项通过校验)

- [ ] **Step 2: 运行系统已有的回归测试**

执行命令：
`pytest backend/app/test_api_persistence.py backend/app/test_api_resume.py backend/app/test_services_stream_filtering.py -v`

Expected Output:
所有测试用例全量 `PASSED`。

---

### Task 5: 提交记录

- [ ] **Step 1: 提示用户并请示 Git 提交许可**

向用户提请 Git 提交许可，将所有的优化代码进行提交归档。
