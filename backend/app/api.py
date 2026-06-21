# backend/app/api.py
import asyncio
import json
import logging
from contextlib import suppress
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Any, List

logger = logging.getLogger(__name__)

from .database import get_db
from .crud import (
    # Session CRUD
    create_session,
    get_session,
    get_sessions,
    update_session,
    delete_session,
    # Message CRUD
    create_message,
    get_message,
    get_messages_by_session,
    delete_message,
    delete_messages_by_session,
)
from .schemas import (
    # Session Schemas
    ChatRequest,
    ChatResponse,
    ChartArtifactResponse,
    serialize_chat_stream_event,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    # Message Schemas
    MessageCreate,
    MessageResponse,
)
from . import crud
from .chart_artifacts import get_chart_record
from .export_files import get_export_record

from .services import get_agent_service  # FastAPI 兼容层，内部复用 Agent V2 核心服务
from backend.app.skills.registry import get_domain_skills, list_scenarios_by_skill, reload_skills

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _encode_sse(event: Any) -> str:
    """编码 SSE data 行。"""
    serialized_event = serialize_chat_stream_event(event)
    return f"data: {json.dumps(serialized_event, ensure_ascii=False)}\n\n"


@router.get("/skills")
def get_skills_endpoint():
    """获取所有已注册的领域和场景技能
    
    修改时间: 2026-05-15
    修改内容: 
    - 移除硬编码，改由各领域 meta.py 和场景 scenario.py 统一管理展示文案
    - 优先读取 title 和 example_questions 字段
    """
    skills_list = []
    domain_skills = get_domain_skills()
    for domain_name, domain_info in domain_skills.items():
        skills_list.append({
            "name": domain_name,
            # 优先使用 meta.py 中的 title，缺省则回退到格式化名称
            "title": domain_info.get("title") or domain_name.replace("_", " ").title(),
            "description": domain_info["description"],
            "scenarios": [
                {
                    "name": s["name"],
                    "title": s.get("title", s["name"]),
                    "description": s.get("description", ""),
                    # 优先使用 scenario.py 中的 example_questions，缺省则回退到 triggers
                    "questions": s.get("example_questions") or s.get("triggers", [])[:3]
                }
                for s in list_scenarios_by_skill(domain_name)
            ]
        })
    return skills_list

@router.post("/skills/reload")
def reload_skills_endpoint():
    """热重载全部技能"""
    success = reload_skills()
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reload skills. Check syntax in skill files.")
    return {"message": "Skills reloaded successfully"}


# ==================== 数据字典维度表 API ====================
from sqlalchemy import create_engine, text

from .agent.utils.sql_database import build_postgres_search_path_engine_args
from .config import settings


_analytics_engine = None


def _get_analytics_engine():
    """懒加载 analytics 数据库 engine，后续请求复用连接池。"""
    global _analytics_engine
    if _analytics_engine is None:
        url = (settings.analytics_database_url or "").strip()
        if not url:
            return None
        engine_args = build_postgres_search_path_engine_args(
            settings.analytics_db_search_path
        )
        _analytics_engine = create_engine(url, pool_pre_ping=True, **engine_args)
    return _analytics_engine


def init_analytics_engine():
    """应用启动时预热 analytics 连接池，避免首次用户请求等待建连。"""
    engine = _get_analytics_engine()
    if engine is None:
        logger.info("ANALYTICS_DATABASE_URL 未配置，跳过 analytics 连接池预热")
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("analytics 数据库连接池预热完成")
    except Exception as exc:
        logger.warning("analytics 数据库连接池预热失败: %s", exc)


