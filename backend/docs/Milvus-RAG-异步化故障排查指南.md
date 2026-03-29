# Milvus RAG 异步化故障排查指南

修改时间: 2026-03-27 20:55 Asia/Shanghai

主要修改内容:
- 总结本次 Milvus RAG 检索失败引出的故障排查路径
- 梳理同步/异步 checkpointer、LangGraph streaming、Milvus 延迟初始化之间的因果关系
- 沉淀最终修复方案与后续开发检查清单

---

## 1. 背景

本次问题不是单纯的 “Milvus 检索不到数据”，而是一次由流式链路改造引出的**运行时上下文问题**。

我们最初的目标是：

- 将本地 FastAPI 的流式输出升级为 LangGraph v2 结构化 streaming
- 使用 `messages / updates / custom` 多模式输出更好的前端体验

在改造过程中，先后暴露出：

1. 同步 `PostgresSaver` 与异步 `astream()` 不兼容
2. 为了止血回退到同步 `stream()` 后，Milvus lazy init 在线程池 worker 中触发
3. 线程池 worker 没有当前 event loop，导致 Milvus RAG 初始化失败

---

## 2. 故障现象

日志表面上看是这条错误：

```text
MilvusHybridRetriever: 事件循环错误，可能是延迟初始化时机问题:
There is no current event loop in thread 'ThreadPoolExecutor-1_4'
```

上层紧接着会看到：

```text
BusinessRagMiddleware: 未检索到符合条件的 Documentation 类型业务文档
BusinessRagMiddleware: 未检索到相关业务知识
```

这很容易误判成：

- Milvus 服务没启动
- collection 为空
- metadata filter 不匹配
- 用户问题本身无召回结果

但这次的真实情况并不是“查不到”，而是“**首次检索初始化失败后被降级为空结果**”。

---

## 3. 排查过程

### 3.1 第一步：确认不是前端问题

前端只是消费 SSE 事件。真正失败发生在后端：

- `/api/chat/stream`
- `agent_service.process_stream()`
- RAG middleware
- `MilvusHybridRetriever.retrieve()`

所以问题范围首先收敛到后端执行链路。

### 3.2 第二步：先发现的是 checkpointer 错误

流式切到：

```python
agent.astream(...)
```

但本地持久化还是：

```python
PostgresSaver
```

于是 LangGraph 在异步路径中调用：

```python
checkpointer.aget_tuple(...)
```

直接抛出：

```text
NotImplementedError
```

这个阶段的结论是：

- `astream()` 不能只切一半
- 如果 checkpointer 还是同步 `PostgresSaver`
- 就不能稳定走异步 graph 路径

### 3.3 第三步：同步止血后暴露 Milvus 问题

为了先恢复可用性，我们一度把流式回退到：

```python
agent.stream(...)
```

这样确实绕开了同步 saver 的 `aget_tuple()` 问题，但新的副作用出现了：

- 同步 graph 执行路径会使用线程池
- Milvus 检索器又是延迟初始化
- 首次 `retrieve()` 恰好在线程池 worker 里触发

于是报出：

```text
There is no current event loop in thread 'ThreadPoolExecutor-...'
```

### 3.4 第四步：确认不是 Milvus 服务本身坏了

排查时重点看了三类证据：

1. 工厂代码  
   `MilvusHybridRetriever` 是延迟初始化，不是在应用启动时连接 Milvus。

2. retriever 代码  
   真正连接 Milvus 和创建 `VectorStoreIndex` 是在第一次访问 `_lazy_store` / `_lazy_index` 时发生。

3. 异常处理代码  
   `retrieve()` 捕获异常后会记录日志并返回 `[]`，所以上层只会看到“未检索到相关业务知识”。

因此最终确认：

- 问题不是 Milvus 一定挂了
- 而是 lazy init 的执行上下文不对

---

## 4. 根因分析

### 4.1 根因不是单点，而是一条因果链

这次故障真正的链路是：

```text
同步 PostgresSaver
-> 无法安全使用 astream()
-> 为兼容而回退到 stream()
-> LangGraph 同步执行路径使用 ThreadPoolExecutor
-> Milvus 首次 lazy init 落在线程池 worker
-> worker 默认没有 current event loop
-> Milvus / LlamaIndex 初始化失败
-> retriever 降级返回空结果
-> 上层误以为“没有检索到业务知识”
```

### 4.2 容易误解的一点

**不是 `PostgresSaver` 直接把 Milvus 弄坏了。**

更准确地说：

- 同步 `PostgresSaver` 本身没问题
- 但它迫使本地流式执行回退到同步路径
- 同步路径改变了 Milvus lazy init 的运行线程
- 这才间接触发了 event loop 错误

