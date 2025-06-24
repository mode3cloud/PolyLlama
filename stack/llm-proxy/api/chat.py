"""
Chat API endpoints for LLM Proxy Service

Handles chat completions and streaming.
"""

import json
import logging
import base64
import tempfile
from typing import Any, Dict, List, Optional
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Get audio settings from request or config
from config import LLMProxyConfig
import litellm

logger = logging.getLogger(__name__)

chat_router = APIRouter()


def process_base64_attachments(attachments: List[str]) -> List[str]:
    """Convert base64 data URLs to temporary file paths."""
    file_paths = []

    for attachment in attachments:
        if attachment.startswith("data:"):
            # Extract MIME type and base64 data
            header, data = attachment.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]

            # Determine file extension
            ext = ".bin"
            if "image/jpeg" in mime_type or "image/jpg" in mime_type:
                ext = ".jpg"
            elif "image/png" in mime_type:
                ext = ".png"
            elif "image/gif" in mime_type:
                ext = ".gif"
            elif "image/webp" in mime_type:
                ext = ".webp"

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
            tool_manager=None,
        ):
            result.append(chunk)

        return {
            "status": "success",
            "model": llm_service.model,
            "chunks_received": len(result),
            "chunks": result,
        }
    except Exception as e:
        logger.error(f"Test chat failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "model": llm_service.model if "llm_service" in locals() else "unknown",
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

    # Audio-specific options
    voice: Optional[str] = None
    speech_speed: Optional[float] = None
    speech_lang: Optional[str] = None


@chat_router.post("/completions")
async def chat_completion(request: ChatCompletionRequest, req: Request):
    """
    Handle chat completion requests with streaming support.
    """
    try:
        llm_service = req.app.state.llm_service
        mcp_manager = req.app.state.mcp_manager

        # Set model if provided
        if request.model:
            llm_service.set_model(request.model)
        else:
            logger.warning("No model specified in request, using default model")

        logger.info(
            f"Processing chat completion request with model: {llm_service.model}"
        )
        logger.debug(f"Request has {len(request.messages)} messages")

        # Check if model supports vision
        model_name = request.model or llm_service.model
        supports_vision = False
        try:
            supports_vision = litellm.supports_vision(model_name)  # type: ignore
        except:
            # Fallback for models not in litellm's database
            # Check common vision model patterns
            vision_patterns = [
                "vision",
                "gpt-4o",
                "gpt-4v",
                "claude-3",
                "gemini-pro-vision",
                "llava",
                "bakllava",
            ]
            model_lower = model_name.lower()
            supports_vision = any(pattern in model_lower for pattern in vision_patterns)

        logger.info(f"Model {model_name} supports vision: {supports_vision}")

        # Convert pydantic messages to dict format
        messages = []

        for msg in request.messages:
            if msg.role == "user" and msg.attachments and supports_vision:
                # For vision models, format content as array
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})

                for attachment in msg.attachments:
                    content.append(
                        {"type": "image_url", "image_url": {"url": attachment}}
                    )

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
                tool_manager=mcp_manager,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise HTTPException(
            status_code=500, detail=f"Chat completion failed: {str(e)}"
        ) from e


async def _stream_chat_completion(
    llm_service,
    messages: List[Dict[str, Any]],
    session_id: Optional[str],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    tool_manager,
):
    """Generator for streaming chat completions."""
    try:
        # Send initial connection event
        yield 'data: {"type": "connected"}\n\n'

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
            tool_manager=tool_manager,
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
        yield 'data: {"type": "done"}\n\n'

    except Exception as e:
        logger.error(f"Error in streaming chat completion: {e}", exc_info=True)
        error_data = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {error_data}\n\n"
        yield 'data: {"type": "done"}\n\n'