@router.get("/dimensions/{table_name}")
def get_dimension_table(table_name: str):
    """获取指定维度表全部数据，用于前端数据字典展示。

    修改时间: 2026-05-20
    修改内容:
    - 白名单从 .env DIMENSION_TABLES 配置读取（settings.dimension_tables）
    - 移除本地 Mock 降级，数据库未配置或连接失败直接返回错误便于排查
    - 懒加载 engine 复用连接池，避免每次请求新建 TCP 连接
    """
    whitelist = settings.dimension_tables
    if not whitelist:
        raise HTTPException(
            status_code=503,
            detail="Dimension tables whitelist is not configured (DIMENSION_TABLES)",
        )

    if table_name not in whitelist:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table_name}' is not in the dimension whitelist",
        )

    engine = _get_analytics_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Analytics database is not configured (ANALYTICS_DATABASE_URL)",
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM ods."{table_name}"')
            )
            all_columns = list(result.keys())
            # 剔除时间相关字段（如 created_at, updated_at），前端展示更紧凑
            _TIME_COL_PATTERNS = frozenset({"_at", "_time", "_date"})
            skip_indices = [
                i for i, col in enumerate(all_columns)
                if any(col.lower().endswith(p) for p in _TIME_COL_PATTERNS)
            ]
            columns = [
                col for i, col in enumerate(all_columns)
                if i not in skip_indices
            ]
            all_rows = [list(row) for row in result.fetchall()]
            rows = [
                [cell for i, cell in enumerate(row) if i not in skip_indices]
                for row in all_rows
            ]
            limit = settings.dimension_result_hard_limit or 300
            if len(rows) > limit:
                rows = rows[:limit]
            return {
                "table_name": table_name,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
    except Exception as exc:
        logger.error("维度表查询失败 table=%s: %s", table_name, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query dimension table '{table_name}': {exc}",
        )


# ==================== Session API ====================


@router.post(
    "/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
def create_session_endpoint(session: SessionCreate, db: Session = Depends(get_db)):
    """创建新会话"""
    db_session = create_session(db, session)
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": 0,
        "messages": []
    }


@router.get("/sessions", response_model=List[SessionResponse])
def get_sessions_endpoint(db: Session = Depends(get_db)):
    """获取所有会话"""
    sessions = get_sessions(db)
    # 添加消息数量 - 2025-01-01
    result = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
            "messages": []
        }
        result.append(session_dict)
    return result


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """根据ID获取会话"""
    db_session = get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": len(db_session.messages),
        "messages": []
    }


@router.put("/sessions/{session_id}", response_model=SessionResponse)
def update_session_endpoint(
    session_id: str, session_update: SessionUpdate, db: Session = Depends(get_db)
):
    """更新会话"""
    db_session = update_session(db, session_id, session_update)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": len(db_session.messages),
        "messages": []
    }


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """删除会话（级联删除关联的消息）"""
    success = delete_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return {"message": f"会话 {session_id} 已删除"}


# ==================== Message API ====================


