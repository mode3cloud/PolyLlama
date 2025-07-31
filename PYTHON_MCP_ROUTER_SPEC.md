# Python MCP Router Specification

## Overview

This specification outlines the implementation of a Python-based MCP (Model Context Protocol) router that replicates the functionality of the [mcp-router](https://github.com/mcp-router/mcp-router) project but works on Linux without the GUI dependency. The router will use `mcp-config.json` for configuration and provide a unified interface for managing multiple MCP servers.

## Architecture Overview

### Core Principles

1. **Configuration-Driven**: Use `mcp-config.json` for all server configurations
2. **Cross-Platform**: Pure Python implementation for Linux compatibility  
3. **Protocol Compatibility**: Full MCP protocol compliance with existing tools
4. **Headless Operation**: No GUI dependency, CLI and HTTP API driven
5. **Security**: Built-in authentication, logging, and access control
6. **Performance**: Efficient routing with connection pooling and caching

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Python MCP Router                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   HTTP Server   │  │   CLI Interface │  │  Config Manager │ │
│  │   (FastAPI)     │  │   (Click/Typer) │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  MCP Router     │  │  Tool Registry  │  │ Session Manager │ │
│  │   Core          │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Server Manager  │  │ Health Monitor  │  │   Logging &     │ │
│  │                 │  │                 │  │   Analytics     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│           MCP Server Connections (Subprocess Management)        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Server A      │  │   Server B      │  │   Server N      │ │
│  │  (GitHub)       │  │  (Browser)      │  │  (Custom)       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Project Structure

```
mcp_router/
├── __init__.py
├── main.py                     # Entry point
├── cli.py                      # CLI interface
├── config/
│   ├── __init__.py
│   ├── manager.py              # Configuration management
│   ├── schema.py               # Pydantic models
│   └── validator.py            # Config validation
├── core/
│   ├── __init__.py
│   ├── router.py               # Main routing logic
│   ├── server_manager.py       # MCP server lifecycle
│   ├── tool_registry.py        # Tool discovery and management
│   └── session.py              # Session management
├── transport/
│   ├── __init__.py
│   ├── stdio.py                # STDIO transport
│   ├── http.py                 # HTTP transport
│   └── sse.py                  # Server-Sent Events
├── api/
│   ├── __init__.py
│   ├── app.py                  # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── mcp.py              # MCP protocol endpoints
│   │   ├── servers.py          # Server management
│   │   └── health.py           # Health and status
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py             # Authentication
│       └── logging.py          # Request logging
├── monitoring/
│   ├── __init__.py
│   ├── health.py               # Health checking
│   ├── metrics.py              # Performance metrics
│   └── alerts.py               # Alert system
└── utils/
    ├── __init__.py
    ├── logging.py              # Logging utilities
    ├── security.py             # Security utilities
    └── helpers.py              # General utilities
```

### 2. Configuration System

#### mcp-config.json Schema

```json
{
  "mcpServers": {
    "server-name": {
      "command": "string",
      "args": ["string"],
      "env": {
        "ENV_VAR": "value"
      },
      "enabled": true,
      "autoStart": true,
      "timeout": 30,
      "retries": 3,
      "healthCheck": {
        "enabled": true,
        "interval": 30,
        "timeout": 5
      },
      "security": {
        "allowedMethods": ["tools/list", "tools/call"],
        "rateLimiting": {
          "enabled": true,
          "requestsPerMinute": 60
        }
      }
    }
  },
  "router": {
    "host": "0.0.0.0",
    "port": 3001,
    "logLevel": "INFO",
    "authentication": {
      "enabled": false,
      "apiKey": "optional-api-key"
    },
    "cors": {
      "enabled": true,
      "origins": ["*"]
    }
  },
  "monitoring": {
    "enabled": true,
    "healthCheckInterval": 30,
    "metricsRetention": 86400
  }
}
```

#### Configuration Manager Implementation

```python
# config/manager.py
from pathlib import Path
from typing import Dict, Any, Optional
import json
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import ValidationError

from .schema import RouterConfig
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = "mcp-config.json"):
        self.config_path = Path(config_path)
        self.config: Optional[RouterConfig] = None
        self.observers: list = []
        self._lock = asyncio.Lock()
        
    async def load_config(self) -> RouterConfig:
        """Load and validate configuration from file."""
        async with self._lock:
            try:
                if not self.config_path.exists():
                    logger.warning(f"Config file {self.config_path} not found, creating default")
                    await self._create_default_config()
                
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                
                self.config = RouterConfig(**config_data)
                logger.info(f"Configuration loaded from {self.config_path}")
                return self.config
                
            except ValidationError as e:
                logger.error(f"Invalid configuration: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise
    
    async def save_config(self, config: RouterConfig):
        """Save configuration to file."""
        async with self._lock:
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(config.dict(), f, indent=2)
                self.config = config
                logger.info("Configuration saved successfully")
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")
                raise
    
    def watch_config(self, callback):
        """Watch configuration file for changes."""
        class ConfigHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path == str(self.config_path):
                    asyncio.create_task(callback())
        
        observer = Observer()
        observer.schedule(ConfigHandler(), str(self.config_path.parent), recursive=False)
        observer.start()
        self.observers.append(observer)
```

### 3. Core Router Implementation

#### Main Router Logic

```python
# core/router.py
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import uuid

from ..config.manager import ConfigManager
from ..transport.stdio import StdioTransport
from .server_manager import ServerManager
from .tool_registry import ToolRegistry
from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class MCPRequest:
    jsonrpc: str
    method: str
    params: Optional[Dict[str, Any]]
    id: Optional[str]

@dataclass
class MCPResponse:
    jsonrpc: str
    id: Optional[str]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

class MCPRouter:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.server_manager = ServerManager(config_manager)
        self.tool_registry = ToolRegistry()
        self.sessions: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize the router and start configured servers."""
        config = await self.config_manager.load_config()
        await self.server_manager.initialize()
        
        # Start enabled servers
        for server_name, server_config in config.mcpServers.items():
            if server_config.enabled and server_config.autoStart:
                await self.server_manager.start_server(server_name)
        
        # Populate tool registry
        await self.tool_registry.discover_tools(self.server_manager)
        
    async def handle_request(self, request_data: Dict[str, Any], session_id: Optional[str] = None) -> MCPResponse:
        """Handle incoming MCP request and route to appropriate server."""
        try:
            request = MCPRequest(**request_data)
            
            if request.method == "initialize":
                return await self._handle_initialize(request, session_id)
            elif request.method == "tools/list":
                return await self._handle_tools_list(request)
            elif request.method == "tools/call":
                return await self._handle_tools_call(request)
            elif request.method == "resources/list":
                return await self._handle_resources_list(request)
            elif request.method == "prompts/list":
                return await self._handle_prompts_list(request)
            else:
                return MCPResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    error={"code": -32601, "message": f"Method not found: {request.method}"}
                )
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return MCPResponse(
                jsonrpc="2.0",
                id=request_data.get("id"),
                error={"code": -32603, "message": str(e)}
            )
    
    async def _handle_initialize(self, request: MCPRequest, session_id: str) -> MCPResponse:
        """Handle MCP initialize request."""
        protocol_version = request.params.get("protocolVersion", "2025-03-26")
        
        # Store session information
        self.sessions[session_id] = {
            "protocol_version": protocol_version,
            "initialized": True,
            "created_at": asyncio.get_event_loop().time()
        }
        
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "python-mcp-router",
                    "version": "1.0.0"
                }
            }
        )
    
    async def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request by aggregating from all servers."""
        tools = await self.tool_registry.get_all_tools()
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={"tools": tools}
        )
    
    async def _handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request by routing to appropriate server."""
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        # Find which server owns this tool
        server_name = await self.tool_registry.get_tool_server(tool_name)
        if not server_name:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32602, "message": f"Tool not found: {tool_name}"}
            )
        
        # Route to the appropriate server
        result = await self.server_manager.call_tool(server_name, tool_name, arguments)
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result=result
        )
```

### 4. Server Management

#### Server Manager Implementation

```python
# core/server_manager.py
import asyncio
import subprocess
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import json
import signal
import time

from ..transport.stdio import StdioTransport
from ..config.manager import ConfigManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ServerConnection:
    name: str
    process: Optional[subprocess.Popen] = None
    transport: Optional[StdioTransport] = None
    status: str = "stopped"  # stopped, starting, running, error
    last_health_check: Optional[float] = None
    error_count: int = 0
    tools: list = field(default_factory=list)

class ServerManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.connections: Dict[str, ServerConnection] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize server manager."""
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
    async def start_server(self, server_name: str) -> bool:
        """Start a specific MCP server."""
        config = await self.config_manager.load_config()
        server_config = config.mcpServers.get(server_name)
        
        if not server_config:
            logger.error(f"Server configuration not found: {server_name}")
            return False
            
        if server_name in self.connections:
            connection = self.connections[server_name]
            if connection.status == "running":
                logger.info(f"Server {server_name} is already running")
                return True
            elif connection.status == "starting":
                logger.info(f"Server {server_name} is already starting")
                return False
        
        logger.info(f"Starting MCP server: {server_name}")
        connection = ServerConnection(name=server_name, status="starting")
        self.connections[server_name] = connection
        
        try:
            # Prepare environment
            env = dict(os.environ)
            env.update(server_config.env or {})
            
            # Start process
            process = subprocess.Popen(
                [server_config.command] + (server_config.args or []),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            # Create transport
            transport = StdioTransport(process)
            connection.process = process
            connection.transport = transport
            
            # Initialize MCP connection
            await self._initialize_server_connection(connection, server_config)
            
            connection.status = "running"
            logger.info(f"Successfully started server: {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server {server_name}: {e}")
            connection.status = "error"
            connection.error_count += 1
            return False
    
    async def stop_server(self, server_name: str) -> bool:
        """Stop a specific MCP server."""
        if server_name not in self.connections:
            return False
            
        connection = self.connections[server_name]
        logger.info(f"Stopping server: {server_name}")
        
        try:
            if connection.transport:
                await connection.transport.close()
            
            if connection.process:
                connection.process.terminate()
                try:
                    connection.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    connection.process.kill()
                    connection.process.wait()
            
            connection.status = "stopped"
            logger.info(f"Successfully stopped server: {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping server {server_name}: {e}")
            return False
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific server."""
        if server_name not in self.connections:
            raise Exception(f"Server not found: {server_name}")
            
        connection = self.connections[server_name]
        if connection.status != "running" or not connection.transport:
            raise Exception(f"Server not running: {server_name}")
        
        # Extract original tool name (remove server prefix if present)
        original_tool_name = tool_name
        if tool_name.startswith(f"{server_name}__"):
            original_tool_name = tool_name[len(f"{server_name}__"):]
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": original_tool_name,
                "arguments": arguments
            }
        }
        
        response = await connection.transport.send_request(request)
        
        if "error" in response:
            raise Exception(f"Tool call failed: {response['error']}")
            
        return response.get("result", {})
```

### 5. HTTP API Server

#### FastAPI Application

```python
# api/app.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import json
import uuid

from ..core.router import MCPRouter
from ..config.manager import ConfigManager
from .middleware.auth import AuthMiddleware
from .middleware.logging import LoggingMiddleware

app = FastAPI(title="Python MCP Router", version="1.0.0")

# Global router instance
router: Optional[MCPRouter] = None
config_manager: Optional[ConfigManager] = None

async def get_router() -> MCPRouter:
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router

@app.on_event("startup")
async def startup_event():
    global router, config_manager
    config_manager = ConfigManager()
    router = MCPRouter(config_manager)
    await router.initialize()

@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    router: MCPRouter = Depends(get_router)
):
    """Main MCP protocol endpoint."""
    try:
        data = await request.json()
        session_id = request.headers.get("x-session-id", str(uuid.uuid4()))
        
        # Check if streaming is requested
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            return StreamingResponse(
                stream_mcp_response(router, data, session_id),
                media_type="text/event-stream"
            )
        
        # Standard JSON response
        response = await router.handle_request(data, session_id)
        return response.__dict__
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def stream_mcp_response(router: MCPRouter, data: dict, session_id: str):
    """Stream MCP response for long-running operations."""
    try:
        response = await router.handle_request(data, session_id)
        
        # Send the response as server-sent event
        yield f"data: {json.dumps(response.__dict__)}\n\n"
        
    except Exception as e:
        error_response = {
            "jsonrpc": "2.0",
            "id": data.get("id"),
            "error": {"code": -32603, "message": str(e)}
        }
        yield f"data: {json.dumps(error_response)}\n\n"

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/servers")
async def list_servers(router: MCPRouter = Depends(get_router)):
    """List all configured servers and their status."""
    servers = []
    for name, connection in router.server_manager.connections.items():
        servers.append({
            "name": name,
            "status": connection.status,
            "error_count": connection.error_count,
            "last_health_check": connection.last_health_check,
            "tools_count": len(connection.tools)
        })
    return {"servers": servers}

@app.post("/servers/{server_name}/start")
async def start_server(server_name: str, router: MCPRouter = Depends(get_router)):
    """Start a specific server."""
    success = await router.server_manager.start_server(server_name)
    if success:
        return {"message": f"Server {server_name} started successfully"}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to start server {server_name}")

@app.post("/servers/{server_name}/stop")
async def stop_server(server_name: str, router: MCPRouter = Depends(get_router)):
    """Stop a specific server."""
    success = await router.server_manager.stop_server(server_name)
    if success:
        return {"message": f"Server {server_name} stopped successfully"}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to stop server {server_name}")
```

### 6. Command Line Interface

#### CLI Implementation

```python
# cli.py
import click
import asyncio
import json
from pathlib import Path

from .config.manager import ConfigManager
from .core.router import MCPRouter
from .api.app import app
import uvicorn

@click.group()
def cli():
    """Python MCP Router - Manage multiple MCP servers from a unified interface."""
    pass

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=3001, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(config, host, port, reload):
    """Start the MCP router HTTP server."""
    click.echo(f"Starting Python MCP Router on {host}:{port}")
    click.echo(f"Using configuration: {config}")
    
    # Set global config path
    import os
    os.environ["MCP_CONFIG_PATH"] = config
    
    uvicorn.run(
        "mcp_router.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
def status(config):
    """Show status of all configured servers."""
    async def _status():
        config_manager = ConfigManager(config)
        router = MCPRouter(config_manager)
        await router.initialize()
        
        click.echo("\nMCP Server Status:")
        click.echo("-" * 50)
        
        for name, connection in router.server_manager.connections.items():
            status_color = "green" if connection.status == "running" else "red"
            click.echo(f"{name}: ", nl=False)
            click.secho(connection.status, fg=status_color)
            if connection.tools:
                click.echo(f"  Tools: {len(connection.tools)}")
            if connection.error_count > 0:
                click.echo(f"  Errors: {connection.error_count}")
    
    asyncio.run(_status())

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
@click.argument("server_name")
def start(config, server_name):
    """Start a specific MCP server."""
    async def _start():
        config_manager = ConfigManager(config)
        router = MCPRouter(config_manager)
        await router.initialize()
        
        success = await router.server_manager.start_server(server_name)
        if success:
            click.secho(f"Successfully started {server_name}", fg="green")
        else:
            click.secho(f"Failed to start {server_name}", fg="red")
    
    asyncio.run(_start())

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
@click.argument("server_name")
def stop(config, server_name):
    """Stop a specific MCP server."""
    async def _stop():
        config_manager = ConfigManager(config)
        router = MCPRouter(config_manager)
        await router.initialize()
        
        success = await router.server_manager.stop_server(server_name)
        if success:
            click.secho(f"Successfully stopped {server_name}", fg="green")
        else:
            click.secho(f"Failed to stop {server_name}", fg="red")
    
    asyncio.run(_stop())

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
def tools(config):
    """List all available tools from configured servers."""
    async def _tools():
        config_manager = ConfigManager(config)
        router = MCPRouter(config_manager)
        await router.initialize()
        
        tools = await router.tool_registry.get_all_tools()
        
        click.echo("\nAvailable Tools:")
        click.echo("-" * 50)
        
        for tool in tools:
            click.echo(f"• {tool['name']}")
            if tool.get('description'):
                click.echo(f"  {tool['description']}")
            click.echo(f"  Server: {tool.get('server', 'unknown')}")
            click.echo()
    
    asyncio.run(_tools())

@cli.command()
@click.option("--config", default="mcp-config.json", help="Configuration file path")
def validate(config):
    """Validate the configuration file."""
    try:
        config_manager = ConfigManager(config)
        asyncio.run(config_manager.load_config())
        click.secho("Configuration is valid!", fg="green")
    except Exception as e:
        click.secho(f"Configuration error: {e}", fg="red")

if __name__ == "__main__":
    cli()
```

### 7. Transport Layer

#### STDIO Transport Implementation

```python
# transport/stdio.py
import asyncio
import json
import uuid
from typing import Dict, Any, Optional
import subprocess

from ..utils.logging import get_logger

logger = get_logger(__name__)

class StdioTransport:
    def __init__(self, process: subprocess.Popen):
        self.process = process
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._writer_queue = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._closed = False
        
    async def start(self):
        """Start the transport reader and writer tasks."""
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._writer_task = asyncio.create_task(self._writer_loop())
        
    async def close(self):
        """Close the transport and cleanup resources."""
        self._closed = True
        
        if self._reader_task:
            self._reader_task.cancel()
        if self._writer_task:
            self._writer_task.cancel()
            
        # Cancel all pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        
        self._pending_requests.clear()
        
    async def send_request(self, request: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Send a request and wait for response."""
        if self._closed:
            raise Exception("Transport is closed")
            
        request_id = request.get("id", str(uuid.uuid4()))
        request["id"] = request_id
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            # Queue the request for sending
            await self._writer_queue.put(request)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise Exception(f"Request timeout after {timeout}s")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise
    
    async def _reader_loop(self):
        """Read responses from the process stdout."""
        try:
            while not self._closed and self.process.poll() is None:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.readline
                )
                
                if not line:
                    break
                    
                try:
                    response = json.loads(line.strip())
                    await self._handle_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {line.strip()}: {e}")
                    
        except Exception as e:
            logger.error(f"Reader loop error: {e}")
        finally:
            # Mark transport as closed and cancel pending requests
            self._closed = True
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(Exception("Transport closed"))
    
    async def _writer_loop(self):
        """Write requests to the process stdin."""
        try:
            while not self._closed:
                request = await self._writer_queue.get()
                
                if request is None:  # Shutdown signal
                    break
                    
                request_line = json.dumps(request) + "\n"
                
                await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdin.write, request_line
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdin.flush
                )
                
        except Exception as e:
            logger.error(f"Writer loop error: {e}")
    
    async def _handle_response(self, response: Dict[str, Any]):
        """Handle incoming response from the server."""
        request_id = response.get("id")
        
        if request_id and request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(response)
        else:
            # Handle notifications or unexpected responses
            logger.debug(f"Received response without pending request: {response}")
```

### 8. Installation and Usage

#### Requirements

```txt
# requirements.txt
fastapi>=0.104.0
uvicorn>=0.24.0
click>=8.1.0
pydantic>=2.5.0
watchdog>=3.0.0
aiofiles>=23.2.1
python-multipart>=0.0.6
```

#### Installation Script

```bash
#!/bin/bash
# install.sh

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .

echo "Python MCP Router installed successfully!"
echo "Usage:"
echo "  mcp-router serve                    # Start HTTP server"
echo "  mcp-router status                   # Show server status"
echo "  mcp-router start <server-name>      # Start specific server"
echo "  mcp-router stop <server-name>       # Stop specific server"
echo "  mcp-router tools                    # List available tools"
```

#### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install -e .

# Expose port
EXPOSE 3001

# Default command
CMD ["mcp-router", "serve", "--host", "0.0.0.0", "--port", "3001"]
```

#### Docker Compose Integration

```yaml
# Add to docker-compose.yml.j2
mcp-router:
  build:
    context: ./stack/mcp-router
  container_name: mcp-router
  ports:
    - "3001:3001"
  volumes:
    - ./mcp-config.json:/app/mcp-config.json:ro
  environment:
    - MCP_CONFIG_PATH=/app/mcp-config.json
    - LOG_LEVEL=INFO
  networks:
    - polyllama-network
  depends_on:
    - llm-proxy
  restart: unless-stopped
```

## Migration Strategy

### Phase 1: Implementation
1. Implement core router functionality
2. Add STDIO transport support  
3. Create basic HTTP API server
4. Develop CLI interface

### Phase 2: Integration
1. Replace current mcp-server with mcp-router in docker-compose
2. Update configuration to use new format
3. Test compatibility with existing MCP clients
4. Verify tool routing works correctly

### Phase 3: Enhancement
1. Add monitoring and metrics
2. Implement authentication and security features
3. Add configuration validation and hot-reload
4. Optimize performance and add caching

### Phase 4: Production
1. Add comprehensive error handling
2. Implement graceful shutdown
3. Add logging and debugging capabilities
4. Create documentation and examples

## Compatibility Notes

### MCP Protocol Compatibility
- Full support for MCP protocol version 2025-03-26
- Compatible with existing MCP clients (Claude Desktop, Cline, etc.)
- Supports both standard JSON-RPC and Server-Sent Events transport
- Maintains tool namespacing (server__tool_name format)

### Configuration Migration
- Existing mcp-config.json files are fully compatible
- Additional configuration options are optional
- Backward compatibility with all existing server configurations

### Performance Considerations
- Efficient subprocess management with proper cleanup
- Connection pooling and health checking
- Caching of tool discovery results
- Async/await throughout for better concurrency

## Security Features

### Authentication
- Optional API key authentication
- Rate limiting per server/tool
- Request logging and audit trails

### Isolation
- Each MCP server runs in separate subprocess
- Environment variable isolation
- Resource usage monitoring

### Configuration Security
- Input validation on all configuration
- Secure handling of environment variables
- File permission checks

This specification provides a comprehensive foundation for implementing a Python-based MCP router that fully replaces the current Node.js implementation while maintaining compatibility and adding Linux support.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Research mcp-router architecture and functionality", "status": "completed", "priority": "high"}, {"id": "2", "content": "Analyze current mcp-server implementation", "status": "completed", "priority": "high"}, {"id": "3", "content": "Create comprehensive Python MCP router specification", "status": "completed", "priority": "high"}]