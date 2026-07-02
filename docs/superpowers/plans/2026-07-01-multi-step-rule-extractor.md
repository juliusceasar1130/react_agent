# Multi-Step Rule Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the SQL Agent Rule Extractor to extract, parameterise, and save multi-step SQL cases (multiple database queries within a single turn) while preserving the single-step extraction behavior, fixing the backend pipeline execution order bug, and updating the frontend review panel fallback.

**Architecture:** 
1. Add configuration `RULE_EXTRACTOR_MAX_SQL_STEPS` in `.env` and `config.py`.
2. Rename `SingleSqlFilter` to `SqlStepFilter` in `rule_extractor.py` and implement step-based validation and concatenation.
3. Change the execution order of the pipeline: place `SqlStepFilter` first to hydrate `context.extracted_sql` and `context.tool_result` before safety and emptiness validation.
4. Update `EmptyResultFilter` to check the final step's result.
5. Update `llm_refiner.py` to prompt the LLM to preserve step annotations and parameterise all SQL statements.
6. Fix frontend `parseOriginalSql` in `AdminReviewPanel.vue` to format fallback SQL steps.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Milvus/PgVector, Vue 3, Pinia.

---

### Task 1: Configuration Layer Updates

**Files:**
- Modify: [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py)
- Modify: [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env)

- [ ] **Step 1: Add new config option in `config.py`**
  Add the `rule_extractor_max_sql_steps` configuration parameter to the `Settings` class in `backend/app/config.py`.

  ```python
  # Insert around line 245, near other rule_extractor settings
  rule_extractor_max_sql_steps: int = int(os.getenv("RULE_EXTRACTOR_MAX_SQL_STEPS", "3"))
  ```

- [ ] **Step 2: Add option in `.env`**
  Append `# RULE_EXTRACTOR_MAX_SQL_STEPS=3` in `f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env` at the bottom.

  ```ini
  # ==========================================
  # Rule Extractor (案例自演进规则提取器)
  # ...
  RULE_EXTRACTOR_DOMAIN_ENABLED="true"
  RULE_EXTRACTOR_MAX_SQL_STEPS="3"
  ```

- [ ] **Step 3: Verify configuration loading**
  Run:
  ```powershell
  conda activate py312_agent
  python -c "from backend.app.config import settings; print(settings.rule_extractor_max_sql_steps)"
  ```
  Expected output: `3`

- [ ] **Step 4: Commit changes**
  ```bash
  git add backend/app/config.py .env
  git commit -m "config: add rule_extractor_max_sql_steps setting"
  ```

---

### Task 2: Backend Rule Extractor Refactoring & Order Fix

**Files:**
- Modify: [backend/app/agent/vector/rule_extractor.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/rule_extractor.py)

