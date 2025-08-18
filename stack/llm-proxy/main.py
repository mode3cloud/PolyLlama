"""
LLM Proxy Service

FastAPI service that handles LLM interactions using LiteLLM for provider abstraction.
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

from api.chat import chat_router
from api.sessions import sessions_router
from api.models import models_router
from api.mcp import mcp_router
from api.mcp_server import mcp_server_router
from services.multi_llm_service import MultiLLMService
from services.message_manager import MessageManager
from services.mcp_manager import MCPManager
from services.mcp_proxy_client import MCPProxyClient
from services.mcp_server import MCPServer
from services.audio_service_api import AudioServiceAPI
from config import LLMProxyConfig

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Global service instances
llm_service: MultiLLMService
message_manager: MessageManager
mcp_manager: MCPManager
audio_service: AudioServiceAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global llm_service, message_manager, mcp_manager, audio_service

    # Startup
    logger.info("Starting PolyLlama LLM Proxy Service...")

    # Initialize services
    message_manager = MessageManager(redis_url=LLMProxyConfig.REDIS_URL)
    llm_service = MultiLLMService()  # No Neo4j for now
    llm_service.message_manager = message_manager  # Set message manager directly
    
    # Check if we should use proxy client or direct connection
    # Use proxy client if MCP server is running separately
    use_proxy = os.environ.get("USE_MCP_PROXY", "true").lower() == "true"
    
    if use_proxy:
        # Use proxy client to connect to MCP server on port 3001
        logger.info("Using MCP proxy client to connect to MCP server")
        mcp_manager = MCPProxyClient(mcp_server_url="http://localhost:3001")
    else:
        # Direct connection to MCP servers
        config_path = os.environ.get("MCP_CONFIG_PATH", "/app/mcp-config.json")
        mcp_manager = MCPManager(config_path=config_path)

    # Initialize audio service
    audio_service = AudioServiceAPI(
        api_base=LLMProxyConfig.KOKORO_API_BASE,
        timeout=LLMProxyConfig.KOKORO_API_TIMEOUT,
    )
    try:
        await audio_service.initialize()
        logger.info("Audio service initialized successfully")
    except Exception as e:
        logger.warning("Failed to initialize audio service (non-critical): %s", e)

    # Initialize MCP manager with resilient startup
    # Run in background to not block startup if MCP server isn't ready yet
    async def init_mcp_background():
        """Initialize MCP Manager in background with retry logic."""
        try:
            # Wait a bit for MCP server to start up if using proxy
            if use_proxy:
                await asyncio.sleep(5)  # Give MCP server more time to start
            else:
                await asyncio.sleep(2)
                
            await mcp_manager.initialize()
            
            if hasattr(mcp_manager, 'tools_cache'):
                logger.info(f"MCP Manager background initialization complete with {len(mcp_manager.tools_cache)} tools")
            else:
                logger.info("MCP Manager background initialization complete")
        except Exception as e:
            logger.error(f"MCP Manager background initialization failed: {e}")
    
    # Start background initialization
    asyncio.create_task(init_mcp_background())
    logger.info("MCP Manager initialization started in background")

    # Store in app state for access in routes
    app.state.llm_service = llm_service
    app.state.message_manager = message_manager
    app.state.mcp_manager = mcp_manager
    app.state.audio_service = audio_service

    logger.info("PolyLlama LLM Proxy Service initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PolyLlama LLM Proxy Service...")

    if llm_service:
        await llm_service.close()
    if message_manager:
        await message_manager.close()
    if mcp_manager:
        await mcp_manager.shutdown()
    if audio_service:
        await audio_service.close()

    logger.info("PolyLlama LLM Proxy Service shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="PolyLlama LLM Proxy Service",
    description="LLM interactions with provider abstraction via LiteLLM",
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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "polyllama-llm-proxy",
        "mcp_connected": mcp_manager._initialized if mcp_manager else False,
    }


# Include API routers
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(models_router, prefix="/api/models", tags=["models"])
app.include_router(mcp_router, tags=["mcp"])
app.include_router(mcp_server_router, tags=["mcp-server"])


def main():
    """Main entry point for the LLM Proxy service."""
    config = LLMProxyConfig()

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info",
    )


if __name__ == "__main__":
    main()
