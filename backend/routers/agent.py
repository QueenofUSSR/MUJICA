import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

import requests
from core.dependencies import get_db, logger
from core.models import AgentConversation, AgentMessage
from core.permission import get_current_user
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session

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
DEFAULT_TITLE_PREFIX = '对话 '

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


# DeepSeek configuration (only provider now)
DEEPSEEK_API_KEY = _env_any("DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "DEEPSEEK_KEY", "DEEPSEEK_TOKEN", "DEEPSEEK")
DEEPSEEK_BASE_URL = _env_any("DEEPSEEK_BASE_URL", "DEEPSEEK_BASE", "DEEPSEEK_URL",
                             "BASE_URL") or "https://api.deepseek.com"
# default model
DEFAULT_MODEL = os.environ.get("CHATGPT_MODEL", "deepseek-chat")
# allow passing a one-time key in request for debugging when enabled
DEBUG_ALLOW_TEMP_KEY = os.environ.get('DEBUG_ALLOW_TEMP_KEY', '').lower() in ('1', 'true', 'yes')

logger.info(
    f"DeepSeek configured: {bool(DEEPSEEK_API_KEY)}; base_url={DEEPSEEK_BASE_URL}; debug_temp_key={DEBUG_ALLOW_TEMP_KEY}")


def _default_conversation_title() -> str:
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


def _get_or_create_user_conversation(db: Session, user) -> AgentConversation:
    conv = db.query(AgentConversation).filter_by(user_id=user.id).order_by(AgentConversation.id.desc()).first()
    if conv is None:
        conv = AgentConversation(user_id=int(user.id), title=_default_conversation_title())
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


@router.get('')
async def get_conversation(conversation_id: Optional[int] = None, db: Session = Depends(get_db),
                           current_user: dict = Depends(get_current_user)) -> Dict:
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')

    if conversation_id:
        conv = db.query(AgentConversation).filter_by(id=int(conversation_id), user_id=user.id).first()
        if not conv:
            raise HTTPException(status_code=404, detail='对话不存在')
        msgs = db.query(AgentMessage).filter_by(conversation_id=conv.id).order_by(AgentMessage.id.asc()).all()
        return {"id": conv.id, "title": conv.title, "created_at": conv.created_at, "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "meta": m.meta, "created_at": m.created_at} for m in
            msgs]}

    convs = db.query(AgentConversation).filter_by(user_id=user.id).order_by(AgentConversation.id.desc()).all()
    conv_list = []
    for c in convs:
        last_msg = db.query(AgentMessage).filter_by(conversation_id=c.id).order_by(AgentMessage.id.desc()).first()
        conv_list.append({"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at,
                          "last_message": (last_msg.content if last_msg else None)})

    current = None
    if convs:
        latest = convs[0]
        msgs = db.query(AgentMessage).filter_by(conversation_id=latest.id).order_by(AgentMessage.id.asc()).all()
        current = {"id": latest.id, "title": latest.title, "created_at": latest.created_at, "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "meta": m.meta, "created_at": m.created_at} for m in
            msgs]}

    return {"conversations": conv_list, "current": current}


@router.post('/conversation')
async def create_conversation(body: Optional[Dict[str, object]] = Body(None), db: Session = Depends(get_db),
                              current_user: dict = Depends(get_current_user)) -> Dict:
    """Create a new empty conversation for the current user."""
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')

    raw_title = body.get('title') if isinstance(body, dict) else None
    title = _normalize_title_input(raw_title)

    conv = AgentConversation(user_id=int(user.id), title=title or _default_conversation_title())
    try:
        db.add(conv)
        db.commit()
        db.refresh(conv)
    except Exception as e:
        db.rollback()
        logger.error(f"create conversation failed: {e}")
        raise HTTPException(status_code=500, detail='创建对话失败')

    return {"conversation_id": conv.id,
        "conversation": {"id": conv.id, "title": conv.title, "created_at": conv.created_at,
            "updated_at": conv.updated_at}}


def _call_deepseek(prompt: str, model_id: str, max_tokens: int = 1024, temperature: float = 0.2,
                   api_key: Optional[str] = None) -> str:
    """Call DeepSeek HTTP chat completions endpoint and return assistant text.
    Uses api_key override if provided (and DEBUG_ALLOW_TEMP_KEY is true).
    """
    use_key = api_key or DEEPSEEK_API_KEY
    if not use_key or not DEEPSEEK_BASE_URL:
        logger.warning(
            f"DeepSeek API key or base URL not configured. key present? {bool(DEEPSEEK_API_KEY)}; base present? {bool(DEEPSEEK_BASE_URL)}")
        return ""

    url = DEEPSEEK_BASE_URL.rstrip('/') + '/v1/chat/completions'
    headers = {'Authorization': f'Bearer {use_key}', 'Content-Type': 'application/json'}
    payload = {'model': model_id, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens,
        'temperature': temperature, 'stream': False}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        logger.warning(f"DeepSeek HTTP request failed: {e}")
        return ""

    if resp.status_code != 200:
        logger.warning(f"DeepSeek call failed status={resp.status_code}, body={resp.text}")
        return ""

    try:
        data = resp.json()
    except Exception:
        return resp.text or ""

    choices = data.get('choices', []) if isinstance(data, dict) else []
    if not choices:
        return ""

    first = choices[0]
    # Support choices[0].message.content or choices[0].text
    msg = first.get('message') or {}
    if isinstance(msg, dict):
        return msg.get('content') or first.get('text') or ''
    return first.get('text') or ''


