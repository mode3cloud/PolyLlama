"""
LLM Proxy Service

FastAPI service that handles LLM interactions, chat sessions, and tool orchestration.
Acts as a proxy between the Web UI and the MCP Tools service.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

# Add the current directory to the path so we can import from mcp_server
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from api.chat import chat_router
from api.sessions import sessions_router
from api.files import files_router
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
    title="LLM Proxy Service",
    description="LLM interactions, chat sessions, and tool orchestration",
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
    
    logger.info("Starting LLM Proxy Service...")
    
    # Initialize Neo4j connection for message persistence
    from neo4j import GraphDatabase
    neo4j_config = LLMProxyConfig.get_neo4j_config()
    neo4j_driver = GraphDatabase.driver(
        neo4j_config["uri"],
        auth=(neo4j_config["username"], neo4j_config["password"])
    )
    
    # Initialize services
    message_manager = MessageManager(neo4j_driver)
    llm_service = MultiLLMService(neo4j_driver=neo4j_driver)
    mcp_client = MCPClient(LLMProxyConfig.MCP_SERVICE_URL)
    
    # Store in app state for access in routes
    app.state.llm_service = llm_service
    app.state.message_manager = message_manager
    app.state.mcp_client = mcp_client
    
    logger.info("LLM Proxy Service initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on shutdown."""
    global llm_service, message_manager, mcp_client
    
    logger.info("Shutting down LLM Proxy Service...")
    
    if llm_service:
        await llm_service.close()
    if mcp_client:
        await mcp_client.close()
    
    logger.info("LLM Proxy Service shutdown complete")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "llm-proxy",
        "mcp_connected": mcp_client.is_connected() if mcp_client else False
    }


# Include API routers
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files_router, prefix="/api/files", tags=["files"])
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