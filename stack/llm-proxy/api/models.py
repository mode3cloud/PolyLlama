"""
Model management API endpoints for LLM Proxy Service

Handles model listing and capability checks.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import litellm

logger = logging.getLogger(__name__)

models_router = APIRouter()


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    name: str
    provider: str
    size: Optional[int] = None
    supports_vision: Optional[bool] = None


class ModelListResponse(BaseModel):
    """Response model for model listing."""
    models: List[ModelInfo]


@models_router.get("", response_model=ModelListResponse)
async def get_models(request: Request, provider: Optional[str] = None):
    """Get available models from all providers or a specific provider."""
    try:
        llm_service = request.app.state.llm_service
        
        # Get models from the service
        models = await llm_service.get_available_models(provider)
        
        # Convert to response format and check vision support
        model_infos = []
        for model in models:
            model_info = ModelInfo(**model)
            
            # Check if model supports vision
            try:
                model_info.supports_vision = litellm.supports_vision(model_info.id)
            except:
                # Fallback for models not in litellm's database
                # Check common vision model patterns
                vision_patterns = ['vision', 'gpt-4o', 'gpt-4v', 'claude-3', 'gemini-pro-vision', 'llava', 'bakllava']
                model_lower = model_info.id.lower()
                model_info.supports_vision = any(pattern in model_lower for pattern in vision_patterns)
            
            model_infos.append(model_info)
        
        return ModelListResponse(models=model_infos)
        
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")