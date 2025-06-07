"""
Chat API endpoints for LLM Proxy Service

Handles chat completions and streaming.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

chat_router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions."""
    messages: List[ChatMessage]
    model: Optional[str] = None
    session_id: Optional[str] = None
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int = 8192
    system_prompt: Optional[str] = None


@chat_router.post("/completions")
async def chat_completion(request: ChatCompletionRequest, req: Request):
    """
    Handle chat completion requests with streaming support.
    """
    try:
        llm_service = req.app.state.llm_service
        mcp_client = req.app.state.mcp_client
        
        # Set model if provided
        if request.model:
            llm_service.set_model(request.model)
        
        # Convert pydantic messages to dict format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Prepare system prompt
        system_prompt = request.system_prompt or "You are a helpful AI assistant."
        
        # Return streaming response
        return StreamingResponse(
            _stream_chat_completion(
                llm_service=llm_service,
                messages=messages,
                session_id=request.session_id,
                system_prompt=system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tool_manager=mcp_client
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
            
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


async def _stream_chat_completion(
    llm_service,
    messages: List[Dict[str, Any]],
    session_id: Optional[str],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    tool_manager
):
    """Generator for streaming chat completions."""
    try:
        # Send initial connection event
        yield "data: {\"type\": \"connected\"}\n\n"
        
        # Get streaming response from LLM service
        chat_stream = llm_service.chat_completion(
            messages=messages,
            session_id=session_id,
            persistence=session_id is not None,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_manager=tool_manager
        )
        
        # Stream chunks
        async for chunk in chat_stream:
            chunk_data = json.dumps(chunk)
            yield f"data: {chunk_data}\n\n"
        
        # Signal completion
        yield "data: {\"type\": \"done\"}\n\n"
        
    except Exception as e:
        logger.error(f"Error in streaming chat completion: {e}")
        error_data = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {error_data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"