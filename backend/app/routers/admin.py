import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app import crud
from backend.app.schemas import MessageResponse, MessageApproveRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def process_collected_message_async(message_id: str):
    """后台异步执行过滤提取、LLM 意图预提炼并存入 refined_payload"""
    from backend.app.database import SessionLocal
    from backend.app.agent.vector.rule_extractor import DEFAULT_EXTRACTOR_PIPELINE
    from backend.app.agent.vector.llm_refiner import refine_sql_case_with_llm
    
    db = SessionLocal()
    try:
        payload = DEFAULT_EXTRACTOR_PIPELINE.process(message_id, db)
        if not payload:
            logger.warning("异步处理中止：Message %s 未通过规则过滤器管道拦截，自动移出队列", message_id)
            crud.update_message_feedback(db, message_id=message_id, feedback="none")
            return
            
        raw_query = payload["raw_user_query"]
        raw_sql = payload["extracted_sql"]
        domain = payload["domain"]
        
        llm_query, llm_sql = refine_sql_case_with_llm(raw_query, raw_sql)
        
        refined_json = json.dumps({
            "rewritten_query": llm_query,
            "desensitized_sql": llm_sql,
            "domain": domain
        }, ensure_ascii=False)
        
        crud.update_message_refined_payload(db, message_id=message_id, payload=refined_json)
        logger.info("预提纯成功，草稿已存入 refined_payload: msg_id=%s", message_id)
        
    except Exception as e:
        logger.error("异步提炼处理发生未捕获异常：message_id=%s, err=%s", message_id, e)
    finally:
        db.close()


@router.post("/admin/messages/{message_id}/approve")
def approve_message_endpoint(
    message_id: str,
    req: MessageApproveRequest,
    db: Session = Depends(get_db)
):
    db_message = crud.get_message(db, message_id)
    if not db_message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    from backend.app.agent.vector.factory import add_document_to_store
    
    refined_data = {}
    if db_message.refined_payload:
        try:
            refined_data = json.loads(db_message.refined_payload)
        except Exception:
            pass
            
    final_query = req.custom_query or refined_data.get("rewritten_query")
    final_sql = req.custom_sql or refined_data.get("desensitized_sql")
    domain = refined_data.get("domain", "general")
    
    if not final_query or not final_sql:
        raise HTTPException(status_code=400, detail="缺少有效的 SQL 案例数据，且未完成预提炼")
        
    add_document_to_store(
        text=final_query,
        metadata={
            "type": "sql_example",
            "sql": final_sql,
            "domain": domain
        }
    )
    
    crud.update_message_feedback(db, message_id=message_id, feedback="approved")
    
    return {"status": "success", "message_id": message_id}


@router.get("/admin/messages/pending", response_model=List[MessageResponse])
def get_pending_messages_endpoint(db: Session = Depends(get_db)):
    """获取所有处于待审核 (collected) 状态的案例消息列表"""
    return crud.get_collected_messages(db)
