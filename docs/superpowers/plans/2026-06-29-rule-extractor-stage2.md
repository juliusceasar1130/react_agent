# 规则提取器与拓扑精准回溯 (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现规则提取器管道 (Rule Extractor Pipeline)，完成对收藏消息 (feedback='collected') 中的 SQL 语句安全性校验、单步 SQL 检查、空结果过滤，并通过 `tool_call_id` 高效精准回溯多轮澄清会话。

**Architecture:** 
1. 采用 Pipeline & Filters 设计模式，构建 `PipelineManager`、`ExtractionContext` 与 `BaseFilter` 基类；
2. 依次实现四大静态规则过滤器：`SafetyWarningFilter`、`SingleSqlFilter`、`EmptyResultFilter` 和 `DomainFilter`；
3. 实现 `TopologyBacktrackFilter`，依据 `tool_results` 字典的键名与 `tool_calls` 的 `id` 进行拓扑溯源配对；
4. 全程使用 TDD 开发，编写完整的单元测试覆盖所有规则过滤分支和多轮拓扑回溯。

**Tech Stack:** Python, SQLAlchemy, Pytest.

---

### Task 1: 规则提取器基础框架及上下文设计

**Files:**
- Create: `backend/app/agent/vector/rule_extractor.py`
- Create: `backend/app/agent/vector/test_rule_extractor.py`

- [ ] **Step 1: 编写提取器骨架测试用例**
  创建测试文件 [test_rule_extractor.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/test_rule_extractor.py) 并写入骨架测试代码：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from backend.app.agent.vector.rule_extractor import (
      ExtractionContext,
      BaseFilter,
      PipelineManager
  )

  class DummyPassFilter(BaseFilter):
      def execute(self, context: ExtractionContext) -> bool:
          return True

  class DummyFailFilter(BaseFilter):
      def execute(self, context: ExtractionContext) -> bool:
          context.is_rejected = True
          context.reject_reason = "dummy_failed"
          return False

  def test_pipeline_manager_passes_all_filters():
      """测试所有过滤器都通过时，管道成功返回"""
      db_mock = MagicMock()
      manager = PipelineManager(filters=[DummyPassFilter()])
      payload = manager.process("msg-1", db_mock)
      
      assert payload is not None
      assert payload["message_id"] == "msg-1"

  def test_pipeline_manager_stops_on_fail_filter():
      """测试任何过滤器失败时，管道中止并记录原因"""
      db_mock = MagicMock()
      manager = PipelineManager(filters=[DummyPassFilter(), DummyFailFilter()])
      payload = manager.process("msg-2", db_mock)
      
      assert payload is None
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.agent.vector.rule_extractor'`

- [ ] **Step 3: 实现 rule_extractor.py 基础骨架**
  创建 [rule_extractor.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/rule_extractor.py) 并定义上下文、基类与管道管理器：
  ```python
  import json
  from typing import List, Dict, Any, Optional

  class ExtractionContext:
      """提取任务上下文，保存会话状态、中间提取产物及最终输出结果"""
      def __init__(self, message_id: str, db_session):
          self.message_id = message_id
          self.db = db_session
          
          # 流程控制
          self.is_rejected = False
          self.reject_reason = ""
          
          # 原始数据（从 DB 自动加载）
          self.target_message = None     # 目标 assistant 消息
          self.history_messages = []     # 精准回溯还原的上下文历史链
          
          # 待输出至 LLM 的提炼素材（中间产物）
          self.raw_user_query = ""       # 用户原始提问
          self.extracted_sql = ""        # 提取出的单个成功 SQL
          self.tool_result = ""          # 该 SQL 的执行返回结果
          self.domain = "general"        # 业务技能域

  class BaseFilter:
      """过滤器基类"""
      def execute(self, context: ExtractionContext) -> bool:
          raise NotImplementedError

  class PipelineManager:
      """管道调度管理器"""
      def __init__(self, filters: List[BaseFilter]):
          self.filters = filters
          
      def process(self, message_id: str, db) -> Optional[Dict[str, Any]]:
          context = ExtractionContext(message_id, db)
          
          # 从数据库拉取目标消息（在测试骨架中，如果是 Mock 先做基础适配）
          from backend.app.crud import get_message
          db_message = get_message(db, message_id)
          context.target_message = db_message
          
          for filter_instance in self.filters:
              if not filter_instance.execute(context):
                  context.is_rejected = True
                  return None
                  
          return {
              "message_id": context.message_id,
              "raw_user_query": context.raw_user_query,
              "extracted_sql": context.extracted_sql,
              "tool_result": context.tool_result,
              "domain": context.domain,
              "history_messages": context.history_messages
          }
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -v`
  Expected: PASS

