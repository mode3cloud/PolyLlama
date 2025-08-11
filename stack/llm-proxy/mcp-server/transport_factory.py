"""
Transport Factory for MCP - Creates appropriate transports for different server types
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional
from dataclasses import dataclass

import aiohttp
from fastmcp.client.transports import StdioTransport

logger = logging.getLogger(__name__)


class SSETransport:
    """Server-Sent Events (SSE) transport for MCP."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.response: Optional[aiohttp.ClientResponse] = None
        
    async def connect(self) -> None:
        """Establish SSE connection."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        try:
            self.response = await self.session.get(
                self.url,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    **self.headers
                }
            )
            self.response.raise_for_status()
            logger.info(f"Connected to SSE endpoint: {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SSE endpoint {self.url}: {e}")
            raise
    
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request over SSE and receive response."""
        if not self.response:
            await self.connect()
        
        # For SSE, we typically POST to a different endpoint
        # and receive events through the SSE stream
        request_url = self.url.replace('/events', '/request')
        
        async with self.session.post(
            request_url,
            json=request,
            headers=self.headers
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def receive_event(self) -> Optional[Dict[str, Any]]:
        """Receive an event from the SSE stream."""
        if not self.response:
            return None
        
        async for line in self.response.content:
            line = line.decode('utf-8').strip()
            
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse SSE data: {data}")
                    continue
        
        return None
    
    async def close(self) -> None:
        """Close the SSE connection."""
        if self.response:
            self.response.close()
        
        if self.session:
            await self.session.close()
        
        logger.info(f"Closed SSE connection to {self.url}")


class StreamableHTTPTransport:
    """Streamable HTTP transport for MCP (supports streaming responses)."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def connect(self) -> None:
        """Initialize HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            logger.info(f"Initialized HTTP session for {self.url}")
    
    async def send_request(
        self, 
        request: Dict[str, Any], 
        stream: bool = False
    ) -> Any:
        """Send HTTP request and handle response."""
        if not self.session:
            await self.connect()
        
        headers = {
            'Content-Type': 'application/json',
            **self.headers
        }
        
        if stream:
            headers['Accept'] = 'text/event-stream'
        
        try:
            async with self.session.post(
                self.url,
                json=request,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                if stream:
                    # Return async generator for streaming
                    return self._stream_response(response)
                else:
                    # Return complete response
                    return await response.json()
                    
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise
    
    async def _stream_response(self, response: aiohttp.ClientResponse):
        """Stream response data."""
        async for line in response.content:
            line = line.decode('utf-8').strip()
            
            if line.startswith('data: '):
                data = line[6:]
                if data == '[DONE]':
                    break
                    
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse streaming data: {data}")
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            logger.info(f"Closed HTTP session for {self.url}")


class WebSocketTransport:
    """WebSocket transport for MCP (for bidirectional communication)."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        try:
            self.ws = await self.session.ws_connect(
                self.url,
                headers=self.headers
            )
            logger.info(f"Connected to WebSocket: {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket {self.url}: {e}")
            raise
    
    async def send_request(self, request: Dict[str, Any]) -> None:
        """Send request over WebSocket."""
        if not self.ws:
            await self.connect()
        
        await self.ws.send_json(request)
    
    async def receive_response(self) -> Optional[Dict[str, Any]]:
        """Receive response from WebSocket."""
        if not self.ws:
            return None
        
        msg = await self.ws.receive()
        
        if msg.type == aiohttp.WSMsgType.TEXT:
            return json.loads(msg.data)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            logger.error(f"WebSocket error: {msg.data}")
            return None
        elif msg.type == aiohttp.WSMsgType.CLOSED:
            logger.info("WebSocket connection closed")
            return None
        
        return None
    
    async def close(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
        
        if self.session:
            await self.session.close()
        
        logger.info(f"Closed WebSocket connection to {self.url}")


class TransportFactory:
    """Factory for creating appropriate MCP transports."""
    
    @staticmethod
    async def create_transport(server_config: Dict[str, Any]) -> Any:
        """Create appropriate transport based on server configuration."""
        server_type = server_config.get('type', 'stdio')
        
        if server_type == 'stdio':
            # Standard I/O transport (default)
            return StdioTransport(
                command=server_config.get('command'),
                args=server_config.get('args', []),
                env=server_config.get('env')
            )
            
        elif server_type == 'sse':
            # Server-Sent Events transport
            transport = SSETransport(
                url=server_config.get('url'),
                headers=server_config.get('headers', {})
            )
            await transport.connect()
            return transport
            
        elif server_type == 'streamable_http':
            # Streamable HTTP transport
            transport = StreamableHTTPTransport(
                url=server_config.get('url'),
                headers=server_config.get('headers', {})
            )
            await transport.connect()
            return transport
            
        elif server_type == 'websocket':
            # WebSocket transport
            transport = WebSocketTransport(
                url=server_config.get('url'),
                headers=server_config.get('headers', {})
            )
            await transport.connect()
            return transport
            
        else:
            raise ValueError(f"Unknown transport type: {server_type}")
    
    @staticmethod
    def detect_transport_type(server_config: Dict[str, Any]) -> str:
        """Auto-detect transport type from server configuration."""
        # Check for explicit type
        if 'type' in server_config:
            return server_config['type']
        
        # Check for URL patterns
        if 'url' in server_config:
            url = server_config['url']
            
            if url.startswith('ws://') or url.startswith('wss://'):
                return 'websocket'
            elif '/events' in url or '/sse' in url:
                return 'sse'
            else:
                return 'streamable_http'
        
        # Check for command (STDIO)
        if 'command' in server_config:
            return 'stdio'
        
        # Default to STDIO
        return 'stdio'
    
    @staticmethod
    async def create_client_for_transport(transport: Any):
        """Create appropriate client for a transport."""
        from fastmcp.client import Client
        
        if isinstance(transport, StdioTransport):
            # FastMCP native support
            return Client(transport)
            
        elif isinstance(transport, (SSETransport, StreamableHTTPTransport, WebSocketTransport)):
            # Create adapter for custom transports
            return MCPTransportAdapter(transport)
        
        else:
            raise ValueError(f"Unsupported transport type: {type(transport)}")


class MCPTransportAdapter:
    """Adapter to make custom transports compatible with FastMCP Client interface."""
    
    def __init__(self, transport: Any):
        self.transport = transport
        self._connected = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        if hasattr(self.transport, 'connect'):
            await self.transport.connect()
        self._connected = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self.transport, 'close'):
            await self.transport.close()
        self._connected = False
    
    async def list_tools(self) -> list:
        """List available tools."""
        request = {
            'jsonrpc': '2.0',
            'method': 'tools/list',
            'params': {},
            'id': 'list_tools'
        }
        
        response = await self.transport.send_request(request)
        
        if 'result' in response:
            return response['result'].get('tools', [])
        
        return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with arguments."""
        request = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': tool_name,
                'arguments': arguments
            },
            'id': f'call_{tool_name}'
        }
        
        if isinstance(self.transport, StreamableHTTPTransport):
            # Handle streaming response
            response_stream = await self.transport.send_request(request, stream=True)
            
            # Collect streaming response
            result = []
            async for chunk in response_stream:
                if 'result' in chunk:
                    result.append(chunk['result'])
            
            return result if result else None
            
        else:
            # Handle regular response
            response = await self.transport.send_request(request)
            
            if 'result' in response:
                return response['result']
            elif 'error' in response:
                raise Exception(f"Tool call error: {response['error']}")
            
            return None


