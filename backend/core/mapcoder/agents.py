from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import asyncio

from .provider import call_llm


@dataclass
class AgentResult:
    ok: bool
    text: str
    meta: Dict[str, Any]


class RetrieverAgent:
    async def run(self, prompt: str, model_id: Optional[str] = None) -> AgentResult:
        q = f"给我3个与此任务相关的编程示例（问题+解题思路），简洁列点：\n{prompt}"
        text = await asyncio.to_thread(call_llm, q, model_id, 800)
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "retrieval"})


class PlannerAgent:
    async def run(self, prompt: str, model_id: Optional[str] = None) -> AgentResult:
        q = (
            "基于任务，生成不低于3个候选计划（含关键步骤与风险），并给每个计划一个0-1的置信度：\n" + prompt
        )
        text = await asyncio.to_thread(call_llm, q, model_id, 800)
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "planning"})


class CoderAgent:
    async def run(self, prompt: str, plan: Optional[str] = None, model_id: Optional[str] = None) -> AgentResult:
        base = f"请根据以下任务{('与计划' if plan else '')}生成可运行的代码，并给出必要说明：\n任务：{prompt}\n"
        if plan:
            base += f"计划：{plan}\n"
        text = await asyncio.to_thread(call_llm, base, model_id, 1600)
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "coding"})


class DebuggerAgent:
    async def run(self, prompt: str, code: Optional[str] = None, model_id: Optional[str] = None) -> AgentResult:
        base = "请基于样例I/O进行调试，指出问题并给出修复后的代码；若未知样例，可进行常识性检查。\n"
        if code:
            base += f"待调试代码：\n{code}\n"
        base += f"任务：{prompt}\n"
        text = await asyncio.to_thread(call_llm, base, model_id, 1600)
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "debugging"})