---

### Task 2: 实现安全过滤器与空结果集过滤器

**Files:**
- Modify: `backend/app/agent/vector/rule_extractor.py`
- Modify: `backend/app/agent/vector/test_rule_extractor.py`

- [ ] **Step 1: 编写 SafetyWarningFilter 与 EmptyResultFilter 测试用例**
  在 `test_rule_extractor.py` 尾部追加测试：
  ```python
  def test_safety_warning_filter():
      """测试安全过滤器拦截违规 SQL 或带安全警告的消息"""
      from backend.app.agent.vector.rule_extractor import SafetyWarningFilter, ExtractionContext
      
      # 1. 模拟 SQL 含有 DROP
      ctx1 = ExtractionContext("m1", MagicMock())
      ctx1.tool_result = "SUCCESS"
      msg_mock1 = MagicMock()
      msg_mock1.content = "SQL: DROP TABLE chat_messages"
      ctx1.target_message = msg_mock1
      
      f = SafetyWarningFilter()
      assert f.execute(ctx1) is False
      assert "DROP" in ctx1.reject_reason
      
      # 2. 模拟执行结果包含 Safety Warning 警告
      ctx2 = ExtractionContext("m2", MagicMock())
      msg_mock2 = MagicMock()
      msg_mock2.content = "SELECT 1"
      ctx2.target_message = msg_mock2
      ctx2.tool_result = "Safety Warning: query blocked"
      assert f.execute(ctx2) is False
      
      # 3. 正常情况通过
      ctx3 = ExtractionContext("m3", MagicMock())
      msg_mock3 = MagicMock()
      msg_mock3.content = "SELECT * FROM users"
      ctx3.target_message = msg_mock3
      ctx3.tool_result = "[{'id': 1}]"
      assert f.execute(ctx3) is True

  def test_empty_result_filter():
      """测试空结果集拦截"""
      from backend.app.agent.vector.rule_extractor import EmptyResultFilter, ExtractionContext
      
      f = EmptyResultFilter()
      
      # 1. 模拟空列表返回
      ctx1 = ExtractionContext("m1", MagicMock())
      ctx1.tool_result = "[]"
      assert f.execute(ctx1) is False
      
      # 2. 模拟非 JSON 的非结构化空结果
      ctx2 = ExtractionContext("m2", MagicMock())
      ctx2.tool_result = ""
      assert f.execute(ctx2) is False
      
      # 3. 有效结果通过
      ctx3 = ExtractionContext("m3", MagicMock())
      ctx3.tool_result = "[{'total': 12}]"
      assert f.execute(ctx3) is True
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "safety or empty" -v`
  Expected: FAIL with `ImportError: cannot import name 'SafetyWarningFilter'`

