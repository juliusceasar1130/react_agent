## MODIFIED Requirements
### Requirement: Milvus RAG Embedding Model
The system SHALL support locally deployed dense embedding providers for the Milvus hybrid search backend, with `ollama` and `llama.cpp` selectable through configuration, while ensuring ingestion and query use the same provider configuration.

#### Scenario: Generate embeddings for Milvus with Ollama
- **WHEN** `EMBEDDING_PROVIDER=ollama` and a document chunk or user query is embedded for the Milvus vector store
- **THEN** the system uses the local `qwen3-embedding:0.6b` model via Ollama without making external API calls to NVIDIA.

#### Scenario: Generate embeddings for Milvus with llama.cpp
- **WHEN** `EMBEDDING_PROVIDER=llama_cpp` and a document chunk or user query is embedded for the Milvus vector store
- **THEN** the system uses the local `Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0` model through the `llama.cpp` `/embedding` endpoint without making external API calls to NVIDIA.

#### Scenario: Apply Qwen instruction-aware query embedding
- **WHEN** `EMBEDDING_PROVIDER=llama_cpp` and query embedding is requested for Milvus retrieval
- **THEN** the query is formatted with the configured Qwen instruction template before it is sent to the embedding provider
- **AND** document ingestion text remains unchanged.

### Requirement: PGVector RAG Embedding Model
The system SHALL retain the use of `baai/bge-m3` for the PGVector backend purely for dense vector retrieval. (No changes in behavior, listed for clarity relative to Milvus).

#### Scenario: Generate embeddings for PGVector
- **WHEN** a document chunk or user query is ingested into the PGVector store
- **THEN** it is embedded using the `baai/bge-m3` model via existing HuggingFace/local integration.
