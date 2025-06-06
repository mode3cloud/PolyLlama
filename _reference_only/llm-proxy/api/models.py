"""
Model management API endpoints for LLM Proxy Service

Handles model listing and capability checks.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

models_router = APIRouter()


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    name: str
    provider: str
    supports_reasoning: bool = False


class ModelListResponse(BaseModel):
    """Response model for model listing."""
    models: List[ModelInfo]


@models_router.get("", response_model=ModelListResponse)
async def get_models(request: Request, provider: Optional[str] = None):
    """Get available models."""
    try:
        # Import the get_available_models function
        import sys
        from pathlib import Path
        
        # Add parent directory to path for imports
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent.parent
        sys.path.insert(0, str(project_root))
        
        from mcp_tools.shared.multi_llm_service import get_available_models
        
        # Get models from the service
        if provider:
            model_ids = await get_available_models(provider)
            provider_name = provider
        else:
            # Get all models from all providers
            model_ids = []
            providers = ["openai", "anthropic", "ollama", "lm_studio"]
            
            for prov in providers:
                try:
                    prov_models = await get_available_models(prov)
                    # Add provider prefix to distinguish models
                    model_ids.extend([f"{prov}:{model}" for model in prov_models])
                except Exception as e:
                    logger.warning(f"Could not get models from {prov}: {e}")
        
        # Convert to model info objects
        models = []
        for model_id in model_ids:
            if ":" in model_id:
                provider_name, model_name = model_id.split(":", 1)
            else:
                provider_name = "unknown"
                model_name = model_id
            
            # Check if model supports reasoning (based on model name)
            supports_reasoning = any(keyword in model_name.lower() for keyword in [
                "o1", "reasoning", "think", "chain", "cot"
            ])
            
            models.append(ModelInfo(
                id=model_id,
                name=model_name,
                provider=provider_name,
                supports_reasoning=supports_reasoning
            ))
        
        return ModelListResponse(models=models)
        
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")


@models_router.get("/{model_id}/supports-reasoning")
async def check_reasoning_support(model_id: str, request: Request):
    """Check if a model supports reasoning."""
    try:
        llm_service = request.app.state.llm_service
        
        supports_reasoning = await llm_service.supports_reasoning(model_id)
        
        return {"supports_reasoning": supports_reasoning}
        
    except Exception as e:
        logger.error(f"Error checking reasoning support: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check reasoning support: {str(e)}")