# 文件

- [数据模型与聊天持久化](data-model-and-persistence.md) - 聊天会话和消息的 SQLAlchemy 数据模型、双模式代理检查点持久化（PostgresSaver / AsyncPostgresSaver），以及支撑无损恢复的工件快照列。
- [RAG 与数据库词典检索](rag-and-lexicon.md) - 双后端检索（pgvector / Milvus 混合），支持可选 NVIDIA 重排序、三层数据库词典（表 DDL、去重列值、行实体）以及反馈驱动的黄金用例流水线。
- [技能与场景（领域知识层）](skills-and-scenarios.md) - 通过目录约定驱动发现领域技能与场景技能，并管理其注册表/重载；同时提供无需 LLM 的直接路径场景引擎（固定查询毫秒级响应），以及配套前端直通面板契约：executeScenarioApi 单独 60s 超时 + 独立竞态守卫。
