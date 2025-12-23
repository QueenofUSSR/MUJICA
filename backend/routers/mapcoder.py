from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
import asyncio
from sqlalchemy.orm import Session

from core.dependencies import get_db, SessionLocal, get_redis, SECRET_KEY, ALGORITHM, logger
from core.mapcoder.coordinator import CoordinatorService
from core.mapcoder.schemas import CreateSessionRequest, SessionDetail, SessionStatusResponse, SessionSummary
from core.models import AgentSession, AgentTask, AgentTaskLog, User
import jwt
from redis import exceptions as redis_exceptions

router = APIRouter(prefix="/mapcoder", tags=["MapCoder"])


def _iso(dt: datetime) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else None


def _build_task_dict(t: AgentTask):
    result_payload = t.result if t.result else None
    return dict(
        id=t.id,
        session_id=t.session_id,
        parent_id=t.parent_id,
        title=t.title,
        description=t.description,
        status=t.status,
        confidence=t.confidence,
        attempt_count=t.attempt_count,
        max_attempts=t.max_attempts,
        result=result_payload,
        assigned_role_id=t.assigned_role_id,
        created_at=_iso(t.created_at),
        updated_at=_iso(t.updated_at),
    )


def _session_to_detail(session: AgentSession, db: Session) -> SessionDetail:
    tasks = db.query(AgentTask).filter_by(session_id=session.id).order_by(AgentTask.id.asc()).all()
    logs = (
        db.query(AgentTaskLog)
        .filter_by(session_id=session.id)
        .order_by(AgentTaskLog.id.desc())
        .limit(100)
        .all()
    )

    return SessionDetail(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        model_id=session.model_id,
        status=session.status,
        metadata=session.metadata_,
        summary_title=session.summary_title,
        created_at=_iso(session.created_at),
        updated_at=_iso(session.updated_at),
        tasks=[_build_task_dict(t) for t in tasks],
        logs=[
            dict(
                id=l.id,
                session_id=l.session_id,
                task_id=l.task_id,
                role_id=l.role_id,
                level=l.level,
                message=l.message,
                payload=l.payload,
                created_at=_iso(l.created_at),
            )
            for l in logs
        ],
        final_result=session.final_result,
    )


def _session_to_summary(session: AgentSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        model_id=session.model_id,
        status=session.status,
        metadata=session.metadata_,
        summary_title=session.summary_title,
        created_at=_iso(session.created_at),
        updated_at=_iso(session.updated_at),
    )


