import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

import requests
from core.dependencies import get_db, logger
from core.permission import get_current_user
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session

from core.models import AgentSession

router = APIRouter(prefix="/agent", tags=["AI助手"])

# configuration
MAX_ROWS = 500
DEFAULT_LIMIT = 100
FORBIDDEN_TABLES = {"users", "messages"}

# load .env from backend folder if present
_base_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _base_dir / '.env'
if _dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=str(_dotenv_path))
else:
    from dotenv import load_dotenv

    load_dotenv()
# default session title prefix
DEFAULT_TITLE_PREFIX = '任务 '

def _env_any(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def _mask(v: Optional[str]):
    if not v:
        return None
    if len(v) <= 8:
        return '****'
    return v[:4] + '...' + v[-4:]


# OpenAI configuration (previously DeepSeek)
OPENAI_API_KEY = _env_any("OPENAI_API_KEY", "OPENAI_KEY", "OPENAI")
OPENAI_BASE_URL = _env_any("OPENAI_BASE_URL", "OPENAI_BASE", "OPENAI_URL") or None
# default model
DEFAULT_MODEL = os.environ.get("CHATGPT_MODEL", "gpt-4o")
# allow passing a one-time key in request for debugging when enabled
DEBUG_ALLOW_TEMP_KEY = os.environ.get('DEBUG_ALLOW_TEMP_KEY', '').lower() in ('1', 'true', 'yes')

logger.info(f"OpenAI configured: {bool(OPENAI_API_KEY)}; base_url={OPENAI_BASE_URL}; debug_temp_key={DEBUG_ALLOW_TEMP_KEY}")


def _default_session_title() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return f"{DEFAULT_TITLE_PREFIX}{ts}"


def _normalize_title_input(title: Optional[str]) -> Optional[str]:
    if not isinstance(title, str):
        return None
    cleaned = title.strip()
    if not cleaned or cleaned == '新对话':
        return None
    return cleaned


def _summary_title_from_text(text: str, limit: int = 24) -> Optional[str]:
    if not isinstance(text, str):
        return None
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None
    return cleaned[:limit] + ('…' if len(cleaned) > limit else '')


def _get_or_create_latest_session(db: Session, user) -> AgentSession:
    sess = (
        db.query(AgentSession)
        .filter_by(user_id=user.id)
        .order_by(AgentSession.id.desc())
        .first()
    )
    if sess is None:
        sess = AgentSession(
            user_id=user.id,
            title=_default_session_title(),
            status='pending',
            metadata_={},
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)
    return sess


@router.get('')
async def get_session_summary(session_id: Optional[int] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)) -> Dict:
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')
    if session_id:
        sess = db.query(AgentSession).filter_by(id=int(session_id), user_id=user.id).first()
        if not sess:
            raise HTTPException(status_code=404, detail='任务会话不存在')
        return {
            'id': sess.id,
            'title': sess.title,
            'status': sess.status,
            'created_at': sess.created_at,
            'updated_at': sess.updated_at,
            'metadata': sess.metadata_,
            'final_result': sess.final_result,
        }
    sessions = db.query(AgentSession).filter_by(user_id=user.id).order_by(AgentSession.id.desc()).all()
    return {
        'sessions': [
            {
                'id': s.id,
                'title': s.title,
                'created_at': s.created_at,
                'updated_at': s.updated_at,
                'status': s.status,
                'final_result': s.final_result,
            }
            for s in sessions
        ]
    }