class TransportHealthMonitor:
    """Monitor transport health and automatically reconnect if needed."""
    
    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self.transports: Dict[str, Any] = {}
        self.health_status: Dict[str, Dict[str, Any]] = {}
        self._monitoring = False
        self._monitor_task = None
    
    def add_transport(self, name: str, transport: Any):
        """Add a transport to monitor."""
        self.transports[name] = transport
        self.health_status[name] = {
            'status': 'unknown',
            'last_check': None,
            'error_count': 0,
            'reconnect_count': 0
        }
    
    def remove_transport(self, name: str):
        """Remove a transport from monitoring."""
        if name in self.transports:
            del self.transports[name]
            del self.health_status[name]
    
    async def start_monitoring(self):
        """Start health monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started transport health monitoring")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped transport health monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            for name, transport in list(self.transports.items()):
                await self._check_transport_health(name, transport)
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_transport_health(self, name: str, transport: Any):
        """Check health of a single transport."""
        try:
            # Perform health check based on transport type
            if isinstance(transport, StdioTransport):
                # For STDIO, check if process is still running
                # This would require access to the underlying process
                pass
                
            elif isinstance(transport, SSETransport):
                # For SSE, check if connection is still alive
                if transport.response and not transport.response.closed:
                    self.health_status[name]['status'] = 'healthy'
                else:
                    await self._reconnect_transport(name, transport)
                    
            elif isinstance(transport, StreamableHTTPTransport):
                # For HTTP, send a ping request
                ping_request = {'jsonrpc': '2.0', 'method': 'ping', 'id': 'health_check'}
                try:
                    await asyncio.wait_for(
                        transport.send_request(ping_request),
                        timeout=5.0
                    )
                    self.health_status[name]['status'] = 'healthy'
                except:
                    await self._reconnect_transport(name, transport)
                    
            elif isinstance(transport, WebSocketTransport):
                # For WebSocket, check if connection is open
                if transport.ws and not transport.ws.closed:
                    self.health_status[name]['status'] = 'healthy'
                else:
                    await self._reconnect_transport(name, transport)
            
            self.health_status[name]['last_check'] = asyncio.get_event_loop().time()
            
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            self.health_status[name]['status'] = 'error'
            self.health_status[name]['error_count'] += 1
    
    async def _reconnect_transport(self, name: str, transport: Any):
        """Attempt to reconnect a transport."""
        logger.info(f"Attempting to reconnect transport: {name}")
        
        try:
            # Close existing connection
            if hasattr(transport, 'close'):
                await transport.close()
            
            # Reconnect
            if hasattr(transport, 'connect'):
                await transport.connect()
            
            self.health_status[name]['status'] = 'healthy'
            self.health_status[name]['reconnect_count'] += 1
            logger.info(f"Successfully reconnected transport: {name}")
            
        except Exception as e:
            logger.error(f"Failed to reconnect transport {name}: {e}")
            self.health_status[name]['status'] = 'failed'
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health report for all monitored transports."""
        return {
            'monitoring': self._monitoring,
            'transports': self.health_status.copy()
        }