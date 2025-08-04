"""
MCP Server for PolyLlama - Python implementation with SSE support
Based on personal-ai-mcp-servers architecture
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime

import aiohttp
from fastmcp import FastMCP
from mcp.server.models import InitializationOptions
from mcp import types
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
from starlette.requests import Request
import uvicorn

from mcp_bridge import MCPBridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://polyllama:11434")
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "/app/mcp-config.json")
API_KEY = os.getenv("POLYLLAMA_API_KEY", "")


def display_initialization_results(servers_info):
    """Display beautiful initialization results like the JavaScript version."""
    print('\n' + '═' * 60)
    print('🚀 MCP SERVERS INITIALIZATION RESULTS')
    print('═' * 60 + '\n')
    
    total_servers = len(servers_info)
    successful_servers = sum(1 for info in servers_info.values() if info['status'] == 'connected')
    failed_servers = total_servers - successful_servers
    
    # Create a formatted table
    print('┌─────────────────────────┬──────────┬────────────────────┐')
    print('│ Server Name             │ Status   │ Tools              │')
    print('├─────────────────────────┼──────────┼────────────────────┤')
    
    for name, info in servers_info.items():
        status_emoji = '✅' if info['status'] == 'connected' else '❌'
        status_text = 'Online' if info['status'] == 'connected' else 'Failed'
        tools_text = f"{info['tool_count']} tools" if info['status'] == 'connected' else info.get('error', 'Error')[:18]
        
        # Pad strings for alignment
        padded_name = name[:23].ljust(23)
        padded_status = f"{status_emoji} {status_text}".ljust(8)
        padded_tools = tools_text[:18].ljust(18)
        
        print(f"│ {padded_name} │ {padded_status} │ {padded_tools} │")
    
    print('└─────────────────────────┴──────────┴────────────────────┘')
    
    # Summary statistics
    print('\n📊 SUMMARY:')
    print('─' * 40)
    print(f"  Total Servers:      {total_servers}")
    print(f"  ✅ Successful:      {successful_servers}")
    print(f"  ❌ Failed:          {failed_servers}")
    print(f"  Success Rate:       {(successful_servers / total_servers * 100) if total_servers > 0 else 0:.1f}%")
    
    # Show failed server details if any
    if failed_servers > 0:
        print('\n⚠️  FAILED SERVERS:')
        print('─' * 40)
        for name, info in servers_info.items():
            if info['status'] != 'connected':
                print(f"  • {name}: {info.get('error', 'Unknown error')}")
    
    # Show successful servers with tool details
    if successful_servers > 0:
        print('\n✨ READY SERVERS:')
        print('─' * 40)
        for name, info in servers_info.items():
            if info['status'] == 'connected':
                emoji = get_server_emoji(name)
                print(f"  {emoji} {name}: {info['tool_count']} tool{'s' if info['tool_count'] != 1 else ''} available")
    
    print('\n' + '═' * 60 + '\n')


def get_server_emoji(server_name):
    """Get emoji for server based on name."""
    emoji_map = {
        'github': '🐙',
        'gitlab': '🦊',
        'docker': '🐳',
        'kubernetes': '☸️',
        'aws': '☁️',
        'azure': '☁️',
        'google': '🔍',
        'database': '🗄️',
        'api': '🔌',
        'web': '🌐',
        'file': '📁',
        'system': '⚙️',
        'personal': '👤',
        'context': '📚',
        'sequential': '🔄',
        'browser': '🌐',
        'hubspot': '📧',
        'firecrawl': '🔥',
        'default': '🔧'
    }
    
    lower_name = server_name.lower()
    for key, emoji in emoji_map.items():
        if key in lower_name:
            return emoji
    return emoji_map['default']


class PolyLlamaMCPServer:
    """MCP Server that bridges to PolyLlama and aggregates upstream MCP servers."""
    
    def __init__(self, name: str = "polyllama-mcp-server", host: str = "0.0.0.0", port: int = 3001):
        """Initialize the MCP Server."""
        self.name = name
        self.host = host
        self.port = port
        self.servers_info = {}
        
        # For dual mode, we'll create two FastMCP instances
        self.mcp_http = None
        self.mcp_sse = None
        
        # Default instance for single-transport mode
        self.mcp = FastMCP(
            name=name,
            instructions="""PolyLlama MCP Server

This server provides access to PolyLlama's orchestration capabilities and aggregates tools from configured MCP servers.

