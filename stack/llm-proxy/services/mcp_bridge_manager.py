"""
MCP Bridge Manager for LLM Proxy Service

Uses HTTP bridge to communicate with MCP servers instead of direct stdio.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class MCPBridgeManager:
    """Manages MCP servers through HTTP bridge service."""
    
    def __init__(self, bridge_url: Optional[str] = None):
        self.bridge_url = bridge_url or os.getenv("MCP_BRIDGE_URL", "http://mcp-bridge:3000")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.tools_cache: List[Dict[str, Any]] = []
        self._initialized = False
        self._refresh_task = None
        self._refresh_interval = 60  # Refresh every 60 seconds
        
    async def initialize(self):
        """Initialize connection to MCP bridge and refresh tools."""
        if self._initialized:
            return
            
        logger.info(f"Connecting to MCP Bridge at {self.bridge_url}")
        
        try:
            # Check bridge status
            response = await self.client.get(f"{self.bridge_url}/status")
            response.raise_for_status()
            
            status = response.json()
            logger.info(f"MCP Bridge status: {status}")
            
            # Refresh tools cache
            await self._refresh_tools_cache()
            self._initialized = True
            
            # Start periodic refresh task
            self._refresh_task = asyncio.create_task(self._periodic_refresh())
            
            logger.info(f"MCP Bridge Manager initialized with {len(self.tools_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Bridge Manager: {e}")
            # Don't raise - allow service to start without MCP
    
    async def _refresh_tools_cache(self):
        """Refresh the tools cache from bridge."""
        try:
            response = await self.client.get(f"{self.bridge_url}/tools")
            response.raise_for_status()
            
            data = response.json()
            self.tools_cache = data.get("tools", [])
            
            # Log any errors from individual servers
            if "errors" in data:
                for server, error in data.get("errors", {}).items():
                    logger.warning(f"Server '{server}' has error: {error}")
            
            logger.info(f"Refreshed tools cache: {len(self.tools_cache)} tools available")
            
        except Exception as e:
            logger.error(f"Failed to refresh tools cache: {e}")
            self.tools_cache = []
    
    async def _periodic_refresh(self):
        """Periodically refresh tools cache."""
        while self._initialized:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self._refresh_tools_cache()
            except Exception as e:
                logger.error(f"Error in periodic refresh: {e}")
                
    async def shutdown(self):
        """Shutdown the bridge connection."""
        self._initialized = False
        
        # Cancel refresh task
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
                
        await self.client.aclose()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from all servers."""
        if not self._initialized:
            await self.initialize()
        return self.tools_cache
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the appropriate server."""
        if not self._initialized:
            await self.initialize()
        
        # Find the tool and its server
        tool_info = None
        for tool in self.tools_cache:
            if tool.get("name") == tool_name:
                tool_info = tool
                break
        
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        server_name = tool_info.get("server")
        if not server_name:
            raise RuntimeError(f"No server found for tool '{tool_name}'")
        
        # Execute via bridge
        try:
            response = await self.client.post(
                f"{self.bridge_url}/execute",
                json={
                    "toolName": tool_name,
                    "arguments": arguments,
                    "server": server_name
                }
            )
            
            # Check if request was successful
            if response.status_code >= 400:
                # Try to extract error details from response body
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', f'HTTP {response.status_code} error')
                    
                    # Extract detailed error information if available
                    if isinstance(error_message, str) and 'Details:' in error_message:
                        # This is likely an MCP error with details
                        return f"Tool execution failed: {error_message}"
                    else:
                        return f"Tool execution failed: {error_message}"
                except:
                    # If we can't parse the error response, use status text
                    return f"Tool execution failed: HTTP {response.status_code} - {response.text}"
            
            response.raise_for_status()  # This shouldn't be reached if status >= 400
            
            result = response.json()
            if result.get("success"):
                raw_result = result.get("result")
                # Handle structured content responses from MCP
                if isinstance(raw_result, list) and len(raw_result) > 0:
                    # Extract text from structured content like [{"type": "text", "text": "..."}]
                    text_parts = []
                    for item in raw_result:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    if text_parts:
                        return "\n".join(text_parts)
                    # If no text items found, try to parse nested JSON
                    elif len(raw_result) == 1 and isinstance(raw_result[0], dict):
                        # Handle nested structure like [{"type": "text", "text": '{"content": [...]}'}]
                        nested_text = raw_result[0].get("text", "")
                        if nested_text:
                            try:
                                nested_json = json.loads(nested_text)
                                if isinstance(nested_json, dict) and "content" in nested_json:
                                    # Extract from nested content array
                                    content_texts = []
                                    for content_item in nested_json.get("content", []):
                                        if isinstance(content_item, dict) and content_item.get("type") == "text":
                                            content_texts.append(content_item.get("text", ""))
                                    if content_texts:
                                        return "\n".join(content_texts)
                                return json.dumps(nested_json, indent=2)
                            except json.JSONDecodeError:
                                return nested_text
                    # Fallback to string representation
                    return str(raw_result)
                elif isinstance(raw_result, str):
                    return raw_result
                else:
                    # For other types, convert to string
                    return json.dumps(raw_result, indent=2) if raw_result else ""
            else:
                # Return error as result instead of raising exception
                error_msg = result.get('error', 'Unknown error')
                return f"Tool execution failed: {error_msg}"
                
        except httpx.HTTPStatusError as e:
            # HTTP error - extract details from response if available
            error_details = ""
            try:
                error_data = e.response.json()
                error_details = error_data.get('error', str(e))
            except:
                error_details = e.response.text or str(e)
            
            logger.error(f"HTTP error executing tool '{tool_name}': {error_details}")
            return f"Tool execution failed with HTTP {e.response.status_code}: {error_details}"
            
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            # Return error message instead of raising
            return f"Tool execution failed with error: {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of MCP bridge and servers."""
        return {
            "initialized": self._initialized,
            "bridge_url": self.bridge_url,
            "total_tools": len(self.tools_cache)
        }
    
    async def get_bridge_status(self, include_tools: bool = False) -> Dict[str, Any]:
        """Get detailed status from bridge."""
        try:
            params = {"includeTools": "true"} if include_tools else {}
            response = await self.client.get(f"{self.bridge_url}/status", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get bridge status: {e}")
            return {"error": str(e)}
    
    def format_tools_for_llm(self, tool_selection: Optional[Dict[str, Dict[str, bool]]] = None) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling with optional filtering."""
        tools_to_format = self.tools_cache
        
        # Debug: Log tool structure to understand why filtering fails
        if tool_selection and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Tool selection provided: {tool_selection}")
            logger.debug(f"Sample tool structure: {self.tools_cache[0] if self.tools_cache else 'No tools'}")
        
        # Filter tools if selection is provided
        if tool_selection:
            filtered_tools = []
            filtered_count = 0
            
            for tool in self.tools_cache:
                tool_name = tool.get("name", "")
                server_name = tool.get("server", "")
                
                # Debug logging for first few tools
                if filtered_count < 3:
                    logger.debug(f"Checking tool: {tool_name} from server: {server_name}")
                
                # Check if this tool is selected
                if (server_name in tool_selection and 
                    tool_name in tool_selection[server_name] and 
                    tool_selection[server_name][tool_name]):
                    filtered_tools.append(tool)
                    filtered_count += 1
            
            tools_to_format = filtered_tools
            logger.info(f"Filtered tools from {len(self.tools_cache)} to {len(tools_to_format)} based on selection")
            
            # If filtering resulted in too few tools, something is wrong
            if len(tools_to_format) < 10 and len(self.tools_cache) > 50:
                logger.warning(f"Tool filtering may have failed - only {len(tools_to_format)} tools selected from {len(self.tools_cache)} available")
        
        # Apply OpenAI 128 tool limit as safety net
        if len(tools_to_format) > 128:
            logger.warning(f"Tool count {len(tools_to_format)} exceeds OpenAI limit of 128. Truncating to first 128 tools.")
            tools_to_format = tools_to_format[:128]
        
        formatted_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {})
                }
            }
            for tool in tools_to_format
        ]
        
        logger.info(f"Formatted {len(formatted_tools)} tools for LLM")
        return formatted_tools
    
    async def reinitialize(self):
        """Reinitialize the bridge connection and MCP servers."""
        try:
            response = await self.client.post(f"{self.bridge_url}/reinitialize")
            response.raise_for_status()
            
            # Reset state
            self._initialized = False
            self.tools_cache = []
            
            # Reinitialize
            await self.initialize()
            
        except Exception as e:
            logger.error(f"Failed to reinitialize MCP bridge: {e}")