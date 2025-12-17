from __future__ import annotations

import os
import requests
from typing import Optional

from core.dependencies import logger

# Read configuration from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE") or os.environ.get("OPENAI_URL")
DEFAULT_MODEL = os.environ.get("CHATGPT_MODEL", "gpt-4o")
DEBUG_ALLOW_TEMP_KEY = os.environ.get("DEBUG_ALLOW_TEMP_KEY", "false").lower() in ("1", "true", "yes")
TEMP_OPENAI_KEY = os.environ.get("TEMP_OPENAI_KEY") if DEBUG_ALLOW_TEMP_KEY else None


def _mock_response_for_prompt(prompt: str, model: str) -> str:
    # Local deterministic simple mock for development when provider is not configured.
    low = prompt.lower()
    if "给我3个" in low or ("3个" in low and "示例" in low):
        return "1) 示例A：问题：...；思路：...\n2) 示例B：问题：...；思路：...\n3) 示例C：问题：...；思路：..."
    if "候选计划" in low or "计划" in low:
        return "计划A(置信度0.9)：步骤1, 步骤2。\n计划B(置信度0.6)：步骤1, 步骤2。\n计划C(置信度0.4)：步骤1, 步骤2。"
    if "生成可运行的代码" in low or "生成代码" in low or "实现" in low:
        return "def quicksort(a):\n    if len(a)<=1: return a\n    pivot=a[0]\n    left=[x for x in a[1:] if x<=pivot]\n    right=[x for x in a[1:] if x>pivot]\n    return quicksort(left)+[pivot]+quicksort(right)\n\n# 示例使用: quicksort([3,1,2])"
    if "调试" in low or "修复" in low or "debug" in low:
        return "找到问题：边界条件未处理。建议修复：在循环中判断空列表并返回。\n修复后的代码：..."
    return f"（模拟）{prompt[:800]}"


def call_llm(
    prompt: str,
    model_id: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
) -> str:
    """Call an OpenAI-compatible LLM HTTP endpoint (non-streaming).

    Resolution order for API key:
    - explicit api_key parameter (if provided)
    - TEMP_OPENAI_KEY if DEBUG_ALLOW_TEMP_KEY
    - OPENAI_API_KEY from environment

    If no key is available, return a deterministic mock response to keep local dev working.
    """
    model = model_id or DEFAULT_MODEL
    key = api_key or TEMP_OPENAI_KEY or OPENAI_API_KEY

    if not key:
        logger.warning(
            "LLM provider 未配置: OPENAI_API_KEY 为空，且未启用临时密钥；使用本地模拟回答以便开发测试"
        )
        return _mock_response_for_prompt(prompt, model)

    base = (OPENAI_BASE_URL.rstrip("/") if OPENAI_BASE_URL else "https://api.openai.com")
    if base.endswith("/v1"):
        url = base + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        logger.info(f"LLM call -> model={model} url={url} tokens={max_tokens}")
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"LLM 调用失败 status={resp.status_code} body={resp.text[:500]}")
            return ""
        data = resp.json()
        choices = data.get("choices") or []
        if choices and isinstance(choices, list):
            first = choices[0]
            msg = first.get("message") or {}
            content = msg.get("content") or first.get("text") or ""
            return content or ""
        return ""
    except Exception as e:
        logger.warning(f"LLM 请求异常: {e}")
        # Fallback to mock to avoid breaking the flow in development
        return _mock_response_for_prompt(prompt, model)
