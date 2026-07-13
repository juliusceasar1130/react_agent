# Agent 多格式结构化输出阶段 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成后端多格式结构化输出（`StructuredDataResult` 与 `FreeMarkdownResult`）的基础模型定义、环境变量条件装配以及本地单元测试验证。

**Architecture:** 
1. 通过环境变量 `AGENT_STRUCTURED_OUTPUT` 控制是否启用多格式结构化输出，默认为 `False`，实现双模向后兼容。
2. 定义 Pydantic 模型作为格式化工具的 Schema。当启用时，利用 `ToolStrategy(Union[...])` 动态装配至 `create_agent` 的 `response_format` 中。
3. 提供独立的单元测试脚本，在本地模拟 Agent 推理和输出校验。

**Tech Stack:** `langchain==1.2.15`, `langgraph==1.1.8`, `pydantic==2.x`

---

## 任务分解清单

### Task 1: 环境变量开关配置与注册

**Files:**
- Modify: [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py)
- Modify: [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env)

- [ ] **Step 1: 在 `.env` 中加入配置开关**
  
  在 [f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env) 文件的尾部添加以下行：
  ```bash
  # 是否开启多格式结构化输出 (默认 false)
  AGENT_STRUCTURED_OUTPUT=false
  ```

- [ ] **Step 2: 在 `backend/app/config.py` 中注册属性**
  
  在 [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py) 的 `Settings` 类中添加 `agent_structured_output` 属性：
  ```python
  # 在 Settings 类内（大约第 80 行，dimension_result_hard_limit 后面）
  agent_structured_output: bool = _parse_debug_flag(
      os.getenv("AGENT_STRUCTURED_OUTPUT", "false")
  )
  ```

- [ ] **Step 3: 运行验证**
  
  运行以下命令验证环境变量解析正确：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.config import settings; print('Switch status:', settings.agent_structured_output)"
  ```
  Expected: 输出 `Switch status: False`

- [ ] **Step 4: Commit**
  ```bash
  git add backend/app/config.py .env
  git commit -m "config: add agent_structured_output environment switch"
  ```

---

### Task 2: 定义 Pydantic 数据模型

**Files:**
- Create: [backend/app/agent/schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/schemas.py)

- [ ] **Step 1: 新建并实现 `schemas.py` 里的 Pydantic 数据模型**
  
  创建文件并写入以下内容：
  ```python
  # backend/app/agent/schemas.py
  from typing import Any, Literal, Optional
  from pydantic import BaseModel, Field

  class ReasoningStep(BaseModel):
      step: int = Field(description="思考步骤序号")
      thought: str = Field(description="模型思考内容（中文）")
      confidence: Literal["high", "medium", "low", "assumption"] = Field(description="可信度")
      user_should_verify: bool = Field(default=False, description="是否需要用户确认")
      suggestion: Optional[str] = Field(default=None, description="验证建议")

  class TableData(BaseModel):
      title: Optional[str] = Field(default=None, description="表格标题")
      headers: list[str] = Field(description="表头列名列表")
      rows: list[list[Any]] = Field(description="数据行列表")

  class StructuredDataResult(BaseModel):
      """强结构化数据输出模型（适用于报表与数据查询）"""
      judgment: str = Field(description="对查询意图的基本判断与数据范围说明")
      reasoning_process: Optional[list[ReasoningStep]] = Field(default=None, description="模型推理思考步骤")
      tables: list[TableData] = Field(description="查询结果表格数据列表")
      columns: Optional[list[dict]] = Field(default=None, description="列渲染控制定义")
      insights: list[str] = Field(description="数据洞察与核心结论列表")
      used_tables: Optional[list[str]] = Field(default=None, description="实际使用的数据表名列表（非必填，大模型基于上下文抄写）")
      query_time: Optional[str] = Field(default=None, description="数据真实查询时刻（非必填，大模型基于上下文抄写）")
      execution_trace_id: Optional[str] = Field(default=None, description="工具调用执行记录追踪ID（非必填，大模型基于上下文抄写）")
      total_count: Optional[int] = Field(default=None, description="总数据条数")
      data_freshness: Optional[str] = Field(default=None, description="数据新鲜度说明")

  class FreeMarkdownResult(BaseModel):
      """自由文本输出模型（适用于 RAG 问答、开发问题、澄清问题等）"""
      response_type: Literal["explanation", "clarification", "refusal", "other"] = Field(description="回复类型分类标签")
      content: str = Field(description="支持包含 Mermaid、代码块等任意 Markdown 格式的主体文本")
      suggested_tables: Optional[list[str]] = Field(default=None, description="可能相关的数据表建议")
      suggested_questions: Optional[list[str]] = Field(default=None, description="可能具体的查询问法建议")
  ```

- [ ] **Step 2: 验证数据类合法性**
  
  运行以下命令：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.agent.schemas import StructuredDataResult; print(StructuredDataResult.model_fields.keys())"
  ```
  Expected: 成功打印所有字段的名称（`judgment`, `tables`, `insights` 等）且不抛出导入错误。

- [ ] **Step 3: Commit**
  ```bash
  git add backend/app/agent/schemas.py
  git commit -m "feat: define structured response schemas for agent"
  ```

