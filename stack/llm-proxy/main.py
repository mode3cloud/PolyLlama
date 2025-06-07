"""
LLM Proxy Service

FastAPI service that handles LLM interactions using LiteLLM for provider abstraction.
"""

import logging
import sys
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
from services.multi_llm_service import MultiLLMService
from services.message_manager import MessageManager
from services.mcp_client import MCPClient
from config import LLMProxyConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PolyLlama LLM Proxy Service",
    description="LLM interactions with provider abstraction via LiteLLM",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
llm_service: MultiLLMService = None
message_manager: MessageManager = None
mcp_client: MCPClient = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global llm_service, message_manager, mcp_client
    
    logger.info("Starting PolyLlama LLM Proxy Service...")
    
    # Initialize services
    message_manager = MessageManager()
    llm_service = MultiLLMService(neo4j_driver=None)  # No Neo4j for now
    llm_service.message_manager = message_manager  # Set message manager directly
    mcp_client = MCPClient(LLMProxyConfig.MCP_SERVICE_URL)
    
    # Connect MCP client
    await mcp_client.connect()
    
    # Store in app state for access in routes
    app.state.llm_service = llm_service
    app.state.message_manager = message_manager
    app.state.mcp_client = mcp_client
    
    logger.info("PolyLlama LLM Proxy Service initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on shutdown."""
    global llm_service, message_manager, mcp_client
    
    logger.info("Shutting down PolyLlama LLM Proxy Service...")
    
    if llm_service:
        await llm_service.close()
    if mcp_client:
        await mcp_client.close()
    
    logger.info("PolyLlama LLM Proxy Service shutdown complete")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "polyllama-llm-proxy",
        "mcp_connected": mcp_client.is_connected() if mcp_client else False
    }


# Include API routers
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(models_router, prefix="/api/models", tags=["models"])


def main():
    """Main entry point for the LLM Proxy service."""
    config = LLMProxyConfig()
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()