- [ ] **Step 3: 实现安全和空结果过滤器类**
  在 `rule_extractor.py` 中实现 `SafetyWarningFilter` 与 `EmptyResultFilter`：
  ```python
  class SafetyWarningFilter(BaseFilter):
      """安全过滤器：阻止恶意 DDL/DML 或带安全警告拦截的 SQL 存入"""
      def execute(self, context: ExtractionContext) -> bool:
          target_content = (context.target_message.content or "").upper()
          tool_res = (context.tool_result or "").upper()
          
          # 1. 检查 SQL 关键字拦截
          blocked_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "GRANT"]
          for kw in blocked_keywords:
              if kw in target_content:
                  context.reject_reason = f"SafetyWarningFilter: 含有违规关键字 {kw}"
                  return False
                  
          # 2. 检查结果返回的拦截器标记
          warning_markers = ["SAFETY WARNING", "BLOCKED BY SECURITY FILTER", "PERMISSION DENIED"]
          for marker in warning_markers:
              if marker in tool_res:
                  context.reject_reason = f"SafetyWarningFilter: 包含安全警告标记: {marker}"
                  return False
                  
          return True

  class EmptyResultFilter(BaseFilter):
      """空结果集过滤器：丢弃执行成功但没有返回任何实质数据的 SQL 案例"""
      def execute(self, context: ExtractionContext) -> bool:
          res_str = (context.tool_result or "").strip()
          if not res_str:
              context.reject_reason = "EmptyResultFilter: 结果为空白文本"
              return False
              
          try:
              # 解析为 Python 对象校验
              data = json.loads(res_str)
              if isinstance(data, list) and len(data) == 0:
                  context.reject_reason = "EmptyResultFilter: 结果为结构化空列表 []"
                  return False
              if isinstance(data, dict) and len(data) == 0:
                  context.reject_reason = "EmptyResultFilter: 结果为结构化空字典 {}"
                  return False
          except Exception:
              # 无法解析为 JSON，若只是普通文本且内容过短，也视为空
              if len(res_str) < 2:
                  context.reject_reason = "EmptyResultFilter: 结果为非结构化无意义短文本"
                  return False
                  
          return True
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "safety or empty" -v`
  Expected: PASS

---

### Task 3: 实现单步 SQL 校验器 (极简丢弃策略)

**Files:**
- Modify: `backend/app/agent/vector/rule_extractor.py`
- Modify: `backend/app/agent/vector/test_rule_extractor.py`

- [ ] **Step 1: 编写 SingleSqlFilter 测试用例**
  在 `test_rule_extractor.py` 中追加测试：
  ```python
  def test_single_sql_filter():
      """测试单步 SQL 过滤规则"""
      from backend.app.agent.vector.rule_extractor import SingleSqlFilter, ExtractionContext
      
      f = SingleSqlFilter()
      
      # 1. 模拟存在多个 sql_db_query 的多步骤查询（包含两个 SQL 调用）
      ctx1 = ExtractionContext("m1", MagicMock())
      mock_msg1 = MagicMock()
      mock_msg1.tool_calls = json.dumps([
          {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT 1"}},
          {"id": "t2", "name": "sql_db_query", "args": {"query": "SELECT 2"}}
      ])
      mock_msg1.tool_results = json.dumps({
          "t1": "res1",
          "t2": "res2"
      })
      ctx1.target_message = mock_msg1
      assert f.execute(ctx1) is False
      assert "多步查询" in ctx1.reject_reason
      
      # 2. 模拟 SQL 执行报错的消息
      ctx2 = ExtractionContext("m2", MagicMock())
      mock_msg2 = MagicMock()
      mock_msg2.tool_calls = json.dumps([
          {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT 1"}}
      ])
      mock_msg2.tool_results = json.dumps({
          "t1": "Error: column 'x' does not exist"
      })
      ctx2.target_message = mock_msg2
      assert f.execute(ctx2) is False
      assert "执行报错" in ctx2.reject_reason
      
      # 3. 正常单步成功 SQL
      ctx3 = ExtractionContext("m3", MagicMock())
      mock_msg3 = MagicMock()
      mock_msg3.tool_calls = json.dumps([
          {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT * FROM users"}}
      ])
      mock_msg3.tool_results = json.dumps({
          "t1": "[{'id': 1}]"
      })
      ctx3.target_message = mock_msg3
      assert f.execute(ctx3) is True
      assert ctx3.extracted_sql == "SELECT * FROM users"
      assert ctx3.tool_result == "[{'id': 1}]"
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "single_sql" -v`
  Expected: FAIL with `ImportError: cannot import name 'SingleSqlFilter'`

