# 管理员审批、LLM 意图提炼与 Milvus 写入 (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现管理员审批接口、后台异步 LLM 意图提纯与 SQL 脱敏服务，以及通过 LlamaIndex 向 Milvus 向量库写入 Few-Shot SQL 黄金案例的完整功能。

**Architecture:**
1. **Admin API**: `POST /api/admin/messages/{message_id}/approve`
   - 参数支持可选的 `custom_query` 和 `custom_sql`（允许管理员编辑改写）。
   - 修改 `ChatMessage` 状态为 `'approved'`。
   - 使用 FastAPI `BackgroundTasks` 异步启动提炼入库流程。
2. **LLM Refiner Service** (`backend/app/agent/vector/llm_refiner.py`):
   - 基于 `get_llm()`，构造 Structured Prompt 进行**指代消解**和**SQL 敏感数据脱敏**。
   - 容错机制：当大模型提炼失败时，自动回退到规则提取器输出的原始文本和 SQL，保障流程不断。
3. **Milvus Document Writer** (`backend/app/agent/vector/factory.py`):
   - 开发 `add_document_to_store(text, metadata)` 适配器。
   - 内部加载 Milvus Hybrid 索引，插入 LlamaIndex `Document`。

**Tech Stack:** Python, LangChain, FastAPI, SQLAlchemy, LlamaIndex, Milvus.

---

### Task 1: 编写管理员审批接口及 Pydantic Schema 校验

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/api.py`
- Modify: `backend/app/test_api_persistence.py`

- [ ] **Step 1: 编写审批接口 API 单元测试**
  在 `test_api_persistence.py` 尾部追加测试用例：
  ```python
  def test_approve_message_endpoint():
      """测试管理员批准消息接口，修改状态并触发异步处理"""
      from unittest.mock import patch, MagicMock
      from fastapi.testclient import TestClient
      from backend.app.main import app
      
      # Mock 数据库查询返回 collected 状态的消息
      mock_msg = MagicMock()
      mock_msg.id = "msg-collected-1"
      mock_msg.feedback = "collected"
      
      # Mock crud 中的 get_message 与 update_message_feedback
      with patch("backend.app.api.crud.get_message", return_value=mock_msg), \
           patch("backend.app.api.crud.update_message_feedback") as mock_update_feedback, \
           patch("backend.app.api.process_collected_message_async") as mock_bg_task:
           
          client = TestClient(app)
          response = client.post(
              "/api/admin/messages/msg-collected-1/approve",
              json={"custom_query": "改写的问题", "custom_sql": "SELECT 1"}
          )
          
          assert response.status_code == 200
          assert response.json()["status"] == "processing"
          mock_update_feedback.assert_called_once_with(
              db=pytest.anyint or MagicMock(),
              message_id="msg-collected-1",
              feedback="approved"
          )
          mock_bg_task.assert_called_once()
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; python -m pytest backend/app/test_api_persistence.py -k "approve_message" -v`
  Expected: FAIL with `404 Not Found` or `422 Unprocessable Entity`

- [ ] **Step 3: 修改 schemas.py 新增审批 Request 模型**
  在 [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py) 中新增定义：
  ```python
  class MessageApproveRequest(BaseModel):
      custom_query: Optional[str] = None
      custom_sql: Optional[str] = None
  ```

- [ ] **Step 4: 修改 api.py 新增批准 API 端点及异步骨架**
  在 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 中编写审批路由并定义空实现函数 `process_collected_message_async`：
  ```python
  from backend.app.schemas import MessageApproveRequest
  from fastapi import BackgroundTasks

  def process_collected_message_async(
      message_id: str,
      custom_query: Optional[str] = None,
      custom_sql: Optional[str] = None
  ):
      """后台异步执行 LLM 提炼并写入 Milvus 向量库"""
      pass

  @router.post("/admin/messages/{message_id}/approve")
  def approve_message_endpoint(
      message_id: str,
      req: MessageApproveRequest,
      bg_tasks: BackgroundTasks,
      db: Session = Depends(get_db)
  ):
      db_message = crud.get_message(db, message_id)
      if not db_message:
          raise HTTPException(status_code=404, detail="Message not found")
          
      # 修改 feedback 状态为 approved 归档
      crud.update_message_feedback(db, message_id=message_id, feedback="approved")
      
      # 异步拉起 LLM 加工与向量库落库
      bg_tasks.add_task(
          process_collected_message_async,
          message_id=message_id,
          custom_query=req.custom_query,
          custom_sql=req.custom_sql
      )
      
      return {"status": "processing", "message_id": message_id}
  ```

- [ ] **Step 5: 运行测试验证通过**
  Run: `conda activate py312_agent; python -m pytest backend/app/test_api_persistence.py -k "approve_message" -v`
  Expected: PASS

---

### Task 2: 实现后台 LLM 提炼服务 (llm_refiner.py)

**Files:**
- Create: `backend/app/agent/vector/llm_refiner.py`
- Create: `backend/app/agent/vector/test_llm_refiner.py`

- [ ] **Step 1: 编写 LLM 提炼服务的单元测试**
  创建测试文件 [test_llm_refiner.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/test_llm_refiner.py) 写入测试用例：
  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from backend.app.agent.vector.llm_refiner import refine_sql_case_with_llm

  @patch("backend.app.agent.vector.llm_refiner.get_llm")
  def test_refine_sql_case_with_llm_success(mock_get_llm):
      """测试 LLM 成功解析意图并对 SQL 中的车身号/日期脱敏"""
      mock_llm_instance = MagicMock()
      # 模拟大模型返回符合 JSON 协议的字符串
      mock_llm_instance.invoke.return_value = MagicMock(content="""
      {
          "rewritten_query": "查询昨天二号线的出车数",
          "desensitized_sql": "SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = <日期>"
      }
      """)
      mock_get_llm.return_value = mock_llm_instance
      
      query = "查2号线的出车数 [澄清提问: 我们想和您确认哪天？ -> 澄清回答: 昨天]"
      sql = "SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = '2026-06-28'"
      
      res_query, res_sql = refine_sql_case_with_llm(query, sql)
      
      assert res_query == "查询昨天二号线的出车数"
      assert "<日期>" in res_sql
      assert "2026-06-28" not in res_sql
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; python -m pytest backend/app/agent/vector/test_llm_refiner.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.agent.vector.llm_refiner'`

