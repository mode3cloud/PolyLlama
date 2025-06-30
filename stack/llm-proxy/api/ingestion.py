"""
Webhook Ingestion API for Graphiti Knowledge Integration

This module provides webhook endpoints for ingesting content into the Graphiti knowledge graph
via MCP (Model Context Protocol) tools. The endpoints are protected by POLYLLAMA_API_KEY
and integrate with the existing MCP infrastructure.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# Create router with prefix for ingestion endpoints
ingestion_router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


class WebhookIngestionRequest(BaseModel):
    """
    Request model for webhook ingestion.
    
    This model defines the structure for content ingestion requests that will be
    processed and added to the Graphiti knowledge graph via MCP tools.
    """
    
    source_type: str = Field(
        ...,
        description="Type of content source",
        regex="^(email|meeting_notes|document|chat|web_content|file_upload)$"
    )
    
    text_content: str = Field(
        ...,
        description="The text content to be processed and ingested",
        min_length=1,
        max_length=100000  # Reasonable limit for text content
    )
    
    # Optional metadata fields
    title: Optional[str] = Field(
        None,
        description="Content title or subject line",
        max_length=500
    )
    
    author: Optional[str] = Field(
        None,
        description="Content author or creator",
        max_length=200
    )
    
    source_url: Optional[str] = Field(
        None,
        description="Source URL if the content originated from a web source",
        max_length=2000
    )
    
    timestamp: Optional[str] = Field(
        None,
        description="Content creation timestamp (ISO 8601 format)",
    )
    
    tags: Optional[list] = Field(
        default_factory=list,
        description="List of tags or categories for the content"
    )
    
    priority: Optional[str] = Field(
        "medium",
        description="Content priority level",
        regex="^(low|medium|high)$"
    )
    
    custom_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional custom metadata for the content"
    )
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list."""
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        return [str(tag)[:50] for tag in v]  # Limit tag length to 50 chars
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp format."""
        if v is None:
            return None
        try:
            # Try to parse the timestamp to validate format
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError("timestamp must be in ISO 8601 format")


class WebhookIngestionResponse(BaseModel):
    """Response model for webhook ingestion."""
    
    success: bool = Field(..., description="Whether the ingestion was successful")
    message: str = Field(..., description="Human-readable status message")
    episode_id: Optional[str] = Field(None, description="Generated episode ID if successful")
    entities_extracted: Optional[int] = Field(None, description="Number of entities extracted")
    relationships_created: Optional[int] = Field(None, description="Number of relationships created")
    processed_at: Optional[str] = Field(None, description="Processing timestamp")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class IngestionStatusResponse(BaseModel):
    """Response model for ingestion service status."""
    
    status: str = Field(..., description="Service status")
    mcp_connected: bool = Field(..., description="Whether MCP manager is connected")
    graphiti_available: bool = Field(..., description="Whether Graphiti MCP server is available")
    tools_count: int = Field(..., description="Number of available MCP tools")
    uptime: str = Field(..., description="Service uptime")


@ingestion_router.post("/", response_model=WebhookIngestionResponse)
async def webhook_ingest(request_data: WebhookIngestionRequest, request: Request):
    """
    Main webhook ingestion endpoint.
    
    This endpoint accepts content from various sources and processes it through
    the Graphiti knowledge graph via MCP tools. The endpoint is protected by
    POLYLLAMA_API_KEY authentication (handled by nginx).
    
    Args:
        request_data: The ingestion request containing content and metadata
        request: FastAPI request object for accessing app state
        
    Returns:
        WebhookIngestionResponse with processing results
    """
    try:
        # Get MCP manager from app state
        mcp_manager = getattr(request.app.state, 'mcp_manager', None)
        if not mcp_manager:
            logger.error("MCP manager not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP service not available"
            )
            
        # Check if MCP manager is initialized
        if not mcp_manager._initialized:
            logger.error("MCP manager not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP service not initialized"
            )
        
        # Prepare metadata for the MCP tool
        metadata = {
            "title": request_data.title,
            "author": request_data.author,
            "source_url": request_data.source_url,
            "timestamp": request_data.timestamp or datetime.now().isoformat(),
            "tags": request_data.tags,
            "priority": request_data.priority,
            **request_data.custom_metadata
        }
        
        # Remove None values from metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # Prepare arguments for the MCP add_episodes tool
        tool_args = {
            "source_type": request_data.source_type,
            "content": request_data.text_content,
            "metadata": metadata
        }
        
        logger.info(f"Processing ingestion request for source_type: {request_data.source_type}")
        logger.debug(f"Content length: {len(request_data.text_content)} characters")
        
        # Execute the add_episodes MCP tool
        try:
            result = await mcp_manager.execute_tool("add_episodes", tool_args)
            
            # Parse the result - MCP tools return the result as a string
            if isinstance(result, str):
                import json
                try:
                    result_data = json.loads(result)
                except json.JSONDecodeError:
                    # If result is not JSON, treat as plain text response
                    result_data = {"success": True, "message": result}
            else:
                result_data = result
            
            # Check if the tool execution was successful
            if result_data.get("success", False):
                logger.info(f"Successfully processed content via MCP tool: {result_data.get('episode_id', 'unknown')}")
                
                return WebhookIngestionResponse(
                    success=True,
                    message=result_data.get("message", "Content successfully ingested into knowledge graph"),
                    episode_id=result_data.get("episode_id"),
                    entities_extracted=result_data.get("entities_extracted"),
                    relationships_created=result_data.get("relationships_created"),
                    processed_at=result_data.get("processed_at")
                )
            else:
                # Tool execution failed
                error_msg = result_data.get("error", "Unknown error from MCP tool")
                logger.error(f"MCP tool execution failed: {error_msg}")
                
                return WebhookIngestionResponse(
                    success=False,
                    message="Failed to process content",
                    error=error_msg
                )
                
        except Exception as tool_error:
            logger.error(f"Error executing MCP tool 'add_episodes': {tool_error}")
            
            # Check if this is a "tool not found" error
            if "not found" in str(tool_error).lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Graphiti ingestion service not available. Please ensure the Graphiti MCP server is configured and running."
                )
            
            return WebhookIngestionResponse(
                success=False,
                message="Error processing content through knowledge graph",
                error=str(tool_error)
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions (they're handled by FastAPI)
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during content ingestion"
        )


@ingestion_router.get("/status", response_model=IngestionStatusResponse)
async def get_ingestion_status(request: Request):
    """
    Get the status of the ingestion service.
    
    This endpoint provides health information about the ingestion service,
    including MCP connectivity and Graphiti availability.
    
    Args:
        request: FastAPI request object for accessing app state
        
    Returns:
        IngestionStatusResponse with service status information
    """
    try:
        # Get MCP manager from app state
        mcp_manager = getattr(request.app.state, 'mcp_manager', None)
        
        if not mcp_manager:
            return IngestionStatusResponse(
                status="error",
                mcp_connected=False,
                graphiti_available=False,
                tools_count=0,
                uptime="unknown"
            )
        
        # Check MCP status
        mcp_status = mcp_manager.get_status()
        mcp_connected = mcp_status.get("initialized", False)
        
        # Get available tools
        tools = []
        graphiti_available = False
        if mcp_connected:
            try:
                tools = await mcp_manager.list_tools()
                # Check if add_episodes tool is available
                graphiti_available = any(tool.get("name") == "add_episodes" for tool in tools)
            except Exception as e:
                logger.warning(f"Failed to list MCP tools: {e}")
        
        # Determine overall status
        if mcp_connected and graphiti_available:
            status_value = "healthy"
        elif mcp_connected:
            status_value = "degraded"  # MCP works but Graphiti not available
        else:
            status_value = "error"  # MCP not connected
        
        return IngestionStatusResponse(
            status=status_value,
            mcp_connected=mcp_connected,
            graphiti_available=graphiti_available,
            tools_count=len(tools),
            uptime="unknown"  # Could be enhanced to track actual uptime
        )
        
    except Exception as e:
        logger.error(f"Error getting ingestion status: {e}")
        return IngestionStatusResponse(
            status="error",
            mcp_connected=False,
            graphiti_available=False,
            tools_count=0,
            uptime="unknown"
        )