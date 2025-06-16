"""
MCP API endpoints for the LLM Proxy Service.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import asyncio
from services.mcp_manager import MCPManager

logger = logging.getLogger(__name__)

# Create router
mcp_router = APIRouter(prefix="/api/mcp", tags=["MCP"])

# Global MCP manager instance
mcp_manager = MCPManager()


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolExecutionResponse(BaseModel):
    """Response model for tool execution."""
    tool_name: str
    result: Any
    success: bool = True
    error: str = None


# Background task for MCP initialization
async def initialize_mcp_background():
    """Initialize MCP manager in the background."""
    try:
        # Wait a bit for the service to fully start
        await asyncio.sleep(2)
        logger.info("Starting MCP manager initialization...")
        await mcp_manager.initialize()
        logger.info("MCP manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MCP manager: {e}", exc_info=True)


@mcp_router.on_event("startup")
async def startup_event():
    """Initialize MCP manager on startup."""
    # Start MCP initialization in the background
    asyncio.create_task(initialize_mcp_background())
    logger.info("MCP manager initialization started in background")


@mcp_router.on_event("shutdown")
async def shutdown_event():
    """Shutdown MCP manager on shutdown."""
    try:
        await mcp_manager.shutdown()
        logger.info("MCP manager shutdown successfully")
    except Exception as e:
        logger.error(f"Error during MCP manager shutdown: {e}")


@mcp_router.get("/status")
async def get_mcp_status():
    """Get the status of MCP servers and tools."""
    try:
        status = mcp_manager.get_status()
        return {
            "status": "configured" if status["initialized"] else "not_configured",
            "servers": status["servers"],
            "total_tools": status["total_tools"]
        }
    except Exception as e:
        logger.error(f"Error getting MCP status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp_router.get("/tools")
async def list_tools():
    """List all available MCP tools."""
    try:
        tools = await mcp_manager.list_tools()
        return {
            "tools": tools,
            "count": len(tools)
        }
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp_router.post("/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(request: ToolExecutionRequest):
    """Execute a specific MCP tool."""
    try:
        result = await mcp_manager.execute_tool(
            request.tool_name,
            request.arguments
        )
        
        return ToolExecutionResponse(
            tool_name=request.tool_name,
            result=result,
            success=True
        )
    except ValueError as e:
        # Tool not found
        return ToolExecutionResponse(
            tool_name=request.tool_name,
            result=None,
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing tool '{request.tool_name}': {e}")
        return ToolExecutionResponse(
            tool_name=request.tool_name,
            result=None,
            success=False,
            error=str(e)
        )


@mcp_router.get("/tools/formatted")
async def get_formatted_tools():
    """Get tools formatted for LLM function calling."""
    try:
        formatted_tools = mcp_manager.format_tools_for_llm()
        return {
            "tools": formatted_tools,
            "count": len(formatted_tools)
        }
    except Exception as e:
        logger.error(f"Error formatting MCP tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))