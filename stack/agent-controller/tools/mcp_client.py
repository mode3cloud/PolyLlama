"""
MCP (Model Context Protocol) client integration for tool wrappers.

This module provides a standardized interface for integrating with MCP-enabled
services and tools, allowing seamless communication with external systems.
"""

from typing import Dict, Any, List, Optional, Union, AsyncGenerator
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime

from .base import Tool, ToolResult, ToolError, ToolStatus, ToolParameter


logger = logging.getLogger(__name__)


@dataclass
class MCPRequest:
    """Represents an MCP request."""
    method: str
    params: Dict[str, Any]
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "method": self.method,
            "params": self.params
        }
        if self.id:
            result["id"] = self.id
        return result


@dataclass
class MCPResponse:
    """Represents an MCP response."""
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPResponse":
        """Create from dictionary."""
        return cls(
            result=data.get("result"),
            error=data.get("error"),
            id=data.get("id")
        )
    
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.error is None


class MCPClientError(Exception):
    """Raised when MCP client encounters an error."""
    pass


class MCPTransport(ABC):
    """Abstract base class for MCP transport mechanisms."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to MCP service."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to MCP service."""
        pass
    
    @abstractmethod
    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send request and receive response."""
        pass
    
    @abstractmethod
    async def send_notification(self, request: MCPRequest) -> None:
        """Send notification (no response expected)."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass


class HTTPMCPTransport(MCPTransport):
    """HTTP-based MCP transport."""
    
    def __init__(self, base_url: str, timeout: float = 30.0):
        """
        Initialize HTTP transport.
        
        Args:
            base_url: Base URL for MCP service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish HTTP session."""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            # Test connection with health check
            async with self._session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    self._connected = True
                else:
                    raise MCPClientError(f"Health check failed: {response.status}")
        except ImportError:
            raise MCPClientError("aiohttp required for HTTP transport")
        except Exception as e:
            raise MCPClientError(f"Failed to connect: {str(e)}")
    
    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
    
    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send HTTP request."""
        if not self._connected or not self._session:
            raise MCPClientError("Not connected")
        
        try:
            url = f"{self.base_url}/mcp"
            headers = {"Content-Type": "application/json"}
            data = json.dumps(request.to_dict())
            
            async with self._session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    result_data = await response.json()
                    return MCPResponse.from_dict(result_data)
                else:
                    error_text = await response.text()
                    return MCPResponse(error={
                        "code": response.status,
                        "message": error_text
                    })
                    
        except Exception as e:
            return MCPResponse(error={
                "code": -1,
                "message": str(e)
            })
    
    async def send_notification(self, request: MCPRequest) -> None:
        """Send HTTP notification."""
        if not self._connected or not self._session:
            raise MCPClientError("Not connected")
        
        try:
            url = f"{self.base_url}/mcp/notify"
            headers = {"Content-Type": "application/json"}
            data = json.dumps(request.to_dict())
            
            async with self._session.post(url, data=data, headers=headers) as response:
                if response.status != 204:  # No Content expected for notifications
                    logger.warning(f"Unexpected notification response status: {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
    
    @property
    def is_connected(self) -> bool:
        """Check if HTTP transport is connected."""
        return self._connected and self._session is not None


class MockMCPTransport(MCPTransport):
    """Mock MCP transport for testing and development."""
    
    def __init__(self):
        """Initialize mock transport."""
        self._connected = False
        self._mock_responses: Dict[str, Any] = {}
    
    def set_mock_response(self, method: str, response: Any) -> None:
        """Set mock response for a method."""
        self._mock_responses[method] = response
    
    async def connect(self) -> None:
        """Mock connection."""
        await asyncio.sleep(0.1)  # Simulate connection time
        self._connected = True
    
    async def disconnect(self) -> None:
        """Mock disconnection."""
        self._connected = False
    
    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send mock request."""
        if not self._connected:
            return MCPResponse(error={"code": -1, "message": "Not connected"})
        
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Return mock response if available
        if request.method in self._mock_responses:
            return MCPResponse(result=self._mock_responses[request.method])
        
        # Default mock responses
        if request.method == "email.search":
            return MCPResponse(result={
                "emails": [
                    {
                        "id": "mock_email_1",
                        "subject": f"Mock result for: {request.params.get('query', '')}",
                        "sender": "mock@example.com",
                        "date": datetime.now().isoformat()
                    }
                ]
            })
        elif request.method == "search.web":
            return MCPResponse(result={
                "results": [
                    {
                        "title": f"Mock search result for: {request.params.get('query', '')}",
                        "url": "https://example.com/mock",
                        "snippet": "This is a mock search result..."
                    }
                ]
            })
        else:
            return MCPResponse(error={
                "code": -32601,
                "message": f"Method not found: {request.method}"
            })
    
    async def send_notification(self, request: MCPRequest) -> None:
        """Send mock notification."""
        if self._connected:
            await asyncio.sleep(0.05)  # Simulate processing
    
    @property
    def is_connected(self) -> bool:
        """Check mock connection status."""
        return self._connected


