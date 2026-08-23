# 文件

- [智能体系统提示词模板与加载器](agent-prompts.md) - 两个基于文件的系统提示词模板（主编排器提示词与 SQL 子智能体提示词）、带缓存/热重载的 SystemPromptLoader、MAIN_SYSTEM_PROMPT_PATH / SYSTEM_PROMPT_PATH 配置项，以及 main 与 subagent 的协作契约（路由、任务模板、两级澄清、无损呈现）。
- [代理服务与组装（SQLAgentService）](agent-service.md) - 说明主 DeepAgent 及其 SQL 子代理的组装方式：同步/异步双初始化路径、LLM 工厂、token 估算器、调用限制中间件，以及 FastAPI 生命周期包装器。
- [智能体中间件流水线](middleware-pipeline.md) - LangChain 智能体中间件：技能注入、单轮业务 RAG + 词表检索写入 Context API、上下文窗口告警、提示词编译器（系统消息合并）以及 RAG 提示词注入。
- [后端/前端架构概览](overview.md) - rearch_agent 的顶层视图：一个 FastAPI + DeepAgent（LangGraph）后端，协调主智能体与已编译的 SQL 领域子智能体、统一制品存储、RAG/词典检索，以及 Vue 3 流式聊天前端。
- [智能体状态与瞬态上下文（状态/上下文沙箱化）](state-and-context.md) - 两级智能体状态模型：为主智能体提供精简的全局 CustomState，为 SQL 子智能体提供沙箱化的 SqlSubAgentState，以及负责携带每轮 RAG/词表负载的 Context API（RequestContext），并保持零检查点膨胀。
- [SQL 域子智能体（sql_domain_agent）](subagent-sql.md) - 已编译的 SQL 专家子智能体：其工具工厂集合、被封装的 sql_db_query 守卫流水线、系统提示词，以及如何作为 CompiledSubAgent 打包给主 DeepAgent。
- [智能体工具与 SQL 安全层](tools-and-sql-linter.md) - SQL 子智能体的工具表面：包装后的 sql_db_query 保护管道、数据库词汇表工具，以及旁路通道图表/CSV 产物工具，外加两层 SQL 安全机制（正则表达式 + AST 检查器）。
