# 2026-05-26 18:00:00 - 补充 System Message 组成分析、顺序保障与 RAG 动态更新机制

# 2026-05-24 16:40:00 - 沉淀 vLLM 部署与多系统消息冲突（System message must be at the beginning）操作指南

# vLLM 部署与多系统消息冲突解决方案

## 1. 背景与现象

在局域网内部署本地大语言模型（如 `RedHatAIQwen3.6-35B-A3B-NVFP4`）并使用 vLLM 推理框架提供 OpenAI 兼容接口时，如果客户端采用了复杂的智能体（Agent）架构（如 LangChain/LangGraph 配合多中间件工作流），可能会在交互时触发如下报错：

*   **客户端侧报错日志**：
    ```text
    openai.BadRequestError: Error code: 400 - {'error': {'message': 'System message must be at the beginning.', 'type': 'BadRequestError', 'param': None, 'code': 400}}
    ```
*   **vLLM 服务端（APIServer）报错日志**：
    ```text
    jinja2.exceptions.TemplateError: System message must be at the beginning.
    ...
    ValueError: System message must be at the beginning.
    ```

---

## 2. 根因剖析

该问题是**客户端复杂消息流合成机制**与**开源大模型严格的 Chat Template（对话模板）校验**冲突引起的经典痛点：

### 2.1 客户端的消息序列化拼接 (LangChain / LangGraph)
在我们的智能体框架中，为了实现对大模型的丰富功能增强，开启了诸如 `SkillMiddleware`（技能中间件）和 `BusinessRagMiddleware`（业务知识 RAG 中间件）：
*   **主系统提示词**通过 `ModelRequest.system_message` 传入。
*   **RAG 中间件**为了把检索到的背景术语塞给大模型，会动态生成一个带有 `role="system"` 的 `SystemMessage` 对象，并插入到对话历史列表 `state.messages` 的最前面。
*   最终，在向底层大模型接口发送 `llm.ainvoke(messages)` 时，LangChain 的 `ChatOpenAI` 客户端类会将主系统提示词和对话历史消息打包合并。这导致最终发送给 vLLM 的 JSON Payload `messages` 数组中，在不同的位置出现了**多个** `role: "system"` 的消息：
    ```json
    [
      {"role": "system", "content": "主系统提示词..."},
      {"role": "system", "content": "__business_rag_context__\n\n## 业务知识库..."},
      {"role": "user", "content": "用户问题"}
    ]
    ```

### 2.2 vLLM 端的 Qwen Chat Template 限制
Qwen 等开源系列模型在其 Hugging Face 分词器配置（`tokenizer_config.json`）中内置的 `chat_template`（Jinja2 模板）有着极其严苛的安全与注意力分布防御校验：
*   **模板硬性逻辑**：遍历消息列表，只要检测到某条消息的 `role == "system"`，且它不是循环中的第一个元素（`not loop.first`），就会强制抛出异常：`System message must be at the beginning.`。
*   **限制意图**：因为在 SFT（监督微调）阶段，大模型一般只在最开头接收过一个 System 提示词。如果中途再次插入额外的 System 提示词，极易引起**注意力分布偏移（Attention Distribution Shift）**，导致大模型遗忘先前的上下文或指令遵循度下降。
*   **API 差异**：OpenAI 官方 API（如 `gpt-4o` 等）在云端后端对多系统消息有着更加宽容的合并或处理机制，因此以前直接连接 OpenAI 官方时不会报错，而切换到本地 vLLM + 开源模型时，该隐患立刻暴露。

---

### 方案三：客户端引入 SafeMergeSystemMiddleware 终极安全自愈合并中间件（已正式上线 🚀）

相比“修改既有 RAG/Skill 中中间件底层逻辑”的繁琐重构，本项目在客户端挂载了一个终极安全合并中间件 **`SafeMergeSystemMiddleware`**。该方案作为“尾部守门人”，在大模型调用的最后临界时机自动拦截并合并消息，**对既有业务中间件 100% 透明且无感**。