---

### Task 3: 后端初始化层条件装配

**Files:**
- Modify: [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py)

- [ ] **Step 1: 在 `service.py` 头部引入数据模型**
  
  在 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py) 文件头（例如第 58 行后面）添加导入：
  ```python
  from backend.app.agent.schemas import StructuredDataResult, FreeMarkdownResult
  ```

- [ ] **Step 2: 修改同步初始化 `_initialize_agent` 装配参数**
  
  在 `backend/app/agent/service.py` 中定位 `self.agent = create_agent`（约第 646 行），修改为：
  ```python
  # 动态确定 response_format
  response_format = None
  if settings.agent_structured_output:
      from typing import Union
      from langchain.agents.structured_output import ToolStrategy
      response_format = ToolStrategy(
          Union[StructuredDataResult, FreeMarkdownResult],
          handle_errors=True
      )

  self.agent = create_agent(
      model=llm,
      tools=tools,
      system_prompt=system_prompt,
      middleware=middleware_list,
      response_format=response_format,  # 动态注入
      **agent_kwargs,
  )
  ```

- [ ] **Step 3: 修改异步初始化 `_ainitialize_agent` 装配参数**
  
  定位异步初始化中的 `self.agent = create_agent`（约第 775 行），进行相同的修改：
  ```python
  # 动态确定 response_format
  response_format = None
  if settings.agent_structured_output:
      from typing import Union
      from langchain.agents.structured_output import ToolStrategy
      response_format = ToolStrategy(
          Union[StructuredDataResult, FreeMarkdownResult],
          handle_errors=True
      )

  self.agent = create_agent(
      model=llm,
      tools=tools,
      system_prompt=system_prompt,
      middleware=middleware_list,
      response_format=response_format,  # 动态注入
      **agent_kwargs,
  )
  ```

- [ ] **Step 4: 运行检查以保证无编译或装配语法错误**
  
  运行以下命令：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.agent.service import SQLAgentService; print('SQLAgentService loaded successfully')"
  ```
  Expected: 输出 `SQLAgentService loaded successfully`

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/agent/service.py
  git commit -m "feat: support conditional structured response format in create_agent"
  ```

---

### Task 4: 本地单元测试验证

**Files:**
- Create: [C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_agent.py](file:///C:/Users/julius/.gemini/antigravity-ide/scratch/test_structured_agent.py)

- [ ] **Step 1: 新建本地测试脚本**
  
  在 `C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_agent.py` 文件中写入以下测试代码：
  ```python
  import asyncio
  import os
  from backend.app.config import settings
  # 强行在测试运行时开启开关
  settings.agent_structured_output = True

  from backend.app.agent.service import SQLAgentService
  from backend.app.agent.schemas import StructuredDataResult, FreeMarkdownResult

  async def main():
      print("正在初始化 SQLAgentService...")
      # 创建同步和异步环境的 Service（根据 service.py 支持的方法）
      service = SQLAgentService(session_id="test_session_id_123")
      await service._ainitialize_agent()
      
      # 1. 测试普通开发性问题 -> 应该被分流到 FreeMarkdownResult
      print("\n--- 测试开发性问题（预期分流为 FreeMarkdownResult） ---")
      inputs = {"messages": [("user", "帮我解释下 SQL 查询中 JOIN 的区别")]}
      response = await service.agent.ainvoke(inputs)
      
      structured = response.get("structured_response")
      print("类型为:", type(structured))
      if structured:
          print("内容概要:", getattr(structured, "content", "")[:100])
          assert isinstance(structured, FreeMarkdownResult)
      else:
          print("⚠️ 警告：未能获取到结构化输出")

      # 2. 测试简单数据查询问题 -> 应该被分流为 StructuredDataResult
      print("\n--- 测试数据查询问题（预期分流为 StructuredDataResult） ---")
      inputs_db = {"messages": [("user", "帮我查一下数据库里包含哪些表格")]}
      response_db = await service.agent.ainvoke(inputs_db)
      structured_db = response_db.get("structured_response")
      print("类型为:", type(structured_db))
      if structured_db:
          print("字段值:", structured_db.model_dump())
          assert isinstance(structured_db, (StructuredDataResult, FreeMarkdownResult))
      else:
          print("⚠️ 警告：未能获取到结构化输出")

  if __name__ == "__main__":
      asyncio.run(main())
  ```

- [ ] **Step 2: 运行测试并分析输出**
  
  运行测试命令：
  ```powershell
  conda run -n py312_agent python "C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_agent.py"
  ```
  Expected: 
  1. 第一个测试成功输出 `类型为: <class 'backend.app.agent.schemas.FreeMarkdownResult'>`
  2. 第二个测试成功输出并解析出 tables 列表，或在失败时正确优雅地降级为 `FreeMarkdownResult` 说明失败。
  3. 全程无任何 `ValidationError` 未被捕获抛出的闪退。

- [ ] **Step 3: 恢复测试环境并清理**
  
  确保本地代码中的环境变量开关默认依然为 `false`（ Task 1 设定的状态），测试脚本仅在运行时内存中改变它。
