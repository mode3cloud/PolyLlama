"""
Webhook ingestion API endpoints for Graphiti knowledge integration

Handles automated ingestion of data into the Graphiti knowledge base from varied sources.
"""

import logging
from typing import Optional, Any, Dict
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ingestion_router = APIRouter()


class IngestionRequest(BaseModel):
    """Request model for webhook ingestion."""
    
    source_type: str = Field(..., description="Type of source (e.g., email, meeting notes, etc.)")
    text_content: str = Field(..., description="Text content to ingest")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    source_id: Optional[str] = Field(default=None, description="Unique identifier for the source")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp of the content")


class IngestionResponse(BaseModel):
    """Response model for webhook ingestion."""
    
    status: str = Field(..., description="Status of the ingestion")
    message: str = Field(..., description="Human-readable message")
    ingestion_id: Optional[str] = Field(default=None, description="Unique identifier for this ingestion")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of processing")


@ingestion_router.post("", response_model=IngestionResponse)
async def ingest_content(request: Request, ingestion_request: IngestionRequest):
    """
    Webhook endpoint for ingesting content into Graphiti knowledge base.
    
    This endpoint accepts content from various sources and processes it for 
    knowledge graph ingestion. The actual Graphiti integration will be 
    implemented based on the specific Graphiti instance configuration.
    """
    try:
        logger.info(f"Received ingestion request for source_type: {ingestion_request.source_type}")
        
        # Validate required fields
        if not ingestion_request.text_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_content cannot be empty"
            )
        
        # Set default timestamp if not provided
        if not ingestion_request.timestamp:
            ingestion_request.timestamp = datetime.utcnow()
        
        # Log the ingestion request (for debugging/monitoring)
        logger.info(f"Processing ingestion: source_type={ingestion_request.source_type}, "
                   f"content_length={len(ingestion_request.text_content)}, "
                   f"source_id={ingestion_request.source_id}")
        
        # Get Graphiti service from app state
        graphiti_service = request.app.state.graphiti_service
        
        # Generate ingestion ID
        ingestion_id = f"ing_{ingestion_request.source_type}_{int(datetime.utcnow().timestamp())}"
        
        # Process with Graphiti service
        result = await graphiti_service.ingest_content(
            content=ingestion_request.text_content,
            source_type=ingestion_request.source_type,
            source_id=ingestion_request.source_id or ingestion_id,
            metadata=ingestion_request.metadata,
            timestamp=ingestion_request.timestamp
        )
        
        success = result.get("status") == "success"
        
        if success:
            return IngestionResponse(
                status="success",
                message=f"Content from {ingestion_request.source_type} successfully ingested",
                ingestion_id=ingestion_id,
                processed_at=datetime.utcnow()
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process content with Graphiti"
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during ingestion: {str(e)}"
        )


@ingestion_router.get("/status")
async def get_ingestion_status(request: Request):
    """
    Get the status of the ingestion service.
    
    Returns information about the ingestion service health and capabilities.
    """
    try:
        # Get Graphiti service status
        graphiti_service = request.app.state.graphiti_service
        graphiti_status = await graphiti_service.get_status()
        
        return {
            "status": "healthy",
            "service": "ingestion",
            "graphiti_status": graphiti_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting ingestion status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ingestion status"
        )