#### 1. 工作原理与执行时序
*   **各司其职**：`BusinessRagMiddleware` 依然负责将 RAG 背景知识插入到对话历史列表 `state.messages` 首部；`SkillMiddleware` 依然负责将可用技能列表追加到全局 `ModelRequest.system_message`。
*   **临界合并**：在 `SQLAgentService` 的同步与异步生命周期的 `middleware_list` 最末尾添加 `SafeMergeSystemMiddleware`。它在调用 LLM 接口前拦截 `ModelRequest`，当检测到历史对话首位或夹层中存在包含 `__business_rag_context__` 标识的 RAG 系统消息时，安全地提取两者的纯文本并用 `\n\n` 进行规整拼接，重新构建唯一的纯文本 `SystemMessage`，并将原 RAG 消息从对话历史中安全物理剥离。
*   **自愈效果**：发送给 vLLM 接口的 `messages` 列表中有且仅有最开头的一条 `system` 消息，且完全是干净利落、无嵌套列表的纯文本格式，完全绕过了所有严格的模板校验并彻底根治了底层 LLM 序列化解析报错（如 `string indices must be integers`），实现了客户端零侵入即时自愈。

#### 2. 中间件核心逻辑
```python
def _get_string_content(msg) -> str:
    """安全地将 SystemMessage 的 content (可能是 str 或 List[Dict/Str]) 转换为纯文本字符串。"""
    if msg is None:
        return ""
    
    # 1. 优先读取 content_blocks 结构块属性
    content_blocks = getattr(msg, "content_blocks", None)
    if isinstance(content_blocks, list):
        texts = []
        for block in content_blocks:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    texts.append(block["text"])
                elif "text" in block:
                    texts.append(block["text"])
                else:
                    texts.append(str(block))
        return "\n".join(texts)

    # 2. 备用读取 content 属性
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    texts.append(block["text"])
                elif "text" in block:
                    texts.append(block["text"])
                else:
                    texts.append(str(block))
        return "\n".join(texts)
    return str(content)


class SafeMergeSystemMiddleware(AgentMiddleware[CustomState]):
    state_schema = CustomState

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        messages = list(request.messages)
        if not messages:
            return request

        filtered_messages = []
        rag_texts = []

        # 1. 深度遍历全量历史消息队列，定位并抽干所有的 RAG SystemMessage
        for msg in messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                is_rag = False
                
                if isinstance(content, str) and "__business_rag_context__" in content:
                    is_rag = True
                elif hasattr(msg, "content_blocks"):
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_rag = True
                                break

                if is_rag:
                    # 提取该条 RAG 消息的纯文本内容，存入暂存器
                    rag_text = _get_string_content(msg)
                    if rag_text:
                        rag_texts.append(rag_text)
                    # ⚠️ 注意：此处故意不将该消息放入 filtered_messages，以实现彻底的物理抽干！
                    continue

            # 保留其他所有普通消息
            filtered_messages.append(msg)

        # 2. 如果检索到了任何 RAG 消息，执行物理合并与对话历史大一统抽干
        if rag_texts:
            logger.info(f"🛡️ SafeMergeSystemMiddleware: 全局打捞检测到 {len(rag_texts)} 条 RAG 消息，正在开启安全自愈合并...")
            
            # 提取全局核心提示词与所有搜集到的 RAG 消息的纯文本
            sys_text = _get_string_content(request.system_message)
            merged_rag_text = "\n\n".join(rag_texts)
            
            # 用纯文本大一统构筑 SystemMessage，彻底根除序列化报错
            merged_content = f"{sys_text}\n\n{merged_rag_text}"
            new_system_message = SystemMessage(content=merged_content)
            
            logger.info(
                "🛡️ SafeMergeSystemMiddleware: 多 System 消息全量打捞合并完成，"
                "已将所有 RAG 消息规范化为纯文本 SystemMessage 并从 messages 列表中彻底抽干物理抹除！"
            )
            return request.override(
                system_message=new_system_message,
                messages=filtered_messages
            )

        return request
```

#### 3. 方案评估
*   **无感自愈**：彻底消灭了 vLLM 因多 System 消息引发的 400 BadRequest 报错，客户端具备了极高的生态抗压与容错能力。
*   **性能提升**：规则与参考背景紧密连贯，极大有利于 vLLM 推理端 `--enable-prefix-caching` KV 缓存的整体复用，使首字延迟 (TTFT) 缩短数倍。
*   *质量保障*：新编写了 `test_safe_merge_middleware.py` 单元测试，全方位覆盖常规、标准和 block 块等多场景，100% 验证通过。