- [ ] **Step 3: 实现 SingleSqlFilter 校验器**
  在 `rule_extractor.py` 中定义 `SingleSqlFilter`，实现多步直接舍弃，并提取成功 SQL 及其 tool_result：
  ```python
  class SingleSqlFilter(BaseFilter):
      """单步 SQL 校验器：确保智能体仅执行了一步且执行成功的 SQL"""
      def execute(self, context: ExtractionContext) -> bool:
          msg = context.target_message
          if not msg or not msg.tool_calls:
              context.reject_reason = "SingleSqlFilter: 目标消息没有工具调用"
              return False
              
          try:
              tool_calls = json.loads(msg.tool_calls)
              tool_results = json.loads(msg.tool_results) if msg.tool_results else {}
          except Exception as e:
              context.reject_reason = f"SingleSqlFilter: 序列化解析错误 {e}"
              return False
              
          # 过滤并找出所有 sql_db_query 工具调用
          sql_calls = [tc for tc in tool_calls if tc.get("name") == "sql_db_query"]
          
          if not sql_calls:
              context.reject_reason = "SingleSqlFilter: 没有调用 sql_db_query 工具"
              return False
              
          # 💡 极简丢弃策略：如果有多个不同的 SQL 执行记录，说明是复杂的多步查询，直接丢弃
          if len(sql_calls) > 1:
              context.reject_reason = "SingleSqlFilter: 包含多个 SQL 工具调用（属于多步查询，舍弃）"
              return False
              
          sql_call = sql_calls[0]
          call_id = sql_call.get("id")
          
          # 检查执行结果
          result_content = tool_results.get(call_id)
          if not result_content:
              context.reject_reason = f"SingleSqlFilter: 未找到工具 ID {call_id} 的对应执行结果"
              return False
              
          # 如果结果包含 Error / Exception 报错，说明执行失败，直接过滤丢弃
          if "ERROR:" in result_content.upper() or "EXCEPTION:" in result_content.upper():
              context.reject_reason = f"SingleSqlFilter: SQL 执行报错 ({result_content})"
              return False
              
          # 提取 SQL 及结果赋予 context
          args = sql_call.get("args") or {}
          if isinstance(args, str):
              try:
                  args = json.loads(args)
              except Exception:
                  pass
                  
          sql_query = args.get("query") if isinstance(args, dict) else ""
          if not sql_query:
              context.reject_reason = "SingleSqlFilter: 未能成功解析 query 参数"
              return False
              
          context.extracted_sql = sql_query
          context.tool_result = result_content
          return True
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "single_sql" -v`
  Expected: PASS

---

### Task 4: 实现基于 tool_call_id 的拓扑精准回溯器

**Files:**
- Modify: `backend/app/agent/vector/rule_extractor.py`
- Modify: `backend/app/agent/vector/test_rule_extractor.py`

- [ ] **Step 1: 编写 TopologyBacktrackFilter 测试用例**
  在 `test_rule_extractor.py` 中追加测试：
  ```python
  @patch("backend.app.agent.vector.rule_extractor.get_messages_by_session")
  def test_topology_backtrack_filter(mock_get_messages):
      """测试基于 tool_call_id 的精准拓扑回溯"""
      from backend.app.agent.vector.rule_extractor import TopologyBacktrackFilter, ExtractionContext
      
      # 构造会话消息链历史：
      # M1: User 原始提问 ("查2产线的出车数")
      # M2: Assistant 中断提问 ("请确认哪天？", tool_calls=[AskUserQuestion(id='ask-1')])
      # M3: User 回答澄清 ("今天", tool_results={'ask-1': '今天'})
      # M4: Assistant 最终回复 ("SELECT ...", tool_calls=[sql_db_query(id='sql-1')]) (这就是收藏的 target_message)
      
      m1 = MagicMock()
      m1.role = "user"
      m1.content = "查2产线的出车数"
      
      m2 = MagicMock()
      m2.role = "assistant"
      m2.content = "我们想和您确认哪天？"
      m2.tool_calls = json.dumps([{"id": "ask-1", "name": "AskUserQuestion", "args": {}}])
      
      m3 = MagicMock()
      m3.role = "user"
      m3.content = "[澄清回答] 今天"
      m3.tool_results = json.dumps({"ask-1": "今天"})
      
      m4 = MagicMock()
      m4.role = "assistant"
      m4.content = "数据结果..."
      m4.tool_calls = json.dumps([{"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT 1"}}])
      m4.tool_results = json.dumps({"sql-1": "[{'val': 1}]"})
      
      mock_get_messages.return_value = [m1, m2, m3, m4]
      
      ctx = ExtractionContext("msg-final", MagicMock())
      ctx.target_message = m4
      
      f = TopologyBacktrackFilter()
      assert f.execute(ctx) is True
      
      # 校验精准回溯的链条
      assert len(ctx.history_messages) == 4
      assert ctx.history_messages[0].content == "查2产线的出车数"
      assert ctx.history_messages[1].content == "我们想和您确认哪天？"
      assert ctx.history_messages[2].content == "[澄清回答] 今天"
      assert ctx.history_messages[3].content == "数据结果..."
      assert ctx.raw_user_query == "查2产线的出车数 [澄清提问: 我们想和您确认哪天？ -> 澄清回答: 今天]"
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "topology_backtrack" -v`
  Expected: FAIL with `ImportError: cannot import name 'TopologyBacktrackFilter'`

