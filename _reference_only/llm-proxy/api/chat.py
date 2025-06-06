"""
Chat API endpoints for LLM Proxy Service

Handles chat completions, streaming, and tool orchestration.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import litellm

logger = logging.getLogger(__name__)

chat_router = APIRouter()


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions."""
    session_id: str
    message: str
    model: Optional[str] = None
    stream: bool = False
    temperature: float = 0.1
    max_tokens: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    """Response model for non-streaming chat completions."""
    content: str
    session_id: str
    message_id: Optional[str] = None


@chat_router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(request: ChatCompletionRequest, req: Request):
    """
    Handle chat completion requests.
    
    Supports both streaming and non-streaming responses.
    """
    try:
        llm_service = req.app.state.llm_service
        mcp_client = req.app.state.mcp_client
        
        # Set model if provided
        if request.model:
            llm_service.set_model(request.model)
        
        # Get tools description from MCP service
        tools_description = await mcp_client.get_tools_description()
        
        # Read system prompts (we'll need to handle this differently in the service)
        system_prompt = "You are a helpful AI assistant with access to various tools."
        tools_prompt = "Use the available tools to help answer user questions accurately."
        
        if request.stream:
            # Return streaming response
            return StreamingResponse(
                _stream_chat_completion(
                    llm_service=llm_service,
                    mcp_client=mcp_client,
                    session_id=request.session_id,
                    message=request.message,
                    system_prompt=system_prompt,
                    tools_prompt=tools_prompt,
                    tools_description=tools_description,
                    temperature=request.temperature
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming response
            response = await llm_service.chat_completion(
                session_id=request.session_id,
                persist=True,
                messages=[litellm.Message(role="user", content=request.message)],
                system_prompt=system_prompt,
                tools_prompt=tools_prompt,
                tools=tools_description,
                tool_manager=mcp_client,  # Use MCP client as tool manager
                temperature=request.temperature,
                stream=False
            )
            
            # Extract response content
            content = response.get("final_response", response.get("response", ""))
            
            return ChatCompletionResponse(
                content=content,
                session_id=request.session_id,
                message_id=response.get("message_id")
            )
            
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


async def _stream_chat_completion(
    llm_service,
    mcp_client,
    session_id: str,
    message: str,
    system_prompt: str,
    tools_prompt: str,
    tools_description: str,
    temperature: float
):
    """Generator for streaming chat completions."""
    try:
        # Yield initial connection
        yield "data: {}\n\n"
        
        # Get streaming response from LLM service
        chat_stream = llm_service.chat_completion(
            session_id=session_id,
            persist=True,
            messages=[litellm.Message(role="user", content=message)],
            system_prompt=system_prompt,
            tools_prompt=tools_prompt,
            tools=tools_description,
            tool_manager=mcp_client,
            temperature=temperature,
            stream=True
        )
        
        # Stream chunks
        async for chunk in chat_stream:
            yield f"data: {json.dumps(chunk)}\n\n"
        
        # Signal completion
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"Error in streaming chat completion: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@chat_router.post("/send-message")
async def send_message_form(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(...),
    model: Optional[str] = Form(None),
    streaming: str = Form("false"),
    files: List[UploadFile] = File(default=[])
):
    """
    Handle form-based message sending with file uploads.
    
    This endpoint maintains compatibility with the existing UI forms.
    """
    try:
        llm_service = request.app.state.llm_service
        mcp_client = request.app.state.mcp_client
        
        # Set model if provided
        if model:
            llm_service.set_model(model)
        
        # Process file uploads
        file_attachments = []
        file_contents = []
        
        for file in files:
            if file.filename:
                # Save file temporarily and process
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    content = await file.read()
                    tmp_file.write(content)
                    tmp_file_path = tmp_file.name
                
                # Process file content
                file_result = await llm_service.process_file(
                    tmp_file_path,
                    file.filename,
                    file.content_type
                )
                
                file_contents.append(file_result.get("content", f"[File: {file.filename}]"))
                file_attachments.append({
                    "id": os.path.basename(tmp_file_path),
                    "name": file.filename,
                    "content_type": file.content_type,
                    "file_path": tmp_file_path
                })
        
        # Prepare full message with file contents
        full_message = message
        if file_contents:
            file_text = "\n\n".join(file_contents)
            full_message += f"\n\nAttached files:\n{file_text}"
        
        # Get tools description
        tools_description = await mcp_client.get_tools_description()
        
        # Read system prompts
        system_prompt = "You are a helpful AI assistant with access to various tools."
        tools_prompt = "Use the available tools to help answer user questions accurately."
        
        is_streaming = streaming.lower() == "true"
        
        if is_streaming:
            return StreamingResponse(
                _stream_chat_completion(
                    llm_service=llm_service,
                    mcp_client=mcp_client,
                    session_id=session_id,
                    message=full_message,
                    system_prompt=system_prompt,
                    tools_prompt=tools_prompt,
                    tools_description=tools_description,
                    temperature=0.1
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming response
            response = await llm_service.chat_completion(
                session_id=session_id,
                persist=True,
                messages=[litellm.Message(role="user", content=full_message)],
                system_prompt=system_prompt,
                tools_prompt=tools_prompt,
                attachments=file_attachments,
                tools=tools_description,
                tool_manager=mcp_client,
                temperature=0.1,
                stream=False
            )
            
            content = response.get("final_response", response.get("response", ""))
            
            return {"content": content}
            
    except Exception as e:
        logger.error(f"Error in send message: {e}")
        raise HTTPException(status_code=500, detail=f"Send message failed: {str(e)}")