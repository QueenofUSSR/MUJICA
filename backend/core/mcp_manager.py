from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from .mcp_registry import MCPRegistry, MCPTemplate


class MCPManager:
    """Install/uninstall/register MCP servers (best-effort synchronous implementation)."""

    def __init__(self) -> None:
        self.registry = MCPRegistry()

    @staticmethod
    def run_pip(args: Iterable[str]) -> Dict[str, str]:
        cmd = [sys.executable, "-m", "pip", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": " ".join(cmd),
        }

    def install_template(self, template_id: str, package: Optional[str] = None) -> Dict[str, object]:
        tpl = self.registry.get_template(template_id)
        if not tpl:
            return {"ok": False, "error": f"Template '{template_id}' not found"}
        pkg_name = package or tpl.package
        if not pkg_name:
            return {"ok": False, "error": "Template does not define a pip package"}
        result = self.run_pip(["install", pkg_name])
        result["ok"] = result["returncode"] == 0
        return result

    def uninstall_package(self, package: str) -> Dict[str, object]:
        result = self.run_pip(["uninstall", "-y", package])
        result["ok"] = result["returncode"] == 0
        return result

    def build_server_entry(
        self,
        template: MCPTemplate,
        server_name: str,
        command_override: Optional[str] = None,
        args_override: Optional[list[str]] = None,
        env_override: Optional[Dict[str, str]] = None,
    ) -> Dict[str, object]:
        command = command_override or template.command
        args = args_override if args_override is not None else template.args
        entry = {
            "command": command,
            "args": args,
            "env": env_override or template.env,
            "metadata": {
                "templateId": template.id,
                "managed": True,
            },
        }
        if template.package:
            entry["metadata"]["package"] = template.package
        return {server_name: entry}

    @staticmethod
    def merge_config(existing: Dict[str, object], servers_patch: Dict[str, object]) -> Dict[str, object]:
        cfg = dict(existing)
        section = cfg.setdefault("mcpServers", {})
        section.update(servers_patch)
        cfg["mcpServers"] = section
        return cfg