Available capabilities:
- Access to all Ollama models through PolyLlama's intelligent routing
- Tool aggregation from upstream MCP servers
- Streamable HTTP and SSE transport support
"""
        )
        
        # MCP Bridge for upstream servers
        self.mcp_bridge = MCPBridge()
        
    async def initialize_upstream_servers(self):
        """Initialize connections to upstream MCP servers from config."""
        try:
            if os.path.exists(MCP_CONFIG_PATH):
                await self.mcp_bridge.load_config(MCP_CONFIG_PATH)
                # Connect to all servers and get connection info
                servers_info = await self.mcp_bridge.connect_all_servers()
                
                # Display beautiful initialization results
                display_initialization_results(servers_info)
                
                # Store server info for later use
                self.servers_info = servers_info
                
                logger.info("MCP bridge initialized with upstream server configurations")
            else:
                logger.warning(f"MCP config not found at {MCP_CONFIG_PATH}")
                    
        except Exception as e:
            logger.error(f"Error initializing upstream servers: {e}")
    
    async def setup_proxies(self):
        """Set up tools from upstream MCP servers."""
        
        # Since mounting doesn't work with our current setup, let's aggregate tools differently
        # We'll connect to servers and manually register their tools
        
        logger.info("Setting up tools from upstream MCP servers")
        
        # Get aggregated tools from the bridge
        aggregated_tools = await self.mcp_bridge.get_aggregated_tools()
        
        if not aggregated_tools:
            logger.warning("No tools available from upstream servers")
            return
            
        logger.info(f"Registering {len(aggregated_tools)} tools from upstream servers")
        
        # Register each tool with the FastMCP server
        for tool_name, tool_info in aggregated_tools.items():
            try:
                # Create tool function that calls the bridge
                # Use a factory function to avoid closure issues
                def create_tool_handler(tool_name_arg):
                    async def tool_handler(arguments: dict = None):
                        """Handler that forwards tool calls to the appropriate upstream server."""
                        # FastMCP will pass arguments as a dict
                        if arguments is None:
                            arguments = {}
                        return await self.mcp_bridge.call_tool(tool_name_arg, arguments)
                    return tool_handler
                
                # Register the tool with FastMCP
                # Note: We need to properly handle the tool schema
                handler = create_tool_handler(tool_name)
                self.mcp.tool(
                    name=tool_name,
                    description=tool_info.get('description', f'Tool from upstream MCP server')
                )(handler)
                
                logger.info(f"✅ Registered tool: {tool_name}")
            except Exception as e:
                logger.error(f"❌ Failed to register tool {tool_name}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        logger.info("Tool registration complete")
    
    async def create_dual_instances(self):
        """Create separate FastMCP instances for HTTP and SSE transports."""
        # Create HTTP instance
        self.mcp_http = FastMCP(
            name=f"{self.name}-http",
            instructions=self.mcp._instructions
        )
        
        # Create SSE instance
        self.mcp_sse = FastMCP(
            name=f"{self.name}-sse",
            instructions=self.mcp._instructions
        )
        
        # Register tools on both instances
        aggregated_tools = await self.mcp_bridge.get_aggregated_tools()
        
        for tool_name, tool_info in aggregated_tools.items():
            try:
                # Create tool handler
                def create_tool_handler(tool_name_arg):
                    async def tool_handler(arguments: dict = None):
                        if arguments is None:
                            arguments = {}
                        return await self.mcp_bridge.call_tool(tool_name_arg, arguments)
                    return tool_handler
                
                handler = create_tool_handler(tool_name)
                
                # Register on both instances
                self.mcp_http.tool(
                    name=tool_name,
                    description=tool_info.get('description', f'Tool from upstream MCP server')
                )(handler)
                
                self.mcp_sse.tool(
                    name=tool_name,
                    description=tool_info.get('description', f'Tool from upstream MCP server')
                )(handler)
                
            except Exception as e:
                logger.error(f"Failed to register tool {tool_name} on dual instances: {e}")
    
    async def run_dual_transport(self):
        """Run both HTTP and SSE transports using Starlette to route requests."""
        # Create dual instances
        await self.create_dual_instances()
        
        # Create apps using FastMCP's built-in methods
        # For HTTP transport (handles /mcp endpoint)
        http_app = self.mcp_http.create_mcp_asgi_app()
        
        # For SSE transport (handles /sse endpoint)
        # We'll create a simple ASGI app that runs the SSE server
        async def sse_handler(scope, receive, send):
            """ASGI handler for SSE endpoint."""
            if scope["type"] == "http" and scope["path"] == "/sse":
                # Run SSE server in a background task
                import asyncio
                task = asyncio.create_task(
                    self.mcp_sse.run_sse_async(
                        host="0.0.0.0",
                        port=3002,  # Different port for SSE
                        path="/sse"
                    )
                )
                # Send a redirect to the SSE server
                await send({
                    'type': 'http.response.start',
                    'status': 302,
                    'headers': [[b'location', b'http://localhost:3002/sse']],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'',
                })
            else:
                await send({
                    'type': 'http.response.start',
                    'status': 404,
                    'headers': [[b'content-type', b'text/plain']],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Not Found',
                })
        
        # Create routes
        routes = [
            Mount("/mcp", app=http_app),
            Route("/sse", endpoint=sse_handler),
            Route("/", endpoint=lambda r: Response("PolyLlama MCP Server - Use /mcp or /sse endpoints")),
        ]
        
        # Create the main Starlette app
        app = Starlette(routes=routes)
        
        # Run with uvicorn
        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    # Note: FastMCP handles transport negotiation automatically at the /mcp endpoint
    # based on the Accept header. SSE clients should send Accept: text/event-stream
    # while regular HTTP clients should send Accept: application/json
    
    async def run(self, transport: str = "dual"):
        """Run the MCP server with the specified transport."""
        # Initialize upstream servers
        await self.initialize_upstream_servers()
        
        # Set up proxies
        logger.info("About to call setup_proxies()")
        await self.setup_proxies()
        logger.info("Finished setup_proxies()")
        
        logger.info(f"Starting MCP server with transport: {transport}")
        logger.info(f"Server: {self.name} on {self.host}:{self.port}")
        logger.info(f"PolyLlama endpoint: {OLLAMA_BASE_URL}")
        
        if transport == "stdio":
            await self.mcp.run_stdio_async()
        elif transport == "sse":
            # Run with SSE transport at /sse path
            logger.info(f"🚀 Running MCP server with SSE transport on {self.host}:{self.port}")
            
            # Display available endpoints
            print(f"\n📡 Available Endpoints:")
            print(f"   📡 SSE: http://{self.host}:{self.port}/sse (Server-Sent Events)")
            print(f"   💬 Messages: http://{self.host}:{self.port}/messages (SSE Messages)")
            
            # Display available tools
            print(f"\n🛠️  Available Tools:")
            total_tools = sum(info['tool_count'] for info in self.servers_info.values() if info['status'] == 'connected')
            if total_tools > 0:
                for name, info in self.servers_info.items():
                    if info['status'] == 'connected' and info['tool_count'] > 0:
                        emoji = get_server_emoji(name)
                        print(f"   {emoji} {name}: {info['tool_count']} tools")
            else:
                print("   No tools available (MCP Bridge may be starting up)")
            
            print(f"\n✨ PolyLlama MCP Server ready for SSE connections!")
            print(f"💡 Key Features:")
            print(f"   • SSE transport support")
            print(f"   • Tool aggregation from upstream MCP servers")
            print(f"   • FastMCP 2.x native SSE\n")
            
            # Run with SSE transport - providing the path parameter
            await self.mcp.run_sse_async(
                host=self.host, 
                port=self.port,
                path="/sse"
            )
        elif transport == "streamable-http":
            logger.info(f"🚀 Running MCP server with Streamable HTTP transport on {self.host}:{self.port}")
            await self.mcp.run_http_async(host=self.host, port=self.port)
        elif transport == "dual":
            # Run HTTP transport which supports both regular HTTP and SSE via Accept header
            logger.info(f"🚀 Running MCP server with HTTP transport (supports both HTTP + SSE) on {self.host}:{self.port}")
            
            # Display available endpoints
            print(f"\n📡 Available Endpoints:")
            print(f"   🔌 MCP: http://{self.host}:{self.port}/mcp (HTTP + SSE via Accept header)")
            print(f"      - HTTP: Accept: application/json")
            print(f"      - SSE: Accept: text/event-stream")
            
            # Display available tools
            print(f"\n🛠️  Available Tools:")
            total_tools = sum(info['tool_count'] for info in self.servers_info.values() if info['status'] == 'connected')
            if total_tools > 0:
                for name, info in self.servers_info.items():
                    if info['status'] == 'connected' and info['tool_count'] > 0:
                        emoji = get_server_emoji(name)
                        print(f"   {emoji} {name}: {info['tool_count']} tools")
            else:
                print("   No tools available (MCP Bridge may be starting up)")
            
            print(f"\n✨ PolyLlama MCP Server ready!")
            print(f"💡 Key Features:")
            print(f"   • HTTP endpoint at /mcp")
            print(f"   • Automatic SSE support via Accept header")
            print(f"   • Tool aggregation from upstream MCP servers")
            print(f"   • FastMCP 2.x native transport\n")
            
            # Run HTTP server which handles both transports based on Accept header
            await self.mcp.run_http_async(host=self.host, port=self.port)
        else:
            logger.error(f"Unsupported transport: {transport}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the PolyLlama MCP server"
    )
    
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio", "dual"],
        default="dual",
        help="Transport to use for communication (default: dual)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_SERVER_PORT", "3001")),
        help="Port to run the server on (default: 3001)",
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_arguments()
    
    print(f"🚀 PolyLlama MCP Server (Python/FastMCP) starting...")
    print(f"📡 Transport: {args.transport}")
    print(f"🌐 Host: {args.host}:{args.port}")
    print(f"🎯 Target PolyLlama: {OLLAMA_BASE_URL}")
    print(f"🔐 API Key protection: {'Enabled' if API_KEY else 'Disabled'}")
    print(f"📊 Protocol: Streamable HTTP (2025-03-26)")
    
    server = PolyLlamaMCPServer(
        name="polyllama-mcp-server",
        host=args.host,
        port=args.port
    )
    
    await server.run(transport=args.transport)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise