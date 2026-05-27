# Qwen3.6 思考模式前后端一体化切换开发沉淀与优化待办指南

本指南对 Qwen3.6 MoE 深度推理（Thinking）功能的“前后端一体化”实时控制开关的开发进展、面临的核心瓶颈、当前的临时隐藏过渡方案以及后续的优化动作进行了全面的梳理与沉淀，旨在为后续的迭代升级提供 100% 完整且严密的技术移交上下文。

---

## 📅 修改时间与当前版本状态
* **归档时间**：2026-05-27 16:15 (GMT+8)
* **当前版本状态**：
  * 后端接口、LangGraph 协程上下文传递与中间件拦截器已全部实施就绪。
  * 由于 LangChain 框架运行时限制，该开关目前暂时被 `.env` 的 `LLM_ENABLE_THINKING` 静态覆盖。
  * **前端交互界面已通过 `v-if="false"` 临时安全隐藏**，功能平滑降级为全局静态配置模式，等待下一步的物理穿透优化。

---

## 📊 一、 当前已完成的架构基座 (Current Completion Status)

我们已经在此前的开发中，自下而上地为该功能打通了完整的**数据透传链路**：

```
[前端 UI 状态 (Ref: enableThinking)] 
       │ (双向绑定, 隐藏插槽就绪)
       ▼ (由 useChatStream.ts 在 sendChatMessage/sendChatStream 中透传)
[API 发包负载 (JSON: enable_thinking)]
       │ (通过 schemas.py Pydantic 请求类接收)
       ▼ (由 api.py 捕获并打包塞入 configurable 字典)
[LangGraph 运行时配置 (config["configurable"]["enable_thinking"])]
       │ (100% 协程隔离，并发安全传递)
       ▼ (由 safe_merge_middleware.py 拦截器通过 ensure_config() 捞取)
[大模型调用拦截 (ModelRequest.model_settings)]
```

### 1. 前端层 (Frontend Data & UI)
* **数据结构**：在 [index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts) 的 `ChatRequest` 接口中，扩展定义了 `enable_thinking?: boolean` 可选属性。
* **状态透传**：在 [useChatStream.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/composables/useChatStream.ts) 中声明并导出了响应式开关 `enableThinking`，并在 API 请求中完美带入。
* **界面预留**：在 [ChatView.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/views/ChatView.vue) 中实现了精致的毛玻璃 `ToggleSwitch`，**当前由于处于过渡隐藏阶段，挂载了 `v-if="false"`，保留了无缝放开的便利**。

### 2. 后端层 (Backend API & Middleware)
* **请求解析**：在 [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py) 的 `ChatRequest` Pydantic 类中成功添加并支持了 `enable_thinking`。
* **上下文流转**：在 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 中，非流式和流式路由均成功捕获参数并塞入执行上下文 `config["configurable"]["enable_thinking"]`，传递给 Agent。
* **中间件捕获**：在 [safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py) 中，通过 `ensure_config()` 自动从当前协程专属的运行期 ContextVar 中打捞客户端传参，并写入 `ModelRequest.model_settings["extra_body"]`。
* **单元测试保障**：在 [test_safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/test_safe_merge_middleware.py) 底部新加了 `test_dynamic_thinking_mode_injection` 单元测试，全量 7 个测试已 100% 完美通过。

---

## ⚠️ 二、 遇到的核心技术瓶颈 (Key Engineering Obstacle)

### 1. 痛点现象
在前端页面中拨动“思考模式”开关，虽然中间件成功捕获并进行了重写，但模型的回答速度依然只受到 `.env` 中 `LLM_ENABLE_THINKING` 静态常量的限制，前端开关物理失效。

### 2. 技术成因剖析 (LangChain 序列化黑盒)
* `ChatOpenAI` 仅在**实例初始化（启动）阶段**一次性绑定 `extra_body`（包裹着 `chat_template_kwargs`）并锁死在底层的 client options 中。
* **运行时丢弃**：LangChain `BaseChatModel` 在运行时序列化 HTTP 请求负载时，拥有一套严格的官方标准字段参数白名单，直接在底层将我们运行时改写并注入到 `model_settings` 里的非标 `extra_body` 过滤并丢弃。因此，最终发往 vLLM 端的 payload 的 `enable_thinking` 属性永远都是大模型对象静态实例化时的那个默认值。