- [ ] **Step 3: 实现 TopologyBacktrackFilter 拓扑回溯器**
  在 `rule_extractor.py` 中编写 `TopologyBacktrackFilter`：
  ```python
  from backend.app.crud import get_messages_by_session

  class TopologyBacktrackFilter(BaseFilter):
      """精准拓扑回溯过滤器：还原多轮对话并拼装完整意图"""
      def execute(self, context: ExtractionContext) -> bool:
          target = context.target_message
          if not target:
              context.reject_reason = "TopologyBacktrackFilter: 上下文中目标消息为空"
              return False
              
          # 1. 加载当前会话的所有历史消息
          all_messages = get_messages_by_session(context.db, target.session_id)
          if not all_messages:
              context.reject_reason = "TopologyBacktrackFilter: 未能获取会话消息历史"
              return False
              
          # 2. 找到当前 target_message 在历史列表中的位置
          try:
              target_idx = -1
              for idx, m in enumerate(all_messages):
                  if m.id == target.id:
                      target_idx = idx
                      break
              if target_idx == -1:
                  # 如果 id 找不到，备用方案：按内容匹配
                  for idx, m in enumerate(all_messages):
                      if m.content == target.content and m.created_at == target.created_at:
                          target_idx = idx
                          break
          except Exception:
              target_idx = len(all_messages) - 1
              
          if target_idx == -1:
              context.reject_reason = "TopologyBacktrackFilter: 无法定位当前消息在会话历史中的位置"
              return False
              
          # 3. 开始精准向上追溯
          history = []
          curr_idx = target_idx
          
          # 将最终这条回复加入临时追踪链
          history.insert(0, all_messages[curr_idx])
          
          # 向上寻找它的触发 User 消息
          curr_idx -= 1
          if curr_idx < 0:
              context.reject_reason = "TopologyBacktrackFilter: 会话缺少 User 提问"
              return False
              
          prev_msg = all_messages[curr_idx]
          history.insert(0, prev_msg)
          
          # 4. 判断 prev_msg（紧邻的 User 消息）是否是对澄清提问（AskUserQuestion）的回复
          if prev_msg.role == "user" and prev_msg.tool_results:
              try:
                  results = json.loads(prev_msg.tool_results)
              except Exception:
                  results = {}
                  
              # 检查 results 中是否含有 AskUserQuestion 的 key
              # 拓扑咬合：如果包含这个 key，说明该 user 答案是回复上级澄清问答卡片的
              ask_user_ids = list(results.keys())
              
              if ask_user_ids:
                  # 进一步向上寻找产生该 ask_user_id 的 Assistant 澄清消息卡片
                  clarify_idx = curr_idx - 1
                  found_clarify = False
                  
                  while clarify_idx >= 0:
                      potential_clarify = all_messages[clarify_idx]
                      if potential_clarify.role == "assistant" and potential_clarify.tool_calls:
                          try:
                              calls = json.loads(potential_clarify.tool_calls)
                          except Exception:
                              calls = []
                          
                          # 匹配 tool call id
                          if any(c.get("id") == ask_user_ids[0] for c in calls):
                              # 找到了澄清卡片，插入追踪链中
                              history.insert(0, potential_clarify)
                              found_clarify = True
                              
                              # 接着再向上抓取触发该澄清提问的“原始 User 提问”
                              orig_user_idx = clarify_idx - 1
                              if orig_user_idx >= 0:
                                  history.insert(0, all_messages[orig_user_idx])
                              break
                      clarify_idx -= 1
                      
                  if not found_clarify:
                      # 拓扑链断层，退回到普通单轮
                      pass
                      
          # 保存消息历史链
          context.history_messages = history
          
          # 5. 拼装语义意图，供 LLM 后续消解指代
          # 格式化形式为：原始问题 [澄清提问: xxx -> 澄清回答: yyy]
          if len(history) >= 4:
              orig_query = history[0].content
              clarify_q = history[1].content
              clarify_a = history[2].content
              
              # 过滤可能存在的前置澄清修饰词
              clarify_a_clean = clarify_a.replace("[澄清回答]", "").strip()
              context.raw_user_query = f"{orig_query} [澄清提问: {clarify_q} -> 澄清回答: {clarify_a_clean}]"
          else:
              context.raw_user_query = history[0].content
              
          return True
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "topology_backtrack" -v`
  Expected: PASS