# OpenAI call helper
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _call_openai(prompt: str, model_id: str, max_tokens: int = 1024, temperature: float = 0.2,
                 api_key: Optional[str] = None) -> str:
    """Call OpenAI-compatible chat completions endpoint and return assistant text.
    Uses api_key override if provided (and DEBUG_ALLOW_TEMP_KEY is true).
    Tries SDK first, falls back to HTTP and supports several provider response shapes.
    """
    use_key = api_key or OPENAI_API_KEY
    if not use_key:
        logger.warning(f"OpenAI API key not configured. OPENAI_API_KEY set? {bool(OPENAI_API_KEY)}")
        return ""

    def _extract_from_data(data):
        # robust extraction from various provider response shapes
        try:
            if not data:
                return ''
            if isinstance(data, dict):
                # try common OpenAI format first
                choices = data.get('choices') or []
                if choices and isinstance(choices, list):
                    first = choices[0]
                    # if first is simple string
                    if isinstance(first, str) and first.strip():
                        return first
                    if isinstance(first, dict):
                        # 1) choices[].message.content may be string
                        msg = first.get('message')
                        if isinstance(msg, dict):
                            cont = msg.get('content') or msg.get('contentText') or msg.get('text')
                            # content might be string
                            if isinstance(cont, str) and cont.strip():
                                return cont
                            # content might be a list of chunks/parts
                            if isinstance(cont, list) and cont:
                                # common: [{'type': 'output_text', 'text': '...'}]
                                parts_texts = []
                                for p in cont:
                                    if isinstance(p, str):
                                        parts_texts.append(p)
                                    elif isinstance(p, dict):
                                        # try standard keys
                                        if 'text' in p and isinstance(p['text'], str):
                                            parts_texts.append(p['text'])
                                        elif 'content' in p and isinstance(p['content'], str):
                                            parts_texts.append(p['content'])
                                if parts_texts:
                                    return ''.join(parts_texts)
                            # sometimes content is dict with 'parts'
                            if isinstance(cont, dict):
                                parts = cont.get('parts') or cont.get('items')
                                if isinstance(parts, list) and parts:
                                    return ''.join([x for x in parts if isinstance(x, str)])
                        # 2) choices[].delta or choices[].text
                        # delta often used in streaming and may carry a 'content' or 'message' key
                        delta = first.get('delta') if isinstance(first, dict) else None
                        if isinstance(delta, dict):
                            # delta.message or delta.content
                            dmsg = delta.get('message') or delta.get('content')
                            if isinstance(dmsg, str) and dmsg.strip():
                                return dmsg
                            if isinstance(dmsg, dict):
                                # try parts etc
                                dcont = dmsg.get('content') or dmsg.get('parts')
                                if isinstance(dcont, str) and dcont.strip():
                                    return dcont
                                if isinstance(dcont, list) and dcont:
                                    return ''.join([x for x in dcont if isinstance(x, str)])
                        # 3) choices[].text (legacy completion API)
                        if 'text' in first and isinstance(first['text'], str) and first['text'].strip():
                            return first['text']
                        # 4) choices[].content
                        if 'content' in first:
                            c = first['content']
                            if isinstance(c, str) and c.strip():
                                return c
                            if isinstance(c, list) and c:
                                return ''.join([x for x in c if isinstance(x, str)])
                            if isinstance(c, dict):
                                parts = c.get('parts') or c.get('items')
                                if isinstance(parts, list) and parts:
                                    return ''.join([x for x in parts if isinstance(x, str)])
                # providers may return top-level fields
                for key in ('output', 'result', 'answer', 'response', 'text'):
                    v = data.get(key)
                    if isinstance(v, str) and v.strip():
                        return v
                    if isinstance(v, dict):
                        # try nested keys
                        for subk in ('content', 'text', 'parts'):
                            sv = v.get(subk)
                            if isinstance(sv, str) and sv.strip():
                                return sv
                            if isinstance(sv, list) and sv:
                                return ''.join([x for x in sv if isinstance(x, str)])
                # some providers embed messages in data['messages'] as a list
                msgs = data.get('messages') or data.get('message')
                if isinstance(msgs, list) and msgs:
                    firstm = msgs[0]
                    if isinstance(firstm, dict):
                        for subk in ('content', 'text'):
                            if subk in firstm and isinstance(firstm[subk], str) and firstm[subk].strip():
                                return firstm[subk]
                            if subk in firstm and isinstance(firstm[subk], list) and firstm[subk]:
                                return ''.join([x for x in firstm[subk] if isinstance(x, str)])
            # fallback: if it's a plain string
            if isinstance(data, str) and data.strip():
                return data
            if isinstance(data, list) and data:
                return ''.join([x for x in data if isinstance(x, str)])
        except Exception as e:
            logger.warning(f"_extract_from_data error: {e}")
        return ''

    # prefer official SDK if available
    if OpenAI is not None:
        try:
            client = OpenAI(api_key=use_key, base_url=OPENAI_BASE_URL) if OPENAI_BASE_URL else OpenAI(api_key=use_key)
            try:
                resp = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )
            except Exception as sdk_call_exc:
                # some providers or SDK versions may expose a different method; try responses.create as fallback
                logger.info(f"chat.completions.create failed: {sdk_call_exc}; trying responses.create")
                try:
                    resp = client.responses.create(
                        model=model_id,
                        input=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                except Exception as sdk_alt_exc:
                    logger.warning(f"OpenAI SDK alternate call failed: {sdk_alt_exc}")
                    resp = None

            if resp is not None:
                # attempt to normalize resp to dict-like for extraction
                data = None
                try:
                    # SDK objects sometimes allow .to_dict() or behave like dict
                    if hasattr(resp, 'to_dict'):
                        data = resp.to_dict()
                    elif isinstance(resp, dict):
                        data = resp
                    else:
                        # try serializing
                        import json as _json
                        try:
                            data = _json.loads(getattr(resp, 'text', '') or str(resp))
                        except Exception:
                            # as last resort, inspect repr
                            data = None
                except Exception:
                    data = None

                # if we have data, try extract
                if data:
                    extracted = _extract_from_data(data)
                    if extracted:
                        return extracted
                    # if not extracted, log for debugging
                    logger.info(f"OpenAI SDK returned data but extraction failed; data keys: {list(data.keys())}")
                else:
                    # resp might be simple; try to inspect attributes
                    try:
                        # try typical SDK attribute path
                        choices = getattr(resp, 'choices', None)
                        if choices and isinstance(choices, (list, tuple)):
                            first = choices[0]
                            # attempt to read message content
                            content = None
                            if hasattr(first, 'message'):
                                msg = getattr(first, 'message')
                                if isinstance(msg, dict):
                                    content = msg.get('content')
                                elif hasattr(msg, 'get'):
                                    content = msg.get('content')
                            if not content and hasattr(first, 'text'):
                                content = getattr(first, 'text')
                            if isinstance(content, str) and content.strip():
                                return content
                    except Exception:
                        pass
                    # as final fallback, try str(resp)
                    resp_text = str(resp)
                    if resp_text and resp_text.strip():
                        return resp_text
            # if SDK route didn't return usable text, continue to HTTP fallback below
        except Exception as e:
            logger.warning(f"OpenAI SDK request failed entirely: {e}")

    # fallback to raw HTTP (compatible with OpenAI-style endpoints)
    url = (OPENAI_BASE_URL.rstrip('/') if OPENAI_BASE_URL else 'https://api.openai.com') + '/v1/chat/completions'
    headers = {'Authorization': f'Bearer {use_key}', 'Content-Type': 'application/json'}
    payload = {'model': model_id, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens,
               'temperature': temperature, 'stream': False}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        logger.warning(f"OpenAI HTTP request failed: {e}")
        return ""

    # log status and body for debugging when things look wrong
    status = getattr(resp, 'status_code', None)
    body_text = None
    try:
        body_text = resp.text
    except Exception:
        body_text = None
    logger.info(f"OpenAI HTTP call status={status}")

    if status != 200:
        logger.warning(f"OpenAI call failed status={status}, body={body_text}")
        return ""

    try:
        data = resp.json()
    except Exception:
        # not JSON, but maybe text contains the answer
        if body_text:
            logger.info("OpenAI response not JSON, returning raw text")
            return body_text
        return ""

    # Try robust extraction from JSON data
    extracted = _extract_from_data(data)
    if extracted:
        return extracted

    # if nothing extracted, log a concise debug snapshot and return raw text as last resort
    try:
        # log top-level keys and a short preview of the body (no secrets)
        keys = list(data.keys()) if isinstance(data, dict) else None
        preview = None
        try:
            import json as _json
            preview = _json.dumps({k: data.get(k) for k in (keys or [])[:3]}, ensure_ascii=False)[:1000]
        except Exception:
            preview = str(data)[:1000]
        logger.warning(f"OpenAI returned JSON but couldn't extract assistant text. top_keys={keys}; preview={preview}")
    except Exception:
        logger.warning("OpenAI returned JSON but couldn't extract assistant text and couldn't stringify it")
    return body_text or ''


def _is_provider_available(temp_key: Optional[str] = None) -> bool:
    if OPENAI_API_KEY:
        return True
    if DEBUG_ALLOW_TEMP_KEY and temp_key:
        return True
    return False


@router.post('')
async def post_message(body: Dict[str, object] = Body(...), db: Session = Depends(get_db),
                       current_user: dict = Depends(get_current_user)) -> dict[str, bool | Any] | str:
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail='请求体必须为 JSON 对象')

    text_input = body.get('text')
    if not text_input:
        raise HTTPException(status_code=400, detail='text 字段不能为空')

    context_size = int(body.get('context_size', 12) or 12)
    model_id = str(body.get('model_id') or DEFAULT_MODEL)
    temp_openai_key = body.get('temp_openai_key') if isinstance(body.get('temp_openai_key'), str) else None

    # availability check
    if not _is_provider_available(temp_openai_key):
        logger.warning(f"No OpenAI provider configured (requested model: {model_id})")
        raise HTTPException(status_code=503, detail='模型服务未配置或不可用，请检查后端环境变量（OPENAI_API_KEY）')

    # choose/create session container
    session_id_input = body.get('session_id')
    title = _normalize_title_input(body.get('title'))

    if session_id_input is not None:
        try:
            sid = int(str(session_id_input))
            session = db.query(AgentSession).filter_by(id=sid, user_id=user.id).first()
            if not session:
                raise HTTPException(status_code=404, detail='任务会话不存在')
        except ValueError:
            raise HTTPException(status_code=400, detail='session_id 必须是整数')
    else:
        session = _get_or_create_latest_session(db, user)
        if title:
            session.title = title
            db.commit()

    # save user message
    history = session.metadata_ or {}
    transcripts = history.get('messages', [])
    transcripts.append({'role': 'user', 'content': str(text_input), 'created_at': datetime.now(timezone.utc).isoformat()})
    history['messages'] = transcripts[-context_size:]
    session.metadata_ = history
    db.commit()

    context = "\n".join([f"{m['role']}: {m['content']}" for m in history.get('messages', [])])
    prompt = f"\n用户问题: {text_input}\n\n对话上下文:\n{context}\n\n请基于上述对话内容直接回答用户的问题。"

    # call OpenAI (use temp key if provided and allowed)
    if temp_openai_key and DEBUG_ALLOW_TEMP_KEY:
        assistant_text = _call_openai(prompt, model_id, api_key=str(temp_openai_key))
    else:
        assistant_text = _call_openai(prompt, model_id)

    assistant_text = assistant_text or "抱歉，模型服务未配置或调用失败，无法生成答案。"

    transcripts = history.get('messages', [])
    transcripts.append({'role': 'assistant', 'content': assistant_text, 'created_at': datetime.now(timezone.utc).isoformat()})
    history['messages'] = transcripts[-context_size:]
    session.metadata_ = history
    session.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"提示词: {prompt}")
    logger.info(f"回答: {assistant_text}")
    return assistant_text


@router.delete('')
async def clear_session(session_id: Optional[int] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)) -> Dict:
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')
    if session_id:
        session = db.query(AgentSession).filter_by(id=int(session_id), user_id=user.id).first()
    else:
        session = (
            db.query(AgentSession)
            .filter_by(user_id=user.id)
            .order_by(AgentSession.id.desc())
            .first()
        )
    if not session:
        return {'status': 'success', 'deleted': 0, 'message': '无任务会话'}
    try:
        db.delete(session)
        db.commit()
        return {'status': 'success', 'session_id': session.id}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail='删除任务失败')


@router.get('/status')
async def agent_status() -> Dict:
    return {
        'openai': {'configured': bool(OPENAI_API_KEY), 'base_url': OPENAI_BASE_URL or None,
            'masked_key': _mask(OPENAI_API_KEY)}, 'debug_allow_temp_key': DEBUG_ALLOW_TEMP_KEY,
        'default_model': DEFAULT_MODEL}
