"""
MCP Server Implementation for LLM Proxy

Provides an MCP-compliant server that aggregates multiple upstream MCP servers.
Supports stdio, SSE, and streamable HTTP transports.
"""

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator

from .mcp_manager import MCPManager

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server that aggregates multiple upstream MCP servers.
    
    This server exposes the aggregated tools from all connected upstream
    servers through the MCP protocol.
    """
    
    def __init__(self, mcp_manager: MCPManager):
        """
        Initialize the MCP Server.
        
        Args:
            mcp_manager: The MCP manager that handles upstream connections
        """
        self.mcp_manager = mcp_manager
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.protocol_version = "2025-06-18"
        self.server_info = {
            "name": "polyllama-mcp-aggregator",
            "version": "1.0.0"
        }
    
    async def handle_message(self, message: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle an incoming MCP protocol message.
        
        Args:
            message: The MCP protocol message
            session_id: Optional session ID for stateful connections
            
        Returns:
            The response message
        """
        method = message.get("method")
        params = message.get("params", {})
        message_id = message.get("id")
        
        if not method:
            return self._error_response(message_id, -32600, "Invalid request: missing method")
        
        try:
            # Route to appropriate handler
            if method == "initialize":
                return await self._handle_initialize(params, message_id, session_id)
            elif method == "tools/list":
                return await self._handle_tools_list(params, message_id, session_id)
            elif method == "tools/call":
                return await self._handle_tools_call(params, message_id, session_id)
            elif method == "completion/complete":
                return await self._handle_completion(params, message_id, session_id)
            else:
                return self._error_response(message_id, -32601, f"Method not found: {method}")
        
        except Exception as e:
            logger.error(f"Error handling method {method}: {e}", exc_info=True)
            return self._error_response(message_id, -32603, f"Internal error: {str(e)}")
    
    async def _handle_initialize(self, params: Dict[str, Any], message_id: Any, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle the initialize method."""
        # Ensure MCP manager is initialized
        if not self.mcp_manager._initialized:
            await self.mcp_manager.initialize()
        
        # Create or update session
        if session_id:
            self.sessions[session_id] = {
                "initialized": True,
                "client_info": params.get("clientInfo", {}),
                "protocol_version": params.get("protocolVersion", self.protocol_version),
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Get available tools for capabilities
        tools = await self.mcp_manager.list_tools()
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "tools": {} if tools else None,
                    "completion": {} if tools else None
                },
                "serverInfo": self.server_info
            }
        }
    
    async def _handle_tools_list(self, params: Dict[str, Any], message_id: Any, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle the tools/list method."""
        # Get tools from MCP manager
        tools = await self.mcp_manager.list_tools()
        
        # Convert to MCP format
        mcp_tools = []
        for tool in tools:
            mcp_tool = {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "inputSchema": tool.get("inputSchema", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
            mcp_tools.append(mcp_tool)
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "tools": mcp_tools
            }
        }
    
    async def _handle_tools_call(self, params: Dict[str, Any], message_id: Any, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle the tools/call method."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return self._error_response(message_id, -32602, "Invalid params: missing tool name")
        
        try:
            # Execute the tool through MCP manager
            result = await self.mcp_manager.execute_tool(tool_name, arguments)
            
            # Format result based on type
            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            elif isinstance(result, dict):
                # Check if it's already in MCP content format
                if "content" in result:
                    content = result["content"]
                elif "type" in result and "text" in result:
                    content = [result]
                else:
                    # Convert dict to JSON string
                    content = [{"type": "text", "text": json.dumps(result, indent=2)}]
            elif isinstance(result, list):
                # Assume it's already a content array
                content = result
            else:
                # Convert to string
                content = [{"type": "text", "text": str(result)}]
            
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "content": content
                }
            }
        
        except ValueError as e:
            return self._error_response(message_id, -32602, f"Tool not found: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return self._error_response(message_id, -32603, f"Tool execution failed: {str(e)}")
    
    async def _handle_completion(self, params: Dict[str, Any], message_id: Any, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle the completion/complete method."""
        # Get the argument for completion
        argument = params.get("argument", {})
        name = argument.get("name", "")
        value = argument.get("value", "")
        
        # Get all tools
        tools = await self.mcp_manager.list_tools()
        
        # Find matching tool names
        completions = []
        for tool in tools:
            tool_name = tool.get("name", "")
            if tool_name.startswith(name):
                completions.append({
                    "values": [tool_name],
                    "total": 1,
                    "hasMore": False
                })
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "completion": completions[0] if completions else {
                    "values": [],
                    "total": 0,
                    "hasMore": False
                }
            }
        }
    
    def _error_response(self, message_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "initialized": False,
            "created_at": datetime.utcnow().isoformat()
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID."""
        return self.sessions.get(session_id)
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        """Clean up sessions older than max_age_seconds."""
        now = datetime.utcnow()
        to_remove = []
        
        for session_id, session_data in self.sessions.items():
            created_at = datetime.fromisoformat(session_data.get("created_at", now.isoformat()))
            age = (now - created_at).total_seconds()
            if age > max_age_seconds:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self.sessions[session_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
    
    async def handle_stdio(self):
        """
        Handle MCP protocol over stdio (for testing and direct usage).
        
        This reads JSON-RPC messages from stdin and writes responses to stdout.
        """
        logger.info("MCP Server running in stdio mode")
        
        # Create a session for stdio mode
        session_id = self.create_session()
        
        # Read from stdin line by line
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                
                # Parse JSON message
                try:
                    message = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue  # Skip invalid JSON
                
                # Handle the message
                response = await self.handle_message(message, session_id)
                
                # Write response to stdout
                print(json.dumps(response))
                sys.stdout.flush()
                
            except Exception as e:
                logger.error(f"Error in stdio handler: {e}", exc_info=True)
    
    async def handle_sse_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Generate Server-Sent Events for SSE transport.
        
        Args:
            session_id: The session ID for this connection
            
        Yields:
            SSE formatted messages
        """
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connection', 'sessionId': session_id})}\n\n"
        
        # Keep connection alive with periodic pings
        while session_id in self.sessions:
            await asyncio.sleep(30)  # Send ping every 30 seconds
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"