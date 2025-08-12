"""
MCP Server for PolyLlama - Dual Transport Implementation using FastMCP
Supports both Streamable HTTP (/mcp) and SSE (/sse) transports
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and apply the dual transport patch
from services import fastmcp_dual_transport_patch  # This applies the patch automatically
from fastmcp import FastMCP

# Import our MCP bridge and manager
from services.mcp_manager import MCPManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Configuration
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "/app/mcp-config.json")
API_KEY = os.getenv("POLYLLAMA_API_KEY", "")


def display_initialization_results(servers_info):
    """Display beautiful initialization results."""
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
        'exa': '🔍',
        'ide': '💻',
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
        
        # Create FastMCP instance
        self.mcp = FastMCP(
            name=name,
            instructions="""PolyLlama MCP Server

This server provides access to PolyLlama's orchestration capabilities and aggregates tools from configured MCP servers.

Available capabilities:
- Access to all Ollama models through PolyLlama's intelligent routing
- Tool aggregation from upstream MCP servers
- Dual transport support: Streamable HTTP (/mcp) and SSE (/sse)
"""
        )
        
        # Override the tools/list and tools/call handlers to use our MCP manager
        self._setup_mcp_handlers()
        
        # MCP Manager for upstream servers
        self.mcp_manager = MCPManager(config_path=MCP_CONFIG_PATH)
    
    def _setup_mcp_handlers(self):
        """Set up custom MCP protocol handlers that use our MCP manager."""
        
        # Override the FastMCP's tools/list handler
        async def custom_list_tools():
            """List all tools from upstream MCP servers."""
            try:
                if not self.mcp_manager._initialized:
                    await self.mcp_manager.initialize()
                
                # Return the tools from our manager
                tools = await self.mcp_manager.list_tools()
                return {"tools": tools}
                
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                return {"tools": []}
        
        # Override the FastMCP's tools/call handler
        async def custom_call_tool(name: str, arguments: dict = None):
            """Call a tool from upstream MCP servers."""
            try:
                if not self.mcp_manager._initialized:
                    await self.mcp_manager.initialize()
                
                if arguments is None:
                    arguments = {}
                
                # Call the tool through our manager
                result = await self.mcp_manager.execute_tool(name, arguments)
                return {"content": [{"type": "text", "text": str(result)}]}
                
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}
        
        # Register the custom handlers with FastMCP
        # Note: We need to replace the internal handlers after FastMCP is created
        self._custom_list_tools = custom_list_tools
        self._custom_call_tool = custom_call_tool
        
    async def initialize_upstream_servers(self):
        """Initialize connections to upstream MCP servers from config."""
        try:
            if os.path.exists(MCP_CONFIG_PATH):
                await self.mcp_manager.initialize()
                
                # Get server info from the status
                status = self.mcp_manager.get_status()
                servers_info = {}
                
                # Convert status format to our display format
                for server_name, server_data in status.get("servers", {}).items():
                    if server_data.get("connected", False):
                        # Count tools for this server
                        tool_count = sum(1 for tool in self.mcp_manager.tools_cache 
                                       if tool.get("name", "").startswith(f"{server_name}__"))
                        servers_info[server_name] = {
                            'status': 'connected',
                            'tool_count': tool_count
                        }
                    else:
                        servers_info[server_name] = {
                            'status': 'failed',
                            'error': 'Connection failed',
                            'tool_count': 0
                        }
                
                # Display beautiful initialization results
                display_initialization_results(servers_info)
                
                # Store server info for later use
                self.servers_info = servers_info
                
                logger.info(f"MCP Manager initialized with {len(self.mcp_manager.tools_cache)} total tools")
            else:
                logger.warning(f"MCP config not found at {MCP_CONFIG_PATH}")
                    
        except Exception as e:
            logger.error(f"Error initializing upstream servers: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def setup_tools(self):
        """Set up tools from upstream MCP servers."""
        
        logger.info("Setting up tools from upstream MCP servers")
        
        # Get all tools from the manager (it's a list, not a dict)
        tools_list = self.mcp_manager.tools_cache
        tool_count = len(tools_list)
        
        if tool_count == 0:
            logger.warning("No tools available from upstream servers")
            return
            
        logger.info(f"Found {tool_count} tools from upstream servers")
        
        # For now, skip tool registration to avoid FastMCP **kwargs issues
        # The tools are still available through the MCP manager for direct calls
        logger.info("Skipping FastMCP tool registration due to **kwargs compatibility issues")
        logger.info("Tools are still available through the underlying MCP manager")
        
        # Override FastMCP's internal tool handlers to use our MCP manager
        self._override_fastmcp_handlers()
        
        logger.info(f"Connected to upstream servers with {tool_count} available tools")
    
    def _override_fastmcp_handlers(self):
        """Override FastMCP's internal handlers to use our MCP manager."""
        
        # Store reference to manager for use in handlers
        mcp_manager = self.mcp_manager
        
        # Override the tools/list handler
        # Return raw tool data instead of FastMCP Tool objects
        async def custom_list_tools():
            """List all tools from upstream MCP servers."""
            try:
                tools = await mcp_manager.list_tools()
                logger.info(f"Returning {len(tools)} tools to FastMCP")
                return tools  # Return raw tool dicts - let FastMCP handle them
                
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                return []
        
        # Override the tools/call handler  
        async def custom_call_tool(name: str, arguments: dict = None):
            """Call a tool from upstream MCP servers."""
            try:
                if arguments is None:
                    arguments = {}
                
                # Call the tool through our manager
                result = await mcp_manager.execute_tool(name, arguments)
                
                # Format result as MCP content
                if isinstance(result, (list, dict)):
                    content = str(result)
                else:
                    content = str(result)
                    
                return [{"type": "text", "text": content}]
                
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return [{"type": "text", "text": f"Error executing tool {name}: {str(e)}"}]
        
        # Replace FastMCP's internal MCP handlers
        self.mcp._mcp_list_tools = custom_list_tools
        self.mcp._mcp_call_tool = custom_call_tool
        
        logger.info("✅ Overrode FastMCP handlers to use MCP manager")
    
    async def run(self, transport: str = "dual"):
        """Run the MCP server with the specified transport."""
        # Initialize upstream servers
        await self.initialize_upstream_servers()
        
        # Set up tools
        logger.info("Setting up tools from upstream servers...")
        await self.setup_tools()
        logger.info("Tool setup complete")
        
        logger.info(f"Starting MCP server with transport: {transport}")
        logger.info(f"Server: {self.name} on {self.host}:{self.port}")
        
        if transport == "stdio":
            await self.mcp.run(transport="stdio")
        elif transport == "dual":
            # The patched FastMCP supports dual transport automatically
            logger.info(f"🚀 Running MCP server with DUAL transport (HTTP + SSE) on {self.host}:{self.port}")
            
            # Display available endpoints
            print(f"\n📡 Available Endpoints:")
            print(f"   🔌 HTTP: http://{self.host}:{self.port}/mcp (Streamable HTTP)")
            print(f"   📡 SSE: http://{self.host}:{self.port}/sse (Server-Sent Events)")
            print(f"   💬 Messages: http://{self.host}:{self.port}/messages/ (SSE bidirectional)")
            print(f"   ❤️  Health: http://{self.host}:{self.port}/health")
            print(f"   📊 Status: http://{self.host}:{self.port}/status")
            
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
            
            print(f"\n✨ PolyLlama MCP Server ready with DUAL transport!")
            print(f"💡 Key Features:")
            print(f"   • Streamable HTTP at /mcp")
            print(f"   • Native SSE at /sse")
            print(f"   • Tool aggregation from upstream MCP servers")
            print(f"   • Based on FastMCP with patched dual transport\n")
            
            # Get the patched app and run it with existing event loop
            app = self.mcp.streamable_http_app()
            
            # Run uvicorn server manually to avoid asyncio.run() conflict
            import uvicorn
            from uvicorn.server import Server
            
            config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
            server = Server(config)
            await server.serve()
        else:
            logger.error(f"Unsupported transport: {transport}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the PolyLlama MCP server with dual transport support"
    )
    
    parser.add_argument(
        "--transport",
        choices=["stdio", "dual"],
        default="dual",
        help="Transport to use: dual (HTTP+SSE) or stdio (default: dual)",
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
    print(f"🔐 API Key protection: {'Enabled' if API_KEY else 'Disabled'}")
    print(f"📊 Protocol: MCP 2025-06-18")
    
    server = PolyLlamaMCPServer(
        name="polyllama-mcp-aggregator",
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
        import traceback
        logger.error(traceback.format_exc())
        raise