from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Dict, Any

from sqlalchemy.orm import Session

from core.dependencies import logger, publish_event
from core.models import AgentRole, AgentSession, AgentTask, AgentTaskLog
from core.mapcoder.schemas import RoleConfig
from .agents import RetrieverAgent, PlannerAgent, CoderAgent, DebuggerAgent, AgentResult


MAPCODER_DEFAULT_ROLES: List[RoleConfig] = [
    RoleConfig(name="retriever", description="检索相关示例", capabilities={"type": "retrieval"}),
    RoleConfig(name="planner", description="生成多候选计划", capabilities={"type": "planning"}),
    RoleConfig(name="coder", description="根据计划生成代码", capabilities={"type": "coding"}),
    RoleConfig(name="debugger", description="基于样例调试并修复", capabilities={"type": "debugging"}),
]

_CODE_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\s*([\s\S]*?)```", re.MULTILINE)


def _extract_code_snippet(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = _CODE_FENCE.search(text)
    if match:
        snippet = match.group(1).strip()
        if snippet:
            return snippet
    stripped = text.strip()
    if stripped.startswith(("class ", "def ", "public ", "#include", "function ", "package ")):
        return stripped
    if "\n" not in stripped and len(stripped.split()) < 6:
        return None
    return stripped if len(stripped) > 20 else None


class CoordinatorService:
    def __init__(self, db: Session):
        self.db = db
        self._retriever = RetrieverAgent()
        self._planner = PlannerAgent()
        self._coder = CoderAgent()
        self._debugger = DebuggerAgent()

    def append_log(
        self,
        session_id: int,
        message: str,
        level: str = "INFO",
        task_id: Optional[int] = None,
        role_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> AgentTaskLog:
        log = AgentTaskLog(
            session_id=session_id,
            task_id=task_id,
            role_id=role_id,
            level=level,
            message=message,
            payload=payload,
        )
        self.db.add(log)
        self.db.flush()
        try:
            publish_event(session_id, {
                "type": "log",
                "log": {
                    "id": log.id,
                    "session_id": session_id,
                    "task_id": task_id,
                    "level": level,
                    "message": message,
                    "payload": payload,
                    "created_at": (log.created_at or datetime.now(timezone.utc)).isoformat(),
                },
            })
        except Exception:
            logger.debug("无法推送日志事件", exc_info=True)
        return log

    async def create_session(
        self,
        user_id: int,
        title: str,
        model_id: Optional[str],
        prompt: Optional[str] = None,
        role_configs: Optional[Iterable[RoleConfig]] = None,
    ) -> AgentSession:
        prompt_clean = (prompt or "").strip()
        metadata: Dict[str, Any] = {}
        if prompt_clean:
            metadata = {"prompt": prompt_clean, "messages": [{"role": "user", "content": prompt_clean}]}
        session = AgentSession(
            user_id=user_id,
            title=title,
            model_id=model_id,
            status="pending" if prompt_clean else "draft",
            metadata_=metadata,
        )
        self.db.add(session)
        self.db.flush()
        logger.info(f"创建会话记录 AgentSession ID: {session.id}")

        if prompt_clean:
            roles = self._ensure_roles(role_configs)
            self._bootstrap_tasks(session, prompt_clean, roles)
            self.append_log(session.id, "会话已创建", level="INFO")

        self.db.commit()
        self.db.refresh(session)
        return session

    def _ensure_roles(self, role_configs: Optional[Iterable[RoleConfig]]) -> List[AgentRole]:
        configs = list(role_configs) if role_configs else MAPCODER_DEFAULT_ROLES
        roles: List[AgentRole] = []
        for cfg in configs:
            role = self.db.query(AgentRole).filter_by(name=cfg.name).first()
            if not role:
                role = AgentRole(
                    name=cfg.name,
                    description=cfg.description,
                    capabilities=cfg.capabilities,
                )
                self.db.add(role)
                self.db.flush()
                logger.info(f"创建角色记录 AgentRole ID: {role.id}")
            roles.append(role)
        return roles

    def _bootstrap_tasks(self, session: AgentSession, prompt: str, roles: List[AgentRole]) -> None:
        # Only create root task; sub tasks will be created dynamically per stage
        root_task = AgentTask(
            session_id=session.id,
            title="整体任务",
            description=prompt,
            status="pending",
        )
        self.db.add(root_task)
        self.db.flush()
        logger.info(f"创建根任务记录 AgentTask ID: {root_task.id}")

    async def run_session(self, session) -> None:
        """Run staged pipeline: retriever -> planner -> coder -> debugger, creating tasks on demand."""
        logger.info(f"Coordinator starting session {session.id}")
        session.status = "running"
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        # Fetch root task (created in bootstrap)
        root = (
            self.db.query(AgentTask)
            .filter_by(session_id=session.id, parent_id=None)
            .order_by(AgentTask.id.asc())
            .first()
        )
        if not root:
            # safety: create one if missing
            root = AgentTask(session_id=session.id, title="整体任务", description=(session.metadata_ or {}).get("prompt", ""), status="pending")
            self.db.add(root)
            self.db.flush()

        # cooperative cancel check helper
        def _canceled() -> bool:
            try:
                fresh = self.db.query(AgentSession).filter_by(id=session.id).first()
                return bool(fresh and fresh.status in ("canceled", "failed"))
            except Exception:
                return False

        prompt = (session.metadata_ or {}).get("prompt") or root.description or ""
        if not prompt:
            self.append_log(session.id, "任务缺少提示词，无法启动", level="ERROR")
            session.status = "failed"
            session.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return

        # 1) retriever
        if _canceled():
            self.append_log(session.id, "任务已被用户停止", level="INFO")
            try:
                publish_event(session.id, {"type": "session", "session": {"id": session.id, "status": "canceled", "updated_at": datetime.now(timezone.utc).isoformat()}})
            except Exception:
                pass
            return
        retr_role = self.db.query(AgentRole).filter_by(name="retriever").first()
        retr_task = AgentTask(session_id=session.id, parent_id=root.id, assigned_role_id=retr_role.id if retr_role else None, title="retriever 子任务", description="检索相关示例", status="pending")
        self.db.add(retr_task); self.db.flush()
        await self._run_task(session, retr_task)

        # 2) planner
        if _canceled():
            return
        plan_role = self.db.query(AgentRole).filter_by(name="planner").first()
        plan_task = AgentTask(session_id=session.id, parent_id=root.id, assigned_role_id=plan_role.id if plan_role else None, title="planner 子任务", description="生成多候选计划", status="pending")
        self.db.add(plan_task); self.db.flush()
        await self._run_task(session, plan_task)

        # 3) coder
        if _canceled():
            return
        coder_role = self.db.query(AgentRole).filter_by(name="coder").first()
        coder_task = AgentTask(session_id=session.id, parent_id=root.id, assigned_role_id=coder_role.id if coder_role else None, title="coder 子任务", description="根据计划生成代码", status="pending")
        self.db.add(coder_task); self.db.flush()
        await self._run_task(session, coder_task)

        # 4) debugger
        if _canceled():
            return
        dbg_role = self.db.query(AgentRole).filter_by(name="debugger").first()
        dbg_task = AgentTask(session_id=session.id, parent_id=root.id, assigned_role_id=dbg_role.id if dbg_role else None, title="debugger 子任务", description="基于样例调试并修复", status="pending")
        self.db.add(dbg_task); self.db.flush()
        await self._run_task(session, dbg_task)

        # aggregate results
        try:
            tasks_all = (
                self.db.query(AgentTask)
                .filter_by(session_id=session.id)
                .order_by(AgentTask.id.asc())
                .all()
            )
            aggregated = {"codes": [], "texts": []}
            for t in tasks_all:
                if t.result and isinstance(t.result, dict):
                    code_txt = t.result.get("code") or None
                    plain_txt = t.result.get("text") or code_txt or None
                    if plain_txt:
                        aggregated["texts"].append({"task_id": t.id, "title": t.title, "text": plain_txt})
                    if code_txt:
                        aggregated["codes"].append({"task_id": t.id, "title": t.title, "code": code_txt})
            final_artifact = aggregated["codes"][-1] if aggregated["codes"] else (
                {"task_id": aggregated["texts"][-1]["task_id"], "title": aggregated["texts"][-1]["title"], "text": "\n\n".join([x["text"] for x in aggregated["texts"][-3:]])} if aggregated["texts"] else {"text": "未生成结果"}
            )
            session.final_result = final_artifact
            session.summary_title = final_artifact.get("title") or (final_artifact.get("text") or final_artifact.get("code") or session.title)[:120]
            session.status = "completed"
            session.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            try:
                publish_event(session.id, {"type": "final_result", "final_result": session.final_result, "summary_title": session.summary_title, "status": session.status, "updated_at": session.updated_at.isoformat()})
            except Exception:
                pass
            self.append_log(session.id, "任务已全部完成", level="INFO")
        except Exception as e:
            logger.warning(f"聚合任务结果失败: {e}")
            session.status = "failed"
            session.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.append_log(session.id, "聚合结果失败", level="ERROR")

    async def _run_task(self, session, task) -> None:
        task.status = "running"
        task.attempt_count = (task.attempt_count or 0) + 1
        task.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.append_log(
            session_id=session.id,
            task_id=task.id,
            role_id=task.assigned_role_id,
            level="INFO",
            message=f"{task.title} 开始执行",
        )

        # Determine role type
        role = self.db.query(AgentRole).filter_by(id=task.assigned_role_id).first() if task.assigned_role_id else None
        role_type = (role.capabilities or {}).get("type") if role else None
        prompt = (session.metadata_ or {}).get("prompt") or task.description or ""

        result: Optional[AgentResult] = None
        if role_type == "retrieval":
            result = await self._retriever.run(prompt, model_id=session.model_id)
        elif role_type == "planning":
            result = await self._planner.run(prompt, model_id=session.model_id)
        elif role_type == "coding":
            # optionally use parent plan
            parent = self.db.query(AgentTask).filter_by(id=task.parent_id).first() if task.parent_id else None
            plan_text = None
            if parent and parent.result:
                plan_text = parent.result.get("text") or parent.result.get("code")
            result = await self._coder.run(prompt, plan=plan_text, model_id=session.model_id)
        elif role_type == "debugging":
            # pass previous code output if any sibling produced code
            code_text = None
            siblings = self.db.query(AgentTask).filter_by(session_id=session.id, parent_id=task.parent_id).all()
            for s in siblings:
                if s.result and isinstance(s.result, dict):
                    cand = s.result.get("code") or s.result.get("text")
                    if cand:
                        code_text = cand
                        break
            result = await self._debugger.run(prompt, code=code_text, model_id=session.model_id)
        else:
            # root or unknown role: just summarize
            result = AgentResult(ok=True, text=f"处理：{task.title}", meta={"type": "generic"})

        await asyncio.sleep(0)

        # Update task based on result
        if result and result.ok:
            task.status = "completed"
            task.confidence = task.confidence or 0.8
            # store text into plan or result depending on role
            payload: Dict[str, Any] = {"text": result.text or "", "meta": result.meta, "role_type": role_type}
            if role_type in {"coding", "debugging"}:
                snippet = _extract_code_snippet(result.text)
                if snippet:
                    payload["code"] = snippet
            task.result = payload

            task.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            # publish task update event
            try:
                publish_event(session.id, {"type": "task_update", "task": {"id": task.id, "status": task.status, "result": task.result, "updated_at": task.updated_at.isoformat()}})
            except Exception:
                pass
            self.append_log(
                session_id=session.id,
                task_id=task.id,
                role_id=task.assigned_role_id,
                level="INFO",
                message=f"{task.title} 已完成",
                payload={"meta": result.meta},
            )
        else:
            task.status = "failed"
            task.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            try:
                publish_event(session.id, {"type": "task_update", "task": {"id": task.id, "status": task.status, "updated_at": task.updated_at.isoformat()}})
            except Exception:
                pass
            self.append_log(
                session_id=session.id,
                task_id=task.id,
                role_id=task.assigned_role_id,
                level="ERROR",
                message=f"{task.title} 执行失败",
            )

    async def run_session_by_id(self, session_id: int) -> None:
        session = self.db.query(AgentSession).filter_by(id=session_id).first()
        if not session:
            logger.warning(f"Session {session_id} 不存在")
            return
        await self.run_session(session)
