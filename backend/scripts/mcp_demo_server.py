# backend/scripts/mcp_demo_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MUJICA Demo", json_response=True)

@mcp.tool()
def echo(text: str) -> str:
    """Echo back the input text."""
    return text

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

if __name__ == "__main__":
    # stdio server (默认就是走 stdio)
    mcp.run()
