"""
Multi-LLM Service for PolyLlama

Unified streaming LLM service using LiteLLM for provider abstraction.
"""

import os
import json
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator, Protocol, TypedDict
from functools import wraps

import litellm
import httpx
import inspect

logger = logging.getLogger(__name__)


# Type definitions
class Tool(TypedDict):
    """Tool specification for function calling."""

    type: str
    function: Dict[str, Any]


class ToolManagerProtocol(Protocol):
    """Protocol for tool managers."""

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments."""
        ...


class MultiLLMService:
    """
    Unified streaming LLM service with LiteLLM integration.

    Provides a single interface for all LLM providers through LiteLLM.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        neo4j_driver: Any | None = None,
        timeout: int = int(os.getenv("MULTI_LLM_REQUEST_TIMEOUT", "120")),
        max_concurrent: int = int(os.getenv("MULTI_LLM_CLIENT_MAX_CONCURRENT", "3")),
    ) -> None:
        # Default to an Ollama model if no OpenAI key is set
        default_model = (
            "ollama/llama3.2:latest"
            if not os.getenv("OPENAI_API_KEY")
            else "openai/gpt-4o"
        )
        self.model = model or os.getenv("DEFAULT_LLM_MODEL_NAME", default_model)
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(f"Initialized MultiLLMService with default model: {self.model}")

        # Message manager for persistence
        self.message_manager = None
        if neo4j_driver:
            from .message_manager import MessageManager

            self.message_manager = MessageManager(neo4j_driver)

        # Configure LiteLLM
        self._prepare_env()
        litellm.modify_params = True
        litellm.REPEATED_STREAMING_CHUNK_LIMIT = 1000
        # Enable debug logging for LiteLLM
        if logger.isEnabledFor(logging.DEBUG):
            litellm.set_verbose = True

    def set_model(self, model: str) -> None:
        """Update the current model."""
        logger.info(f"Setting model to: {model}")
        self.model = model
        self._prepare_env()

    async def chat_completion(
        self,
        messages: List[litellm.Message],
        *,
        session_id: Optional[str] = None,
        persistence: bool = False,
        system_prompt: Optional[str] = None,
        tools_prompt: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tool_manager: Optional["ToolManagerProtocol"] = None,
        attachments: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion using LiteLLM with tool calling and attachment support.

        Args:
            messages: List of litellm.Message objects or dictionaries
            session_id: Session ID for persistence
            persistence: Whether to persist messages
            system_prompt: System prompt to prepend
            tools_prompt: Additional prompt for tools
            tools: List of available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tool_manager: Tool manager for function calling
            attachments: List of file paths to process
            **kwargs: Additional arguments passed to LiteLLM

        Yields:
            Dict containing chunk type and content
        """
        if persistence and not session_id:
            raise ValueError("session_id required when persistence=True")
        if persistence and not self.message_manager:
            raise ValueError("MessageManager required when persistence=True")

        # Message History Handling
        if persistence and session_id:
            session_data = await self.message_manager.get_session_messages(session_id)
            conversation_history = session_data.get("messages", [])
        else:
            conversation_history = []

        # Prepare messages
        current_messages = []

        # Augment system prompt with tools if provided
        sys_prompt = self._augment_system_prompt(
            system_prompt or "", tools_prompt, tools
        )

        # Add system prompt if provided and not already in history
        if sys_prompt and (
            not conversation_history or conversation_history[0].get("role") != "system"
        ):
            current_messages.append({"role": "system", "content": sys_prompt})
            if persistence:
                await self.message_manager.add_system_message(session_id, sys_prompt)

        # Process new messages with type conversion
        for msg in messages:
            # Convert litellm.Message objects to dict format
            if hasattr(msg, "role") and hasattr(msg, "content"):
                msg_dict = {"role": msg.role, "content": msg.content}
            elif isinstance(msg, dict):
                msg_dict = msg
            else:
                raise TypeError(f"Unexpected message type: {type(msg)}")

            if msg_dict["role"] == "user":
                current_messages.append(msg_dict)
                if persistence:
                    await self.message_manager.add_user_message(
                        session_id, msg_dict["content"]
                    )

        # Process attachments if provided
        if attachments:
            from mcp_tools.tools.qdrant.qdrant_ingest.document_processor import (
                DocumentProcessor,
            )

            processor = DocumentProcessor()

            for path in attachments:
                try:
                    file_info = None
                    if inspect.iscoroutinefunction(processor.process_file):
                        file_info = await processor.process_file(path)
                    else:
                        file_info = processor.process_file(path)

                    # Audio fallback: if audio and no transcript, try Whisper
                    if (
                        file_info
                        and file_info.get("type") == "audio"
                        and not file_info.get("transcript")
                    ):
                        try:
                            transcript = await self._transcribe_audio_fallback(path)
                            if transcript:
                                file_info["transcript"] = transcript
                                file_info["summary"] = (
                                    f"[Transcribed audio]: {transcript[:200]}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Audio fallback transcription failed for {path}: {e}"
                            )

                    attach_msg = {
                        "role": "user",
                        "content": f"[ATTACHMENT: {os.path.basename(path)}]\n{file_info.get('summary','')}",
                    }
                    current_messages.append(attach_msg)
                    if persistence:
                        await self.message_manager.add_user_message(
                            session_id, attach_msg["content"]
                        )
                except Exception as e:
                    logger.warning(f"Attachment processing failed for {path}: {e}")

        # Combine with history
        full_conversation = conversation_history + current_messages

        # Format tools for LiteLLM if provided
        tools_spec = self._format_tools(tools) if tools else None

        # Filter supported parameters for this model
        filtered_kwargs = self._filter_supported_kwargs(self.model, kwargs)

        # Streaming LLM Call with Integrated Tool Orchestration
        async with self.semaphore:
            logger.debug("Semaphore acquired")
            assistant_buffer = []
            iteration = 0
            max_iterations = 10
            current_msgs = full_conversation.copy()
            should_continue = True

            while iteration < max_iterations and should_continue:
                iteration += 1
                logger.info(f"Starting iteration {iteration} with model: {self.model}")

                # Prepare completion arguments
                completion_kwargs = {
                    "model": self.model,
                    "messages": current_msgs,
                    "tools": tools_spec,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    **filtered_kwargs,
                }

                # Add Bearer Authorization header for Ollama models to pass API key
                if self.model.startswith("ollama/") and os.getenv("POLYLLAMA_API_KEY"):
                    completion_kwargs["extra_headers"] = {
                        "Authorization": f"Bearer {os.getenv('POLYLLAMA_API_KEY')}"
                    }

                try:
                    logger.debug(f"Messages: {current_msgs}")
                    logger.debug(f"Completion kwargs: {completion_kwargs}")

                    # Make LiteLLM call
                    response = await litellm.acompletion(**completion_kwargs)

                    if response is None:
                        raise ValueError("LiteLLM returned None response")

                    # Check if response is an async generator
                    import inspect

                    if not inspect.isasyncgen(response):
                        logger.warning(
                            f"Response is not an async generator: {type(response)}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error calling litellm.acompletion: {e}", exc_info=True
                    )
                    yield {"type": "error", "error": str(e)}
                    raise

                # Initialize tool call buffers
                tool_buffers = {}
                active_tool_ids = set()
                last_tool_id = None
                chunk_count = 0

                # Stream response
                async for chunk in response:
                    chunk_count += 1
                    logger.debug(f"Received chunk {chunk_count}: {chunk}")

                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta

                        # Check for finish_reason
                        finish_reason = None
                        if (
                            hasattr(chunk.choices[0], "finish_reason")
                            and chunk.choices[0].finish_reason
                        ):
                            finish_reason = chunk.choices[0].finish_reason

                        # Handle content streaming
                        if getattr(delta, "content", None):
                            content = delta.content
                            assistant_buffer.append(content)
                            yield {"type": "content", "content": content}

                        # Handle tool-call streaming (buffered)
                        if getattr(delta, "tool_calls", None) and tool_manager:
                            for tc in delta.tool_calls:
                                tc_id = getattr(tc, "id", None)
                                tc_name = (
                                    getattr(tc.function, "name", None)
                                    if hasattr(tc, "function")
                                    else None
                                )
                                tc_args = (
                                    getattr(tc.function, "arguments", None)
                                    if hasattr(tc, "function")
                                    else None
                                )

                                # New tool call (has both id and name)
                                if tc_id and tc_name:
                                    tool_buffers[tc_id] = {"name": tc_name, "args": ""}
                                    last_tool_id = tc_id
                                    active_tool_ids.add(tc_id)
                                    logger.debug(f"New tool call: {tc_id} - {tc_name}")

                                # Arguments for specific tool (has id but no name)
                                elif tc_id and tc_id in tool_buffers and tc_args:
                                    tool_buffers[tc_id]["args"] += tc_args

                                # Continuation of existing tool (only arguments, no id/name)
                                elif (
                                    tc_args
                                    and last_tool_id
                                    and last_tool_id in tool_buffers
                                ):
                                    tool_buffers[last_tool_id]["args"] += tc_args

                                # Fallback: append to most recent tool if we have args but no clear target
                                elif tc_args and last_tool_id:
                                    if last_tool_id not in tool_buffers:
                                        tool_buffers[last_tool_id] = {
                                            "name": "unknown",
                                            "args": "",
                                        }
                                        active_tool_ids.add(last_tool_id)
                                    tool_buffers[last_tool_id]["args"] += tc_args

                    # Process completed tool calls on finish_reason
                    if (
                        hasattr(chunk, "choices")
                        and chunk.choices
                        and chunk.choices[0].finish_reason in ("tool_calls", "stop")
                    ):
                        logger.info(f"Finish reason: {chunk.choices[0].finish_reason}")

                        # Check if there are any active tool calls to process
                        tool_calls_processed = False
                        for tool_id in list(active_tool_ids):
                            buf = tool_buffers.pop(tool_id, None)
                            if buf:
                                tool_calls_processed = True
                                try:
                                    args = json.loads(buf["args"] or "{}")
                                    logger.info(
                                        f"Executing tool: {buf['name']} with args: {args}"
                                    )

                                    # Add assistant tool call message
                                    tool_call_msg = {
                                        "role": "assistant",
                                        "tool_calls": [
                                            {
                                                "id": tool_id,
                                                "type": "function",
                                                "function": {
                                                    "name": buf["name"],
                                                    "arguments": json.dumps(args),
                                                },
                                            }
                                        ],
                                    }
                                    current_msgs.append(tool_call_msg)

                                    # Execute tool and add to conversation
                                    result = await tool_manager.execute_tool(
                                        buf["name"], args
                                    )
                                    tool_result_msg = {
                                        "role": "tool",
                                        "name": buf["name"],
                                        "content": result,
                                        "tool_call_id": tool_id,
                                    }
                                    current_msgs.append(tool_result_msg)

                                    # Persist tool message if enabled
                                    if persistence:
                                        await self.message_manager.add_tool_message(
                                            session_id, result, buf["name"], tool_id
                                        )

                                    yield {
                                        "type": "tool_result",
                                        "name": buf["name"],
                                        "result": result,
                                    }
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse tool arguments: {e}")
                                    error_msg = {
                                        "role": "tool",
                                        "content": f"Error parsing arguments: {str(e)}",
                                        "tool_call_id": tool_id,
                                    }
                                    current_msgs.append(error_msg)
                                    yield {"type": "tool_error", "error": str(e)}
                                except Exception as err:
                                    logger.error(
                                        f"Tool execution error: {err}", exc_info=True
                                    )
                                    error_msg = {
                                        "role": "tool",
                                        "content": f"Error: {str(err)}",
                                        "tool_call_id": tool_id,
                                    }
                                    current_msgs.append(error_msg)
                                    yield {"type": "tool_error", "error": str(err)}

                                active_tool_ids.remove(tool_id)

                        # Decide whether to continue or break based on whether tool calls were processed
                        if (
                            tool_calls_processed
                            or chunk.choices[0].finish_reason == "tool_calls"
                        ):
                            # Either we processed tool calls or the finish reason explicitly indicates tool calls
                            logger.info(
                                "Tool calls processed, continuing to next iteration"
                            )
                            break
                        else:
                            # finish_reason is "stop" and no tool calls were processed - exit the while loop
                            logger.info("Conversation complete, no more tool calls")
                            should_continue = False
                            break
                else:
                    # No more chunks, break loop
                    logger.info("Stream ended, no more chunks")
                    should_continue = False
                    break

                logger.info(f"Received {chunk_count} chunks in iteration {iteration}")

            # Persist final assistant message
            final_content = "".join(assistant_buffer)
            if persistence and final_content:
                await self.message_manager.add_assistant_message(
                    session_id, final_content
                )

            yield {"type": "complete", "content": final_content}

        logger.debug("Semaphore released")

    async def get_available_models(
        self, provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available models from all providers or a specific provider."""
        models = []

        if provider == "ollama" or provider is None:
            # Get Ollama models from PolyLlama router
            try:
                headers = {}
                # Add API key if configured
                if os.getenv("POLYLLAMA_API_KEY"):
                    headers["Authorization"] = (
                        f"Bearer {os.getenv('POLYLLAMA_API_KEY')}"
                    )

                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        "http://router:11434/api/tags", headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for model in data.get("models", []):
                            models.append(
                                {
                                    "id": f"ollama/{model['name']}",
                                    "name": model["name"],
                                    "provider": "ollama",
                                    "size": model.get("size", 0),
                                }
                            )
            except Exception as e:
                logger.warning(f"Failed to get Ollama models: {e}")

        if provider == "openai" or provider is None:
            # Add OpenAI models if API key is available
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    # Fetch models from OpenAI API
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            "https://api.openai.com/v1/models",
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                        if response.status_code == 200:
                            data = response.json()
                            openai_models = []
                            for model in data.get("data", []):
                                model_id = model.get("id", "")
                                # Filter for chat models (skip embeddings, images, audio, etc.)
                                if model_id.startswith(
                                    ("gpt-", "o1-", "o3-")
                                ) and not any(
                                    x in model_id for x in ["realtime", "audio"]
                                ):
                                    openai_models.append(model_id)

                            # Sort models
                            openai_models.sort()

                            for model in openai_models:
                                models.append(
                                    {
                                        "id": f"openai/{model}",
                                        "name": model,
                                        "provider": "openai",
                                    }
                                )
                        else:
                            logger.warning(
                                f"Failed to fetch OpenAI models: {response.status_code}"
                            )
                            raise Exception(f"API returned {response.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to get OpenAI models from API: {e}")
                    # Fallback to known models
                    fallback_models = [
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4-turbo",
                        "gpt-4",
                        "gpt-3.5-turbo",
                        "o1-preview",
                        "o1-mini",
                        "o3-mini",
                    ]
                    for model in fallback_models:
                        models.append(
                            {
                                "id": f"openai/{model}",
                                "name": model,
                                "provider": "openai",
                            }
                        )

        if provider == "anthropic" or provider is None:
            # Add Anthropic models if API key is available
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    # Fetch models from Anthropic API
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            "https://api.anthropic.com/v1/models",
                            headers={
                                "x-api-key": api_key,
                                "anthropic-version": "2023-06-01",
                            },
                        )
                        if response.status_code == 200:
                            data = response.json()
                            anthropic_models = []
                            for model in data.get("data", []):
                                model_id = model.get("id", "")
                                # Only include models that are actively available
                                if model.get("status") == "active":
                                    anthropic_models.append(model_id)

                            # Sort models
                            anthropic_models.sort(reverse=True)  # Newest first

                            for model in anthropic_models:
                                models.append(
                                    {
                                        "id": f"anthropic/{model}",
                                        "name": model,
                                        "provider": "anthropic",
                                    }
                                )
                        else:
                            logger.warning(
                                f"Failed to fetch Anthropic models: {response.status_code}"
                            )
                            raise Exception(f"API returned {response.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to get Anthropic models from API: {e}")
                    # Fallback to known models
                    fallback_models = [
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                        "claude-3-opus-20240229",
                        "claude-3-sonnet-20240229",
                        "claude-3-haiku-20240307",
                        "claude-2.1",
                        "claude-instant-1.2",
                    ]
                    for model in fallback_models:
                        models.append(
                            {
                                "id": f"anthropic/{model}",
                                "name": model,
                                "provider": "anthropic",
                            }
                        )

        if provider == "google" or provider is None:
            # Add known Google models if API key is available
            if os.getenv("GOOGLE_API_KEY"):
                google_models = ["gemini-pro", "gemini-pro-vision"]
                for model in google_models:
                    models.append(
                        {"id": f"google/{model}", "name": model, "provider": "google"}
                    )

        if provider == "groq" or provider is None:
            # Add known Groq models if API key is available
            if os.getenv("GROQ_API_KEY"):
                groq_models = ["mixtral-8x7b-32768", "llama2-70b-4096"]
                for model in groq_models:
                    models.append(
                        {"id": f"groq/{model}", "name": model, "provider": "groq"}
                    )

        return models

    def _filter_supported_kwargs(self, model: str, kwargs: dict) -> dict:
        """Filter kwargs to only those supported by the model/provider."""
        try:
            supported_params = litellm.get_supported_openai_params(model)
            if supported_params is None:
                return kwargs

            # Always allow these common parameters
            always_allowed = {"api_base", "api_key", "api_version", "extra_headers"}
            supported_set = set(supported_params) | always_allowed

            filtered = {k: v for k, v in kwargs.items() if k in supported_set}
            removed = set(kwargs.keys()) - supported_set

            if removed:
                logger.debug(f"Filtered unsupported params for {model}: {removed}")

            return filtered
        except Exception as e:
            logger.warning(f"Could not filter params for {model}: {e}")
            return kwargs

    def _prepare_env(self):
        """Prepare environment variables for LiteLLM."""
        # Ensure LiteLLM can find provider API keys
        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }

        for provider, env_var in provider_env_map.items():
            if os.getenv(env_var) and env_var not in os.environ:
                os.environ[env_var] = os.getenv(env_var)

        # Set Ollama base URL
        if not os.environ.get("OLLAMA_API_BASE"):
            os.environ["OLLAMA_API_BASE"] = "http://router:11434"

        # Set Ollama API key if configured
        polyllama_key = os.getenv("POLYLLAMA_API_KEY")
        if polyllama_key:
            os.environ["POLYLLAMA_API_KEY"] = polyllama_key

        logger.info(
            f"Environment variables set - OLLAMA_API_BASE: {os.environ.get('OLLAMA_API_BASE')}"
        )

    async def close(self):
        """Clean up resources."""
        pass

    def _augment_system_prompt(
        self,
        system_prompt: str,
        tools_prompt: Optional[str],
        tools: Optional[List[Tool]],
    ) -> str:
        """Augment system prompt with tool information if tools are provided."""
        prompt_parts = []

        if system_prompt:
            prompt_parts.append(system_prompt)

        if tools_prompt:
            prompt_parts.append(tools_prompt)
        elif tools:
            # Auto-generate tools prompt if tools provided but no custom prompt
            tool_names = [t["function"]["name"] for t in tools]
            prompt_parts.append(
                f"You have access to the following tools: {', '.join(tool_names)}. "
                "Use them when appropriate to help answer the user's questions."
            )

        return "\n\n".join(prompt_parts)

    def _format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Format tools for LiteLLM function calling format."""
        # LiteLLM expects tools in OpenAI format
        formatted_tools = []
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                formatted_tools.append(tool)
            else:
                logger.warning(f"Invalid tool format: {tool}")
        return formatted_tools

    async def _transcribe_audio_fallback(self, audio_path: str) -> Optional[str]:
        """Fallback audio transcription using Whisper via OpenAI API."""
        try:
            # Check if OpenAI API key is available
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("No OpenAI API key for audio transcription fallback")
                return None

            # Use OpenAI Whisper API for transcription
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(audio_path, "rb") as audio_file:
                    files = {"file": (os.path.basename(audio_path), audio_file)}
                    data = {"model": "whisper-1"}
                    headers = {"Authorization": f"Bearer {api_key}"}

                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        files=files,
                        data=data,
                        headers=headers,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return result.get("text", "")
                    else:
                        logger.error(
                            f"Whisper API error: {response.status_code} - {response.text}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Audio transcription fallback failed: {e}")
            return None