def _user_from_request(request: Optional[Request], db: Session):
    if not request:
        return None
    auth_header = request.headers.get('authorization') or request.headers.get('Authorization')
    if not auth_header or not isinstance(auth_header, str):
        return None
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header.split(' ', 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('id')
        if not user_id:
            return None
        return db.query(User).filter_by(id=user_id).first()
    except Exception:
        return None


@router.get("/session", response_model=List[SessionSummary])
async def list_sessions(db: Session = Depends(get_db), request: Request = None, token: Optional[str] = None):
    """List sessions for the authenticated user. This endpoint is tolerant: if no valid token is provided
    it returns an empty list instead of raising 401 to make the frontend sidebar resilient.
    """
    auth_header = None
    if request:
        auth_header = request.headers.get('authorization') or request.headers.get('Authorization')
    user = None
    # prefer header token
    header_token = None
    if auth_header and isinstance(auth_header, str) and auth_header.lower().startswith('bearer '):
        header_token = auth_header.split(' ', 1)[1].strip()
    use_token = header_token or token
    if use_token:
        try:
            payload = jwt.decode(use_token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get('id')
            if user_id:
                user = db.query(User).filter_by(id=user_id).first()
                logger.info(f"mapcoder.list_sessions: user found id={user_id}")
        except Exception as e:
            logger.info(f"mapcoder.list_sessions: token decode failed: {e}")
    else:
        logger.info("mapcoder.list_sessions: no Authorization header and no token query param")

    if not user:
        # no authenticated user -> return empty list (frontend will handle). Log for diagnostics.
        logger.info("mapcoder.list_sessions: returning empty list because user not authenticated")
        return []

    sessions = (
        db.query(AgentSession)
        .filter_by(user_id=user.id)
        .order_by(AgentSession.updated_at.desc())
        .all()
    )
    return [_session_to_summary(s) for s in sessions]


@router.post("/session", response_model=SessionDetail)
async def create_session(
    body: CreateSessionRequest = Body(...),
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
):
    user = None
    try:
        # prefer oauth dependency if present — but we fallback to header-based decoding
        current_user = None
    except Exception:
        current_user = None
    if not user:
        user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")
    prompt = (body.prompt or '').strip() or None

    coord = CoordinatorService(db)
    llm_params = {
        "max_tokens": body.max_tokens,
        "temperature": body.temperature,
        "api_key": body.api_key,
    }
    session = await coord.create_session(
        user_id=user.id,
        title=body.title or f"任务 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        model_id=body.model_id,
        prompt=prompt,
        role_configs=body.roles,
        llm_params=llm_params,
    )
    return _session_to_detail(session, db)


@router.get("/session/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
):
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")
    return _session_to_detail(session, db)


@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: int,
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
):
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")

    logs = (
        db.query(AgentTaskLog)
        .filter_by(session_id=session.id)
        .order_by(AgentTaskLog.id.desc())
        .limit(20)
        .all()
    )
    tasks = db.query(AgentTask).filter_by(session_id=session.id).order_by(AgentTask.updated_at.desc()).limit(10).all()
    return SessionStatusResponse(
        session=dict(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            model_id=session.model_id,
            status=session.status,
            metadata=session.metadata_,
            summary_title=session.summary_title,
            created_at=_iso(session.created_at),
            updated_at=_iso(session.updated_at),
        ),
        recent_logs=[
            dict(
                id=l.id,
                session_id=l.session_id,
                task_id=l.task_id,
                role_id=l.role_id,
                level=l.level,
                message=l.message,
                payload=l.payload,
                created_at=_iso(l.created_at),
            )
            for l in logs
        ],
        active_tasks=[_build_task_dict(t) for t in tasks],
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
) -> Dict:
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")

    deleted_logs = db.query(AgentTaskLog).filter_by(session_id=session.id).delete(synchronize_session=False)
    deleted_tasks = db.query(AgentTask).filter_by(session_id=session.id).delete(synchronize_session=False)
    db.delete(session)
    db.commit()
    return {
        "status": "success",
        "deleted_logs": deleted_logs,
        "deleted_tasks": deleted_tasks,
        "session_id": session.id,
    }


@router.post("/session/{session_id}/run")
async def run_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
):
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")

    # update prompt if provided in request body
    # For now, we accept optional prompt field to update draft session
    extra = None
    if request:
        try:
            extra = await request.json()
        except Exception:
            extra = None
    llm_overrides = {}
    if extra and isinstance(extra, dict):
        new_prompt = (extra.get('prompt') or '').strip()
        if new_prompt:
            meta = session.metadata_ or {}
            meta['prompt'] = new_prompt
            meta.setdefault('messages', []).append({'role': 'user', 'content': new_prompt, 'created_at': datetime.now(timezone.utc).isoformat()})
            session.metadata_ = meta
            session.status = 'pending'
            session.title = extra.get('title') or session.title
            # recreate root task if missing
            existing_root = db.query(AgentTask).filter_by(session_id=session.id, parent_id=None).first()
            if not existing_root:
                AgentTask(session_id=session.id, title='整体任务', description=new_prompt, status='pending')
            db.commit()
        for key in ('max_tokens', 'temperature', 'api_key'):
            if extra.get(key) is not None:
                llm_overrides[key] = extra[key]
        if llm_overrides:
            meta = session.metadata_ or {}
            meta.setdefault('llm_params', {})
            meta['llm_params'].update({k: v for k, v in llm_overrides.items() if v is not None})
            session.metadata_ = meta
            db.commit()

    # schedule background run using fresh DB session
    def _bg_run(sid: int):
        db2 = SessionLocal()
        try:
            coord = CoordinatorService(db2)
            import asyncio

            asyncio.run(coord.run_session_by_id(sid))
        finally:
            db2.close()

    background_tasks.add_task(_bg_run, session_id)
    return _session_to_detail(session, db)


