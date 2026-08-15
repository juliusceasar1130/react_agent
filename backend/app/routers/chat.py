import asyncio
import json
import logging
from contextlib import suppress
from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app import crud
from backend.app.crud import MessageCreate
from backend.app.schemas import (
    ChatRequest,
    ChatResponse,
    serialize_chat_stream_event,
)
from backend.app.services import get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _encode_sse(event: Any) -> str:
    """编码 SSE data 行。"""
    serialized_event = serialize_chat_stream_event(event)
    return f"data: {json.dumps(serialized_event, ensure_ascii=False)}\n\n"


@router.post("/message", response_model=ChatResponse)
async def send_message(chat_request: ChatRequest, db: Session = Depends(get_db)):
    """发送消息（非流式）

    修改时间: 2026-03-29 22:35 Asia/Shanghai
    修改内容: 使用 PostgresSaver 自动管理历史，删除手动历史加载逻辑
    - Agent 执行失败时改为返回标准错误，不再伪装为成功 assistant 消息
    """
    logger.info("routers/chat.py - send_message - 用户发送非流式消息")
    logger.info(f"ChatRequest: {chat_request}")

    if chat_request.stream:
        raise HTTPException(
            status_code=400, detail="Use /stream endpoint for streaming"
        )

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    # 保存用户消息
    logger.info("保存用户消息到数据库")
    user_message = crud.create_message(
        db,
        MessageCreate(session_id=session_id, role="user", content=chat_request.message),
    )

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
        crud.create_message(
            db,
            MessageCreate(
                session_id=session_id,
                role="assistant",
                content=f"错误: {str(exc)}",
            ),
        )
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

    async def generate():
        logger.info("Starting real stream generation")
        logger.info(f"消息: {chat_request.message}")
        logger.info(f"会话ID: {session_id}")

        stream_iter = None
        next_event_task: asyncio.Task | None = None
        client_disconnected = False

        try:
            config = {"configurable": {"thread_id": str(session_id)}}
            if chat_request.enable_thinking is not None:
                config["configurable"]["enable_thinking"] = chat_request.enable_thinking

            full_content = ""
            has_reasoning = False
            has_tool_artifact = False
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
                    questions_dump = []
                    question_texts = []
                    for q in questions:
                        q_dict = q.model_dump() if hasattr(q, "model_dump") else q
                        questions_dump.append(q_dict)
                        question_texts.append(f"- {q_dict.get('question')} (选项: {q_dict.get('options')})")
                    clarify_content = "我们需要您的进一步确认：\n" + "\n".join(question_texts)
                    
                    interrupt_tool_calls = list(tool_calls_map.values())
                    for tc in interrupt_tool_calls:
                        tc["status"] = "completed"
                    has_ask_user = any(tc.get("name") == "AskUserQuestion" for tc in interrupt_tool_calls)
                    if not has_ask_user:
                        interrupt_tool_calls.append({
                            "id": f"ask_user_{session_id}",
                            "name": "AskUserQuestion",
                            "args": {"questions": questions_dump},
                            "status": "completed"
                        })
                    
                    crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=clarify_content,
                            tool_calls=json.dumps(interrupt_tool_calls, ensure_ascii=False),
                            tool_results=json.dumps(tool_results_data, ensure_ascii=False) if tool_results_data else None
                        )
                    )
                    yield _encode_sse(event)
                    break

                if event_type == "reasoning":
                    has_reasoning = True

                if event_type in ("rag_context", "lexicon_context", "tool_artifact"):
                    if event_type == "tool_artifact":
                        has_tool_artifact = True
                    yield _encode_sse(event)
                    continue

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
                    if final_content and final_content.strip():
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
                            content=(
                                full_content
                                or (
                                    "（分析已完成，请查看上方思考过程与参考信息）"
                                    if (has_reasoning or has_tool_artifact)
                                    else "回答完成，但未生成可展示的文本内容。"
                                )
                            ),
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
                            subagents=(
                                json.dumps(event.get("subagents"), ensure_ascii=False)
                                if event.get("subagents")
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

            if client_disconnected and not assistant_persisted and (full_content or tool_calls_map):
                try:
                    crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=full_content or "流式生成中途由于客户端断开而被中止。",
                            tool_calls=(
                                json.dumps(list(tool_calls_map.values()), ensure_ascii=False)
                                if tool_calls_map
                                else None
                            ),
                            tool_results=(
                                json.dumps(tool_results_data, ensure_ascii=False)
                                if tool_results_data
                                else None
                            ),
                        ),
                    )
                    logger.info("已成功补存客户端断开时的部分消息回复")
                except Exception as persist_err:
                    logger.error(f"补存断开消息失败: {persist_err}")

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

    messages = crud.get_messages_by_session(db, session_id)
    ask_user_tool_call_id = None
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.tool_calls:
            try:
                tcs = json.loads(msg.tool_calls)
                for tc in tcs:
                    if tc.get("name") == "AskUserQuestion":
                        ask_user_tool_call_id = tc.get("id")
                        break
            except Exception:
                pass
        if ask_user_tool_call_id:
            break

    user_tool_results = None
    if ask_user_tool_call_id:
        user_tool_results = json.dumps({
            ask_user_tool_call_id: json.dumps(chat_request.answers, ensure_ascii=False)
        }, ensure_ascii=False)
    else:
        user_tool_results = json.dumps(chat_request.answers, ensure_ascii=False)

    user_answer_text = "; ".join([f"{k}: {v}" for k, v in chat_request.answers.items()])
    crud.create_message(
        db,
        MessageCreate(
            session_id=session_id,
            role="user",
            content=f"[澄清回答] {user_answer_text}",
            tool_results=user_tool_results
        )
    )

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
            has_reasoning = False
            has_tool_artifact = False
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
                    questions_dump = []
                    question_texts = []
                    for q in questions:
                        q_dict = q.model_dump() if hasattr(q, "model_dump") else q
                        questions_dump.append(q_dict)
                        question_texts.append(f"- {q_dict.get('question')} (选项: {q_dict.get('options')})")
                    clarify_content = "我们需要您的进一步确认：\n" + "\n".join(question_texts)
                    
                    interrupt_tool_calls = list(tool_calls_map.values())
                    for tc in interrupt_tool_calls:
                        tc["status"] = "completed"
                    has_ask_user = any(tc.get("name") == "AskUserQuestion" for tc in interrupt_tool_calls)
                    if not has_ask_user:
                        interrupt_tool_calls.append({
                            "id": f"ask_user_{session_id}",
                            "name": "AskUserQuestion",
                            "args": {"questions": questions_dump},
                            "status": "completed"
                        })
                    
                    crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=clarify_content,
                            tool_calls=json.dumps(interrupt_tool_calls, ensure_ascii=False),
                            tool_results=json.dumps(tool_results_data, ensure_ascii=False) if tool_results_data else None
                        )
                    )
                    yield _encode_sse(event)
                    break

                if event_type == "reasoning":
                    has_reasoning = True

                if event_type in ("rag_context", "lexicon_context", "tool_artifact"):
                    if event_type == "tool_artifact":
                        has_tool_artifact = True
                    yield _encode_sse(event)
                    continue

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
                    if tool_id and tool_id != ask_user_tool_call_id and event.get("content") is not None:
                        tool_results_data[tool_id] = event.get("content")

                elif event_type == "final":
                    final_content = event.get("content")
                    if final_content and final_content.strip():
                        full_content = final_content

                    final_tool_calls = event.get("tool_calls") or list(tool_calls_map.values()) or None
                    final_tool_results = event.get("tool_results") or tool_results_data or None
                    if final_tool_results and ask_user_tool_call_id:
                        if isinstance(final_tool_results, dict):
                            final_tool_results = dict(final_tool_results)
                            final_tool_results.pop(ask_user_tool_call_id, None)

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
                            content=(
                                full_content
                                or (
                                    "（分析已完成，请查看上方思考过程与参考信息）"
                                    if (has_reasoning or has_tool_artifact)
                                    else "回答完成，但未生成可展示的文本内容。"
                                )
                            ),
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
                            subagents=(
                                json.dumps(event.get("subagents"), ensure_ascii=False)
                                if event.get("subagents")
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

            if client_disconnected and not assistant_persisted and (full_content or tool_calls_map):
                try:
                    crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=full_content or "流式生成中途由于客户端断开而被中止。",
                            tool_calls=(
                                json.dumps(list(tool_calls_map.values()), ensure_ascii=False)
                                if tool_calls_map
                                else None
                            ),
                            tool_results=(
                                json.dumps(tool_results_data, ensure_ascii=False)
                                if tool_results_data
                                else None
                            ),
                        ),
                    )
                    logger.info("已成功补存客户端断开时的部分消息回复")
                except Exception as persist_err:
                    logger.error(f"补存断开消息失败: {persist_err}")

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