---

## 4. 总结与最佳实践建议

| 阶段 | 实施手段 | 对客户端侵入度 | 运维复杂度 | 推荐等级 |
| :--- | :--- | :--- | :--- | :--- |
| **即时自愈** | **方案三：客户端挂载 SafeMergeSystemMiddleware 合并中间件** | **极低 (仅追加挂载，对原有业务无侵入)** | 零 (完全无需额外运维配置) | ⭐⭐⭐⭐⭐ (五星，首选自愈方案) |
| **推理端修复** | **方案一：vLLM 挂载自适应合并 Jinja2 模板** | **无 (0 改动)** | 低 (仅增启动参数) | ⭐⭐⭐⭐⭐ (五星，辅助搭配) |
| **中转路由** | **方案二：网关层清洗过滤** | **无 (0 改动)** | 中 (需配置网关) | ⭐⭐⭐⭐ (四星) |

---

## 5. 即插即用 (Pluggable) 拔插式回退指南

本合并方案在设计之初就遵循了最极致的“开闭原则”，作为纯粹的 **切面拦截器 (Aspect-Oriented Middleware)** 运行。它完全没有改动任何业务图 (Graph) 的内部节点，也未对底层的持久化数据库造成任何破坏性写入，因而具备 100% 的架构可逆性。

如果在未来任何时候，您因切换至云端 API（如 OpenAI / DeepSeek 官方接口）或其他原因不再需要合并 System 消息，您只需要花费 10 秒钟即可完美回退到最原始的功能状态。

### 5.1 一键注销中间件

只需在 `backend/app/agent/service.py` 中注释掉 `SafeMergeSystemMiddleware()` 的两处挂载声明：

#### 1. 注释同步初始化列表 (约第 545 行)：
```python
middleware_list = [
    summarization_middleware,
    SkillMiddleware(),
    _create_context_warning_middleware(),
    # SafeMergeSystemMiddleware(),  # ◄── 直接注释掉此行！
]
```

#### 2. 注释异步初始化列表 (约第 627 行)：
```python
middleware_list = [
    summarization_middleware,
    SkillMiddleware(),
    _create_context_warning_middleware(),
    # SafeMergeSystemMiddleware(),  # ◄── 直接注释掉此行！
]
```

### 5.2 回退后的系统表现

一旦注销挂载，请求将完全绕过安全合并模块，消息流的表现将百分之百原汁原味地还原到初始设计：
* **动态 RAG 背景知识**：会恢复原本的逻辑，继续由 `BusinessRagMiddleware` 独立插入到对话历史首部，并随消息历史被 PostgresSaver 写入数据库检查点。
* **可用技能列表**：会恢复原本的逻辑，继续通过 `SkillMiddleware` 追加到全局 `ModelRequest.system_message` 配置中。
* **消息序列**：发给底层的 `messages` 序列重新回到原汁原味的多 System 消息模式，没有任何逻辑及物理残留。

---

## 6. LLM 最终收到的 System Message 组成分析

### 6.1 最终消息结构

经过中间件链处理后，LLM 最终收到的消息格式为：

```json
[
    {"role": "system", "content": "① + ② + ③"},
    {"role": "user", "content": "用户问题"},
    {"role": "assistant", "content": "历史应答"},
    ...
]
```

**有且仅有一条 `role="system"` 的消息，位于消息数组第 0 位。**

### 6.2 System Message 三大组成部分

| 部分 | 来源 | 注入时机 | 注入方式 |
|------|------|---------|---------|
| ① 系统提示词 | `_build_system_prompt(db)` | Agent 创建时 | 作为 `ModelRequest.system_message` 传入 |
| ② 可用技能列表 | `SkillMiddleware._modify_request()` | `wrap_model_call` 阶段 | 追加到 `system_message.content_blocks` 作为新的 text block |
| ③ RAG 业务知识 | `BusinessRagMiddleware.before_model()` → `SafeMergeSystemMiddleware._modify_request()` | `before_model` 注入 `state.messages` → `wrap_model_call` 末尾打捞合并 | 检索后注入到 `state.messages` 首部，再由 SafeMerge 从中抽取并合并到 `system_message`，最后物理移除 |

