"""
FastMCP Dual Transport Patch

This module patches FastMCP to support both streamable HTTP (/mcp) and SSE (/sse) 
transports simultaneously on the same server instance.
"""

import logging
from typing import Optional
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount
from starlette.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server import NotificationOptions

logger = logging.getLogger(__name__)


def patch_fastmcp_for_dual_transport():
    """
    Patch FastMCP to support both streamable HTTP and SSE transports.
    This must be called before creating any FastMCP instances.
    """
    
    # Store the original method
    _original_streamable_http_app = FastMCP.streamable_http_app
    
    def patched_app(self) -> Starlette:
        """
        Enhanced streamable_http_app that also includes SSE support.
        """
        # Get the original streamable HTTP app
        app = _original_streamable_http_app(self)
        
        # Add CORS middleware if not already present
        # Note: Starlette apps have middleware as a list, not a method
        try:
            # Try to add CORS middleware
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        except Exception:
            # Middleware might already be added
            pass
        
        # Create SSE transport
        sse_transport = SseServerTransport("/messages/")
        
        # Add SSE endpoint handler
        async def handle_sse(request: Request) -> Response:
            """Handle SSE connections."""
            try:
                # Get the MCP server instance
                mcp_server = self._mcp_server
                
                # Connect SSE transport
                async with sse_transport.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    # Create initialization options
                    init_options = mcp_server.create_initialization_options(
                        NotificationOptions(tools_changed=True)
                    )
                    
                    # Run the MCP server with SSE transport
                    await mcp_server.run(
                        streams[0],  # read_stream
                        streams[1],  # write_stream
                        init_options
                    )
                
                return Response()
                
            except Exception as e:
                logger.error(f"SSE handler error: {e}")
                return Response(
                    content=f"SSE connection error: {str(e)}",
                    status_code=500
                )
        
        # Add routes for SSE
        app.add_route("/sse", handle_sse, methods=["GET"])
        
        # Mount the SSE message handler
        app.routes.append(
            Mount("/messages/", app=sse_transport.handle_post_message)
        )
        
        # Add additional endpoints for compatibility
        
        # Health check endpoint
        async def health_check(request: Request) -> Response:
            return Response(
                content='{"status": "ok", "service": "polyllama-mcp-server-dual-transport"}',
                media_type="application/json"
            )
        
        app.add_route("/health", health_check, methods=["GET"])
        
        # Status endpoint
        async def status(request: Request) -> Response:
            # Get tool count from the MCP server
            tool_count = len(self._mcp_server._tools) if hasattr(self, '_mcp_server') else 0
            
            status_data = {
                "service": "polyllama-mcp-server-dual-transport",
                "transport": ["streamable-http", "sse"],
                "endpoints": {
                    "mcp": "/mcp",
                    "sse": "/sse",
                    "messages": "/messages/",
                    "health": "/health",
                    "status": "/status",
                    "info": "/info"
                },
                "tool_count": tool_count,
                "features": {
                    "streamingSupported": True,
                    "bidirectionalCommunication": True,
                    "dualTransport": True
                }
            }
            
            import json
            return Response(
                content=json.dumps(status_data),
                media_type="application/json"
            )
        
        app.add_route("/status", status, methods=["GET"])
        
        # Info endpoint
        async def info(request: Request) -> Response:
            # Get tools from the MCP server
            tools = []
            if hasattr(self, '_mcp_server') and hasattr(self._mcp_server, '_tools'):
                for tool_name, tool_info in self._mcp_server._tools.items():
                    tools.append({
                        "name": tool_name,
                        "description": tool_info.get('description', '')
                    })
            
            info_data = {
                "name": self.name,
                "version": "1.0.0",
                "description": "PolyLlama MCP Server with dual transport support (streamable HTTP + SSE)",
                "protocol": "streamable-http",
                "protocolVersion": "2025-03-26",
                "tools": tools,
                "endpoints": {
                    "mcp": "/mcp",
                    "sse": "/sse",
                    "messages": "/messages/",
                    "health": "/health",
                    "info": "/info",
                    "status": "/status"
                },
                "authenticationRequired": False,
                "toolCount": len(tools),
                "features": {
                    "streamingSupported": True,
                    "bidirectionalCommunication": True,
                    "dualTransport": True,
                    "connectionResumption": False
                }
            }
            
            import json
            return Response(
                content=json.dumps(info_data),
                media_type="application/json"
            )
        
        app.add_route("/info", info, methods=["GET"])
        
        logger.info("FastMCP patched for dual transport support")
        logger.info("Available endpoints: /mcp (streamable-http), /sse (SSE), /messages/ (SSE messages)")
        
        return app
    
    # Replace the method
    FastMCP.streamable_http_app = patched_app
    
    # Store reference to original method
    FastMCP._original_streamable_http_app = _original_streamable_http_app
    
    logger.info("FastMCP dual transport patch applied successfully")