- [ ] **Step 1: Rename and rewrite `SingleSqlFilter` to `SqlStepFilter`**
  Replace the `SingleSqlFilter` class in `backend/app/agent/vector/rule_extractor.py` with `SqlStepFilter`.
  The filter will extract multiple successful SQL queries, skipping intermediate errors.

  ```python
  class SqlStepFilter(BaseFilter):
      """SQL 步骤校验器：提取单步或多步执行成功的 SQL 序列"""
      def execute(self, context: ExtractionContext) -> bool:
          from backend.app.config import settings
          
          msg = context.target_message
          if not msg or not msg.tool_calls:
              context.reject_reason = "SqlStepFilter: 目标消息没有工具调用"
              return False
              
          try:
              tool_calls = json.loads(msg.tool_calls)
              tool_results = json.loads(msg.tool_results) if msg.tool_results else {}
          except Exception as e:
              context.reject_reason = f"SqlStepFilter: 序列化解析错误 {e}"
              return False
              
          # 过滤并找出所有 sql_db_query 工具调用
          sql_calls = [tc for tc in tool_calls if tc.get("name") == "sql_db_query"]
          
          if not sql_calls:
              context.reject_reason = "SqlStepFilter: 没有调用 sql_db_query 工具"
              return False
              
          # 计算最大步数
          max_steps = 1 if settings.rule_extractor_single_sql_enabled else settings.rule_extractor_max_sql_steps
          
          # 过滤出执行成功的 SQL 调用记录（过滤掉结果包含 ERROR 或 EXCEPTION 的调用）
          valid_sql_calls = []
          for sc in sql_calls:
              call_id = sc.get("id")
              result_content = tool_results.get(call_id) or ""
              
              if not result_content:
                  continue
              if "ERROR:" in result_content.upper() or "EXCEPTION:" in result_content.upper():
                  # 属于执行失败或报错步骤，跳过
                  continue
              valid_sql_calls.append((sc, result_content))
              
          if not valid_sql_calls:
              context.reject_reason = "SqlStepFilter: 没有执行成功的 SQL 工具调用"
              return False
              
          if len(valid_sql_calls) > max_steps:
              context.reject_reason = f"SqlStepFilter: 包含多个 SQL 工具调用 (成功次数 {len(valid_sql_calls)} 超过上限 {max_steps}，舍弃)"
              return False
              
          # 提取 SQL 文本并拼装
          extracted_sqls = []
          extracted_results = []
          
          for idx, (call, res_content) in enumerate(valid_sql_calls):
              args = call.get("args") or {}
              if isinstance(args, str):
                  try:
                      args = json.loads(args)
                  except Exception:
                      pass
                      
              sql_query = args.get("query") if isinstance(args, dict) else ""
              if not sql_query:
                  context.reject_reason = f"SqlStepFilter: 无法解析第 {idx + 1} 步的 query 参数"
                  return False
                  
              extracted_sqls.append(sql_query)
              extracted_results.append(res_content)
              
          # 组装存储格式
          if len(extracted_sqls) == 1:
              context.extracted_sql = extracted_sqls[0]
              context.tool_result = extracted_results[0]
          else:
              # 多步拼接
              joined_sql = []
              joined_res = []
              for idx, (sql, res) in enumerate(zip(extracted_sqls, extracted_results)):
                  joined_sql.append(f"-- Step {idx + 1}\n{sql.strip()};")
                  joined_res.append(f"[Step {idx + 1} Result]\n{res.strip()}")
              context.extracted_sql = "\n\n".join(joined_sql)
              context.tool_result = "\n\n".join(joined_res)
              
          return True
  ```

- [ ] **Step 2: Update `EmptyResultFilter` to validate the final step**
  Modify `EmptyResultFilter.execute` in `backend/app/agent/vector/rule_extractor.py`. If `context.tool_result` contains step separators, only validate the final step's result.

  ```python
  class EmptyResultFilter(BaseFilter):
      """空结果集过滤器：丢弃最终执行成功但没有返回任何实质数据的 SQL 案例"""
      def execute(self, context: ExtractionContext) -> bool:
          from backend.app.config import settings
          if not settings.rule_extractor_empty_result_enabled:
              return True
  
          res_str = (context.tool_result or "").strip()
          if not res_str:
              context.reject_reason = "EmptyResultFilter: 结果为空白文本"
              return False
              
          # 如果包含多步结果标识，仅检验最后一步的结果
          if "[Step " in res_str:
              steps = res_str.split("[Step ")
              last_step = steps[-1].strip()
              # 去除类似 "N Result]\n" 的行头
              lines = last_step.split("\n", 1)
              if len(lines) > 1:
                  res_str = lines[1].strip()
              else:
                  res_str = ""
                  
          if not res_str:
              context.reject_reason = "EmptyResultFilter: 最后一步结果为空白文本"
              return False
              
          try:
              data = json.loads(res_str)
              if isinstance(data, list) and len(data) == 0:
                  context.reject_reason = "EmptyResultFilter: 最后一步结果为结构化空列表 []"
                  return False
              if isinstance(data, dict) and len(data) == 0:
                  context.reject_reason = "EmptyResultFilter: 最后一步结果为结构化空字典 {}"
                  return False
          except Exception:
              if len(res_str) < 2:
                  context.reject_reason = "EmptyResultFilter: 最后一步结果为非结构化无意义短文本"
                  return False
                  
          return True
  ```

