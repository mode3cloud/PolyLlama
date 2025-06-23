"""
Chat API endpoints for LLM Proxy Service

Handles chat completions and streaming.
"""

import json
import logging
import base64
import tempfile
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import litellm

logger = logging.getLogger(__name__)

chat_router = APIRouter()


def process_base64_attachments(attachments: List[str]) -> List[str]:
    """Convert base64 data URLs to temporary file paths."""
    file_paths = []
    
    for attachment in attachments:
        if attachment.startswith('data:'):
            # Extract MIME type and base64 data
            header, data = attachment.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]
            
            # Determine file extension
            ext = '.bin'
            if 'image/jpeg' in mime_type or 'image/jpg' in mime_type:
                ext = '.jpg'
            elif 'image/png' in mime_type:
                ext = '.png'
            elif 'image/gif' in mime_type:
                ext = '.gif'
            elif 'image/webp' in mime_type:
                ext = '.webp'
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                # Decode and write base64 data
                tmp_file.write(base64.b64decode(data))
                file_paths.append(tmp_file.name)
        else:
            # Assume it's already a file path
            file_paths.append(attachment)
    
    return file_paths


@chat_router.get("/test")
async def test_chat(req: Request):
    """Test endpoint to verify LLM service is working."""
    try:
        llm_service = req.app.state.llm_service
        
        # Simple test message
        test_messages = [{"role": "user", "content": "Say hello"}]
        
        result = []
        async for chunk in llm_service.chat_completion(
            messages=test_messages,
            session_id=None,
            persistence=False,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
            tool_manager=None
        ):
            result.append(chunk)
        
        return {
            "status": "success",
            "model": llm_service.model,
            "chunks_received": len(result),
            "chunks": result
        }
    except Exception as e:
        logger.error(f"Test chat failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "model": llm_service.model if 'llm_service' in locals() else "unknown"
        }


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str
    content: str
    attachments: Optional[List[str]] = None  # Base64 encoded images or file paths


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
        else:
            logger.warning("No model specified in request, using default model")
        
        logger.info(f"Processing chat completion request with model: {llm_service.model}")
        logger.debug(f"Request has {len(request.messages)} messages")
        
        # Check if model supports vision
        model_name = request.model or llm_service.model
        supports_vision = False
        try:
            supports_vision = litellm.supports_vision(model_name)
        except:
            # Fallback for models not in litellm's database
            # Check common vision model patterns
            vision_patterns = ['vision', 'gpt-4o', 'gpt-4v', 'claude-3', 'gemini-pro-vision', 'llava', 'bakllava']
            model_lower = model_name.lower()
            supports_vision = any(pattern in model_lower for pattern in vision_patterns)
        
        logger.info(f"Model {model_name} supports vision: {supports_vision}")
        
        # Convert pydantic messages to dict format
        messages = []
        attachments = []
        
        for msg in request.messages:
            if msg.role == "user" and msg.attachments and supports_vision:
                # For vision models, format content as array
                content = []
                if msg.content:
                    content.append({
                        "type": "text", 
                        "text": msg.content
                    })
                
                for attachment in msg.attachments:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": attachment
                        }
                    })
                
                message_dict = {"role": msg.role, "content": content}
                messages.append(message_dict)
            else:
                # Standard message format
                message_dict = {"role": msg.role, "content": msg.content}
                messages.append(message_dict)
                
                # For non-vision models with attachments, add a note about the image
                if msg.role == "user" and msg.attachments and not supports_vision:
                    # Add a text description that an image was attached
                    image_count = len(msg.attachments)
                    image_note = f"\n\n[Note: {image_count} image{'s' if image_count > 1 else ''} attached but this model doesn't support vision]"
                    message_dict["content"] += image_note
        
        # We don't process attachments anymore since document processing isn't implemented
        
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
        
        logger.info(f"Starting chat stream with model: {llm_service.model}")
        logger.debug(f"Session ID: {session_id}, Messages count: {len(messages)}")
        
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
        chunk_count = 0
        async for chunk in chat_stream:
            chunk_count += 1
            chunk_data = json.dumps(chunk)
            yield f"data: {chunk_data}\n\n"
            
            # Log first few chunks for debugging
            if chunk_count <= 3:
                logger.debug(f"Chunk {chunk_count}: {chunk}")
        
        logger.info(f"Streamed {chunk_count} chunks")
        
        # Signal completion
        yield "data: {\"type\": \"done\"}\n\n"
        
    except Exception as e:
        logger.error(f"Error in streaming chat completion: {e}", exc_info=True)
        error_data = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {error_data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"