@chat_router.post("/completions_audio")
async def chat_completion_audio(request: ChatCompletionRequest, req: Request):
    """
    Handle chat completion requests with audio streaming support.

    This endpoint returns a multipart response containing both text and audio streams.
    """
    try:
        llm_service = req.app.state.llm_service
        mcp_manager = req.app.state.mcp_manager
        audio_service = req.app.state.audio_service

        # Set model if provided
        if request.model:
            llm_service.set_model(request.model)
        else:
            logger.warning("No model specified in request, using default model")

        logger.info(
            f"Processing audio chat completion request with model: {llm_service.model}"
        )

        # Check if model supports vision (same logic as regular completions)
        model_name = request.model or llm_service.model
        supports_vision = False
        try:
            supports_vision = litellm.supports_vision(model_name)  # type: ignore
        except:
            vision_patterns = [
                "vision",
                "gpt-4o",
                "gpt-4v",
                "claude-3",
                "gemini-pro-vision",
                "llava",
                "bakllava",
            ]
            model_lower = model_name.lower()
            supports_vision = any(pattern in model_lower for pattern in vision_patterns)

        # Convert pydantic messages to dict format (same as regular completions)
        messages = []
        for msg in request.messages:
            if msg.role == "user" and msg.attachments and supports_vision:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})

                for attachment in msg.attachments:
                    content.append(
                        {"type": "image_url", "image_url": {"url": attachment}}
                    )

                message_dict = {"role": msg.role, "content": content}
                messages.append(message_dict)
            else:
                message_dict = {"role": msg.role, "content": msg.content}
                messages.append(message_dict)

                if msg.role == "user" and msg.attachments and not supports_vision:
                    image_count = len(msg.attachments)
                    image_note = f"\n\n[Note: {image_count} image{'s' if image_count > 1 else ''} attached but this model doesn't support vision]"
                    message_dict["content"] += image_note

        # Prepare system prompt
        system_prompt = request.system_prompt or "You are a helpful AI assistant."

        voice = request.voice or LLMProxyConfig.AUDIO_DEFAULT_VOICE
        speed = request.speech_speed or LLMProxyConfig.AUDIO_DEFAULT_SPEED
        lang = request.speech_lang or LLMProxyConfig.AUDIO_DEFAULT_LANG

        # Return streaming response with audio
        return StreamingResponse(
            _stream_chat_completion_with_audio(
                llm_service=llm_service,
                audio_service=audio_service,
                messages=messages,
                session_id=request.session_id,
                system_prompt=system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tool_manager=mcp_manager,
                voice=voice,
                speed=speed,
                lang=lang,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Error in audio chat completion: {e}")
        raise HTTPException(
            status_code=500, detail=f"Audio chat completion failed: {str(e)}"
        ) from e


async def _stream_chat_completion_with_audio(
    llm_service,
    audio_service,
    messages: List[Dict[str, Any]],
    session_id: Optional[str],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    tool_manager,
    voice: str,
    speed: float,
    lang: str,
):
    """Generator for streaming chat completions with audio."""
    try:
        # Send initial connection event
        yield 'data: {"type": "connected"}\n\n'

        logger.info(f"Starting audio chat stream with model: {llm_service.model}")

        # Create queues for text accumulation
        text_queue = asyncio.Queue()
        audio_queue = asyncio.Queue()

        # Track completion
        text_complete = False
        audio_complete = False

        async def collect_text():
            """Collect text from LLM stream and queue it."""
            nonlocal text_complete
            try:
                # Get streaming response from LLM service
                chat_stream = llm_service.chat_completion(
                    messages=messages,
                    session_id=session_id,
                    persistence=session_id is not None,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tool_manager=tool_manager,
                )

                # Stream chunks
                async for chunk in chat_stream:
                    # Extract text content from chunk
                    if isinstance(chunk, dict):
                        # Only process content chunks for audio generation
                        # Skip "complete" events to avoid re-generating audio for the full message
                        if chunk.get("type") == "content" and "content" in chunk:
                            text_content = chunk.get("content", "")
                            if text_content:
                                await text_queue.put(text_content)

                    # Also yield the original chunk as text event
                    chunk_data = json.dumps({"type": "text", "data": chunk})
                    await audio_queue.put(("text", chunk_data))

            except Exception as e:
                logger.error(f"Error in text collection: {e}")
                error_data = json.dumps({"type": "error", "error": str(e)})
                await audio_queue.put(("error", error_data))
            finally:
                text_complete = True
                await text_queue.put(None)  # Signal completion

        async def generate_audio():
            """Generate audio from queued text."""
            nonlocal audio_complete
            try:
                # Create async generator from queue
                async def text_generator():
                    while True:
                        text = await text_queue.get()
                        if text is None:
                            break
                        yield text

                # Generate audio for streaming text
                async for (
                    audio_data,
                    sample_rate,
                    text_chunk,
                ) in audio_service.generate_audio_for_streaming_text(
                    text_generator(), voice=voice, speed=speed, lang=lang
                ):
                    # Convert audio to base64
                    audio_base64 = audio_service.audio_to_base64(audio_data)

                    # Create audio event
                    audio_data = json.dumps(
                        {
                            "type": "audio",
                            "data": {
                                "audio": audio_base64,
                                "sample_rate": sample_rate,
                                "text": text_chunk,
                                "format": "wav",
                            },
                        }
                    )

                    await audio_queue.put(("audio", audio_data))

            except Exception as e:
                logger.error(f"Error in audio generation: {e}")
                # Continue without audio on error
            finally:
                audio_complete = True
                await audio_queue.put(None)  # Signal completion

        # Start both tasks concurrently
        text_task = asyncio.create_task(collect_text())
        audio_task = asyncio.create_task(generate_audio())

        # Stream events from audio queue
        while True:
            item = await audio_queue.get()

            if item is None:
                # Check if both tasks are complete
                if text_complete and audio_complete:
                    break
                continue

            _, event_data = item
            yield f"data: {event_data}\n\n"

        # Wait for tasks to complete
        await text_task
        await audio_task

        # Signal completion
        yield 'data: {"type": "done"}\n\n'

    except Exception as e:
        logger.error(f"Error in streaming audio chat completion: {e}", exc_info=True)
        error_data = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {error_data}\n\n"
        yield 'data: {"type": "done"}\n\n'