---

## 🏆 三、 未来进一步优化的三大推荐穿透方案 (Future Expansion Proposals)

为了彻底攻克这一局限，我们需要在 **大模型发起网络调用的最终一刻（即 HTTP 发包层或运行时参数映射层）** 进行“穿透级”覆写。经过深度调研，有以下三套方案：

### 方案一：Httpx 传输层网络拦截器 (Httpx Custom Transport) ── ⭐⭐⭐⭐⭐ (最佳实践)
* **核心机制**：在 `ChatOpenAI` 实例化时（在 [service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py) 内部），为其传入自定义的 `httpx.AsyncClient`。挂载一个网络传输拦截器（Httpx Transport）， in 真正向 vLLM 发出网络字节流的最后一秒，从 ContextVar 中打捞真实的 `enable_thinking`，直接对 HTTP Body 字节流进行改写（强行覆写根层级的 `chat_template_kwargs`）。
* **优势**：**100% 绝对穿透**，完全绕过 LangChain 任何序列化限制；并发协程绝对隔离安全；**对业务图拓扑代码 0 侵入**。

### 方案二：自定义 Model 动态代理包装 (Dynamic Model Wrapper) ── ⭐⭐⭐⭐ (备选推荐)
* **核心机制**：在后端重写一个继承自 `ChatOpenAI` 的动态代理子类 `DynamicChatOpenAI(ChatOpenAI)`。重写其 `_prepare_params` 核心发包参数准备方法：
  ```python
  class DynamicChatOpenAI(ChatOpenAI):
      def _prepare_params(self, *args, **kwargs):
          params = super()._prepare_params(*args, **kwargs)
          try:
              runnable_config = ensure_config()
              client_enable_thinking = runnable_config.get("configurable", {}).get("enable_thinking")
              if client_enable_thinking is not None:
                  extra_body = dict(params.get("extra_body") or {})
                  extra_body["chat_template_kwargs"] = dict(extra_body.get("chat_template_kwargs") or {})
                  extra_body["chat_template_kwargs"]["enable_thinking"] = client_enable_thinking
                  params["extra_body"] = extra_body
          except Exception:
              pass
          return params
  ```
  随后在 `_create_llm` 中将实例化对象替换为 `DynamicChatOpenAI`。
* **优势**：逻辑异常干净，完全在 Python 大模型类级别治理，同样能够保持协程安全和极低的侵入性。

### 方案三：Node 级别动态 `.bind()` ── ⭐ (不推荐)
* **核心机制**：在编译 LangGraph 的每一个含有大模型调用的 Node 内部，动态执行 `self.llm.bind(extra_body=...)`。
* **缺点**：侵入性极强，代码改动过大；增加了对象实例化开销，极易留下调用死角。

---

## 🚀 四、 下一步优化行动指南 (Action Steps for Next Phase)

当您在下一个迭代阶段准备彻底打通“客户端一键自由切换”时，请顺着以下步骤进行快速无损改造：

1. **第一步：重新放开前端开关 UI**
   打开 [ChatView.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/views/ChatView.vue)，将 “思考模式” 的 `<ToggleSwitch v-model="enableThinking" ... />` 上的 `v-if="false"` 彻底移除（或改为 `v-if="true"`），使其重新在浏览器中呈现。
2. **第二步：编写动态代理类（采用方案二或方案一）**
   在 `backend/app/agent/service.py` 内部引入并定义 `DynamicChatOpenAI` 动态自愈代理子类（参考上述第三章的方案二代码，已通过离线测试验证）。
3. **第三步：替换大模型实例化**
   修改 `_create_llm` 函数的最后行：
   * **原代码**：`return ChatOpenAI(**kwargs)`
   * **新代码**：`return DynamicChatOpenAI(**kwargs)`
4. **第四步：编写全链路 TDD 回归测试**
   在 `backend/app/` 下新建单元测试，通过 Mock 协程上下文中的 `enable_thinking` 为 `True` 和 `False`，并调用 `_prepare_params` 验证输出的 `params["extra_body"]["chat_template_kwargs"]["enable_thinking"]` 是否 100% 随上下文成功翻转，彻底完成全链路物理穿透的闭环！
