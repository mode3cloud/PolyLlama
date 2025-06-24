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
async def get_mcp_status(request: Request):
    """Get the status of MCP servers and tools."""
    try:
        mcp_manager = request.app.state.mcp_manager
        status = mcp_manager.get_status()
        
        # Get detailed bridge status if available
        servers = {}
        if status["initialized"]:
            try:
                bridge_status = await mcp_manager.get_bridge_status()
                servers = bridge_status.get("servers", {})
            except Exception as e:
                logger.warning(f"Failed to get bridge status: {e}")
        
        return {
            "status": "configured" if status["initialized"] else "not_configured",
            "servers": servers,
            "total_tools": status["total_tools"],
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