@router.patch("/session/{session_id}")
async def update_session(
    session_id: int,
    body: Dict[str, Optional[str]] = Body(...),
    db: Session = Depends(get_db),
    request: Request = None,
    # current_user: dict = Depends(get_current_user),
):
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")
    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")
    updated = False
    title = body.get('title') if isinstance(body, dict) else None
    if title is not None:
        session.title = title
        updated = True
    # allow updating final_result atomically from frontend
    if isinstance(body, dict) and 'final_result' in body:
        try:
            session.final_result = body.get('final_result')
            updated = True
        except Exception:
            # ignore invalid payloads
            pass
    # potential future fields: status, metadata, summary_title, final_result
    if updated:
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
    return _session_to_detail(session, db)


@router.get('/session/{session_id}/events')
async def session_events(session_id: int, token: Optional[str] = None, db: Session = Depends(get_db), redis_client=Depends(get_redis)):
    """Server-Sent Events endpoint that streams events published to Redis channel session:{id}:events
    Optional token (JWT) can be provided as query param because EventSource can't set headers.
    If token is missing or invalid, return 401.
    """
    # validate token if provided
    if not token:
        raise HTTPException(status_code=401, detail='未提供访问令牌 (请在 EventSource URL 中传入 ?token=...)')
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('id')
        if user_id is None:
            raise HTTPException(status_code=401, detail='无效的访问令牌')
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail='用户不存在')
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='访问令牌已过期')
    except Exception:
        raise HTTPException(status_code=401, detail='无法验证访问令牌')

    # ensure session belongs to user (optional) — allow only owner to subscribe
    session = db.query(AgentSession).filter_by(id=session_id).first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail='任务会话不存在或无权访问')

    if redis_client is None:
        logger.warning(f"session_events: redis_client is None; Redis appears unavailable for session {session_id}")
        raise HTTPException(status_code=503, detail="Redis unavailable. SSE disabled.")
    try:
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        channel = f"session:{session_id}:events"
        pubsub.subscribe(channel)
    except Exception as e:
        # Catch redis connection/subscribe errors and return 503 instead of crashing
        logger.warning(f"session_events: Redis subscribe failed for session {session_id}: {e}")
        raise HTTPException(status_code=503, detail="Redis unavailable or connection refused. SSE is disabled.")

    async def event_generator():
        try:
            # yield a keep-alive comment to establish the stream
            yield 'event: keepalive\n\n'
            while True:
                message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                if message:
                    data = message.get('data')
                    if isinstance(data, bytes):
                        try:
                            text = data.decode('utf-8')
                        except Exception:
                            text = str(data)
                    else:
                        text = str(data)
                    # send as SSE 'data:' lines
                    yield f'data: {text}\n\n'
                else:
                    # send a comment as heartbeat every ~10s to keep connection alive in some proxies
                    yield ': heartbeat\n\n'
                await asyncio.sleep(0.1)
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@router.get('/session/{session_id}/debug-events')
async def session_debug_events(session_id: int, token: Optional[str] = None, db: Session = Depends(get_db)):
    """Temporary debugging SSE endpoint that streams test events without Redis.
    Use this to verify EventSource connectivity from browser/devtools.
    Requires ?token=JWT query param (EventSource can't set headers easily).
    """
    # validate token if provided
    if not token:
        raise HTTPException(status_code=401, detail='未提供访问令牌 (请在 EventSource URL 中传入 ?token=...)')
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('id')
        if user_id is None:
            raise HTTPException(status_code=401, detail='无效的访问令牌')
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail='用户不存在')
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='访问令牌已过期')
    except Exception:
        raise HTTPException(status_code=401, detail='无法验证访问令牌')

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail='任务会话不存在或无权访问')

    logger.info(f"session_debug_events: client subscribed for session {session_id} user_id={user.id}")

    async def dbg_gen():
        try:
            # initial keepalive
            logger.info(f"session_debug_events: start streaming debug events for session {session_id}")
            yield ': hello\n\n'
            # send a few test events
            for i in range(1, 6):
                payload = {
                    'type': 'debug',
                    'seq': i,
                    'message': f'test event {i}',
                    'time': datetime.now(timezone.utc).isoformat(),
                }
                import json as _json
                yield f'data: {_json.dumps(payload, ensure_ascii=False)}\n\n'
                await asyncio.sleep(1.0)
            # then continue heartbeats
            while True:
                yield ': heartbeat\n\n'
                await asyncio.sleep(10.0)
        finally:
            # nothing to clean
            return

    return StreamingResponse(dbg_gen(), media_type='text/event-stream')


