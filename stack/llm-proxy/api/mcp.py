"""
MCP API endpoints for the LLM Proxy Service.
"""

import logging
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
mcp_router = APIRouter(prefix="/api/mcp", tags=["MCP"])

# MCP manager will be accessed from app.state


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""

    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolExecutionResponse(BaseModel):
    """Response model for tool execution."""

    tool_name: str
    result: Any
    success: bool = True
    error: Optional[str] = None


# Note: MCP manager is initialized in main.py startup event


@mcp_router.get("/status")
async def get_mcp_status(request: Request, include_tools: bool = False):
    """Get the status of MCP servers and tools."""
    try:
        mcp_manager = request.app.state.mcp_manager
        status = mcp_manager.get_status()
        
        # Get detailed bridge status if available
        servers = {}
        total_connected_tools = 0
        
        if status["initialized"]:
            try:
                bridge_status = await mcp_manager.get_bridge_status(include_tools=include_tools)
                servers = bridge_status.get("servers", {})
                
                # Calculate total tools from connected servers
                for server_name, server_info in servers.items():
                    if server_info.get("connected") and server_info.get("toolCount"):
                        total_connected_tools += server_info.get("toolCount", 0)
                        
            except Exception as e:
                logger.warning(f"Failed to get bridge status: {e}")
        
        # Use connected tools count if available, otherwise fall back to cache
        actual_total_tools = total_connected_tools if total_connected_tools > 0 else status["total_tools"]
        
        return {
            "status": "configured" if status["initialized"] else "not_configured",
            "servers": servers,
            "total_tools": actual_total_tools,
            "cache_tools": status["total_tools"],  # Include cached count for debugging
            "connected_tools": total_connected_tools,  # Include connected count
        }
    except Exception as e:
        logger.error("Error getting MCP status: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@mcp_router.get("/tools")
async def list_tools(request: Request):
    """List all available MCP tools."""
    try:
        mcp_manager = request.app.state.mcp_manager
        tools = await mcp_manager.list_tools()
        return {"tools": tools, "count": len(tools)}
    except Exception as e:
        logger.error("Error listing MCP tools: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@mcp_router.post("/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(tool_request: ToolExecutionRequest, request: Request):
    """Execute a specific MCP tool."""
    try:
        mcp_manager = request.app.state.mcp_manager
        result = await mcp_manager.execute_tool(tool_request.tool_name, tool_request.arguments)

        return ToolExecutionResponse(
            tool_name=tool_request.tool_name, result=result, success=True
        )
    except ValueError as e:
        # Tool not found
        return ToolExecutionResponse(
            tool_name=tool_request.tool_name, result=None, success=False, error=str(e)
        )
    except Exception as e:
        logger.error("Error executing tool '%s': %s", tool_request.tool_name, e)
        return ToolExecutionResponse(
            tool_name=tool_request.tool_name, result=None, success=False, error=str(e)
        )


@mcp_router.get("/tools/formatted")
async def get_formatted_tools(request: Request):
    """Get tools formatted for LLM function calling."""
    try:
        mcp_manager = request.app.state.mcp_manager
        formatted_tools = mcp_manager.format_tools_for_llm()
        return {"tools": formatted_tools, "count": len(formatted_tools)}
    except Exception as e:
        logger.error("Error formatting MCP tools: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
