## MODIFIED Requirements
### Requirement: Milvus RAG Embedding Model
The system SHALL use a locally deployed `qwen3-embedding:0.6b` via Ollama for all dense embeddings within the Milvus hybrid search backend.

#### Scenario: Generate embeddings for Milvus
- **WHEN** a document chunk or user query is ingested into the Milvus vector store
- **THEN** it is embedded using the local `qwen3-embedding:0.6b` model without making external API calls to NVIDIA.

### Requirement: PGVector RAG Embedding Model
The system SHALL retain the use of `baai/bge-m3` for the PGVector backend purely for dense vector retrieval. (No changes in behavior, listed for clarity relative to Milvus).

#### Scenario: Generate embeddings for PGVector
- **WHEN** a document chunk or user query is ingested into the PGVector store
- **THEN** it is embedded using the `baai/bge-m3` model via existing HuggingFace/local integration.
