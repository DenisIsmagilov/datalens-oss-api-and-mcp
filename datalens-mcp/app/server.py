from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.registry import (
    CREATE_TOOLS,
    READ_TOOLS,
    handle_call_rpc,
    handle_list_rpc_methods,
)


def register_read_tools(mcp: FastMCP) -> None:
    for tool_name, rpc_name in READ_TOOLS.items():
        mcp.add_tool(
            _make_rpc_handler(rpc_name),
            name=tool_name,
            description=f"Proxy to datalens-api RPC {rpc_name}",
        )


def register_create_tools(mcp: FastMCP) -> None:
    for tool_name, rpc_name in CREATE_TOOLS.items():
        mcp.add_tool(
            _make_rpc_handler(rpc_name),
            name=tool_name,
            description=f"Side-effect: creates resource via datalens-api RPC {rpc_name}",
        )


def _make_rpc_handler(rpc_name: str):
    async def handler(args: dict) -> str:
        return await handle_call_rpc(rpc_name, args)

    return handler


def build_mcp() -> FastMCP:
    settings = get_settings()
    mcp = FastMCP(
        "datalens-mcp",
        host="0.0.0.0",
        port=settings.datalens_mcp_port,
        streamable_http_path="/mcp",
    )

    @mcp.tool()
    async def list_rpc_methods() -> str:
        return await handle_list_rpc_methods()

    @mcp.tool()
    async def call_rpc(method: str, args: dict) -> str:
        return await handle_call_rpc(method, args)

    register_read_tools(mcp)
    register_create_tools(mcp)

    return mcp
