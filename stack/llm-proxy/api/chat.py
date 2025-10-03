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
import datetime
import pytz

logger = logging.getLogger(__name__)

chat_router = APIRouter()


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

    # Tool selection options
    tool_selection: Optional[Dict[str, Dict[str, bool]]] = (
        None  # Server -> Tool -> enabled
    )

    # Audio-specific options
    voice: Optional[str] = None
    speech_speed: Optional[float] = None
    speech_lang: Optional[str] = None


# Shared constants
def get_default_system_prompt() -> str:
    # Set your location and timezone
    location = "Katy, TX"
    timezone = "America/Chicago"
    now = datetime.datetime.now(pytz.timezone(timezone))
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    return (
        f"You are a helpful AI assistant.\n"
        f"Current date: {date_str}\n"
        f"Current time: {time_str}\n"
        f"Location: {location}\n"
    )


async def _check_vision_support(model_name: str, llm_service) -> bool:
    """Check if the given model supports vision capabilities."""
    supports_vision = False

    # For Ollama models, use our capability check
    if model_name.startswith("ollama/"):
        supports_vision = await llm_service.check_ollama_vision_support(model_name)
    # For LM Studio models, use our capability check
    elif model_name.startswith("lmstudio/"):
        supports_vision = await llm_service.check_lmstudio_vision_support(model_name)
    else:
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

    return supports_vision


def _convert_messages_to_dict(
    messages: List[ChatMessage], supports_vision: bool
) -> List[Dict[str, Any]]:
    """Convert pydantic ChatMessage objects to dict format with vision support."""
    converted_messages = []

    for msg in messages:
        if (
            msg.role == "user"
            and msg.attachments
            and len(msg.attachments) > 0
            and supports_vision
        ):
            # For vision models, format content as array
            content = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})

            for attachment in msg.attachments:
                content.append({"type": "image_url", "image_url": {"url": attachment}})

            message_dict = {"role": msg.role, "content": content}
            converted_messages.append(message_dict)
        else:
            # Standard message format
            message_dict = {"role": msg.role, "content": msg.content}
            converted_messages.append(message_dict)

            # For non-vision models with attachments, add a note about the image
            if (
                msg.role == "user"
                and msg.attachments
                and len(msg.attachments) > 0
                and not supports_vision
            ):
                # Add a text description that an image was attached
                image_count = len(msg.attachments)
                image_note = f"\n\n[Note: {image_count} image{'s' if image_count > 1 else ''} attached but this model doesn't support vision]"
                message_dict["content"] += image_note

    return converted_messages


def _setup_model(request: ChatCompletionRequest, llm_service):
    """Set up the model from request or use default."""
    if request.model:
        # The set_model method will handle adding ollama/ prefix if needed
        llm_service.set_model(request.model)
    else:
        logger.warning("No model specified in request, using default model")


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


