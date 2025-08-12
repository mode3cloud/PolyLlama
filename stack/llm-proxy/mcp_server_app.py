"""
MCP Server Application

A standalone FastAPI app that runs the MCP server on port 3001.
This provides protocol-compliant MCP access to the aggregated tools.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from api.mcp_server import mcp_server_router
from services.mcp_manager import MCPManager
from services.mcp_server import MCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Global instances
mcp_manager: MCPManager = None
mcp_server: MCPServer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global mcp_manager, mcp_server
    
    # Startup
    logger.info("Starting PolyLlama MCP Server...")
    
    # Initialize MCP manager
    config_path = os.environ.get("MCP_CONFIG_PATH", "/app/mcp-config.json")
    mcp_manager = MCPManager(config_path=config_path)
    
    # Initialize MCP manager with resilient startup
    try:
        await mcp_manager.initialize()
        logger.info(f"MCP Manager initialized with {len(mcp_manager.tools_cache)} tools")
    except Exception as e:
        logger.error(f"Failed to initialize MCP Manager: {e}")
        # Continue anyway - tools might become available later
    
    # Create MCP server
    mcp_server = MCPServer(mcp_manager)
    
    # Store in app state for access in routes
    app.state.mcp_manager = mcp_manager
    app.state.mcp_server = mcp_server
    
    logger.info("PolyLlama MCP Server initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PolyLlama MCP Server...")
    
    if mcp_manager:
        await mcp_manager.shutdown()
    
    logger.info("PolyLlama MCP Server shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="PolyLlama MCP Server",
    description="MCP protocol server that aggregates multiple upstream MCP servers",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include MCP server router (includes all endpoints)
app.include_router(mcp_server_router)


def main():
    """Main entry point for the MCP Server."""
    port = int(os.environ.get("MCP_SERVER_PORT", "3001"))
    host = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
    
    uvicorn.run(
        "mcp_server_app:app",
        host=host,
        port=port,
        reload=os.environ.get("DEBUG", "false").lower() == "true",
        log_level="info",
    )


if __name__ == "__main__":
    main()