- [ ] **Step 3: Rearrange pipeline execution order**
  Modify `DEFAULT_EXTRACTOR_PIPELINE` at the bottom of `backend/app/agent/vector/rule_extractor.py` to place `SqlStepFilter` at the first position.

  ```python
  # DEFAULT_EXTRACTOR_PIPELINE definition around line 355
  DEFAULT_EXTRACTOR_PIPELINE = PipelineManager(filters=[
      SqlStepFilter(),           # Place SQL extraction and hydration first
      SafetyWarningFilter(),     # Now safely reads context.tool_result and context.extracted_sql
      EmptyResultFilter(),       # Validates context.tool_result
      TopologyBacktrackFilter(),
      DomainFilter()
  ])
  ```

- [ ] **Step 4: Commit changes**
  ```bash
  git add backend/app/agent/vector/rule_extractor.py
  git commit -m "feat: refactor rule extractor to support multi-step SQL extraction and fix execution order bug"
  ```

---

### Task 3: Unit Tests for Rule Extractor

**Files:**
- Modify: [backend/app/agent/vector/test_rule_extractor.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/test_rule_extractor.py)

- [ ] **Step 1: Update imports and existing tests**
  Change all occurrences of `SingleSqlFilter` to `SqlStepFilter` in `backend/app/agent/vector/test_rule_extractor.py`.
  Adjust `test_pipeline_integration` Mock configuration to align with the new pipeline order.

- [ ] **Step 2: Add test cases for multi-step extraction**
  Append test cases checking multi-step SQL concatenation and limit constraints.

  ```python
  def test_multi_sql_filter_success():
      """测试当单步模式禁用时，能成功提取和拼接多步 SQL"""
      from backend.app.agent.vector.rule_extractor import SqlStepFilter, ExtractionContext
      from backend.app.config import settings
      import json
      
      f = SqlStepFilter()
      ctx = ExtractionContext("m_multi", MagicMock())
      
      mock_msg = MagicMock()
      mock_msg.tool_calls = json.dumps([
          {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT id FROM position WHERE name = 'paint_shop'"}},
          {"id": "t2", "name": "sql_db_query", "args": {"query": "SELECT count(*) FROM paint_defect WHERE position_id = 42"}}
      ])
      mock_msg.tool_results = json.dumps({
          "t1": "[{'id': 42}]",
          "t2": "[{'count': 10}]"
      })
      ctx.target_message = mock_msg
      
      with patch.object(settings, "rule_extractor_single_sql_enabled", False):
          with patch.object(settings, "rule_extractor_max_sql_steps", 3):
              assert f.execute(ctx) is True
              assert "-- Step 1" in ctx.extracted_sql
              assert "-- Step 2" in ctx.extracted_sql
              assert "[Step 1 Result]" in ctx.tool_result
              assert "[Step 2 Result]" in ctx.tool_result
              assert "SELECT count(*)" in ctx.extracted_sql

  def test_multi_sql_filter_exceeds_limit():
      """测试多步 SQL 步数超出上限时被丢弃"""
      from backend.app.agent.vector.rule_extractor import SqlStepFilter, ExtractionContext
      from backend.app.config import settings
      import json
      
      f = SqlStepFilter()
      ctx = ExtractionContext("m_multi_exceed", MagicMock())
      
      mock_msg = MagicMock()
      mock_msg.tool_calls = json.dumps([
          {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT 1"}},
          {"id": "t2", "name": "sql_db_query", "args": {"query": "SELECT 2"}},
          {"id": "t3", "name": "sql_db_query", "args": {"query": "SELECT 3"}}
      ])
      mock_msg.tool_results = json.dumps({
          "t1": "res1", "t2": "res2", "t3": "res3"
      })
      ctx.target_message = mock_msg
      
      with patch.object(settings, "rule_extractor_single_sql_enabled", False):
          with patch.object(settings, "rule_extractor_max_sql_steps", 2):
              assert f.execute(ctx) is False
              assert "超过上限" in ctx.reject_reason
  ```

