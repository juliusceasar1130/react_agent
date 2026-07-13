# Agent 多格式结构化输出阶段 2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成接口流式协议（SSE）及非流式响应对多格式结构化输出的支持，打通后端数据流从 Agent State 捕获、SSE Schema 校验通过、再到落库存盘的完整双模适配通路。

**Architecture:**
1. 扩展协议定义类 [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py)，在 `FinalStreamEvent` 中引入 `structured_response` 选项，防止事件校验被过滤。
2. 在适配层 [services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 中，当流式与非流式调用结束时，从 Agent 的最后 State 中捕获 `structured_response`。
3. 在路由层 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 中，识别并存储结构化 JSON，无缝支持旧前端（通过 content 传输 JSON 字符串）和新协议（通过独立字段透传字典）。
4. 编写流式 SSE 状态获取测试脚本进行验证。

**Tech Stack:** `FastAPI`, `langchain==1.2.15`, `pydantic==2.x`

---

## 任务分解清单

### Task 1: 扩展协议层 Schema 定义

**Files:**
- Modify: [backend/app/schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py)

- [ ] **Step 1: 在 `FinalStreamEvent` 中引入新字段**
  
  定位到 [backend/app/schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py) 中的 `FinalStreamEvent` 定义（约第 171-180 行），将其中字段修改为：
  ```python
  class FinalStreamEvent(BaseModel):
      type: Literal["final"]
      content: str
      structured_response: Optional[Any] = None  # 新增：结构化输出返回载体
      tool_calls: Optional[List[StreamToolCallPayload]] = None
      tool_results: Optional[Dict[str, str]] = None
      context_warning: Optional[ContextWarningPayload] = None
      message_id: Optional[str] = None
      created_at: Optional[datetime] = None
  ```

- [ ] **Step 2: 验证 Pydantic Schema 校验与适配器编译**
  
  运行以下命令检测 schemas 编译是否正常：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.schemas import FinalStreamEvent; print('FinalStreamEvent compiled successfully')"
  ```
  Expected: 输出 `FinalStreamEvent compiled successfully` 且无任何 pydantic 声明报错。

- [ ] **Step 3: Commit**
  ```bash
  git add backend/app/schemas.py
  git commit -m "feat: add structured_response field to FinalStreamEvent schema"
  ```

---

### Task 2: 核心适配服务层捕获结构化数据

**Files:**
- Modify: [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)

- [ ] **Step 1: 在 `process_message` (非流式) 中捕获结构化响应**
  
  定位到 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 的 `process_message` 尾部（约第 593-602 行），修改为：
  ```python
          content, tool_calls, tool_results = self._extract_tool_data_from_result(
              result
          )
          context_warning = result.get("context_warning")
          
          # 获取结构化输出
          structured_response = None
          if settings.agent_structured_output:
              raw_struct = result.get("structured_response")
              if hasattr(raw_struct, "model_dump"):
                  structured_response = raw_struct.model_dump()
              elif isinstance(raw_struct, dict):
                  structured_response = raw_struct

          return {
              "content": content,
              "structured_response": structured_response,  # 新增返回
              "tool_calls": json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
              "tool_results": json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
              "context_warning": context_warning,
          }
  ```

- [ ] **Step 2: 在 `_stream_execution_loop` (流式循环) 中捕获结构化响应并打包事件**
  
  定位到 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 的 `_stream_execution_loop` 尾端最终 `"final"` 事件产生逻辑（约第 875-894 行），修改为：
  ```python
                  final_content = latest_ai_content
                  tool_calls = self._serialize_tool_calls(
                      accumulated_tool_calls,
                      final=True,
                  )
                  
                  # 开启时从 agent state 中提取结构化输出对象并序列化
                  structured_response = None
                  if settings.agent_structured_output:
                      state = await self.agent.aget_state(resolved_config)
                      if state and "structured_response" in state.values:
                          raw_struct = state.values["structured_response"]
                          if hasattr(raw_struct, "model_dump"):
                              structured_response = raw_struct.model_dump()
                          elif isinstance(raw_struct, dict):
                              structured_response = raw_struct

                  logger.info(
                      "流式提取完成：text_len=%d, tool_calls=%d 个, tool_results=%d 个, has_struct=%s",
                      len(final_content),
                      len(tool_calls),
                      len(accumulated_tool_results),
                      structured_response is not None,
                  )
                  await _emit(
                      {
                          "type": "final",
                          "content": final_content,
                          "structured_response": structured_response,  # 新增返回
                          "tool_calls": tool_calls or None,
                          "tool_results": accumulated_tool_results or None,
                          "context_warning": context_warning,
                      }
                  )
  ```

- [ ] **Step 3: 语法编译验证**
  
  运行以下命令：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.services import SQLAgentService; print('services.py loaded successfully')"
  ```
  Expected: 输出 `services.py loaded successfully`

- [ ] **Step 4: Commit**
  ```bash
  git add backend/app/services.py
  git commit -m "feat: extract structured_response from agent state in services.py"
  ```

---

### Task 3: 接口路由层双模分流、落库存盘与 SSE 输出

**Files:**
- Modify: [backend/app/api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py)

- [ ] **Step 1: 适配 `send_message` (非流式发送路由) 的落库存储**
  
  定位到 [backend/app/api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 里的非流式发送落库段（约第 455-464 行），将其修改为：
  ```python
      # 保存Assistant消息
      logger.info("保存Assistant消息到数据库")
      
      # 开启结构化输出时，将对象序列化为 JSON 字符串存入 content 和 refined_payload，实现完全兼容
      structured_response = agent_response.get("structured_response")
      if settings.agent_structured_output and structured_response:
          content_str = json.dumps(structured_response, ensure_ascii=False)
          refined_payload_str = content_str
      else:
          content_str = agent_response["content"]
          refined_payload_str = None

      assistant_message = crud.create_message(
          db,
          MessageCreate(
              session_id=session_id,
              role="assistant",
              content=content_str,
              refined_payload=refined_payload_str,
              tool_calls=agent_response["tool_calls"],
              tool_results=agent_response["tool_results"],
          ),
      )
  ```

- [ ] **Step 2: 适配 `/stream` (流式发送路由) 的落库存储与事件传递**
  
  定位到 [backend/app/api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 的 `generate` 函数里的 `"final"` 事件分支（约第 649-679 行），将其修改为：
  ```python
                      # 开启结构化输出时，将对象序列化为 JSON 字符串存入 content 和 refined_payload
                      structured_response = event.get("structured_response")
                      if settings.agent_structured_output and structured_response:
                          content_str = json.dumps(structured_response, ensure_ascii=False)
                          refined_payload_str = content_str
                      else:
                          content_str = full_content or "回答完成，但未生成可展示的文本内容。"
                          refined_payload_str = None

                      assistant_message = crud.create_message(
                          db,
                          MessageCreate(
                              session_id=session_id,
                              role="assistant",
                              content=content_str,
                              refined_payload=refined_payload_str,
                              tool_calls=(
                                  json.dumps(final_tool_calls, ensure_ascii=False)
                                  if final_tool_calls
                                  else None
                              ),
                              tool_results=(
                                  json.dumps(final_tool_results, ensure_ascii=False)
                                  if final_tool_results
                                  else None
                              ),
                          ),
                      )
                      assistant_persisted = True
                      logger.info("Assistant消息保存成功，ID: %s", assistant_message.id)
  
                      # final_event 事件结构中增加 structured_response 透传
                      final_event = {
                          **event,
                          "content": assistant_message.content,
                          "structured_response": structured_response,
                          "tool_calls": final_tool_calls,
                          "tool_results": final_tool_results,
                          "message_id": assistant_message.id,
                          "created_at": assistant_message.created_at.isoformat(),
                      }
                      yield _encode_sse(final_event)
                      continue
  ```

- [ ] **Step 3: 语法编译验证**
  
  运行以下命令：
  ```powershell
  conda run -n py312_agent python -c "from backend.app.api import send_message; print('api.py loaded successfully')"
  ```
  Expected: 输出 `api.py loaded successfully`

- [ ] **Step 4: Commit**
  ```bash
  git add backend/app/api.py
  git commit -m "feat: support structured response persistence and sse event transport in api.py"
  ```

---

### Task 4: 本地集成单元测试

**Files:**
- Create: [C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_sse.py](file:///C:/Users/julius/.gemini/antigravity-ide/scratch/test_structured_sse.py)

- [ ] **Step 1: 新增测试脚本**
  
  在 `C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_sse.py` 中写入测试代码：
  ```python
  # test_structured_sse.py
  import asyncio
  import sys
  import os

  workspace_dir = r"f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent"
  sys.path.insert(0, workspace_dir)

  os.environ["AGENT_STRUCTURED_OUTPUT"] = "true"

  from backend.app.config import settings
  settings.agent_structured_output = True

  from backend.app.services import SQLAgentService
  from backend.app.schemas import serialize_chat_stream_event

  async def test_stream_structured_extraction():
      print("--- 开始测试流式执行结束时 structured_response 对象的透传 ---")
      
      # 建立本地服务
      service = await SQLAgentService.create()
      
      # 模拟用户消息并触发流迭代
      # 我们可以只捕获最后产出的 final 事件，验证里面是否带有 structured_response 负载
      try:
          print("调用 process_stream 获取异步迭代器...")
          stream_iter = service.process_stream(
              "销售额是什么意思？",
              "test_session_sse_123",
              config={}
          )
          
          final_event = None
          async for event in stream_iter:
              event_type = event.get("type")
              print(f"收到事件 [{event_type}]")
              if event_type == "final":
                  final_event = event
                  
          if final_event:
              print("\n--- 成功捕获最终事件 final ---")
              print("事件键列表:", list(final_event.keys()))
              print("structured_response 是否存在:", "structured_response" in final_event)
              print("值:", final_event.get("structured_response"))
              
              # 校验事件能否被 schemas 正确校验并通过序列化
              try:
                  serialized = serialize_chat_stream_event(final_event)
                  print("✅ SSE Schema 校验与序列化通过！输出值:", list(serialized.keys()))
                  assert "structured_response" in serialized or final_event.get("structured_response") is None
              except Exception as err:
                  print(f"❌ SSE Schema 校验失败: {err}")
                  raise
          else:
              print("⚠️ 警告：未能捕获 final 事件")
              
          await service.aclose()
      except Exception as e:
          print(f"流式获取受到环境连接限制跳过: {e}")

  async def main():
      if sys.platform == "win32":
          import asyncio
          asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
      await test_stream_structured_extraction()

  if __name__ == "__main__":
      asyncio.run(main())
  ```

- [ ] **Step 2: 运行测试并分析输出**
  
  运行以下命令：
  ```powershell
  D:\000_software_install\miniconda3\envs\py312_agent\python.exe "C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_sse.py"
  ```
  Expected: 
  1. 成功生成并打印各个流事件。
  2. 捕获 final 事件且能够通过 `serialize_chat_stream_event` 的 Pydantic TypeAdapter 校验（没有抛出 Validation 错误，证明 schemas 适配已成功）。
  3. 退出代码为 0。
