"""
MCP Bridge Server for PolyLlama
Provides MCP tool discovery and execution via HTTP/SSE endpoints
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="MCP Bridge", version="1.0.0")

# Add CORS middleware to allow n8n and other clients to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

# Global state for MCP servers
mcp_servers: Dict[str, Dict] = {}
mcp_tools: List[Dict] = []

# Request models
class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Optional[Dict[str, Any]] = None


def load_mcp_config():
    """Load MCP configuration from file."""
    config_path = os.getenv("MCP_CONFIG_PATH", "/app/mcp-config.json")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("mcpServers", {})
    except Exception as e:
        logger.error(f"Failed to load MCP config: {e}")
        return {}


async def discover_mcp_tools():
    """Discover tools from configured MCP servers."""
    global mcp_servers, mcp_tools

    config = load_mcp_config()
    discovered_tools = []
    server_status = {}

    for server_name, server_config in config.items():
        try:
            # Check if server uses mcp-remote (HTTP-based servers)
            if "mcp-remote" in str(server_config.get("args", [])):
                # Extract URL from args
                args = server_config.get("args", [])
                url = None
                for arg in args:
                    if arg.startswith("http://"):
                        url = arg
                        break

                if url:
                    # Try to connect to HTTP-based MCP server
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                url,
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "tools/list",
                                    "params": {},
                                    "id": 1
                                },
                                timeout=5.0
                            )

                            if response.status_code == 200:
                                data = response.json()
                                if "result" in data:
                                    tools = data["result"].get("tools", [])
                                    for tool in tools:
                                        tool["server"] = server_name
                                        discovered_tools.append(tool)

                                    server_status[server_name] = {
                                        "connected": True,
                                        "tool_count": len(tools),
                                        "type": "http"
                                    }
                                    logger.info(f"Connected to {server_name}: {len(tools)} tools")
                    except Exception as e:
                        logger.warning(f"Failed to connect to {server_name}: {e}")
                        server_status[server_name] = {
                            "connected": False,
                            "error": str(e),
                            "type": "http"
                        }
            else:
                # Try to spawn stdio-based MCP server
                try:
                    command = server_config.get("command", "")
                    args = server_config.get("args", [])
                    env = os.environ.copy()
                    env.update(server_config.get("env", {}))

                    # Build the full command
                    full_command = [command] + args

                    logger.info(f"Attempting to spawn {server_name} with command: {' '.join(full_command)}")

                    # Try to initialize the server
                    proc = await asyncio.create_subprocess_exec(
                        *full_command,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env
                    )

                    # Send initialize request
                    init_request = json.dumps({
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "mcp-bridge", "version": "1.0.0"}
                        },
                        "id": 1
                    }) + "\n"

                    proc.stdin.write(init_request.encode())
                    await proc.stdin.drain()

                    # Try to read response with timeout
                    try:
                        response_line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
                        if response_line:
                            response = json.loads(response_line.decode())
                            logger.info(f"Initialized {server_name}: {response}")

                            # Request tools list
                            tools_request = json.dumps({
                                "jsonrpc": "2.0",
                                "method": "tools/list",
                                "params": {},
                                "id": 2
                            }) + "\n"

                            proc.stdin.write(tools_request.encode())
                            await proc.stdin.drain()

                            # Read tools response
                            tools_line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
                            if tools_line:
                                tools_response = json.loads(tools_line.decode())
                                tools = tools_response.get("result", {}).get("tools", [])

                                for tool in tools:
                                    tool["server"] = server_name
                                    discovered_tools.append(tool)

                                server_status[server_name] = {
                                    "connected": True,
                                    "tool_count": len(tools),
                                    "type": "stdio"
                                }
                                logger.info(f"Connected to {server_name}: {len(tools)} tools")

                            # Terminate the process for now (we'll handle persistent connections later)
                            proc.terminate()

                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for response from {server_name}")
                        proc.terminate()
                        server_status[server_name] = {
                            "connected": False,
                            "error": "Timeout waiting for response",
                            "type": "stdio"
                        }

                except FileNotFoundError:
                    logger.info(f"Command not found for {server_name}: {command} (package may not be installed yet)")
                    server_status[server_name] = {
                        "connected": False,
                        "error": f"Command not found: {command} (package may not be installed)",
                        "type": "stdio"
                    }
                except Exception as e:
                    logger.error(f"Error spawning {server_name}: {e}")
                    server_status[server_name] = {
                        "connected": False,
                        "error": str(e),
                        "type": "stdio"
                    }
        except Exception as e:
            logger.error(f"Error processing server {server_name}: {e}")
            server_status[server_name] = {
                "connected": False,
                "error": str(e)
            }

    mcp_servers = server_status
    mcp_tools = discovered_tools

    logger.info(f"MCP discovery complete: {len(discovered_tools)} tools from {len(server_status)} servers")
    return {"servers": server_status, "tools": discovered_tools}


@app.on_event("startup")
async def startup():
    """Initialize MCP discovery on startup."""
    logger.info("Starting MCP Bridge...")

    # Initial discovery attempt
    await discover_mcp_tools()

    # Schedule periodic re-discovery to pick up newly installed packages
    asyncio.create_task(periodic_tool_discovery())

    logger.info("MCP Bridge initialized")


async def periodic_tool_discovery():
    """Periodically check for new MCP servers as packages are installed."""
    import os

    last_check_installed = False
    while True:
        try:
            # Check if packages are installed
            packages_installed = os.path.exists("/app/mcp-packages-installed.flag")

            # If packages were just installed, re-discover tools
            if packages_installed and not last_check_installed:
                logger.info("MCP packages installation detected, re-discovering tools...")
                await discover_mcp_tools()
                last_check_installed = True
            elif not packages_installed:
                logger.info("Waiting for MCP packages to be installed...")

            # Wait 10 seconds before next check
            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Error in periodic discovery: {e}")
            await asyncio.sleep(30)


@app.get("/health")
async def health():
    """Health check endpoint."""
    total_servers = len(mcp_servers)
    connected_servers = sum(1 for s in mcp_servers.values() if s.get("connected"))

    # Consider the bridge healthy if it's running and can accept requests,
    # even if no MCP servers are connected (they might be HTTP-based or optional)
    is_healthy = True  # Bridge itself is operational

    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={
            "status": "ready" if connected_servers > 0 else "degraded",
            "initialized": True,
            "servers": {
                "total": total_servers,
                "connected": connected_servers
            },
            "tool_count": len(mcp_tools)
        }
    )


@app.get("/api/mcp/status")
async def get_status():
    """Get MCP bridge status."""
    return {
        "initialized": True,
        "available": len(mcp_tools) > 0,
        "servers": mcp_servers,
        "tool_count": len(mcp_tools)
    }


@app.get("/api/mcp/tools")
async def get_tools():
    """Get available tools in MCP format."""
    return {"tools": mcp_tools}


@app.get("/api/mcp/tools/formatted")
async def get_formatted_tools():
    """Get tools in OpenAI-compatible format."""
    formatted_tools = []

    for tool in mcp_tools:
        formatted = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
        }
        formatted_tools.append(formatted)

    return {"tools": formatted_tools}


@app.post("/api/mcp/execute")
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool and return the result."""

    # Find the tool and its server
    tool_server = None
    for tool in mcp_tools:
        if tool.get("name") == request.tool_name:
            tool_server = tool.get("server")
            break

    if not tool_server:
        raise HTTPException(status_code=404, detail=f"Tool {request.tool_name} not found")

    # Get server configuration
    config = load_mcp_config()
    server_config = config.get(tool_server)

    if not server_config:
        raise HTTPException(status_code=500, detail=f"Server {tool_server} configuration not found")

    # Extract URL for HTTP-based servers
    args = server_config.get("args", [])
    url = None
    for arg in args:
        if arg.startswith("http://"):
            url = arg
            break

    if not url:
        raise HTTPException(status_code=501, detail=f"Tool execution not supported for server type")

    try:
        # Execute tool via HTTP
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": request.tool_name,
                        "arguments": request.arguments or {}
                    },
                    "id": 2
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {
                        "success": True,
                        "tool_name": request.tool_name,
                        "result": data["result"]
                    }
                elif "error" in data:
                    return {
                        "success": False,
                        "tool_name": request.tool_name,
                        "error": data["error"].get("message", "Unknown error")
                    }

            return {
                "success": False,
                "tool_name": request.tool_name,
                "error": f"Server returned status {response.status_code}"
            }

    except Exception as e:
        logger.error(f"Error executing tool {request.tool_name}: {e}", exc_info=True)
        return {
            "success": False,
            "tool_name": request.tool_name,
            "error": str(e)
        }


