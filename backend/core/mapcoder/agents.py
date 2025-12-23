from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import asyncio
from browser_use import Agent as BrowserUseAgent, Browser, ChatOpenAI
from .provider import call_llm


@dataclass
class AgentResult:
    ok: bool
    text: str
    meta: Dict[str, Any]


class RetrieverAgent:
    async def run(self, prompt: str, model_id: Optional[str] = None, llm_params: Optional[dict] = None) -> AgentResult:
        q = f"给我3个与此任务相关的编程示例（问题+解题思路），简洁列点：\n{prompt}"
        params = llm_params or {}
        text = await asyncio.to_thread(call_llm, q, model_id, params.get("max_tokens", 800), params.get("temperature", 0.2), params.get("api_key"))
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "retrieval"})


class PlannerAgent:
    async def run(self, prompt: str, model_id: Optional[str] = None, llm_params: Optional[dict] = None) -> AgentResult:
        q = (
            "基于任务，生成不低于3个候选计划（含关键步骤与风险），并给每个计划一个0-1的置信度：\n" + prompt
        )
        params = llm_params or {}
        text = await asyncio.to_thread(call_llm, q, model_id, params.get("max_tokens", 800), params.get("temperature", 0.2), params.get("api_key"))
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "planning"})


class CoderAgent:
    async def run(self, prompt: str, plan: Optional[str] = None, model_id: Optional[str] = None, llm_params: Optional[dict] = None) -> AgentResult:
        base = f"请根据以下任务{('与计划' if plan else '')}生成可运行的代码，并给出必要说明：\n任务：{prompt}\n"
        if plan:
            base += f"计划：{plan}\n"
        params = llm_params or {}
        text = await asyncio.to_thread(call_llm, base, model_id, params.get("max_tokens", 1600), params.get("temperature", 0.2), params.get("api_key"))
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "coding"})


class DebuggerAgent:
    async def run(self, prompt: str, code: Optional[str] = None, model_id: Optional[str] = None, llm_params: Optional[dict] = None) -> AgentResult:
        base = "请基于样例I/O进行调试，指出问题并给出修复后的代码；若未知样例，可进行常识性检查。\n"
        if code:
            base += f"待调试代码：\n{code}\n"
        base += f"任务：{prompt}\n"
        params = llm_params or {}
        text = await asyncio.to_thread(call_llm, base, model_id, params.get("max_tokens", 1600), params.get("temperature", 0.2), params.get("api_key"))
        return AgentResult(ok=bool(text), text=text or "", meta={"type": "debugging"})
    
class BrowserNavAgent:
    async def run(self, prompt: str, model_id: Optional[str] = None, llm_params: Optional[dict] = None) -> AgentResult:
        params = llm_params or {}
        api_key = params.get("api_key")
        
        # 1. 初始化 LangChain LLM
        # Browser Use 推荐使用 gpt-4o
        llm = ChatOpenAI(
            model=model_id or "gpt-4o",
            api_key=api_key,
            temperature=0.0
        )

        # 2. 初始化 Browser (不使用 Config 类)
        # 尝试直接传递 headless 参数，如果不支持则使用默认值
        try:
            # 大多数新版本支持直接传 headless=True
            # 注意：如果此处报错 "unexpected keyword argument 'headless'"，
            # 请改为 browser = Browser() 即可
            browser = Browser() 
        except Exception:
            browser = Browser()
        
        enhanced_prompt = (
            f"{prompt}\n\n"
            "【执行策略】\n"
            "1. 不要直接从搜索结果列表页提取信息，那里的信息不完整。\n"
            "2. 你必须点击最权威的一个搜索结果链接（优先点击 '百度百科'、'官方维基' 或 '知乎' 等详情页）。\n"
            "3. 等待详情页加载完成后，再提取我需要的内容。\n"
            "4. 如果页面内容被折叠（如“展开全部”），请尝试点击展开。"
        )
        agent = BrowserUseAgent(
            task=enhanced_prompt,
            llm=llm,
            browser=browser
        )

        try:
            # 3. 执行
            history = await agent.run()
            
            # 4. 提取结果
            # history.final_result() 返回 Agent 的最终总结字符串
            final_text = history.final_result()
            if not final_text:
                final_text = "浏览器任务执行完成，但未返回具体文本摘要。"
            
            return AgentResult(ok=True, text=final_text, meta={"type": "browser_navigation"})
            
        except Exception as e:
            # 捕获所有异常，防止让整个 Coordinator 崩溃
            return AgentResult(ok=False, text=f"浏览器操作失败: {str(e)}", meta={"type": "browser_navigation"})