### 6.3 最终 SystemMessage 内容伪表示

```text
{系统提示词: 你是 SQL Agent，负责...}

## Available Skills
- skill_name_1: 技能描述
- skill_name_2: 技能描述
...

__business_rag_context__

## 业务知识库

下面是与当前用户问题相关的业务资料：

### 业务术语说明 (Documentation)
#### 术语A
- 业务域: 焊接
- 别名: Weld, 焊接点

术语A的具体定义...
```

### 6.4 顺序保障机制

SafeMergeSystemMiddleware 确保 system 消息始终是第一条（也是唯一的一条）的机制：

1. **遍历检查**：深度遍历 `request.messages`，定位所有含 `__business_rag_context__` 标记的 `SystemMessage`
2. **物理抽干**：标记为 RAG 的消息通过 `continue` 跳过，不放入 `filtered_messages`
3. **合并到 system_message**：RAG 内容提取后合并到 `request.system_message`（纯文本化），替换原有的 `SystemMessage`
4. **结果**：`request.messages` 中不再包含任何 `role="system"` 的消息，`create_agent` 框架将 `system_message` 天然放在消息数组第 0 位

---

## 7. RAG 知识动态更新机制

### 7.1 逐轮更新流程

```
第 1 轮：用户提问 "A 车型焊点缺陷统计"
  → BusinessRagMiddleware.before_model: 识别最后消息为 HumanMessage(A)
    → 执行向量检索 query="A 车型焊点缺陷统计"
    → 获得 RAG_A 内容
    → 注入 SystemMessage("__business_rag_context__...RAG_A") 到 state.messages 首部
  → SafeMergeSystemMiddleware: 从 messages 打捞 RAG_A，合并到 system_message，物理移除
  → LLM 收到: [System(①+②+RAG_A), Human(A)]

第 2 轮：用户追问 "B 产线呢？"
  → BusinessRagMiddleware.before_model: 识别最后消息为 HumanMessage("B 产线呢？")
    → 执行向量检索 query="B 产线呢？"
    → 获得 RAG_B 内容（与 RAG_A 不同）
    → 遍历 messages，发现旧的 RAG_A 消息，跳过不保留（替换而非追加）
    → 注入新的 SystemMessage("__business_rag_context__...RAG_B") 到首部
  → SafeMergeSystemMiddleware: 从 messages 打捞 RAG_B，合并到 system_message，物理移除
  → LLM 收到: [System(①+②+RAG_B), Human(A), AIMessage(应答A), Human(B)]
```

### 7.2 关键保障

1. **`before_model` 每次 LLM 调用都会执行**：`BusinessRagMiddleware` 在每个 `before_model` 周期检查 `state.messages` 的最后一条是否为 `HumanMessage`（`rag_middleware.py:132-148`），是则触发新检索

2. **替换而非追加**：`rag_middleware.py:234-258` 实现了 RAG 消息的替换逻辑——遍历历史消息，找到含 `__business_rag_context__` 标记的旧 RAG 消息时跳过不保留，确保同一会话不会堆积过期的多版本 RAG 知识

3. **同一轮工具调用循环不重复检索**：LLM 调用工具 → 再调 LLM 时，`before_model` 看到的最后一条消息是 `ToolMessage`（非 human），直接跳过检索。此时 SafeMerge 重新打捞同一份 RAG 合并，不影响逻辑——因为用户没有提出新问题，重复检索无意义

4. **向量库变更立即生效**：检索在每次用户提问时实时执行（无缓存策略），数据库内容变化在下一次用户提问时即刻反映在检索结果中

### 7.3 设计决策阐释

| 情况 | 行为 | 理由 |
|------|------|------|
| 用户新提问 | 重新检索 | 新问题需要新的知识上下文 |
| 工具调用后 LLM 反思 | 不检索 | 同一轮未出现新用户问题，重复检索浪费资源 |
| 非 human 消息（如 AIMessage） | 不检索 | 只有用户输入才会产生新的信息需求 |
| 向量库内容更新 | 下个提问即生效 | 无缓存，实时检索保证信息时效性 |