class MCPClient:
    """MCP client for communicating with MCP-enabled services."""
    
    def __init__(self, transport: MCPTransport):
        """
        Initialize MCP client.
        
        Args:
            transport: Transport mechanism for MCP communication
        """
        self.transport = transport
        self._request_id = 0
    
    def _next_request_id(self) -> str:
        """Generate next request ID."""
        self._request_id += 1
        return str(self._request_id)
    
    async def connect(self) -> None:
        """Connect to MCP service."""
        await self.transport.connect()
    
    async def disconnect(self) -> None:
        """Disconnect from MCP service."""
        await self.transport.disconnect()
    
    async def call_method(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Call MCP method.
        
        Args:
            method: Method name
            params: Method parameters
            
        Returns:
            MCP response
        """
        request = MCPRequest(
            method=method,
            params=params or {},
            id=self._next_request_id()
        )
        return await self.transport.send_request(request)
    
    async def send_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send notification (no response expected).
        
        Args:
            method: Method name
            params: Method parameters
        """
        request = MCPRequest(
            method=method,
            params=params or {}
        )
        await self.transport.send_notification(request)
    
    # Convenience methods for common operations
    async def search_emails(
        self,
        query: str,
        limit: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search emails via MCP."""
        response = await self.call_method("email.search", {
            "query": query,
            "limit": limit,
            **kwargs
        })
        
        if response.is_success():
            return response.result.get("emails", [])
        else:
            raise MCPClientError(f"Email search failed: {response.error}")
    
    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """Get email by ID via MCP."""
        response = await self.call_method("email.get", {"id": email_id})
        
        if response.is_success():
            return response.result
        else:
            raise MCPClientError(f"Get email failed: {response.error}")
    
    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search web via MCP."""
        response = await self.call_method("search.web", {
            "query": query,
            "num_results": num_results,
            **kwargs
        })
        
        if response.is_success():
            return response.result.get("results", [])
        else:
            raise MCPClientError(f"Web search failed: {response.error}")
    
    async def query_database(
        self,
        query: str,
        database: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Query database via MCP."""
        response = await self.call_method("database.query", {
            "query": query,
            "database": database,
            **kwargs
        })
        
        if response.is_success():
            return response.result
        else:
            raise MCPClientError(f"Database query failed: {response.error}")


class MCPToolAdapter:
    """Adapts MCP services to tool interface."""
    
    def __init__(self, client: MCPClient):
        """
        Initialize MCP tool adapter.
        
        Args:
            client: MCP client instance
        """
        self.client = client
    
    async def execute_tool_via_mcp(
        self,
        tool_name: str,
        method: str,
        args: Dict[str, Any]
    ) -> ToolResult:
        """
        Execute tool via MCP.
        
        Args:
            tool_name: Name of the tool
            method: MCP method to call
            args: Tool arguments
            
        Returns:
            ToolResult from MCP execution
        """
        start_time = datetime.now()
        
        try:
            response = await self.client.call_method(method, args)
            
            if response.is_success():
                execution_time = (datetime.now() - start_time).total_seconds()
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    data=response.result,
                    execution_time=execution_time,
                    metadata={
                        "mcp_method": method,
                        "tool_name": tool_name
                    }
                )
            else:
                execution_time = (datetime.now() - start_time).total_seconds()
                error_msg = response.error.get("message", "Unknown MCP error")
                return ToolResult(
                    status=ToolStatus.FAILURE,
                    error=f"MCP error: {error_msg}",
                    execution_time=execution_time,
                    metadata={
                        "mcp_method": method,
                        "mcp_error": response.error
                    }
                )
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ToolResult(
                status=ToolStatus.FAILURE,
                error=f"MCP execution failed: {str(e)}",
                execution_time=execution_time,
                metadata={"mcp_method": method}
            )


# Example enhanced tools with MCP integration
class MCPEmailSearchTool(Tool):
    """Email search tool with MCP integration."""
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        """Initialize with optional MCP client."""
        self.mcp_client = mcp_client
        self.adapter = MCPToolAdapter(mcp_client) if mcp_client else None
    
    @property
    def name(self) -> str:
        return "mcp_email_search"
    
    @property
    def description(self) -> str:
        return "Search emails using MCP-enabled email service"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Email search query",
                required=True
            ),
            ToolParameter(
                name="limit",
                type="number",
                description="Maximum results",
                required=False,
                default=10
            )
        ]
    
    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        """Execute email search via MCP."""
        if self.adapter:
            return await self.adapter.execute_tool_via_mcp(
                self.name,
                "email.search",
                args
            )
        else:
            # Fallback to mock behavior
            return ToolResult(
                status=ToolStatus.FAILURE,
                error="No MCP client configured"
            )


# Factory function for creating MCP clients
def create_mcp_client(
    transport_type: str = "mock",
    **transport_kwargs
) -> MCPClient:
    """
    Create MCP client with specified transport.
    
    Args:
        transport_type: Type of transport ("http", "mock")
        **transport_kwargs: Transport-specific arguments
        
    Returns:
        Configured MCP client
    """
    if transport_type == "http":
        transport = HTTPMCPTransport(**transport_kwargs)
    elif transport_type == "mock":
        transport = MockMCPTransport()
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")
    
    return MCPClient(transport)