@app.post("/api/mcp/execute/stream")
async def execute_tool_stream(request: ToolExecuteRequest):
    """Execute a tool and stream the result via SSE."""

    async def generate():
        """Generate SSE stream."""
        try:
            # Send initial event
            yield f"data: {json.dumps({'event': 'start', 'tool': request.tool_name})}\n\n"

            # Execute tool (reuse logic from execute_tool)
            result = await execute_tool(request)

            # Send result event
            if result.get("success"):
                yield f"data: {json.dumps({'event': 'result', 'success': True, 'result': result.get('result')})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'error', 'success': False, 'error': result.get('error')})}\n\n"

            # Send done event
            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/mcp/refresh")
async def refresh_tools():
    """Refresh tool discovery."""
    result = await discover_mcp_tools()
    return {
        "success": True,
        "servers": result["servers"],
        "tool_count": len(result["tools"])
    }


# SSE endpoints removed - using streamable HTTP at /mcp instead

    # Get the request body
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    request_id = body.get("id", 1)

    logger.info(f"SSE MCP request: method={method}, id={request_id}")

    async def event_generator():
        """Generate SSE events for MCP response."""
        try:
            # Handle different MCP methods
            if method == "initialize":
                result = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "prompts": {},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": "mcp-bridge",
                            "version": "1.0.0"
                        }
                    }
                }
                yield f"data: {json.dumps(result)}\n\n"

            elif method == "tools/list":
                result = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": mcp_tools
                    }
                }
                yield f"data: {json.dumps(result)}\n\n"

            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})

                # Find and execute the tool
                tool_found = False
                for tool in mcp_tools:
                    if tool.get("name") == tool_name:
                        tool_found = True
                        # TODO: Execute tool via appropriate server
                        result = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [{
                                    "type": "text",
                                    "text": f"Tool {tool_name} executed (placeholder)"
                                }]
                            }
                        }
                        yield f"data: {json.dumps(result)}\n\n"
                        break

                if not tool_found:
                    error_result = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool {tool_name} not found"
                        }
                    }
                    yield f"data: {json.dumps(error_result)}\n\n"

            else:
                # Unknown method
                error_result = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method {method} not found"
                    }
                }
                yield f"data: {json.dumps(error_result)}\n\n"

        except Exception as e:
            logger.error(f"SSE error: {e}", exc_info=True)
            error_result = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(error_result)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/mcp")