### 4.3 ThreadPoolExecutor 线程为什么会报错

`ThreadPoolExecutor` 的工作线程不是“不允许”有 event loop，而是**默认没有**。

所以当某段初始化逻辑依赖：

```python
asyncio.get_running_loop()
```

或依赖当前线程已有 event loop 的第三方库时，在 worker 线程里就可能失败。

---

## 5. 最终解决方案

### 5.1 方案对比

曾评估过三种方案：

1. 在线程池 worker 里临时补 event loop  
   缺点是补洞式修复，后续维护风险高。

2. 保留同步 `stream()`，并把 Milvus 改成启动期预热  
   可以避开当前问题，但会把本地 FastAPI 链路长期留在 sync/sync 混合状态。

3. 本地 FastAPI 全链路切回 async  
   让 `AsyncPostgresSaver`、`ainvoke()/astream()`、Milvus lazy init 的执行上下文重新一致。

最终采用的是第 3 种。

### 5.2 落地方案

最终修复包含四个关键点：

1. 本地 checkpointer 从同步 `PostgresSaver` 改为：

```python
AsyncConnectionPool + AsyncPostgresSaver
```

2. FastAPI 兼容层从：

```python
agent.invoke()
agent.stream()
```

切回：

```python
await agent.ainvoke()
async for chunk in agent.astream(...)
```

3. 去掉 `services.py` 中模块导入时 eager 初始化全局 `agent_service` 的方式，改为：

- `initialize_agent_service()`
- `get_agent_service()`
- `shutdown_agent_service()`

并在 FastAPI `lifespan` 中显式管理 startup / shutdown。

4. 保留 Milvus 的 lazy init，不做线程内 event loop 兜底，也不改成启动期预热。

### 5.3 为什么这个方案有效

切回 async 后：

- checkpointer 与 graph 执行方式一致
- 本地流式执行不再需要回退到线程池主导的同步路径
- Milvus 首次 lazy init 更自然地发生在已有 event loop 的 async 请求上下文中

这就同时消除了：

- `aget_tuple -> NotImplementedError`
- `ThreadPoolExecutor -> no current event loop`

---

## 6. 经验总结

### 6.1 经验一：不要把“流式协议升级”和“运行时模型切换”分开看

表面上你只是在改 SSE 或 token streaming，实际上只要动到：

- `stream()/astream()`
- checkpointer
- middleware/tool 执行上下文

就已经是在改运行时架构了。

### 6.2 经验二：同步/异步组件要成套切换

下面这种组合风险很高：

- 同步 saver + 异步 graph
- 异步 saver + 同步 graph
- lazy init + 线程池 worker + 依赖 event loop 的初始化

更稳的原则是：

> **持久化方式、graph 调用方式、资源生命周期管理，尽量保持同一套 async/sync 模型。**

### 6.3 经验三：看到“未检索到结果”时先排除初始化失败

尤其在 retriever 有降级逻辑时：

- “空结果”不一定代表召回失败
- 也可能是初始化失败、连接失败、上下文错误后被吞掉了

排查时要先看：

- 是否有更早的异常日志
- retriever 是否做了 `except -> return []`
- 首次初始化是否发生在意料之外的线程或上下文里

### 6.4 经验四：模块导入时 eager 初始化不适合 async 资源

凡是需要：

- `AsyncConnectionPool`
- async checkpointer
- startup/shutdown 显式关闭

这类资源都不应在模块导入阶段直接创建。

更推荐：

- app startup 初始化
- app shutdown 回收
- 通过 getter 读取已初始化实例

---

## 7. 后续开发检查清单

以后如果再遇到类似问题，可以先按这个顺序检查：

1. 当前是 `stream()` 还是 `astream()`？
2. 当前 checkpointer 是同步还是异步？
3. 是否存在模块导入时 eager 初始化？
4. 首次 lazy init 是在主 async 请求上下文触发，还是在线程池 worker 中触发？
5. retriever/tool 是否把异常吞掉并返回空结果？
6. 上层看到的是“真空结果”，还是“初始化失败后的降级结果”？

---

## 8. 一句话结论

这次 Milvus RAG 失败，本质上不是“Milvus 查不到”，而是：

> **同步 `PostgresSaver` 迫使本地流式执行回退到同步路径，进而让 Milvus 的延迟初始化在线程池 worker 中触发，最终因为缺少 event loop 而失败。**

最终正确修复不是在线程池里补 loop，而是：

> **把本地 FastAPI 持久化、graph 执行和生命周期管理整体切回 async。**
