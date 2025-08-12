"""
MCP Proxy Client

This client connects to the local MCP server instead of directly to upstream servers.
Used by the main LLM proxy service to avoid STDIO conflicts.
"""

import asyncio
import logging
import httpx
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPProxyClient:
    """Client that connects to the local MCP server for tool access."""
    
    def __init__(self, mcp_server_url: str = "http://localhost:3001"):
        """
        Initialize the MCP proxy client.
        
        Args:
            mcp_server_url: URL of the local MCP server
        """
        self.mcp_server_url = mcp_server_url
        self.session_id = None
        self._initialized = False
        self.tools_cache: List[Dict[str, Any]] = []
    
    async def initialize(self):
        """Initialize connection to the MCP server with retry logic."""
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Create a session
                    response = await client.post(
                        f"{self.mcp_server_url}/mcp",
                        json={},
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        self.session_id = data.get("sessionId")
                        
                        # Initialize the session
                        init_response = await client.post(
                            f"{self.mcp_server_url}/mcp",
                            json={
                                "jsonrpc": "2.0",
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2025-06-18",
                                    "capabilities": {},
                                    "clientInfo": {
                                        "name": "llm-proxy-client",
                                        "version": "1.0.0"
                                    }
                                },
                                "id": 1
                            },
                            headers={
                                "Content-Type": "application/json",
                                "X-Session-Id": self.session_id
                            }
                        )
                        
                        if init_response.status_code == 200:
                            # List tools
                            tools_response = await client.post(
                                f"{self.mcp_server_url}/mcp",
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "tools/list",
                                    "params": {},
                                    "id": 2
                                },
                                headers={
                                    "Content-Type": "application/json",
                                    "X-Session-Id": self.session_id
                                }
                            )
                            
                            if tools_response.status_code == 200:
                                result = tools_response.json()
                                mcp_tools = result.get("result", {}).get("tools", [])
                                
                                # Convert MCP format to internal format
                                self.tools_cache = []
                                for tool in mcp_tools:
                                    tool_name = tool.get("name", "")
                                    # Extract server name from tool name (format: server__tool)
                                    server_name = "unknown"
                                    if "__" in tool_name:
                                        server_name = tool_name.split("__")[0]
                                    
                                    self.tools_cache.append({
                                        "name": tool_name,
                                        "description": tool.get("description"),
                                        "inputSchema": tool.get("inputSchema", {}),
                                        "server": server_name
                                    })
                                
                                self._initialized = True
                                logger.info(f"Connected to MCP server with {len(self.tools_cache)} tools")
                                return  # Success!
                            else:
                                logger.error(f"Failed to list tools: {tools_response.status_code}")
                        else:
                            logger.error(f"Failed to initialize session: {init_response.status_code}")
                    else:
                        logger.error(f"Failed to create session: {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to connect to MCP server: {e}")
                
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
        
        logger.error(f"Failed to connect to MCP server after {max_retries} attempts")
        self._initialized = False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools."""
        if not self._initialized:
            await self.initialize()
        return self.tools_cache
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via the MCP server."""
        if not self._initialized:
            await self.initialize()
        
        if not self.session_id:
            raise ValueError("No active session with MCP server")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.mcp_server_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        },
                        "id": f"call_{tool_name}"
                    },
                    headers={
                        "Content-Type": "application/json",
                        "X-Session-Id": self.session_id
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        content = result["result"].get("content", [])
                        # Extract text from content array
                        if content and len(content) > 0:
                            if isinstance(content[0], dict) and "text" in content[0]:
                                return content[0]["text"]
                        return content
                    elif "error" in result:
                        raise Exception(f"Tool execution error: {result['error']}")
                else:
                    raise Exception(f"HTTP error {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of the MCP proxy connection."""
        return {
            "initialized": self._initialized,
            "total_servers": 1 if self._initialized else 0,
            "total_tools": len(self.tools_cache),
            "servers": {
                "mcp-proxy": {
                    "connected": self._initialized,
                    "type": "proxy",
                    "tool_count": len(self.tools_cache)
                }
            } if self._initialized else {}
        }
    
    async def get_bridge_status(self, include_tools: bool = False) -> Dict[str, Any]:
        """Get detailed status with optional tool information."""
        servers = {}
        
        if self._initialized:
            # Group tools by server name
            tools_by_server = {}
            for tool in self.tools_cache:
                server_name = tool.get("server", "unknown")
                if server_name not in tools_by_server:
                    tools_by_server[server_name] = []
                tools_by_server[server_name].append(tool)
            
            # Create server entries for each unique server
            for server_name, server_tools in tools_by_server.items():
                servers[server_name] = {
                    "connected": True,
                    "type": "proxy",
                    "toolCount": len(server_tools),
                    "lastError": None
                }
                
                if include_tools:
                    servers[server_name]["tools"] = server_tools
        
        return {"servers": servers}
    
    def format_tools_for_llm(self, tool_selection: Optional[Dict[str, Dict[str, bool]]] = None) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling."""
        formatted_tools = []
        
        for tool in self.tools_cache:
            # Check if tool is selected
            if tool_selection:
                # Handle flat selection format
                flat_selection = {}
                for server_name, tools in tool_selection.items():
                    for tool_name, enabled in tools.items():
                        flat_selection[tool_name] = enabled
                
                if not flat_selection.get(tool["name"], True):
                    continue
            
            # Convert to OpenAI function format
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            formatted_tools.append(formatted_tool)
        
        return formatted_tools
    
    async def shutdown(self):
        """Shutdown the proxy client."""
        self._initialized = False
        self.session_id = None
        self.tools_cache = []
        logger.info("MCP Proxy Client shutdown")