---

### Task 5: 业务域提取过滤器与管道集成

**Files:**
- Modify: `backend/app/agent/vector/rule_extractor.py`
- Modify: `backend/app/agent/vector/test_rule_extractor.py`

- [ ] **Step 1: 编写 DomainFilter 测试用例**
  在 `test_rule_extractor.py` 中追加测试：
  ```python
  def test_domain_filter():
      """测试 required_skill 的业务域属性提取"""
      from backend.app.agent.vector.rule_extractor import DomainFilter, ExtractionContext
      
      f = DomainFilter()
      
      # 1. 正常包含 required_skill
      ctx1 = ExtractionContext("m1", MagicMock())
      mock_msg1 = MagicMock()
      mock_msg1.tool_calls = json.dumps([
          {"id": "t1", "name": "load_skill", "args": {"skill": "paint_shop"}}
      ])
      ctx1.target_message = mock_msg1
      assert f.execute(ctx1) is True
      assert ctx1.domain == "paint_shop"
      
      # 2. 不包含任何 load_skill，默认为 general
      ctx2 = ExtractionContext("m2", MagicMock())
      mock_msg2 = MagicMock()
      mock_msg2.tool_calls = json.dumps([
          {"id": "t2", "name": "sql_db_query", "args": {}}
      ])
      ctx2.target_message = mock_msg2
      assert f.execute(ctx2) is True
      assert ctx2.domain == "general"
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -k "domain_filter" -v`
  Expected: FAIL with `ImportError: cannot import name 'DomainFilter'`

- [ ] **Step 3: 实现 DomainFilter 类并集成默认规则链**
  在 `rule_extractor.py` 中定义 `DomainFilter`：
  ```python
  class DomainFilter(BaseFilter):
      """业务域提取器：读取 load_skill 或 tool metadata，定位所属业务技能域进行硬性隔离"""
      def execute(self, context: ExtractionContext) -> bool:
          msg = context.target_message
          if not msg or not msg.tool_calls:
              context.domain = "general"
              return True
              
          try:
              calls = json.loads(msg.tool_calls)
          except Exception:
              context.domain = "general"
              return True
              
          # 寻找 load_skill 记录
          load_skill_calls = [c for c in calls if c.get("name") == "load_skill"]
          if load_skill_calls:
              args = load_skill_calls[0].get("args") or {}
              if isinstance(args, str):
                  try:
                      args = json.loads(args)
                  except Exception:
                      pass
              domain = args.get("skill") if isinstance(args, dict) else "general"
              context.domain = domain
          else:
              context.domain = "general"
              
          return True
  ```

- [ ] **Step 4: 创建默认提取器管道链对象**
  在 `rule_extractor.py` 尾部定义注册器：
  ```python
  # 默认的过滤器校验管道，按业务边界顺序链式执行
  DEFAULT_EXTRACTOR_PIPELINE = PipelineManager(filters=[
      SafetyWarningFilter(),
      SingleSqlFilter(),
      EmptyResultFilter(),
      TopologyBacktrackFilter(),
      DomainFilter()
  ])
  ```

- [ ] **Step 5: 运行规则提取器全量测试**
  Run: `conda activate py312_agent; pytest backend/app/agent/vector/test_rule_extractor.py -v`
  Expected: 所有过滤器和回溯测试（共 5 个用例）全部完美 PASS

- [ ] **Step 6: 提交成果（此处记录任务完成状况，由用户审批后续进行 commit）**
