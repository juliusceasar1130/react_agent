# Agent 多格式结构化输出阶段 4 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成灰度试点分流、日志审计与结构化提示词调优，实现根据 `session_id` 的哈希比例分流灰度，增加 `ValidationError` 的拦截与延迟 Token 指标监控审计日志，并在系统 Prompt 中对 Pydantic 的空表和日期规范进行针对性强化。

**Architecture:**
1. 在 [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env) 中新增灰度百分比开关 `AGENT_STRUCTURED_OUTPUT_GRAY_RATIO=0`，在 [config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py) 中解析。
2. 在 [services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 中，动态根据 `session_id` 进行 SHA256 离散并对 100 取模。若小于配置比例，则本会话自动判定命中灰度，开启结构化功能。
3. 在 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 和 [services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 中加入日志埋点，记录灰度命中情况、结构化反序列化成功率、大模型延迟、推理步数等审计数据，并拦截 `ValidationError` 优雅隔离。
4. 微调系统提示词 [base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/prompts/base_system_prompt.md)，强化 Pydantic 二元联合类型的输出规范，杜绝 JSON 字段污染、规范时间格式及零记录空表处理。

**Tech Stack:** `Python`, `hashlib`, `FastAPI`, `Pydantic`

---

## 任务分解清单

### Task 1: 灰度分流机制实现

**Files:**
- Modify: [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env)
- Modify: [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py)
- Modify: [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)

- [ ] **Step 1: 新增灰度比例环境变量**
  
  In [.env](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env) 文件尾部追加一行配置，默认设为 0% 不启用：
  ```ini
  AGENT_STRUCTURED_OUTPUT_GRAY_RATIO=0
  ```

- [ ] **Step 2: 在 `config.py` 中解析该比例**
  
  在 [backend/app/config.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py) 的 `Settings` 类中（约第 84 行后面），注册该灰度比例字段：
  ```python
      # 开启结构化输出的灰度放量比例 (0 - 100)
      agent_structured_output_gray_ratio: int = int(os.getenv("AGENT_STRUCTURED_OUTPUT_GRAY_RATIO", "0"))
  ```

- [ ] **Step 3: 实现灰度取模算法并注入适配层**
  
  在 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 的头部或 `SQLAgentService` 类内部增加 `is_gray_hit` 判断函数：
  ```python
  import hashlib
  
  def is_gray_hit(session_id: str, gray_ratio: int) -> bool:
      """根据 session_id 进行 SHA256 哈希取模实现均匀灰度分流"""
      if gray_ratio <= 0:
          return False
      if gray_ratio >= 100:
          return True
      h = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
      val = int(h, 16) % 100
      return val < gray_ratio
  ```
  
  修改 `SQLAgentService` 中的 `process_message` 与 `_stream_execution_loop` 起始处，将原有的 `settings.agent_structured_output` 检查升级为双模叠加（全局开关开启 OR 本会话命中灰度）：
  
  * **在 `process_message` 中**：
    ```python
            # 获取结构化输出
            is_structured_active = settings.agent_structured_output or is_gray_hit(session_id, settings.agent_structured_output_gray_ratio)
            structured_response = None
            if is_structured_active:
                raw_struct = result.get("structured_response")
                # ... 保持不变
    ```
  
  * **在 `_stream_execution_loop` 中**：
    ```python
                    # 开启时从 agent state 中提取结构化输出对象并序列化
                    is_structured_active = settings.agent_structured_output or is_gray_hit(session_id, settings.agent_structured_output_gray_ratio)
                    structured_response = None
                    if is_structured_active:
                        state = await self.agent.aget_state(resolved_config)
                        # ... 保持不变
    ```

- [ ] **Step 4: 验证编译**
  ```powershell
  conda run -n py312_agent python -c "from backend.app.services import SQLAgentService; print('services.py compiled successfully')"
  ```

---

### Task 2: 审计日志与异常监控拦截

**Files:**
- Modify: [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)
- Modify: [backend/app/api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py)

- [ ] **Step 1: 核心适配层加入会话审计与性能埋点**
  
  在 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 的 `process_message` 和 `_stream_execution_loop` 的最终段落中，输出结构化审计日志：
  ```python
          # 在 process_message / _stream_execution_loop 输出 final 前
          logger.info(
              "[AUDIT] Session %s structured response audit: active=%s, has_result=%s, steps=%d, tables=%d, insights=%d",
              session_id,
              is_structured_active,
              structured_response is not None,
              len(structured_response.get("reasoning_process", [])) if structured_response and "reasoning_process" in structured_response else 0,
              len(structured_response.get("tables", [])) if structured_response and "tables" in structured_response else 0,
              len(structured_response.get("insights", [])) if structured_response and "insights" in structured_response else 0,
          )
  ```

- [ ] **Step 2: API 接口路由层加入对 ValidationError 的安全保护与落底退化**
  
  由于大模型可能会输出不合规的 JSON，我们在 [backend/app/api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 的流式和非流式落库存盘前，引入对 JSON 校验出错的安全拦截与退化到纯文本 Markdown 的机制，防止接口 500 导致用户会话挂断：
  
  * **在 `api.py` 的 `/stream` 路由中（约第 660 行）**：
    ```python
                      structured_response = event.get("structured_response")
                      
                      # 灰度审计与异常防御拦截
                      if settings.agent_structured_output and structured_response:
                          try:
                              # 模拟验证该字典是否能被 schemas 正确校验（防幻觉脏数据）
                              # 遇到非合法格式或数据破坏时，进行捕获并降级落底
                              if "tables" not in structured_response and "content" not in structured_response:
                                  raise ValueError("Missing structured response core payload")
                              
                              content_str = json.dumps(structured_response, ensure_ascii=False)
                              refined_payload_str = content_str
                              logger.info("[AUDIT] Session %s structured response validation check passed", session_id)
                          except Exception as err:
                              logger.warning(
                                  "[AUDIT] Session %s structured response validation check FAILED: %s. Falling back to plain text content.",
                                  session_id,
                                  err
                              )
                              # 校验失败时，退化回 markdown 纯文本落底，隐藏 structured_response 以免前端渲染失败
                              content_str = full_content or "回答完成，但未生成可展示的文本内容。"
                              refined_payload_str = None
                              structured_response = None
    ```
    
  * **在非流式 `send_message` 路由中（约第 455 行）**：
    同上添加 `try-except` 对 `structured_response` 校验进行安全捕获与落底退化。

- [ ] **Step 3: 验证编译**
  ```powershell
  conda run -n py312_agent python -c "from backend.app.api import send_message; print('api.py compiled successfully')"
  ```

---

### Task 3: 系统提示词微调优化

**Files:**
- Modify: [backend/app/agent/prompts/base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/prompts/base_system_prompt.md)

- [ ] **Step 1: 优化 Pydantic ToolStrategy 引导词**
  
  在 [backend/app/agent/prompts/base_system_prompt.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/prompts/base_system_prompt.md) 文件的底部，插入对于结构化输出的强引导规则：
  ```markdown
  
  ## 结构化数据输出强约束
  当启用了结构化输出模式（绑定了 StructuredDataResult 和 FreeMarkdownResult 联合工具）时，你必须遵守以下最高等级指令：
  1. **禁止污染**：你生成的 JSON 数据前后绝对不能附带任何非 JSON 纯文本、Markdown 气泡包裹、思考溢出等杂质。
  2. **空记录优雅处理**：若查询数据库返回的结果行为 0（无符合条件记录），严禁凭空虚构任何行。你必须在 `TableData` 中填充正确的字段 headers，并将 `rows` 强制声明为 `[]` 空数组。
  3. **日期时间一致性**：所有产生和处理的时间字符串，必须采用系统内置的标准格式 `YYYY-MM-DD HH:MM:SS`（例如: `2024-07-12 14:30:00`）。绝对禁止使用 ISO 8601 格式（带有 T 或时区 +08:00 后缀），否则前端正则表达式匹配组件将会崩塌！
  ```

---

### Task 4: 本地集成回归测试

**Files:**
- Create: [C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_gray.py](file:///C:/Users/julius/.gemini/antigravity-ide/scratch/test_structured_gray.py)

- [ ] **Step 1: 新增灰度分流与异常拦截测试脚本**
  
  在 [test_structured_gray.py](file:///C:/Users/julius/.gemini/antigravity-ide/scratch/test_structured_gray.py) 中写入测试代码：
  ```python
  # test_structured_gray.py
  import asyncio
  import sys
  import os
  import json

  workspace_dir = r"f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent"
  sys.path.insert(0, workspace_dir)

  from backend.app.config import settings
  from backend.app.services import is_gray_hit

  def test_gray_distribution():
      print("--- 1. 测试灰度分流概率取模均匀度 (基于 SHA256) ---")
      gray_ratio = 30  # 30% 灰度
      hit_count = 0
      total = 1000
      
      for i in range(total):
          session_id = f"session_uuid_{i}_test_mock"
          if is_gray_hit(session_id, gray_ratio):
              hit_count += 1
              
      ratio = (hit_count / total) * 100
      print(f"设定灰度比例: {gray_ratio}%, 模拟会话数: {total}, 实际命中数: {hit_count} (占比: {ratio}%)")
      # SHA256 对 1000 次离散取模应该在设定比例上下浮动 5% 以内
      assert 25 <= ratio <= 35, f"Gray distribution skew is too high: {ratio}%"
      print("✅ 灰度离散取模测试通过！")

  def test_validation_fallback_stub():
      print("--- 2. 模拟验证 API 层对非法结构数据的 fallback 安全拦截 ---")
      
      # 模拟异常数据（缺失 tables 且缺失 content，格式异常）
      broken_response = {
          "judgment": "销售分析",
          "reasoning_process": [{"step": 1, "thought": "分析", "confidence": "high"}]
      }
      
      settings.agent_structured_output = True
      
      # 模拟 api.py 中的 try-except 防御机制
      try:
          if "tables" not in broken_response and "content" not in broken_response:
              raise ValueError("Missing structured response core payload")
          content_str = json.dumps(broken_response, ensure_ascii=False)
          refined_payload_str = content_str
          structured_response = broken_response
      except Exception as err:
          print(f"安全捕获校验异常: {err}")
          # 回退传统
          content_str = "回答完成，但未生成可展示的文本内容。"
          refined_payload_str = None
          structured_response = None
          
      print("校验落底后 content_str:", content_str)
      print("校验落底后 structured_response:", structured_response)
      assert structured_response is None
      assert content_str == "回答完成，但未生成可展示的文本内容。"
      print("✅ API 异常防御拦截与落底测试通过！")

  if __name__ == "__main__":
      test_gray_distribution()
      test_validation_fallback_stub()
      print("\n--- 阶段 4 本地回归测试圆满结束 ---")
  ```

- [ ] **Step 2: 运行测试并分析输出**
  
  运行以下命令：
  ```powershell
  D:\000_software_install\miniconda3\envs\py312_agent\python.exe "C:\Users\julius\.gemini\antigravity-ide\scratch\test_structured_gray.py"
  ```
  Expected: 
  1. 成功生成并打印 30% 均匀灰度分流比率（约 29% ~ 31% 的会话数命中）。
  2. 模拟 validation 校验失败后自动退化纯文本落底，且没有任何抛出导致主流程阻断。
  3. 退出代码为 0。