def _is_provider_available(temp_deepseek_key: Optional[str] = None) -> bool:
    if DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL:
        return True
    if DEBUG_ALLOW_TEMP_KEY and temp_deepseek_key:
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
    temp_deepseek_key = body.get('temp_deepseek_key') if isinstance(body.get('temp_deepseek_key'), str) else None

    # availability check
    if not _is_provider_available(temp_deepseek_key):
        logger.warning(f"No DeepSeek provider configured (requested model: {model_id})")
        raise HTTPException(status_code=503, detail='模型服务未配置或不可用，请检查后端环境变量（DEEPSEEK_API_KEY）')

    # choose/create conversation
    conv_id_in = body.get('conversation_id')
    new_conv_flag = bool(body.get('new_conversation', False))
    raw_title = body.get('title')
    title = _normalize_title_input(raw_title)

    if conv_id_in is not None:
        try:
            cid = int(str(conv_id_in))
            conv = db.query(AgentConversation).filter_by(id=cid, user_id=user.id).first()
            if not conv:
                raise HTTPException(status_code=404, detail='目标对话不存在或不属于当前用户')
        except ValueError:
            raise HTTPException(status_code=400, detail='conversation_id 必须是整数')
    else:
        if new_conv_flag:
            conv = AgentConversation(user_id=int(user.id), title=title or _default_conversation_title())
            try:
                db.add(conv)
                db.commit()
                db.refresh(conv)
            except Exception as e:
                db.rollback()
                logger.error(f"create conversation failed: {e}")
                raise HTTPException(status_code=500, detail='创建对话失败')
            if not text_input:
                return {"conversation_id": conv.id, "created": True}
        else:
            conv = _get_or_create_user_conversation(db, user)

    # save user message
    um = AgentMessage(conversation_id=int(conv.id), role='user', content=str(text_input), meta=None)
    try:
        db.add(um)
        db.commit()
        db.refresh(um)
    except Exception as e:
        db.rollback()
        logger.error(f"save user message failed: {e}")
        raise HTTPException(status_code=500, detail='保存消息失败')

    # prepare context and prompt
    msgs = db.query(AgentMessage).filter_by(conversation_id=conv.id).order_by(AgentMessage.id.asc()).all()
    recent_msgs = msgs[-context_size:] if context_size > 0 else []

    # Update conversation title based on first user message if still using default title
    if len(msgs) == 1 and (not conv.title or conv.title.startswith(DEFAULT_TITLE_PREFIX)):
        first_user_msg = next((m for m in msgs if m.role == 'user'), None)
        auto_title = _summary_title_from_text(first_user_msg.content) if first_user_msg else None
        if auto_title:
            conv.title = auto_title

    context = "\n".join([f"{m.role}: {m.content}" for m in recent_msgs])
    prompt = f"\n用户问题: {text_input}\n\n对话上下文:\n{context}\n\n请基于上述对话内容直接回答用户的问题，中文回答。"

    # call deepseek (use temp key if provided and allowed)
    if temp_deepseek_key and DEBUG_ALLOW_TEMP_KEY:
        assistant_text = _call_deepseek(prompt, model_id, api_key=str(temp_deepseek_key))
    else:
        assistant_text = _call_deepseek(prompt, model_id)

    assistant_text = assistant_text or "抱歉，模型服务未配置或调用失败，无法生成答案。"

    am = AgentMessage(conversation_id=int(conv.id), role='assistant', content=assistant_text, meta=None)
    try:
        db.add(am)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(am)
    except Exception as e:
        db.rollback()
        logger.error(f"save assistant message failed: {e}")

    logger.info(f"提示词: {prompt}")
    logger.info(f"回答: {assistant_text}")
    return assistant_text


@router.delete('')
async def clear_conversation(conversation_id: Optional[int] = None, db: Session = Depends(get_db),
                             current_user: dict = Depends(get_current_user)) -> Dict:
    user = current_user.get('user') if isinstance(current_user, dict) else None
    if not user:
        raise HTTPException(status_code=401, detail='未认证的用户')

    if conversation_id:
        conv = db.query(AgentConversation).filter_by(id=int(conversation_id), user_id=user.id).first()
        if not conv:
            raise HTTPException(status_code=404, detail='对话不存在')
    else:
        conv = db.query(AgentConversation).filter_by(user_id=user.id).order_by(AgentConversation.id.desc()).first()
        if not conv:
            return {"status": "success", "deleted": 0, "message": "无对话或已清空"}

    try:
        deleted_msgs = db.query(AgentMessage).filter_by(conversation_id=conv.id).delete(synchronize_session=False)
        db.delete(conv)
        db.commit()
        return {"status": "success", "message": "对话已删除", "conversation_id": conversation_id or conv.id,
            "deleted_messages": deleted_msgs}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail='删除对话失败')


@router.get('/status')
async def agent_status() -> Dict:
    return {
        'deepseek': {'configured': bool(DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL), 'base_url': DEEPSEEK_BASE_URL or None,
            'masked_key': _mask(DEEPSEEK_API_KEY)}, 'debug_allow_temp_key': DEBUG_ALLOW_TEMP_KEY,
        'default_model': DEFAULT_MODEL}
