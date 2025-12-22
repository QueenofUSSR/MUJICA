from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MCPTemplate:
    """Declarative template describing how to launch/install an MCP server."""

    id: str
    title: str
    description: str
    command: Optional[str]
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    package: Optional[str] = None
    requires_install: bool = False
    homepage: Optional[str] = None
    default_server_name: Optional[str] = None


class MCPRegistry:
    """Simple in-memory registry + helpers (can later be swapped for remote catalogs)."""

    def __init__(self) -> None:
        self._templates: Dict[str, MCPTemplate] = {
            t.id: t for t in self._build_default_templates()
        }

    @staticmethod
    def _build_default_templates() -> List[MCPTemplate]:
        script = Path("backend") / "scripts" / "mcp_demo_server.py"
        templates = [
            MCPTemplate(
                id="local-demo",
                title="内置 Demo Server",
                description="仓库自带脚本，适合测试 MCP 协议流程。",
                command=sys.executable,
                args=[str(script.resolve())],
                requires_install=False,
                homepage="https://github.com/QueenofUSSR/MUJICA",
                default_server_name="demo-local",
            ),
            MCPTemplate(
                id="generic-pip",
                title="自定义 pip Server 模板",
                description="用于安装第三方 MCP server（通过 pip 包名称或 git URL）。",
                command=sys.executable,
                args=["-m", "your_mcp_server"],
                package="",
                requires_install=True,
                homepage="https://modelcontextprotocol.io/",
                default_server_name="custom-server",
            ),
        ]
        return templates

    def list_templates(self) -> List[MCPTemplate]:
        return list(self._templates.values())

    def get_template(self, template_id: str) -> Optional[MCPTemplate]:
        return self._templates.get(template_id)

    @staticmethod
    def _is_package_installed(package: Optional[str]) -> Optional[str]:
        if not package:
            return "built-in"
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None
        return version

    def describe_template(self, template: MCPTemplate) -> Dict[str, object]:
        version = self._is_package_installed(template.package)
        data = asdict(template)
        data.update(
            {
                "installed": version is not None,
                "installedVersion": version,
            }
        )
        return data

    def describe_all(self) -> List[Dict[str, object]]:
        return [self.describe_template(t) for t in self.list_templates()]