- [ ] **Step 3: Run pytest**
  Run:
  ```powershell
  conda activate py312_agent
  pytest backend/app/agent/vector/test_rule_extractor.py -v
  ```
  Expected: All tests pass.

- [ ] **Step 4: Commit changes**
  ```bash
  git add backend/app/agent/vector/test_rule_extractor.py
  git commit -m "test: update rule extractor unit tests for SqlStepFilter and multi-step cases"
  ```

---

### Task 4: LLM Refiner Multi-Step Adaptation

**Files:**
- Modify: [backend/app/agent/vector/llm_refiner.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/llm_refiner.py)

- [ ] **Step 1: Enhance prompt inside `refine_sql_case_with_llm`**
  Modify the system prompt inside `backend/app/agent/vector/llm_refiner.py` to instruct the LLM on handling multi-step queries:
  - Explain the `-- Step N` formatting in the input.
  - Direct the LLM to parameterise/desensitize all SQL statements in the sequence.
  - Ensure the output `desensitized_sql` preserves the `-- Step N` structure and annotations.
  - Highlight step dependencies (e.g. `{{Step1.id}}` or `{{第一步返回的ID}}` instead of hardcoding raw output values).

  ```python
  # Replace prompt string in refine_sql_case_with_llm (around line 27-46):
  prompt = f"""你是一个专业的 SQL 分析专家。你的任务是将一个生产数据查询案例提炼为高泛化性的"黄金 Few-Shot 模板"。
  
  输入案例包含：
  1. 用户的原始查询与澄清问答历史（格式为：原始提问 [澄清提问: xxx -> 澄清回答: yyy]）。
  2. 执行成功的 SQL 语句（可能是单步 SQL，也可能是包含多个 `-- Step N` 注释分割的多步 SQL 序列）。
  
  你需要根据以下规则完成提炼：
  - 对于 rewritten_query：你必须把 `[澄清提问: ... -> 澄清回答: ...]` 里的补充约束条件融入到重写意图中。
    例如："昨天面漆段流挂车有多少？ [澄清提问: 请问是一产线还是二产线？ -> 澄清回答: 二产线]"
    应改写为："查询昨天二产线面漆段流挂缺陷的车辆总数"。
    
  - 对于 desensitized_sql：
    1. 仅将表示具体动态过滤条件的值（如特定日期、具体车身号、序列号、具体工号、具体车型的代码字面值）替换为双大括号占位符，例如 `line_id = {{{{产线ID}}}}`。
    2. 如果 SQL 中存在前后步骤的动态参数依赖关系（例如 Step 2 使用了 Step 1 查询返回的 ID 值），请务必将该依赖值 parameterize 为指向性的占位符，例如 `position_id = {{{{Step1.id}}}}` 或 `position_id = {{{{第一步查询返回的ID}}}}`。
    3. 如果输入是多步 SQL，必须保留所有以 `-- Step N` 开头的步骤注释，不能将其删减或合一，且需依次对各步 SQL 执行脱敏。
    4. 严禁改变 SQL 的表名、列名、JOIN 关联条件或任何 SQL 关键字。
    5. 严禁脱敏业务常量、状态码或枚举值。例如：`status = 1` 中的 `1`，`is_deleted = 0` 中的 `0`，`is_history = 'N'` 中的 `'N'`，`line_type = 'paint'` 中的 `'paint'`，布尔值 `true`/`false` 必须原样保留。
  
  输入案例：
  User Query: {raw_query}
  SQL: {raw_sql}
  """
  ```

