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
from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
from mcp import types

from mcp_bridge import MCPBridge
from patched_fastmcp import patch_fastmcp_for_dual_transport

# Apply the dual transport patch before creating any FastMCP instances
patch_fastmcp_for_dual_transport()

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
        
        self.mcp = FastMCP(
            name=name,
            host=host,
            port=port,
            instructions="""PolyLlama MCP Server

This server provides access to PolyLlama's orchestration capabilities and aggregates tools from configured MCP servers.

Available capabilities:
- Access to all Ollama models through PolyLlama's intelligent routing
- Tool aggregation from upstream MCP servers
- Streamable HTTP and SSE transport support
"""
        )
        
        # Add custom routes after initialization if needed
        # Note: FastMCP doesn't support custom routes directly, so SSE endpoints
        # will be handled by the underlying transport
        
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
    
    def setup_tools(self):
        """Set up the available tools."""
        
        # Commented out hardcoded Ollama tools - we only use upstream MCP tools
        # @self.mcp.tool()
        # async def list_models() -> str:
        #     """List all available models in PolyLlama."""
        #     try:
        #         headers = {}
        #         if API_KEY:
        #             headers["api-key"] = API_KEY
        #             
        #         async with aiohttp.ClientSession() as session:
        #             async with session.get(
        #                 f"{OLLAMA_BASE_URL}/api/tags",
        #                 headers=headers
        #             ) as response:
        #                 if response.status == 200:
        #                     data = await response.json()
        #                     models = data.get("models", [])
        #                     model_names = [m["name"] for m in models]
        #                     return f"Available models: {', '.join(model_names)}"
        #                 else:
        #                     return f"Error listing models: {response.status}"
        #     except Exception as e:
        #         return f"Error: {str(e)}"
        
        # @self.mcp.tool()
        # async def generate_completion(
        #     model: str,
        #     prompt: str,
        #     system: Optional[str] = None,
        #     temperature: float = 0.7
        # ) -> str:
        #     """Generate a completion using a PolyLlama model."""
        #     try:
        #         headers = {"Content-Type": "application/json"}
        #         if API_KEY:
        #             headers["api-key"] = API_KEY
        #         
        #         payload = {
        #             "model": model,
        #             "prompt": prompt,
        #             "temperature": temperature,
        #             "stream": False
        #         }
        #         
        #         if system:
        #             payload["system"] = system
        #         
        #         async with aiohttp.ClientSession() as session:
        #             async with session.post(
        #                 f"{OLLAMA_BASE_URL}/api/generate",
        #                 headers=headers,
        #                 json=payload
        #             ) as response:
        #                 if response.status == 200:
        #                     data = await response.json()
        #                     return data.get("response", "")
        #                 else:
        #                     return f"Error generating completion: {response.status}"
        #     except Exception as e:
        #         return f"Error: {str(e)}"
        
        # @self.mcp.tool()
        # async def get_model_info(model: str) -> Dict[str, Any]:
        #     """Get detailed information about a specific model."""
        #     try:
        #         headers = {}
        #         if API_KEY:
        #             headers["api-key"] = API_KEY
        #         
        #         async with aiohttp.ClientSession() as session:
        #             async with session.post(
        #                 f"{OLLAMA_BASE_URL}/api/show",
        #                 headers=headers,
        #                 json={"name": model}
        #             ) as response:
        #                 if response.status == 200:
        #                     return await response.json()
        #                 else:
        #                     return {"error": f"Model not found: {response.status}"}
        #     except Exception as e:
        #         return {"error": str(e)}
        
        # Register aggregated tools from upstream MCP servers
        tools = self.mcp_bridge.get_all_tools()
        logger.info(f"Registering {len(tools)} tools from upstream MCP servers")
        
        # Debug: print tool names
        if tools:
            logger.info(f"Tools to register: {list(tools.keys())[:5]}...")  # Show first 5
        
        for tool_name, tool_info in tools.items():
            # Create a closure to capture the tool name
            def make_tool_handler(captured_name, captured_info):
                async def handler(**kwargs):
                    """Dynamic handler for upstream MCP tool."""
                    try:
                        result = await self.mcp_bridge.call_tool(captured_name, kwargs)
                        return result
                    except Exception as e:
                        return f"Error calling {captured_name}: {str(e)}"
                
                # Set the function name and docstring
                handler.__name__ = captured_name
                handler.__doc__ = captured_info.get('description', f'Tool from {captured_info.get("server", "unknown")}')
                return handler
            
            # Create and register the tool handler
            tool_handler = make_tool_handler(tool_name, tool_info)
            self.mcp.tool(name=tool_name, description=tool_info.get('description', ''))(tool_handler)
        
        # Log registration complete
        logger.info(f"Tool registration complete")
    
    # Note: FastMCP handles transport negotiation automatically at the /mcp endpoint
    # based on the Accept header. SSE clients should send Accept: text/event-stream
    # while regular HTTP clients should send Accept: application/json
    
    async def run(self, transport: str = "sse"):
        """Run the MCP server with the specified transport."""
        # Initialize upstream servers
        await self.initialize_upstream_servers()
        
        # Set up tools
        logger.info("About to call setup_tools()")
        self.setup_tools()
        logger.info("Finished setup_tools()")
        
        logger.info(f"Starting MCP server with transport: {transport}")
        logger.info(f"Server: {self.name} on {self.host}:{self.port}")
        logger.info(f"PolyLlama endpoint: {OLLAMA_BASE_URL}")
        
        if transport == "stdio":
            await self.mcp.run_stdio_async()
        elif transport == "sse":
            # FastMCP will handle SSE transport properly - using streamable-http for SSE  
            logger.info(f"🚀 Running MCP server with SSE transport on {self.host}:{self.port}")
            
            # Display available endpoints
            print(f"\n📡 Available Endpoints:")
            print(f"   📊 Main MCP: http://{self.host}:{self.port}/mcp (Streamable HTTP)")
            print(f"   📡 SSE: http://{self.host}:{self.port}/sse (Server-Sent Events)")
            print(f"   💬 Messages: http://{self.host}:{self.port}/messages/ (SSE Messages)")
            print(f"   🔍 Health: http://{self.host}:{self.port}/health")
            print(f"   📈 Status: http://{self.host}:{self.port}/status")
            print(f"   ℹ️  Info: http://{self.host}:{self.port}/info")
            
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
            
            print(f"\n✨ PolyLlama MCP Server ready for connections!")
            print(f"💡 Key Features:")
            print(f"   • Dual transport support: /mcp (HTTP) and /sse (SSE)")
            print(f"   • Single server instance for both protocols")
            print(f"   • Beautiful initialization logging")
            print(f"   • Tool aggregation from upstream MCP servers")
            print(f"   • FastMCP-based architecture with patch enhancement\n")
            
            await self.mcp.run_streamable_http_async()
        elif transport == "streamable-http":
            logger.info(f"🚀 Running MCP server with Streamable HTTP transport on {self.host}:{self.port}")
            await self.mcp.run_streamable_http_async()
        else:
            logger.error(f"Unsupported transport: {transport}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the PolyLlama MCP server"
    )
    
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default="sse",
        help="Transport to use for communication (default: sse)",
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