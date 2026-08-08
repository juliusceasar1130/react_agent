# vLLM + Qwen/DeepSeek 思考过程（Reasoning Content）在 LangSmith Trace 与前端流式渲染分析及实施报告

> **报告创建时间**：2026-07-31  
> **文档位置**：`docs/thinking_mode/langsmith_thinking_process_integration_guide.md`  
> **适用场景**：vLLM 部署的 Qwen 3.6 / DeepSeek-R1 / QwQ 等具备 Thinking/Reasoning 能力的模型在 LangChain/LangGraph 架构下的 Observability 与前端展示。

---

## 1. 背景与问题现象

在基于 LangChain / LangGraph + vLLM 部署 Qwen 3.6 推理模型时，希望：
1. 在 **LangSmith Trace** 监控界面中，观察模型每次调用是否产生了思考过程以及具体的思考内容（Reasoning Content）。
2. 在 **前端 UI** 中，能够以流式（打字机）的形式把“思考过程”实时推送并展示在可折叠的 UI 块中。

### 实际观测结果
在 LangSmith Trace 界面查验 `ChatOpenAI` 节点（包括 `finish_reason: "tool_calls"` 与 `finish_reason: "stop"` 节点）的 Output JSON 时，发现：
- `message.kwargs` 中只有 `content`、`tool_calls` 和 `response_metadata`；
- **完全缺失 `additional_kwargs` 字段，且找不到任何 `reasoning_content` 或 `thinking` 相关的思考记录**。

---

## 2. 根因深度分析 (Root Cause)

经过对协议层与 LangChain 源码解析机制的对比诊断，确定根本原因为以下三点：

```
[ vLLM (Qwen 3.6) ] 
       │ 返回 choice.message.reasoning_content (非 OpenAI 官方标准字段)
       ▼
[ langchain_openai.ChatOpenAI ] 
       │ 仅解析 content / tool_calls，静默过滤非标准扩展字段
       ▼
[ AIMessage (kwargs 缺失 additional_kwargs) ] 
       ├──> [ LangSmith Trace ] (源头缺少字段，无法捕获与记忆)
       └──> [ SSE 流式推送 ]   (源头缺少 Token，前端无法拿到思考流)
```

### ① 协议与字段名映射差异
vLLM 在开启 Reasoning 模板或搭载 Qwen 3.6/DeepSeek 模型时，将思考链放在以下字段：
- 非流式（完整响应）：`response.choices[0].message.reasoning_content`
- 流式（Streaming）：`response.choices[0].delta.reasoning_content`

### ② vLLM 服务端配置核验（已确认服务侧正常）
检查 vLLM 启动参数发现：
- 已配置 `--reasoning-parser qwen3`：说明 vLLM 服务端能够正确将 `<think>...</think>` 标签抽离并序列化到标准的 `reasoning_content` API 响应字段中。
- 已配置 `--default-chat-template-kwargs '{"enable_thinking": true}'`：说明后端模板默认开启了思考生成。
- **结论**：vLLM 服务端已完备输出 `reasoning_content`，服务端无需修改。

### ③ `langchain_openai.ChatOpenAI` 的静默过滤
`langchain_openai` 库针对 OpenAI 官方 API 设计。OpenAI 官方（如 o1/o3）使用 `reasoning_tokens` 计数而非透传思考文本。因此 `ChatOpenAI` 在将 API 响应转换为 `AIMessage` 时，**不会自动提取 `reasoning_content` 写入 `AIMessage.additional_kwargs`**。

### ④ 工具调用 (Tool Call) 轮次特点
当模型决定发起工具调用（`finish_reason: "tool_calls"`）时，大多数推理模型在输出 JSON 格式的工具指令时**不生成思考链**，思考内容仅在生成文本回答（`finish_reason: "stop"`）轮次中产生。

---

## 3. 解决方案与技术选型

为了同时解决 **LangSmith Trace 观察记忆** 和 **后续前端流式展示** 的需求，提供以下两种解决方案：

### ⚠️ 实施前提：开启思考模式

vLLM 服务端虽已通过 `--default-chat-template-kwargs '{"enable_thinking": true}'` 默认开启思考，但项目后端 `_create_llm`（`backend/app/agent/service.py`）会通过 `extra_body.chat_template_kwargs.enable_thinking` **覆盖 vLLM 默认值**。当前 `.env` 中 `LLM_ENABLE_THINKING=false`，会关闭思考链生成，导致 `reasoning_content` 为空。

实施前必须修改 `.env`：
```bash
LLM_ENABLE_THINKING=true
```
或移除此变量，让 vLLM 服务端默认值生效。

### 方案 A：使用 LangChain 官方包 `langchain-deepseek`（推荐，零侵入）

虽然包名为 `langchain-deepseek`，但其内部核心即为解决在 OpenAI 协议下提取 `reasoning_content` 的问题，完全兼容 vLLM 部署的 Qwen 3.6 / DeepSeek。

* **依赖安装**：
  ```bash
  pip install langchain-deepseek
  ```
* **初始化替换**：
  ```python
  from langchain_deepseek import ChatDeepSeek

  llm = ChatDeepSeek(
      model="gpt-5-nano",                           # vLLM 上的模型标识（--served-model-name）
      api_base="http://<your-vllm-host>:8089/v1",   # vLLM 服务端地址（实际端口 8089）
      api_key="EMPTY",                              # 无鉴权填任意字符串
      temperature=0.7,
  )
  ```

* **参数名映射**：现有 `_create_llm` 函数使用 `ChatOpenAI`，切换到 `ChatDeepSeek` 时需将参数名从 `openai_api_key` / `openai_api_base` 改为 `api_key` / `api_base`。其余参数（`model`、`temperature`、`max_tokens`、`request_timeout`、`max_retries`、`top_p`、`presence_penalty`）保持不变。

* **`extra_body` 兼容性**：`ChatDeepSeek` 继承自 `BaseChatOpenAI`（`ChatOpenAI` 的基类），因此现有通过 `extra_body` 透传的 vLLM 非标准采样参数（`top_k`、`repetition_penalty`、`min_p`、`chat_template_kwargs.enable_thinking`）**完全兼容，无需改动透传逻辑**。

* **优势**：官方维护，通过重写 `_create_chat_result`（非流式）和 `_convert_chunk_to_generation_chunk`（流式）自动将 `reasoning_content` 写入 `AIMessage.additional_kwargs["reasoning_content"]`，LangSmith Trace 面板即刻自动支持展示。相比方案 B，`ChatDeepSeek` 在 `_convert_chunk_to_generation_chunk` 层（chunk dict 级别）拦截，是 `BaseChatOpenAI` 流式处理链的正确注入点，可靠性更高。

* **依赖状态**：`requirements.txt` 已包含 `langchain-deepseek==1.0.1`，无需额外安装。

---

### 方案 B：自定义扩展 `ChatOpenAI` 类（项目内轻量拦截）

若不想额外引入第三方包，可在项目代码 `backend/app/agent/service.py` 中重写 `ChatOpenAI` 的响应解析逻辑：

```python
from typing import Any, AsyncIterator, Iterator
from langchain_openai import ChatOpenAI
from langchain_core.outputs import ChatResult, ChatGenerationChunk

class QwenThinkingChatOpenAI(ChatOpenAI):
    """
    针对 vLLM + Qwen3.6 / DeepSeek 增强的 ChatOpenAI 适配类
    自动提取 API 返回的 reasoning_content 并挂载到 additional_kwargs 中
    """

    # 1. 非流式调用拦截 (满足 LangSmith Trace 记忆)
    def _create_chat_result(self, response: dict, **kwargs) -> ChatResult:
        chat_result = super()._create_chat_result(response, **kwargs)
        for i, generation in enumerate(chat_result.generations):
            choice = response.get("choices", [])[i]
            message = choice.get("message", {})
            reasoning = message.get("reasoning_content") or message.get("reasoning")
            if reasoning:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return chat_result

    # 2. 同步流式调用拦截
    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        for chunk in super()._stream(*args, **kwargs):
            raw_chunk = getattr(chunk, "generation_info", {}) or {}
            choices = raw_chunk.get("choices", [])
            if choices and "reasoning_content" in choices[0].get("delta", {}):
                reasoning = choices[0]["delta"]["reasoning_content"]
                if reasoning:
                    chunk.message.additional_kwargs["reasoning_content"] = reasoning
            yield chunk

    # 3. 异步流式调用拦截 (满足前端 SSE 实时推送)
    async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        async for chunk in super()._astream(*args, **kwargs):
            raw_chunk = getattr(chunk, "generation_info", {}) or {}
            choices = raw_chunk.get("choices", [])
            if choices and "reasoning_content" in choices[0].get("delta", {}):
                reasoning = choices[0]["delta"]["reasoning_content"]
                if reasoning:
                    chunk.message.additional_kwargs["reasoning_content"] = reasoning
            yield chunk
```

> **⚠️ 注意**：方案 B 通过 `chunk.generation_info` 获取原始 `choices` 数据的方式可能不可靠。`ChatDeepSeek` 源码的实际做法是重写 `_convert_chunk_to_generation_chunk` 方法，在 **chunk dict 层面**（而非 `generation_info`）拦截 `delta.reasoning_content`，这才是 `BaseChatOpenAI` 流式处理链的正确注入点。**优先推荐方案 A**。

---

## 4. 后续前端流式 (SSE) 联动方案

当使用上述方案补全 `additional_kwargs` 后，可在后端 `backend/app/services.py` 的流式事件打包层：

1. **提取思考 Token**：
   在 `_unpack_stream_chunk` 或监听 `on_chat_model_stream` 事件时，判断 `chunk.message.additional_kwargs.get("reasoning_content")`。

2. **打包为 SSE 思考事件**：
   > **⚠️ 不可复用 `stage: "thinking"`**：项目中 `StreamStage` 已有 `"thinking"` 值，但其语义是 **“Agent 正在分析问题”的 loading 状态**（`frontend/src/stores/messages.ts` 中 `stage: 'thinking', statusText: '正在分析问题'`），与模型 reasoning content 语义不同，混用会导致前端逻辑冲突。
   >
   > 同时，项目中 `TokenStreamEvent` 的 Schema 为 `{ type: "token", text: str, node: Optional[str] }`，**没有 `stage` 和 `content` 参数**，不能直接使用。

   ```python
   # 方案一（推荐）：复用现有 status 事件，新增 stage 值 "reasoning"
   from backend.app.schemas import StatusStreamEvent

   if reasoning_token:
       yield StatusStreamEvent(
           stage="reasoning",        # 新增 stage 值，与现有 "thinking"(loading) 区分
           text=reasoning_token,
           source="llm_reasoning"
       )

   # 方案二：新增独立事件类型 "reasoning"
   if reasoning_token:
       yield {"type": "reasoning", "text": reasoning_token}
   ```

3. **前端同步更新（防丢机制）**：
   根据 AGENTS.md 约定，新增流式事件须同步更新前端三处，防止被网络拦截层静默过滤丢弃：
   1. `@/types` 中的 `StreamEvent` 联合类型声明（新增 `reasoning` 分支或 `reasoning` stage）
   2. `@/api/chat` 中的 `STREAM_EVENT_TYPES` 白名单 Set 集合（新增类型）
   3. `@/api/chat` 中 `parseStreamEvent` 的 `switch` 解析分支（新增解析逻辑）

4. **前端渲染**：
   前端在接收到 reasoning 事件/stage 时，向“思考过程”可折叠展开框中追加文本；收到正式 `token` 事件时，切换为回复文本框输出。

5. **双初始化路径同步**：
   根据 AGENTS.md 约定，`_create_llm` 被 `_initialize_agent`（同步，LangGraph 托管模式）和 `_ainitialize_agent`（异步，FastAPI 本地模式）共同调用。修改 LLM 创建逻辑只需改 `_create_llm` 一处，两条路径自动生效。

---

## 5. 总结验证清单

| 验证项 | 预期表现 | 状态 |
| :--- | :--- | :---: |
| **vLLM 服务端配置** | `--reasoning-parser qwen3` + `--default-chat-template-kwargs` 已就绪 | ✅ 已确认 |
| **`.env` 思考开关** | `LLM_ENABLE_THINKING=true` 或移除让 vLLM 默认值生效 | 🛠️ 待修改 |
| **Trace 节点定位** | 在 `finish_reason: "stop"` 的最终回答 `ChatDeepSeek` 节点查看 | 🛠️ 待实施 |
| **Output JSON 结构** | `kwargs.additional_kwargs.reasoning_content` 中包含思考链字符串 | 🛠️ 待实施 |
| **LangSmith 可视化** | 右侧 Output / Attributes 面板可点开查看思考内容 | 🛠️ 待实施 |
| **前端 SSE 流式推送** | 新增 `reasoning` 事件/stage，与现有 `thinking`(loading) 区分 | 🛠️ 规划中 |
| **前端三处防丢更新** | `StreamEvent` 类型 + `STREAM_EVENT_TYPES` 白名单 + `parseStreamEvent` 解析 | 🛠️ 规划中 |