def _convert_to_openai_format(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert llm-proxy internal format to OpenAI streaming format."""
    if chunk.get("type") == "content":
        return {
            "choices": [
                {
                    "delta": {"content": chunk.get("content", "")},
                    "finish_reason": None,
                    "index": 0,
                }
            ]
        }
    elif chunk.get("type") == "tool_call":
        tool_call = chunk.get("tool_call", {})
        return {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "id": tool_call.get("id"),
                                "type": "function",
                                "function": {
                                    "name": tool_call.get("name"),
                                    "arguments": json.dumps(
                                        tool_call.get("arguments", {})
                                    ),
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                    "index": 0,
                }
            ]
        }
    elif chunk.get("type") == "tool_call_streaming":
        # Convert streaming tool call to OpenAI format
        tool_call = chunk.get("tool_call", {})
        if tool_call.get("status") == "started":
            # Send initial tool call with empty arguments
            return {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": tool_call.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.get("name"),
                                        "arguments": "",
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                        "index": 0,
                    }
                ]
            }
        # Skip other streaming statuses for now
        return None
    elif chunk.get("type") == "tool_result":
        # Include tool results as content in OpenAI format
        result = chunk.get("result", "")
        name = chunk.get("name", "unknown")
        # Format tool result as a content message showing the tool execution
        return {
            "choices": [
                {
                    "delta": {"content": f"\n[Tool: {name}]\n{result}\n"},
                    "finish_reason": None,
                    "index": 0,
                }
            ]
        }
    elif chunk.get("type") == "complete":
        # Send final content with finish reason
        return {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}
    # Skip other types like "connected", "tool_error", "done"
    return None


@chat_router.post("/completions")
async def chat_completion(request: ChatCompletionRequest, req: Request):
    """
    Handle chat completion requests with streaming support.
    """
    try:
        llm_service = req.app.state.llm_service
        mcp_manager = req.app.state.mcp_manager

        # Set model if provided
        _setup_model(request, llm_service)

        logger.info(
            f"Processing chat completion request with model: {llm_service.model}"
        )
        logger.debug(f"Request has {len(request.messages)} messages")

        # Check if model supports vision
        # Use the llm_service.model which has the provider prefix added if needed
        model_name = llm_service.model
        supports_vision = await _check_vision_support(model_name, llm_service)

        logger.info(f"Model {model_name} supports vision: {supports_vision}")

        # Debug: Log raw request messages
        logger.info(
            f"Raw request messages: {[{'role': msg.role, 'content': msg.content, 'attachments': msg.attachments} for msg in request.messages]}"
        )

        # Convert pydantic messages to dict format
        messages = _convert_messages_to_dict(request.messages, supports_vision)

        # Debug: Log converted messages
        logger.info(f"Converted messages being sent to LLM: {messages}")

        # Prepare system prompt
        system_prompt = request.system_prompt or get_default_system_prompt()

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
                tool_selection=request.tool_selection,
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
    tool_selection: Optional[Dict[str, Dict[str, bool]]] = None,
):
    """Generator for streaming chat completions."""
    try:
        # OpenAI format doesn't have a connection event, so we skip it

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
            tool_selection=tool_selection,
        )

        # Stream chunks
        chunk_count = 0
        async for chunk in chat_stream:
            chunk_count += 1
            # Convert to OpenAI format
            openai_chunk = _convert_to_openai_format(chunk)
            if openai_chunk:
                chunk_data = json.dumps(openai_chunk)
                yield f"data: {chunk_data}\n\n"

            # Log first few chunks for debugging
            if chunk_count <= 3:
                logger.debug(f"Chunk {chunk_count}: {chunk}")

        logger.info(f"Streamed {chunk_count} chunks")

        # Signal completion in OpenAI format
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in streaming chat completion: {e}", exc_info=True)
        # For errors, we'll send an error in the content
        error_chunk = {
            "choices": [
                {
                    "delta": {"content": f"Error: {str(e)}"},
                    "finish_reason": None,
                    "index": 0,
                }
            ]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


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
        _setup_model(request, llm_service)

        logger.info(
            f"Processing audio chat completion request with model: {llm_service.model}"
        )

        # Check if model supports vision
        # Use the llm_service.model which has the provider prefix added if needed
        model_name = llm_service.model
        supports_vision = await _check_vision_support(model_name, llm_service)

        # Convert pydantic messages to dict format
        messages = _convert_messages_to_dict(request.messages, supports_vision)

        # Prepare system prompt
        system_prompt = request.system_prompt or get_default_system_prompt()

        voice = request.voice or LLMProxyConfig.AUDIO_DEFAULT_VOICE
        speed = request.speech_speed or LLMProxyConfig.AUDIO_DEFAULT_SPEED

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
                tool_selection=request.tool_selection,
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
    tool_selection: Optional[Dict[str, Dict[str, bool]]] = None,
):
    """Generator for streaming chat completions with audio."""
    try:
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
                    tool_selection=tool_selection,
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

                    # Convert to OpenAI format and queue
                    openai_chunk = _convert_to_openai_format(chunk)
                    if openai_chunk:
                        await audio_queue.put(("text", openai_chunk))

            except Exception as e:
                logger.error(f"Error in text collection: {e}")
                # Send error in OpenAI format
                error_chunk = {
                    "choices": [
                        {
                            "delta": {"content": f"Error: {str(e)}"},
                            "finish_reason": None,
                            "index": 0,
                        }
                    ]
                }
                await audio_queue.put(("error", error_chunk))
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
                    text_generator(), voice=voice, speed=speed
                ):
                    # Convert audio to base64
                    audio_base64 = audio_service.audio_to_base64(audio_data)

                    # Create audio event in OpenAI format with audio extension
                    audio_chunk = {
                        "choices": [
                            {
                                "delta": {
                                    "audio": {
                                        "audio": audio_base64,
                                        "sample_rate": sample_rate,
                                        "text": text_chunk,
                                        "format": "wav",
                                    }
                                },
                                "finish_reason": None,
                                "index": 0,
                            }
                        ]
                    }

                    await audio_queue.put(("audio", audio_chunk))

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

            event_type, chunk_data = item
            yield f"data: {json.dumps(chunk_data)}\n\n"

        # Wait for tasks to complete
        await text_task
        await audio_task

        # Signal completion in OpenAI format
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in streaming audio chat completion: {e}", exc_info=True)
        # Send error in OpenAI format
        error_chunk = {
            "choices": [
                {
                    "delta": {"content": f"Error: {str(e)}"},
                    "finish_reason": None,
                    "index": 0,
                }
            ]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