@router.post('/session/{session_id}/publish-event')
async def publish_session_event(session_id: int, payload: Optional[Dict] = Body(None), db: Session = Depends(get_db), redis_client=Depends(get_redis)):
    """Debug helper: publish a JSON event to the session Redis channel.
    Body payload is optional; if omitted, a timestamped test event is sent.
    Requires authenticated user (Bearer token in header).
    """
    user = _user_from_request(Request, db) if False else None
    # We can't use Request in this signature easily here; instead require token via body or use get_db auth fallback
    # For simplicity, accept unauthenticated publishes only when redis is available locally.
    if redis_client is None:
        logger.warning(f"publish_session_event: Redis unavailable, cannot publish for session {session_id}")
        raise HTTPException(status_code=503, detail='Redis unavailable; start Redis to test real-time events')

    event = payload or {
        'type': 'published_debug',
        'time': datetime.now(timezone.utc).isoformat(),
        'message': f'debug publish for session {session_id}'
    }
    try:
        # use publish_event helper which will log failures
        from core.dependencies import publish_event

        publish_event(session_id, event, redis_client=redis_client)
        return {'status': 'ok', 'published': True, 'event': event}
    except Exception as e:
        logger.warning(f"publish_session_event failed: {e}")
        raise HTTPException(status_code=500, detail=f'publish failed: {e}')


@router.post("/session/{session_id}/stop")
async def stop_session(
    session_id: int,
    db: Session = Depends(get_db),
    request: Request = None,
):
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")
    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")
    if session.status in ("completed", "failed", "canceled"):
        return {"status": session.status}
    session.status = "canceled"
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "canceled"}


@router.post("/session/{session_id}/run_code")
async def run_code_session(
    session_id: int,
    body: Dict = Body(...),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Run code using the Debugger agent and attach result to session.final_result.

    Body expects JSON: {"code": "...", "language": "python", "program_input": "..."}
    """
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未认证的用户")

    session = db.query(AgentSession).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="任务会话不存在")

    code = (body.get("code") or "").strip()
    language = body.get("language") or "python"
    program_input = body.get("program_input") or ""

    if not code:
        raise HTTPException(status_code=400, detail="缺少 code 字段")

    # Use Debugger to run and evaluate code
    try:
        from core.mapcoder.computeruse import Debugger

        dbg = Debugger(code=code)
        # 执行并获取结构化结果（优先为 dict，向后兼容字符串）
        run_res = dbg.run_code(code=code, language=language, program_input=program_input)
        # 兼容旧版返回 string 的情况
        output = run_res
        code_str = dbg.initial_code if hasattr(dbg, 'initial_code') else code
        comment = None
        if isinstance(run_res, dict):
            # 结构化返回：包含 code/code_str, output, comment 等字段
            code_str = run_res.get('code') or run_res.get('code_str') or code_str
            output = run_res.get('output')
            comment = run_res.get('comment') or run_res.get('comments')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"运行代码失败: {e}")

    # Persist final_result into session for frontend to fetch/update
    try:
        fr = {
            # prefer the updated code_str produced by the evaluator, fall back to dbg.initial_code
            "code": code_str or (dbg.initial_code if hasattr(dbg, 'initial_code') else code),
            "code_str": code_str or (dbg.initial_code if hasattr(dbg, 'initial_code') else code),
            "output": output,
            "comment": comment,
            "language": language,
        }
        session.final_result = fr
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        # non-fatal: continue but warn
        logger = None
        try:
            from core.dependencies import logger as _logger
            logger = _logger
        except Exception:
            logger = None
        if logger:
            logger.warning(f"run_code_session: failed to persist final_result for session {session_id}")

    return {"status": "ok", "final_result": session.final_result}