@router.post(
    "/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def create_message_endpoint(message: MessageCreate, db: Session = Depends(get_db)):
    """创建新消息"""
    try:
        db_message = create_message(db, message)
        return db_message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/messages/{message_id}", response_model=MessageResponse)
def get_message_endpoint(message_id: str, db: Session = Depends(get_db)):
    """根据ID获取消息"""
    db_message = get_message(db, message_id)
    if not db_message:
        raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
    return db_message


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages_by_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """获取指定会话的所有消息"""
    # 检查会话是否存在
    db_session = get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    messages = get_messages_by_session(db, session_id)
    return messages


@router.delete("/messages/{message_id}")
def delete_message_endpoint(message_id: str, db: Session = Depends(get_db)):
    """删除消息"""
    success = delete_message(db, message_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
    return {"message": f"消息 {message_id} 已删除"}


@router.get("/files/{file_id}")
def download_export_file(file_id: str):
    """下载由 export_to_csv 生成的导出文件。

    修改时间: 2026-04-01 00:00 Asia/Shanghai
    修改内容:
    - 新增基于 file_id 的安全下载接口
    - 避免前端暴露服务器绝对路径
    """
    try:
        record = get_export_record(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="导出文件已过期，请重新导出") from exc

    return FileResponse(
        path=record["stored_path"],
        media_type=record.get("media_type", "application/octet-stream"),
        filename=record.get("filename") or file_id,
    )


@router.get("/charts/{chart_id}", response_model=ChartArtifactResponse)
def get_chart_artifact(chart_id: str):
    """读取图表 artifact，供前端按 chart_id 拉取完整图表配置。"""
    try:
        return get_chart_record(chart_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图表不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="图表已过期，请重新生成") from exc


# ====================== 消息处理 ======================


@router.post("/message", response_model=ChatResponse)
async def send_message(chat_request: ChatRequest, db: Session = Depends(get_db)):
    """发送消息（非流式）

    修改时间: 2026-03-29 22:35 Asia/Shanghai
    修改内容: 使用 PostgresSaver 自动管理历史，删除手动历史加载逻辑
    - Agent 执行失败时改为返回标准错误，不再伪装为成功 assistant 消息
    """
    logger.info("api.py - send_message - 用户发送非流式消息")
    logger.info(f"ChatRequest: {chat_request}")

    if chat_request.stream:
        raise HTTPException(
            status_code=400, detail="Use /stream endpoint for streaming"
        )

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    # ✅ 删除手动历史加载逻辑（PostgresSaver 自动管理）

    # 保存用户消息
    logger.info("保存用户消息到数据库")
    user_message = crud.create_message(
        db,
        MessageCreate(session_id=session_id, role="user", content=chat_request.message),
    )

    # ✅ 构建 config（thread_id 对应 session_id）并透传 enable_thinking
    config = {"configurable": {"thread_id": str(session_id)}}
    if chat_request.enable_thinking is not None:
        config["configurable"]["enable_thinking"] = chat_request.enable_thinking
    agent_service = get_agent_service()

    # 使用Agent处理消息
    logger.info("调用Agent处理消息（PostgresSaver 自动管理历史）")
    try:
        agent_response = await agent_service.process_message(
            chat_request.message,
            session_id,
            config
        )
    except Exception as exc:
        logger.error("非流式 Agent 处理失败: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Agent 处理失败，请稍后重试",
        ) from exc

    # 保存Assistant消息
    logger.info("保存Assistant消息到数据库")
    assistant_message = crud.create_message(
        db,
        MessageCreate(
            session_id=session_id,
            role="assistant",
            content=agent_response["content"],
            tool_calls=agent_response["tool_calls"],
            tool_results=agent_response["tool_results"],
        ),
    )
    logger.info("Assistant消息保存完成")
    return ChatResponse(
        session_id=session_id,
        message=assistant_message,
        is_complete=True,
        context_warning=agent_response.get("context_warning"),
    )


@router.post("/stream")
async def stream_message_post(
    chat_request: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """流式发送消息（POST方法）- 真正的流式处理

    修改时间: 2026-03-31 10:20 Asia/Shanghai
    修改内容:
    - 升级为结构化流式事件透传协议
    - 在 final/error 路径统一处理 assistant 消息落库
    - 保留 [DONE] 作为传输层结束标记，但不再作为业务成功判断依据
    - 新增客户端断开感知，尽量在 SSE 断连后停止继续生成
    - 2026-03-31 21:31 Asia/Shanghai: 对外发送前增加事件 schema 校验，统一 SSE 协议边界
    """
    logger.info("Received streaming chat request via POST")
    logger.info(f"ChatRequest: {chat_request}")

    if not chat_request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    # 检查会话是否存在
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_message = crud.create_message(
        db,
        MessageCreate(session_id=session_id, role="user", content=chat_request.message),
    )
    agent_service = get_agent_service()

    # ✅ 删除手动历史加载逻辑（PostgresSaver 自动管理）

    async def generate():
        logger.info("Starting real stream generation")
        logger.info(f"消息: {chat_request.message}")
        logger.info(f"会话ID: {session_id}")

        stream_iter = None
        next_event_task: asyncio.Task | None = None
        client_disconnected = False

        try:
            # ✅ 构建 config（thread_id 对应 session_id）并透传 enable_thinking
            config = {"configurable": {"thread_id": str(session_id)}}
            if chat_request.enable_thinking is not None:
                config["configurable"]["enable_thinking"] = chat_request.enable_thinking

            full_content = ""
            tool_calls_map: dict[str, dict[str, Any]] = {}
            tool_results_data: dict[str, Any] = {}
            assistant_persisted = False

            logger.info("开始调用agent_service.process_stream...")

            stream_iter = agent_service.process_stream(
                chat_request.message,
                session_id,
                config
            )

            next_event_task = asyncio.create_task(anext(stream_iter))

            while True:
                done, _ = await asyncio.wait(
                    {next_event_task},
                    timeout=0.25,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if next_event_task in done:
                    try:
                        event = next_event_task.result()
                    except StopAsyncIteration:
                        next_event_task = None
                        break

                    next_event_task = asyncio.create_task(anext(stream_iter))
                else:
                    if await request.is_disconnected():
                        client_disconnected = True
                        logger.info("检测到客户端已断开，停止 SSE 生成: session_id=%s", session_id)
                        if next_event_task is not None:
                            next_event_task.cancel()
                            with suppress(asyncio.CancelledError, StopAsyncIteration):
                                await next_event_task
                            next_event_task = None
                        break
                    continue

                event_type = event.get("type")

                if event_type == "interrupt":
                    questions = event.get("questions", [])
                    logger.info("[stream] generate 收到 interrupt: questions=%d, session_id=%s",
                                len(questions), session_id)
                    yield _encode_sse(event)
                    break

                if event_type == "token":
                    token_text = event.get("text", "")
                    if token_text:
                        full_content += token_text

                elif event_type == "tool_call":
                    tool_id = event.get("id")
                    if tool_id:
                        tool_calls_map[tool_id] = {
                            "id": tool_id,
                            "name": event.get("name", ""),
                            "args_text": event.get("args_text", ""),
                            "status": event.get("status", "streaming"),
                        }

                elif event_type == "tool_result":
                    tool_id = event.get("id")
                    if tool_id and event.get("content") is not None:
                        tool_results_data[tool_id] = event.get("content")

                elif event_type == "final":
                    final_content = event.get("content")
                    if final_content is not None:
                        full_content = final_content

                    final_tool_calls = event.get("tool_calls") or list(tool_calls_map.values()) or None
                    final_tool_results = event.get("tool_results") or tool_results_data or None
                    logger.info(
                        "收到最终事件，tool_calls=%d, tool_results=%d",
                        len(final_tool_calls or []),
                        len(final_tool_results or {}),
                    )

                    assistant_message = crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=full_content or "回答完成，但未生成可展示的文本内容。",
                            tool_calls=(
                                json.dumps(final_tool_calls, ensure_ascii=False)
                                if final_tool_calls
                                else None
                            ),
                            tool_results=(
                                json.dumps(final_tool_results, ensure_ascii=False)
                                if final_tool_results
                                else None
                            ),
                        ),
                    )
                    assistant_persisted = True
                    logger.info("Assistant消息保存成功，ID: %s", assistant_message.id)

                    final_event = {
                        **event,
                        "content": assistant_message.content,
                        "tool_calls": final_tool_calls,
                        "tool_results": final_tool_results,
                        "message_id": assistant_message.id,
                        "created_at": assistant_message.created_at.isoformat(),
                    }
                    yield _encode_sse(final_event)
                    continue

                elif event_type == "error":
                    error_message = event.get("message") or "流式处理失败"
                    if not assistant_persisted:
                        assistant_message = crud.create_message(
                            db,
                            MessageCreate(
                                session_id=session_id,
                                role="assistant",
                                content=error_message,
                            ),
                        )
                        assistant_persisted = True
                        event = {
                            **event,
                            "message_id": assistant_message.id,
                            "created_at": assistant_message.created_at.isoformat(),
                        }

                yield _encode_sse(event)

        except asyncio.CancelledError:
            logger.info("SSE 生成任务被取消: session_id=%s", session_id)
            raise
        except Exception as e:
            logger.error(f"流式处理异常: {e}", exc_info=True)
            assistant_message = crud.create_message(
                db,
                MessageCreate(
                    session_id=session_id,
                    role="assistant",
                    content=f"错误: {str(e)}",
                ),
            )
            error_data = {
                "type": "error",
                "message": f"错误: {str(e)}",
                "retryable": False,
                "message_id": assistant_message.id,
                "created_at": assistant_message.created_at.isoformat(),
            }
            yield _encode_sse(error_data)
        finally:
            if next_event_task is not None:
                next_event_task.cancel()
                with suppress(asyncio.CancelledError, StopAsyncIteration):
                    await next_event_task

            if stream_iter is not None:
                with suppress(Exception):
                    await stream_iter.aclose()

            # 仅在连接仍有效时发送结束标记
            if not client_disconnected:
                yield "data: [DONE]\n\n"
                logger.info("[stream] 流式响应结束, 准备发送 [DONE], session_id=%s, 已持久化=%s, client_disconnected=%s", session_id, assistant_persisted, client_disconnected)
            logger.info("[stream] 流式响应结束")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


class ResumeChatRequest(BaseModel):
    session_id: str
    answers: dict


@router.post("/resume")
async def stream_message_resume(
    chat_request: ResumeChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """恢复挂起的消息流（真正的流式处理）"""
    logger.info("Received resume chat request via POST")
    logger.info(f"ResumeChatRequest: {chat_request}")

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    agent_service = get_agent_service()

    async def generate():
        logger.info("Starting real resume stream generation")
        logger.info(f"会话ID: {session_id}")

        stream_iter = None
        next_event_task: asyncio.Task | None = None
        client_disconnected = False

        try:
            config = {"configurable": {"thread_id": str(session_id)}}

            full_content = ""
            tool_calls_map: dict[str, dict[str, Any]] = {}
            tool_results_data: dict[str, Any] = {}
            assistant_persisted = False

            logger.info("开始调用agent_service.process_stream_resume...")

            stream_iter = agent_service.process_stream_resume(
                session_id,
                chat_request.answers,
                config
            )

            next_event_task = asyncio.create_task(anext(stream_iter))

            while True:
                done, _ = await asyncio.wait(
                    {next_event_task},
                    timeout=0.25,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if next_event_task in done:
                    try:
                        event = next_event_task.result()
                    except StopAsyncIteration:
                        next_event_task = None
                        break

                    next_event_task = asyncio.create_task(anext(stream_iter))
                else:
                    if await request.is_disconnected():
                        client_disconnected = True
                        logger.info("检测到客户端已断开，停止 SSE 生成: session_id=%s", session_id)
                        if next_event_task is not None:
                            next_event_task.cancel()
                            with suppress(asyncio.CancelledError, StopAsyncIteration):
                                await next_event_task
                            next_event_task = None
                        break
                    continue

                event_type = event.get("type")

                if event_type == "interrupt":
                    questions = event.get("questions", [])
                    logger.info("[resume] generate 收到 interrupt: questions=%d, session_id=%s",
                                len(questions), session_id)
                    yield _encode_sse(event)
                    break

                if event_type == "token":
                    token_text = event.get("text", "")
                    if token_text:
                        full_content += token_text

                elif event_type == "tool_call":
                    tool_id = event.get("id")
                    if tool_id:
                        tool_calls_map[tool_id] = {
                            "id": tool_id,
                            "name": event.get("name", ""),
                            "args_text": event.get("args_text", ""),
                            "status": event.get("status", "streaming"),
                        }

                elif event_type == "tool_result":
                    tool_id = event.get("id")
                    if tool_id and event.get("content") is not None:
                        tool_results_data[tool_id] = event.get("content")

                elif event_type == "final":
                    final_content = event.get("content")
                    if final_content is not None:
                        full_content = final_content

                    final_tool_calls = event.get("tool_calls") or list(tool_calls_map.values()) or None
                    final_tool_results = event.get("tool_results") or tool_results_data or None
                    logger.info(
                        "收到恢复流的最终事件，tool_calls=%d, tool_results=%d",
                        len(final_tool_calls or []),
                        len(final_tool_results or {}),
                    )

                    assistant_message = crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=full_content or "回答完成，但未生成可展示的文本内容。",
                            tool_calls=(
                                json.dumps(final_tool_calls, ensure_ascii=False)
                                if final_tool_calls
                                else None
                            ),
                            tool_results=(
                                json.dumps(final_tool_results, ensure_ascii=False)
                                if final_tool_results
                                else None
                            ),
                        ),
                    )
                    assistant_persisted = True
                    logger.info("Assistant 消息在恢复流后保存成功，ID: %s", assistant_message.id)

                    final_event = {
                        **event,
                        "content": assistant_message.content,
                        "tool_calls": final_tool_calls,
                        "tool_results": final_tool_results,
                        "message_id": assistant_message.id,
                        "created_at": assistant_message.created_at.isoformat(),
                    }
                    yield _encode_sse(final_event)
                    continue

                elif event_type == "error":
                    error_message = event.get("message") or "恢复流式处理失败"
                    if not assistant_persisted:
                        assistant_message = crud.create_message(
                            db,
                            MessageCreate(
                                session_id=session_id,
                                role="assistant",
                                content=error_message,
                            ),
                        )
                        assistant_persisted = True
                        event = {
                            **event,
                            "message_id": assistant_message.id,
                            "created_at": assistant_message.created_at.isoformat(),
                        }

                yield _encode_sse(event)

        except asyncio.CancelledError:
            logger.info("SSE 恢复生成任务被取消: session_id=%s", session_id)
            raise
        except Exception as e:
            logger.error(f"恢复流式处理异常: {e}", exc_info=True)
            assistant_message = crud.create_message(
                db,
                MessageCreate(
                    session_id=session_id,
                    role="assistant",
                    content=f"错误: {str(e)}",
                ),
            )
            error_data = {
                "type": "error",
                "message": f"错误: {str(e)}",
                "retryable": False,
                "message_id": assistant_message.id,
                "created_at": assistant_message.created_at.isoformat(),
            }
            yield _encode_sse(error_data)
        finally:
            if next_event_task is not None:
                next_event_task.cancel()
                with suppress(asyncio.CancelledError, StopAsyncIteration):
                    await next_event_task

            if stream_iter is not None:
                with suppress(Exception):
                    await stream_iter.aclose()

            if not client_disconnected:
                yield "data: [DONE]\n\n"
            logger.info("[resume] 恢复流式响应结束, session_id=%s, 已持久化=%s, client_disconnected=%s", session_id, assistant_persisted, client_disconnected)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )

