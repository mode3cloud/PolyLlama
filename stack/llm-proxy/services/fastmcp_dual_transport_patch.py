"""
FastMCP Dual Transport Patch for PolyLlama

This module patches FastMCP to support both streamable HTTP (/mcp) and SSE (/sse) 
transports simultaneously on the same server instance.

Based on the personal-ai-mcp-servers implementation approach.
"""

import logging
import os

# Import FastMCP from the external fastmcp package (which is what we're using)
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.routing import Mount
from mcp.server.sse import SseServerTransport
from mcp.server.lowlevel.server import NotificationOptions

logger = logging.getLogger(__name__)

# Enable debug logging for this module
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def patch_fastmcp_for_dual_transport():
    """
    Patch FastMCP to support both streamable HTTP and SSE transports.
    This must be called before creating any FastMCP instances.
    """
    
    logger.info("Starting FastMCP dual transport patch")
    
    # Store the original method - internal FastMCP only has streamable_http_app
    _original_streamable_http_app = FastMCP.streamable_http_app
    
    logger.info(f"Found streamable_http_app: {_original_streamable_http_app is not None}")
    
    def patched_app(self, *args, **kwargs):
        """
        Enhanced app method that also includes SSE support.
        Returns a Starlette app with both /mcp (HTTP) and /sse (SSE) endpoints.
        """
        logger.info(f"PATCHED APP METHOD CALLED with args={args}, kwargs={kwargs}")
        
        # Get the original streamable HTTP app as the base
        logger.info("Using original streamable_http_app")
        app = _original_streamable_http_app(self, *args, **kwargs)
        
        # Add CORS middleware for cross-origin support
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for development
            allow_credentials=True,
            allow_methods=["*"],  # Allow all methods
            allow_headers=["*"],  # Allow all headers
        )
        
        # Create SSE transport with message endpoint
        sse_transport = SseServerTransport("/messages/")
        
        # Store reference to the FastMCP instance
        fastmcp_instance = self
        
        # Add SSE endpoint handler
        async def handle_sse(request: Request) -> Response:
            """Handle SSE connections for MCP protocol."""
            try:
                logger.info("SSE connection established")
                
                # Get the MCP server instance from FastMCP
                mcp_server = fastmcp_instance._mcp_server
                
                # Establish SSE connection
                async with sse_transport.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    # Create initialization options with notifications enabled
                    init_options = mcp_server.create_initialization_options(
                        NotificationOptions(tools_changed=True)
                    )
                    
                    # Run the MCP server protocol with SSE streams
                    await mcp_server.run(
                        streams[0],  # read_stream
                        streams[1],  # write_stream
                        init_options
                    )
                
                # Return empty response as required by SSE transport
                return Response()
                
            except Exception as e:
                logger.error(f"SSE handler error: {e}", exc_info=True)
                return Response(
                    content=f"SSE connection error: {str(e)}",
                    status_code=500
                )
        
        # Add SSE routes
        app.add_route("/sse", handle_sse, methods=["GET"])
        
        # Mount the SSE message handler for bidirectional communication
        app.routes.append(
            Mount("/messages/", app=sse_transport.handle_post_message)
        )
        
        # Add health check endpoint
        async def health_check(request: Request) -> Response:
            """Health check endpoint for monitoring."""
            return JSONResponse(
                content={
                    "status": "ok",
                    "service": "polyllama-mcp-server",
                    "transport": ["streamable-http", "sse"],
                    "endpoints": {
                        "mcp": "/mcp",
                        "sse": "/sse",
                        "messages": "/messages/",
                        "health": "/health"
                    }
                },
                status_code=200
            )
        
        app.add_route("/health", health_check, methods=["GET"])
        
        # Add status endpoint with tool information
        async def status(request: Request) -> Response:
            """Status endpoint showing available tools and configuration."""
            try:
                # Get tool count from the MCP server
                tool_count = 0
                tool_names = []
                
                if hasattr(fastmcp_instance, '_mcp_server'):
                    mcp_server = fastmcp_instance._mcp_server
                    if hasattr(mcp_server, '_tool_handlers'):
                        tool_count = len(mcp_server._tool_handlers)
                        tool_names = list(mcp_server._tool_handlers.keys())
                
                status_data = {
                    "service": "polyllama-mcp-server-dual-transport",
                    "transport": ["streamable-http", "sse"],
                    "endpoints": {
                        "mcp": "/mcp (Streamable HTTP)",
                        "sse": "/sse (Server-Sent Events)",
                        "messages": "/messages/ (SSE Messages)",
                        "health": "/health",
                        "status": "/status"
                    },
                    "tool_count": tool_count,
                    "tools": tool_names[:10] if tool_names else [],  # Show first 10 tools
                    "features": {
                        "streamingSupported": True,
                        "bidirectionalCommunication": True,
                        "dualTransport": True,
                        "corsEnabled": True
                    }
                }
                
                return JSONResponse(content=status_data)
                
            except Exception as e:
                logger.error(f"Status endpoint error: {e}")
                return JSONResponse(
                    content={"error": f"Failed to get status: {str(e)}"},
                    status_code=500
                )
        
        app.add_route("/status", status, methods=["GET"])
        
        # Add root endpoint for basic information
        async def root(request: Request) -> Response:
            """Root endpoint providing service information."""
            return JSONResponse(
                content={
                    "name": "PolyLlama MCP Server",
                    "version": "1.0.0",
                    "description": "MCP server with dual transport support (HTTP + SSE)",
                    "endpoints": {
                        "mcp": "http://localhost:3001/mcp",
                        "sse": "http://localhost:3001/sse",
                        "health": "http://localhost:3001/health",
                        "status": "http://localhost:3001/status"
                    }
                }
            )
        
        app.add_route("/", root, methods=["GET"])
        
        logger.info("FastMCP patched for dual transport support")
        logger.info("Available endpoints:")
        logger.info("  - /mcp (Streamable HTTP)")
        logger.info("  - /sse (Server-Sent Events)")
        logger.info("  - /messages/ (SSE message handler)")
        logger.info("  - /health (Health check)")
        logger.info("  - /status (Service status)")
        
        return app
    
    # Replace the streamable_http_app method with our patched version
    logger.info("Patching streamable_http_app method")
    FastMCP.streamable_http_app = patched_app
    FastMCP._original_streamable_http_app = _original_streamable_http_app
    
    logger.info("FastMCP dual transport patch applied successfully")
    logger.info(f"FastMCP.streamable_http_app is patched: {FastMCP.streamable_http_app == patched_app}")
    logger.info(f"FastMCP has _original_streamable_http_app: {hasattr(FastMCP, '_original_streamable_http_app')}")


# Apply the patch immediately when this module is imported
print("🔧 APPLYING FASTMCP DUAL TRANSPORT PATCH...")
patch_fastmcp_for_dual_transport()
print("✅ PATCH APPLICATION COMPLETE")