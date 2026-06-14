# 领域技能 DDL 移入 System Message 相对尾部实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将加载的领域技能（DDL和核心知识）从 ToolMessage（历史消息）中剥离，移入 System Message 的相对尾部（排在动态 RAG 检索上下文前面），解决长对话下因消息压缩（SummarizationMiddleware）丢失表结构的痛点，并极大提升 vLLM 前缀缓存命中率。

**Architecture:** 改造 `load_skill` 工具使其仅返回状态提示并继续更新 Graph State，重构 `SkillMiddleware` 拦截器以从 State 中读取 `active_skill` 并动态将其 DDL 全文拼装进 System Message 块内。

**Tech Stack:** Python 3.12, FastAPI, LangChain, LangGraph

---

### Task 1: 技能加载工具重构

**Files:**
- Modify: [skill_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/tools/skill_tools.py)

- [ ] **Step 1: 修改 _build_load_skill_command 逻辑**
  
  修改 `backend/app/agent/tools/skill_tools.py` 里的 `_build_load_skill_command` 函数，不再往 ToolMessage 塞入大段 `skill_content`：
  
  ```python
  def _build_load_skill_command(skill_name: str, runtime: ToolRuntime) -> Command:
      skill = get_skill_by_name(skill_name)
      if skill is None:
          available = ", ".join(s["name"] for s in get_all_skills())
          return Command(
              update={
                  "messages": [
                      ToolMessage(
                          content=(
                              f"Skill '{skill_name}' not found. "
                              f"Available skills: {available}"
                          ),
                          tool_call_id=runtime.tool_call_id,
                      )
                  ]
              }
          )

      loaded_skills = _merge_names(runtime.state.get("skills_loaded", []), skill_name)

      return Command(
          update={
              "messages": [
                  ToolMessage(
                      content=(
                          f"Loaded domain skill '{skill_name}' successfully. "
                          "The database tables DDL and business rules have been dynamically mounted "
                          "to your System Prompt. You can now compose SQL queries for this domain."
                      ),
                      tool_call_id=runtime.tool_call_id,
                  )
              ],
              "skills_loaded": loaded_skills,
              "active_skill": skill_name,
          }
      )
  ```

- [ ] **Step 2: 手动验证代码修改**
  
  无需执行命令行测试，确保 `skill_tools.py` 语法正常。

---

### Task 2: 技能中间件 TDD 改造

**Files:**
- Create: `backend/app/agent/middleware/test_skill_middleware.py`
- Modify: [skill_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/skill_middleware.py)

- [ ] **Step 1: 编写失败的单元测试 (TDD)**
  
  创建 `backend/app/agent/middleware/test_skill_middleware.py`，测试中间件对已激活 DDL 的动态系统拼接：
  
  ```python
  import pytest
  from langchain_core.messages import SystemMessage
  from langchain.agents.middleware.types import ModelRequest

  from backend.app.agent.middleware.skill_middleware import SkillMiddleware
  from backend.app.agent.state import CustomState

  def test_skill_middleware_injects_active_ddl():
      # 模拟已激活领域技能的状态
      state = CustomState(
          messages=[],
          skills_loaded=["paint_shop_vehicle_logistics"],
          active_skill="paint_shop_vehicle_logistics"
      )
      
      request = ModelRequest(
          model=None,
          messages=[],
          system_message=SystemMessage(content="Base system prompt"),
          state=state
      )
      
      middleware = SkillMiddleware()
      new_request = middleware._modify_request(request)
      
      content = str(new_request.system_message.content)
      assert "Available Skills" in content
      assert "Active Domain Knowledge: paint_shop_vehicle_logistics" in content
      assert "ods.carbody_history" in content
  ```

- [ ] **Step 2: 运行测试确认其失败**
  
  在 `py312_agent` 环境下运行：
  `conda run -n py312_agent pytest backend/app/agent/middleware/test_skill_middleware.py -v`
  Expected: FAIL（报错，因为尚未在 `skill_middleware.py` 中拼装 DDL）。

- [ ] **Step 3: 修改 skill_middleware.py 以支持 DDL 拼接**
  
  重写 `backend/app/agent/middleware/skill_middleware.py` 里的 `_modify_request` 方法：
  
  ```python
      def _modify_request(self, request: ModelRequest) -> ModelRequest:
          """将技能描述及当前激活领域 DDL 注入到系统提示词"""
          skills_prompt = _build_skills_prompt(get_all_skills())
          skills_addendum = (
              f"\n\n## Available Skills\n\n{skills_prompt}\n\n"
              "Use the load_skill tool when you need detailed domain knowledge. "
              "If the loaded domain skill shows a matching fixed scenario, use the "
              "load_scenario tool before composing SQL. For fixed statistics or "
              "fixed report-style questions, prefer loading a scenario instead of "
              "planning from scratch."
          )

          active_skill = request.state.get("active_skill") if request.state else None
          active_ddl_addendum = ""
          if active_skill:
              from backend.app.skills import load_domain_content
              skill_content = load_domain_content(active_skill)
              if skill_content:
                  active_ddl_addendum = (
                      f"\n\n## Active Domain Knowledge: {active_skill}\n"
                      "下列是当前激活领域的核心表结构 DDL 以及业务易错规则，请在编写 SQL 时严格遵守：\n\n"
                      f"{skill_content}\n"
                  )

          new_content = list(request.system_message.content_blocks) + [
              {"type": "text", "text": skills_addendum}
          ]
          if active_ddl_addendum:
              new_content.append({"type": "text", "text": active_ddl_addendum})
              
          new_system_message = SystemMessage(content=new_content)

          return request.override(system_message=new_system_message)
  ```

- [ ] **Step 4: 运行测试确保其通过 (PASS)**
  
  再次运行：
  `conda run -n py312_agent pytest backend/app/agent/middleware/test_skill_middleware.py -v`
  Expected: PASS。