- [ ] **Step 2: Commit changes**
  ```bash
  git add backend/app/agent/vector/llm_refiner.py
  git commit -m "feat: enhance LLM refiner prompt to handle multi-step SQL templates and data-dependencies"
  ```

---

### Task 5: Unit Tests for LLM Refiner

**Files:**
- Modify: [backend/app/agent/vector/test_llm_refiner.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/test_llm_refiner.py)

- [ ] **Step 1: Add a test case for multi-step refinement**
  Add a new test case `test_refine_multi_sql_case_success` in `backend/app/agent/vector/test_llm_refiner.py` to mock and verify multi-step template parsing.

  ```python
  @patch("backend.app.agent.vector.llm_refiner._create_llm")
  def test_refine_multi_sql_case_success(mock_get_llm):
      """测试 LLM 能够成功提取和脱敏多步拼接的 SQL 模板，并保持步骤结构"""
      mock_llm_instance = MagicMock()
      mock_structured_llm = MagicMock()
      mock_llm_instance.with_structured_output.return_value = mock_structured_llm
      
      mock_structured_llm.invoke.return_value = {
          "raw": MagicMock(),
          "parsed": RefinedSQLCase(
              rewritten_query="查询昨天流挂缺陷车辆的配置",
              desensitized_sql="-- Step 1\nSELECT id FROM position WHERE name = {{产线名称}};\n\n-- Step 2\nSELECT config FROM process WHERE position_id = {{Step1.id}}"
          ),
          "parsing_error": None
      }
      mock_get_llm.return_value = mock_llm_instance
      
      raw_query = "查昨天缺陷车的配置"
      raw_sql = "-- Step 1\nSELECT id FROM position WHERE name = 'paint_shop';\n\n-- Step 2\nSELECT config FROM process WHERE position_id = 42"
      
      res_query, res_sql = refine_sql_case_with_llm(raw_query, raw_sql)
      
      assert "Step 1" in res_sql
      assert "Step 2" in res_sql
      assert "{{产线名称}}" in res_sql
      assert "{{Step1.id}}" in res_sql
  ```

- [ ] **Step 2: Run pytest**
  Run:
  ```powershell
  conda activate py312_agent
  pytest backend/app/agent/vector/test_llm_refiner.py -v
  ```
  Expected: All tests pass.

- [ ] **Step 3: Commit changes**
  ```bash
  git add backend/app/agent/vector/test_llm_refiner.py
  git commit -m "test: add test case for multi-step LLM refinement"
  ```

---

### Task 6: Frontend Fallback Parsing

**Files:**
- Modify: [frontend/src/components/AdminReviewPanel.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/AdminReviewPanel.vue)

- [ ] **Step 1: Rewrite `parseOriginalSql` for multi-step fallback**
  Modify the `parseOriginalSql` function in `frontend/src/components/AdminReviewPanel.vue` (around lines 202-214) to join all SQL calls if multiple exist.

  ```javascript
  function parseOriginalSql(item: Message): string {
    if (item.tool_calls) {
      try {
        const calls = JSON.parse(item.tool_calls)
        const sqlCalls = calls.filter(tc => tc.name === 'sql_db_query' && tc.args?.query)
        
        if (sqlCalls.length === 1) {
          return sqlCalls[0].args.query
        } else if (sqlCalls.length > 1) {
          return sqlCalls.map((tc, idx) => {
            return `-- Step ${idx + 1}\n${tc.args.query.trim()};`
          }).join('\n\n')
        }
      } catch (_) {}
    }
    return ''
  }
  ```

- [ ] **Step 2: Run frontend production build to verify compilation**
  Run:
  ```powershell
  cd frontend
  npm run build
  ```
  Expected: Compiles successfully without errors or linting warnings.

- [ ] **Step 3: Commit changes**
  ```bash
  git add frontend/src/components/AdminReviewPanel.vue
  git commit -m "frontend: enhance parseOriginalSql fallback to support and concatenate multi-step SQL queries"
  ```
