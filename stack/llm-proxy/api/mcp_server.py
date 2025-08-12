"""
MCP Server API endpoints for protocol-compliant MCP access.

This module provides HTTP and SSE endpoints that implement the MCP protocol,
allowing MCP clients to connect and use the aggregated tools.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.mcp_server import MCPServer

logger = logging.getLogger(__name__)

# Create router without prefix (we'll handle /mcp paths directly)
mcp_server_router = APIRouter(tags=["MCP Server"])


class MCPRequest(BaseModel):
    """Request model for MCP protocol messages."""
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = {}
    id: Optional[Any] = None


@mcp_server_router.post("/mcp")
async def handle_mcp_streamable_http(request: Request, response: Response):
    """
    Handle MCP protocol over streamable HTTP transport.
    
    This endpoint supports the single-event SSE format for compatibility
    with mcpinspection and other MCP clients.
    """
    try:
        # Get or create session
        session_id = request.headers.get("x-session-id") or request.headers.get("mcp-session-id")
        
        # Get MCP server instance
        mcp_manager = request.app.state.mcp_manager
        if not hasattr(request.app.state, "mcp_server"):
            request.app.state.mcp_server = MCPServer(mcp_manager)
        mcp_server = request.app.state.mcp_server
        
        # Create session if needed
        if not session_id:
            session_id = mcp_server.create_session()
            response.headers["x-session-id"] = session_id
            response.headers["mcp-session-id"] = session_id
        
        # Parse request body
        body = await request.body()
        
        # Handle empty POST (session creation)
        if not body or body == b'{}':
            # Return session info
            return {
                "sessionId": session_id,
                "status": "connected",
                "serverInfo": mcp_server.server_info
            }
        
        # Parse JSON-RPC message
        try:
            message = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        # Check if client wants streaming
        accept_header = request.headers.get("accept", "")
        wants_streaming = "text/event-stream" in accept_header
        
        if wants_streaming:
            # For streaming, we need to handle the message and stream the response
            async def generate_sse():
                try:
                    # Handle the message
                    result = await mcp_server.handle_message(message, session_id)
                    
                    # Send result as single SSE event (for mcpinspection compatibility)
                    yield f"data: {json.dumps(result)}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error processing MCP message: {e}", exc_info=True)
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        }
                    }
                    yield f"data: {json.dumps(error_response)}\n\n"
            
            return StreamingResponse(
                generate_sse(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Session-Id": session_id,
                }
            )
        else:
            # Non-streaming response
            result = await mcp_server.handle_message(message, session_id)
            return result
    
    except Exception as e:
        logger.error(f"Error in MCP streamable HTTP handler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@mcp_server_router.get("/mcp/sse")
async def handle_mcp_sse(request: Request):
    """
    Handle MCP protocol over Server-Sent Events (SSE) transport.
    
    This endpoint maintains a persistent SSE connection for real-time
    bidirectional communication.
    """
    try:
        # Get MCP server instance
        mcp_manager = request.app.state.mcp_manager
        if not hasattr(request.app.state, "mcp_server"):
            request.app.state.mcp_server = MCPServer(mcp_manager)
        mcp_server = request.app.state.mcp_server
        
        # Create session
        session_id = mcp_server.create_session()
        
        async def generate_sse():
            """Generate SSE stream."""
            try:
                # Send initial connection message
                yield f"data: {json.dumps({'type': 'connection', 'sessionId': session_id, 'serverInfo': mcp_server.server_info})}\n\n"
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(30)  # Ping every 30 seconds
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    
            except asyncio.CancelledError:
                # Clean up session on disconnect
                if session_id in mcp_server.sessions:
                    del mcp_server.sessions[session_id]
                raise
            except Exception as e:
                logger.error(f"Error in SSE generator: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": session_id,
            }
        )
    
    except Exception as e:
        logger.error(f"Error in MCP SSE handler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@mcp_server_router.post("/mcp/message")
async def handle_mcp_message(mcp_request: MCPRequest, request: Request):
    """
    Handle individual MCP messages (for SSE transport).
    
    This endpoint is used by SSE clients to send messages while maintaining
    their SSE connection for receiving responses.
    """
    try:
        # Get session ID from headers
        session_id = request.headers.get("x-session-id")
        if not session_id:
            raise HTTPException(status_code=400, detail="Missing session ID")
        
        # Get MCP server instance
        mcp_server = request.app.state.mcp_server
        if not mcp_server:
            raise HTTPException(status_code=503, detail="MCP server not initialized")
        
        # Check if session exists
        if not mcp_server.get_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Convert to dict for processing
        message = mcp_request.dict()
        
        # Handle the message
        result = await mcp_server.handle_message(message, session_id)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling MCP message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@mcp_server_router.get("/mcp/health")
async def mcp_server_health(request: Request):
    """Check MCP server health and status."""
    try:
        mcp_manager = request.app.state.mcp_manager
        mcp_server = getattr(request.app.state, "mcp_server", None)
        
        status = {
            "healthy": True,
            "mcp_manager_initialized": mcp_manager._initialized if mcp_manager else False,
            "mcp_server_initialized": mcp_server is not None,
            "active_sessions": len(mcp_server.sessions) if mcp_server else 0,
            "total_tools": len(await mcp_manager.list_tools()) if mcp_manager and mcp_manager._initialized else 0
        }
        
        # Clean up old sessions if server exists
        if mcp_server:
            mcp_server.cleanup_old_sessions()
        
        return status
    
    except Exception as e:
        logger.error(f"Error checking MCP server health: {e}", exc_info=True)
        return {
            "healthy": False,
            "error": str(e)
        }