# 技能与澄清工具健壮性优化 (Skill & AskUserQuestion Robustness Refactor)

> **修订日期**：2026-07-20  
> **状态**：已全面落地 (COMPLETED)（辅助技能淘汰已完成 FIFO `pop(0)` 机制重构，澄清卡片数量约束与 JSON 吞错缺陷已修复，TDD 自动化测试用例已全部 PASSED）  
> **文档位置**：`docs/StructuredOutput/refactor/07_skill_tools_and_ask_user_question_robustness_refactor.md`  

**Goal:** 解决 `skill_tools` 驱逐最老技能时的值匹配逻辑漏洞，并优化 `AskUserQuestion` 的提问卡片数量范围及 JSON 异常吞错，全面提高工具的运行健壮性与排错效率。

**Architecture:** 
1. 重构辅助技能淘汰逻辑为严格的基于索引的 FIFO 物理出队队列 (`pop(0)`)，替代原有的值判定 (`remove()`) 以杜绝同名重复元素带来的错删或削减失效隐患。
2. 在澄清提问 Pydantic Schema 中显式指定 `min_length=1, max_length=4`，并在 `parse_questions` 处理器中增加明确的 `ValueError` 解码异常抛出以替代静默吞错，将错误清晰回传。

**Tech Stack:** Python 3.12, Pydantic v2, LangChain Core, Pytest

---

### Task 1: 优化 skill_tools.py 辅助技能驱逐逻辑 (FIFO 改造)

**Files:**
- Modify: `backend/app/agent/tools/skill_tools.py:49-61`
- Test: `backend/app/agent/middleware/test_skill_middleware.py`

- [ ] **Step 1: 编写失败的单元测试 (TDD)**
  在 [test_skill_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_skill_middleware.py#L84) 文件末尾追加测试用例，专门模拟在存在重复技能、且列表长度一次性溢出 2 个元素时的淘汰行为：
  ```python
  def test_load_skill_tool_truncates_over_limit_with_duplicates():
      from unittest.mock import MagicMock
      from langchain.tools import ToolRuntime
      from backend.app.agent.tools.skill_tools import _build_load_skill_command

      # 模拟已重复加载并且长度已超限的情况
      initial_state = {
          "messages": [],
          "skills_loaded": ["skill_a", "skill_a", "skill_b", "skill_c"],
          "active_skill": "skill_c"
      }
      runtime = MagicMock(spec=ToolRuntime)
      runtime.state = initial_state
      runtime.tool_call_id = "test_call_id"

      # 此时加载第 5 个技能 "skill_d"，期望最终削减到恰好 3 个，且移除的是最老端的两个 A
      cmd = _build_load_skill_command("skill_d", runtime)
      loaded = cmd.update["skills_loaded"]
      
      assert len(loaded) == 3
      assert "skill_a" not in loaded
      assert loaded == ["skill_b", "skill_c", "skill_d"]
  ```

- [ ] **Step 2: 运行测试并验证其失败**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/app/agent/middleware/test_skill_middleware.py -k test_load_skill_tool_truncates_over_limit_with_duplicates -v`
  预期输出：FAIL，由于 `remove` 的 Bug，列表长度削减后依然是 4，断言 `len(loaded) == 3` 失败。

- [ ] **Step 3: 修改 skill_tools.py 的驱逐逻辑**
  修改 [skill_tools.py:56-60](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/skill_tools.py#L56-L60)，将原基于值匹配的 remove 逻辑改写为基于物理 FIFO 索引出队的 while 循环：
  ```python
      # 限制辅助技能堆积上限为 3 个，超出截断最先进入的 (FIFO)
      while len(new_loaded) > 3:
          new_loaded.pop(0)
  ```

- [ ] **Step 4: 重新运行单元测试验证通过**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/app/agent/middleware/test_skill_middleware.py -v`
  预期输出：PASS (全量测试顺利通过)。

- [ ] **Step 5: 提交 Commit 申请 (等待用户批准)**
  ```bash
  git add backend/app/agent/tools/skill_tools.py backend/app/agent/middleware/test_skill_middleware.py
  # 等待用户允许后方可 commit
  ```

---

### Task 2: 优化 AskUserQuestion 卡片数量约束与 JSON 吞错

**Files:**
- Modify: `backend/app/agent/tools/ask_user_question.py:23-57`
- Test: `backend/app/agent/tools/test_ask_user_question.py`

- [ ] **Step 1: 编写失败的单元测试 (TDD)**
  在 [test_ask_user_question.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/test_ask_user_question.py#L73) 末尾追加两项测试，专门验证数量边界拦截和损坏 JSON 解析抛错：
  ```python
  def test_ask_user_question_limit_boundaries():
      tool = AskUserQuestion()
      # 测试 0 个提问卡片拦截
      with pytest.raises(Exception):
          tool.args_schema.model_validate({"questions": []})

      # 测试 5 个提问卡片拦截
      oversized = [{"question": f"Q{i}"} for i in range(5)]
      with pytest.raises(Exception):
          tool.args_schema.model_validate({"questions": oversized})

  def test_ask_user_question_parser_error_exposure():
      tool = AskUserQuestion()
      broken_json = '{broken json string'
      
      # 传入解析失败的字符串，应当抛出 ValidationError，且错误内容中包含解析失败自定义文本
      with pytest.raises(Exception) as excinfo:
          tool.args_schema.model_validate({"questions": broken_json})
      assert "澄清提问列表解析失败" in str(excinfo.value)
  ```

- [ ] **Step 2: 运行测试验证其失败**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/app/agent/tools/test_ask_user_question.py -k "test_ask_user_question_limit_boundaries or test_ask_user_question_parser_error_exposure" -v`
  预期输出：FAIL，由于老代码未限制 questions 长度且静默吞错，导致测试断言不通过。

- [ ] **Step 3: 优化 ask_user_question.py 逻辑**
  1. 在 [ask_user_question.py:24](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/ask_user_question.py#L24) 增加字段校验参数：
     ```python
         questions: List[QuestionItem] = Field(
             description="澄清问题卡片列表，支持 1~4 个。",
             min_length=1,
             max_length=4
         )
     ```
  2. 在 `parse_questions` 处理器的解析器 [ask_user_question.py:48-55](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/ask_user_question.py#L48-L55) 中改写异常处理，拒绝静默吞错，直接抛出 `ValueError`：
     ```python
                 try:
                     v = json.loads(v)
                 except Exception as e_json:
                     try:
                         import ast
                         v = ast.literal_eval(v)
                     except Exception as e_ast:
                         raise ValueError(
                             f"澄清提问列表解析失败。传入的内容必须是标准的 JSON 数组格式。\n"
                             f"JSON 解析错误: {e_json}\n"
                             f"AST 解析错误: {e_ast}"
                         )
     ```

- [ ] **Step 4: 运行单元测试验证通过**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/app/agent/tools/test_ask_user_question.py -v`
  预期输出：PASS (全量提问测试用例全部通过)。

- [ ] **Step 5: 提交 Commit 申请 (等待用户批准)**
  ```bash
  git add backend/app/agent/tools/ask_user_question.py backend/app/agent/tools/test_ask_user_question.py
  # 等待用户允许后方可 commit
  ```
