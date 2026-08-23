# Files

- [Data Model & Chat Persistence](data-model-and-persistence.md) - The SQLAlchemy data model for chat sessions and messages, dual-mode agent checkpoint persistence (PostgresSaver / AsyncPostgresSaver), and the artifact snapshot columns that power lossless rehydration.
- [RAG & DB Lexicon Retrieval](rag-and-lexicon.md) - Dual-backend retrieval (pgvector / Milvus hybrid) with optional NVIDIA rerank, the three-layer database lexicon (table DDL, dedup column values, row entities), and the feedback-driven golden-case pipeline.
- [Skills & Scenarios (Domain Knowledge Layer)](skills-and-scenarios.md) - Directory-convention-driven discovery of domain skills and scenario skills, their registry/reload, and the LLM-free direct-path scenario engine that serves fixed queries in milliseconds.