async def mcp_protocol_endpoint(request: Request):
    """
    MCP protocol endpoint for streamable HTTP transport.
    Handles MCP protocol messages and returns SSE stream for responses.
    """
    # Get accept header to determine response format
    accept_header = request.headers.get("accept", "application/json")
    
    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON: {str(e)}"}
        )
    
    # Extract MCP method and params
    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")
    
    logger.info(f"MCP request: method={method}, id={request_id}")
    
    # Handle different MCP methods
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "prompts": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "mcp-bridge",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        # Return list of available tools
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "inputSchema": tool.get("inputSchema", {})
                    }
                    for tool in mcp_tools
                ]
            }
        }
    
    elif method == "tools/call":
        # Execute tool
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        # Find and execute the tool
        tool_result = None
        for tool in mcp_tools:
            if tool.get("name") == tool_name:
                # Execute tool (simplified for now)
                tool_result = {
                    "success": True,
                    "result": f"Executed {tool_name} with args {tool_args}"
                }
                break
        
        if tool_result:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_result)
                        }
                    ]
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool {tool_name} not found"
                }
            }
    
    else:
        # Method not found
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method {method} not found"
            }
        }
    
    # Return response based on Accept header
    if "text/event-stream" in accept_header:
        # Return as SSE
        async def sse_response():
            yield f"data: {json.dumps(response)}\n\n"
        
        return StreamingResponse(
            sse_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Return as regular JSON
        return JSONResponse(content=response)


def main():
    """Run the MCP Bridge server."""
    port = int(os.getenv("MCP_SERVER_PORT", "3001"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")

    logger.info(f"Starting MCP Bridge on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()