- [ ] **Step 3: 实现 llm_refiner.py 提纯与脱敏逻辑**
  创建 [llm_refiner.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/llm_refiner.py)：
  ```python
  import json
  import logging
  from typing import Tuple, Optional
  from backend.app.agent.service import get_llm

  logger = logging.getLogger(__name__)

  def refine_sql_case_with_llm(
      raw_query: str,
      raw_sql: str
  ) -> Tuple[str, str]:
      """调用大模型进行意图改写（指代消解）和 SQL 脱敏参数化
      
      Returns:
          (rewritten_query, desensitized_sql)
      """
      prompt = f"""你是一个专业的 SQL 分析专家。你的任务是处理一个生产数据查询案例：
1. 用户的查询意图（可能在括号中带有澄清交互历史）。
2. 执行成功的 SQL。

你需要将数据提炼并输出为一个标准的 JSON 对象，包含以下两个字段：
- "rewritten_query": 改写后的用户查询，必须是一个语义完整、消解了指代关系、可以直接用于向量库语义检索的单句提问。
- "desensitized_sql": 脱敏后的 SQL。请将 SQL 中具体的字面值（例如特定日期、具体车身号、批次号等）用占位符替换（如 '<日期>', '<车身号>', '<产线ID>'）。严禁改变 SQL 的表名、列名、语法结构或任何 SQL 关键字。

输入案例：
User Query: {raw_query}
SQL: {raw_sql}

请直接返回合法的 JSON 对象，不要输出 Markdown 块或任何解释性文本。例如：
{{"rewritten_query": "查询昨天二产线的流挂车数", "desensitized_sql": "SELECT count(*) FROM paint_vehicle WHERE line_id = <产线ID> AND production_date = <日期>"}}
"""
      try:
          llm = get_llm()
          resp = llm.invoke(prompt)
          content = resp.content.strip()
          
          # 清洗 Markdown 的 ```json 包裹标记
          if content.startswith("```"):
              content = content.split("```")[1]
              if content.startswith("json"):
                  content = content[4:]
          content = content.strip("` \n")
          
          data = json.loads(content)
          rewritten_query = data.get("rewritten_query", raw_query)
          desensitized_sql = data.get("desensitized_sql", raw_sql)
          return rewritten_query, desensitized_sql
          
      except Exception as e:
          logger.error("LLM 提炼案例失败，将降级使用原始问题与原始 SQL。错误: %s", e)
          # 容错降级：返回原始文本与 SQL，确保业务闭环不中断
          return raw_query, raw_sql
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; python -m pytest backend/app/agent/vector/test_llm_refiner.py -v`
  Expected: PASS

---

### Task 3: 向量库写入适配层集成与异步任务编排

**Files:**
- Modify: `backend/app/agent/vector/factory.py`
- Modify: `backend/app/api.py`
- Modify: `backend/app/test_api_persistence.py`

- [ ] **Step 1: 在 factory.py 中实现 add_document_to_store 写入接口**
  修改 [factory.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/factory.py)，支持将 `sql_example` 类型的数据存入向量库：
  ```python
  def add_document_to_store(
      text: str,
      metadata: dict,
  ) -> None:
      """将提炼后的自然语言意图和 SQL 案例写入向量库"""
      rag_backend = (getattr(settings, "rag_backend", "pgvector") or "pgvector").strip().lower()
      
      if rag_backend == "milvus_hybrid":
          from llama_index.core import Document as LlamaIndexDocument
          from backend.app.agent.vector.embedding_provider import configure_llama_index_settings
          from backend.app.agent.vector.milvus_hybrid.milvus_store import (
              create_milvus_hybrid_store,
              create_milvus_hybrid_index,
          )
          
          configure_llama_index_settings(settings)
          
          uri = getattr(settings, "milvus_uri", "http://localhost:19530")
          collection_name = getattr(settings, "milvus_collection_name", "rag_store")
          embed_dim = getattr(settings, "milvus_embed_dim", 1024)
          rrf_k = getattr(settings, "milvus_rrf_k", 60)
          
          store = create_milvus_hybrid_store(
              uri=uri,
              collection_name=collection_name,
              embed_dim=embed_dim,
              rrf_k=rrf_k,
              overwrite=False,
          )
          index = create_milvus_hybrid_index(store)
          
          doc = LlamaIndexDocument(
              text=text,
              metadata=metadata,
          )
          index.insert(doc)
          logger.info("成功插入文档到 Milvus: text=%s, metadata=%s", text[:50], metadata)
      else:
          # pgvector 后端路径
          from backend.app.agent.vector.pgvector.vector_store import create_business_vector_store
          from langchain_core.documents import Document as LangChainDocument
          
          vector_store = create_business_vector_store(
              collection_name="rag_store",
              embedding_model="baai/bge-m3",
              pg_connection_string=settings.database_url,
          )
          vector_store.add_documents([LangChainDocument(page_content=text, metadata=metadata)])
          logger.info("成功插入文档到 PgVector: text=%s, metadata=%s", text[:50], metadata)
  ```

- [ ] **Step 2: 完善 api.py 中的异步处理流程**
  修改 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 中 `process_collected_message_async` 的具体实现：
  ```python
  def process_collected_message_async(
      message_id: str,
      custom_query: Optional[str] = None,
      custom_sql: Optional[str] = None
  ):
      """后台异步执行过滤提取、LLM 意图提炼与向量库入库"""
      from backend.app.database import SessionLocal
      from backend.app.agent.vector.rule_extractor import DEFAULT_EXTRACTOR_PIPELINE
      from backend.app.agent.vector.llm_refiner import refine_sql_case_with_llm
      from backend.app.agent.vector.factory import add_document_to_store
      
      db = SessionLocal()
      try:
          # 1. 运行过滤管道提取原始 query 和成功 SQL
          payload = DEFAULT_EXTRACTOR_PIPELINE.process(message_id, db)
          if not payload:
              logger.warning("异步处理中止：Message %s 未通过规则过滤器管道拦截", message_id)
              return
              
          raw_query = payload["raw_user_query"]
          raw_sql = payload["extracted_sql"]
          domain = payload["domain"]
          
          # 2. 如果管理员手动指定了修改，使用管理员改写的版本；否则通过 LLM 进行提纯脱敏
          final_query = custom_query if custom_query else None
          final_sql = custom_sql if custom_sql else None
          
          if not final_query or not final_sql:
              llm_query, llm_sql = refine_sql_case_with_llm(raw_query, raw_sql)
              final_query = final_query or llm_query
              final_sql = final_sql or llm_sql
              
          # 3. 构造元数据并安全写入向量数据库
          metadata = {
              "type": "sql_example",
              "sql": final_sql,
              "domain": domain
          }
          add_document_to_store(text=final_query, metadata=metadata)
          logger.info("异步提炼并入库成功：msg_id=%s, domain=%s", message_id, domain)
          
      except Exception as e:
          logger.error("异步提炼处理发生未捕获异常：message_id=%s, err=%s", message_id, e)
      finally:
          db.close()
  ```

- [ ] **Step 3: 编写端到端单元测试集成验证**
  在 `test_api_persistence.py` 尾部增加集成测试用例，校验提取 ➡️ 提纯 ➡️ 写入的完整流：
  ```python
  @patch("backend.app.api.add_document_to_store")
  @patch("backend.app.api.refine_sql_case_with_llm")
  def test_process_collected_message_async_integration(mock_refine, mock_add_doc):
      """测试异步提取、提纯并调用向量库写入的集成流程"""
      from backend.app.api import process_collected_message_async
      from unittest.mock import MagicMock, patch
      import json
      
      # Mock 数据库查询返回目标消息
      m_target = MagicMock()
      m_target.id = "m_target"
      m_target.session_id = "sess-1"
      m_target.tool_calls = json.dumps([
          {"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT * FROM users"}}
      ])
      m_target.tool_results = json.dumps({"sql-1": "[{'id': 1}]"})
      
      m_user = MagicMock()
      m_user.id = "m_user"
      m_user.role = "user"
      m_user.content = "查用户"
      
      # Mock 数据库拉取会话历史
      mock_history = [m_user, m_target]
      
      # Mock LLM 返回
      mock_refine.return_value = ("提炼的问题", "SELECT * FROM users")
      
      with patch("backend.app.api.crud.get_message", return_value=m_target), \
           patch("backend.app.agent.vector.rule_extractor.get_messages_by_session", return_value=mock_history):
           
           process_collected_message_async("m_target")
           
           # 断言 LLM 提炼被调用
           mock_refine.assert_called_once_with("查用户", "SELECT * FROM users")
           # 断言向量库写入被调用，且 metadata 的 type 为 sql_example
           mock_add_doc.assert_called_once_with(
               text="提炼的问题",
               metadata={
                   "type": "sql_example",
                   "sql": "SELECT * FROM users",
                   "domain": "general"
               }
           )
  ```

- [ ] **Step 4: 运行所有单元测试校验**
  Run: `conda activate py312_agent; python -m pytest backend/app/ -v`
  Expected: 所有 29 个测试（包含新添加的 2 个审批与异步集成测试）全部完美通过。

- [ ] **Step 5: 提交成果（此处记录任务完成状况，不自主进行 git commit）**
