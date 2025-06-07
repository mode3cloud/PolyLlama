import os
import re
import json
import time
import math
import asyncio
import logging
import hashlib
from functools import lru_cache, wraps
from typing import Any, Callable, Dict, List, Optional, Union, Tuple, AsyncGenerator, Protocol

import litellm  # liteLLM universal SDK
from litellm.utils import token_counter
from mcp_tools.shared.message_manager import MessageManager 
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# 🛠️  T O O L  C L A S S E S
# ---------------------------------------------------------------------------

class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        """Format tool information for LLM.

        Returns:
            A formatted string describing the tool.
        """
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {self.name}
Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""


class ToolManagerProtocol(Protocol):
    """Protocol for tool managers that can execute tools."""
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with the given arguments."""
        ...


# ---------------------------------------------------------------------------
# ♻️  C A C H I N G  &  M O D E L  L I S T I N G
# ---------------------------------------------------------------------------
LLM_CACHE_SIZE = int(os.getenv("MULTI_LLM_CACHE_SIZE", "1000"))
_llm_response_cache: Dict[str, Any] = {}

# Model listing and caching (TTL 60s)
_model_list_cache: Dict[str, Tuple[float, List[str]]] = {}
import httpx

async def get_available_models(provider: Optional[str] = None, force_refresh: bool = False) -> List[str]:
    """
    List available models for a given provider, or for all supported providers if provider is None.

    Args:
        provider: Provider name (e.g. "openai", "anthropic", "ollama", "lm_studio"). If None, lists for all.
        force_refresh: If True, bypass cache.

    Returns:
        List of model names (if provider given) or all models (if provider is None).
    """
    now = time.time()
    ttl = 60

    providers = ["openai", "anthropic", "ollama", "lm_studio"]

    # If provider is specified, do as before
    if provider is not None:
        if not force_refresh and provider in _model_list_cache:
            ts, models = _model_list_cache[provider]
            if now - ts < ttl:
                return models
        try:
            models = []
            if provider == "openai":
                try:
                    import openai
                    from openai import AsyncOpenAI

                    api_key = os.getenv("OPENAI_API_KEY")
                    api_base = os.getenv("OPENAI_API_BASE")

                    aclient = AsyncOpenAI(api_key=api_key, base_url=api_base) if hasattr(openai, "AsyncOpenAI") else openai.OpenAI(
                        api_key=api_key
                    )

                    if hasattr(openai.Model, "alist"):
                        resp = await aclient.models.list()
                        # Handle both OpenAI v1+ (AsyncPage[Model]) and legacy dict response
                        if isinstance(resp, dict) and "data" in resp:
                            models = [m["id"] for m in resp["data"]]
                        else:
                            # OpenAI v1+ returns AsyncPage[Model], which is an async iterable
                            models = [m.id async for m in resp]
                    else:
                        # Fallback to HTTPX
                        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                        base = api_base or "https://api.openai.com/v1"
                        async with httpx.AsyncClient(timeout=5) as client:
                            resp = await client.get(f"{base}/models", headers=headers)
                            resp.raise_for_status()
                            data = resp.json()
                            models = [m["id"] for m in data.get("data", [])]
                except Exception as e:
                    logger.warning(f"OpenAI model listing failed: {e}")
            elif provider == "anthropic":
                # No public API for model listing; return known models
                models = [
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                    "claude-2.1",
                    "claude-2.0",
                    "claude-instant-1.2",
                ]
            elif provider == "ollama":
                base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(f"{base}/api/tags")
                        resp.raise_for_status()
                        data = resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                except Exception as e:
                    logger.warning(f"Ollama model listing failed: {e}")
            elif provider == "lm_studio":
                base = os.getenv("LM_STUDIO_API_BASE", "http://localhost:1234")
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(f"{base}/models")
                        resp.raise_for_status()
                        data = resp.json()
                        models = [m["id"] for m in data.get("data", [])]
                except Exception as e:
                    logger.warning(f"LM Studio model listing failed: {e}")
            else:
                logger.warning(f"Unknown provider for model listing: {provider}")
            # Convert to list of objects with name, provider, full_name
            model_objs = [
                {
                    "name": model,
                    "provider": provider,
                    "full_name": f"{provider}/{model}"
                }
                for model in models
            ]
            _model_list_cache[provider] = (now, model_objs)
            return model_objs
        except Exception as e:
            logger.warning(f"Model listing failed for {provider}: {e}")
            return []
    # If provider is None, list for all
    all_models = []
    for prov in providers:
        try:
            prov_models = await get_available_models(prov, force_refresh=force_refresh)
            all_models.extend(prov_models)
        except Exception as e:
            logger.warning(f"Model listing failed for {prov}: {e}")
    return all_models

# ---------------------------------------------------------------------------
# 🧮  T O K E N   U T I L S
# ---------------------------------------------------------------------------
MODEL_TOKEN_LIMITS = {
    "gpt-3.5-turbo": 16385,
    "gpt-4": 8192,
    "gpt-4o": 128000,
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "default": 8000,
}
TOKEN_SAFETY_BUFFER = 1000

class _MessageTokenManager:
    @staticmethod
    def model_limit(model: str) -> int:
        base = model.split("/")[-1]
        return MODEL_TOKEN_LIMITS.get(base, MODEL_TOKEN_LIMITS["default"])

    @staticmethod
    def count(messages: List[Dict[str, Any]], model: str) -> int:
        total = 0
        for m in messages:
            txt = m.get("content", "")
            total += token_counter(model=model, text=txt)
            if "tool_calls" in m:
                total += token_counter(model=model, text=json.dumps(m["tool_calls"]))
        # small overhead per message
        return total + len(messages) * 4


# ---------------------------------------------------------------------------
# 🔨  S C H E M A  /  J S O N  F I X U P
# ---------------------------------------------------------------------------

def _strip_md_json(text: str) -> str:
    if text is None:
        return ""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text

def _unwrap_schema(obj: Any) -> Any:
    """
    Recursively collapse objects that look like:
      - {type:'string',description:'x'} → 'x'
      - {description: {...}} → unwrap the value
    """
    if isinstance(obj, list):
        return [_unwrap_schema(i) for i in obj]
    if isinstance(obj, dict):
        # whole-object schema
        if set(obj.keys()) >= {"type", "description"} and isinstance(obj["description"], str):
            return obj["description"]
        # nested description dict: {description: {...}}
        if set(obj.keys()) == {"description"} and isinstance(obj["description"], dict):
            return _unwrap_schema(obj["description"])
        # properties wrapper
        if "properties" in obj and isinstance(obj["properties"], dict):
            obj = obj["properties"]
        return {k: _unwrap_schema(v) for k, v in obj.items()}
    return obj

def _repair_schema(obj: Any, defaults: dict = None) -> Any:
    """
    Deep schema repair: recursively unwrap, inject defaults, and fix common issues.
    """
    if defaults is None:
        defaults = {}
    if isinstance(obj, list):
        return [_repair_schema(i, defaults) for i in obj]
    if isinstance(obj, dict):
        # Unwrap {description: {...}} or {type, description: ...}
        if set(obj.keys()) == {"description"} and isinstance(obj["description"], dict):
            return _repair_schema(obj["description"], defaults)
        if set(obj.keys()) >= {"type", "description"} and isinstance(obj["description"], str):
            return obj["description"]
        # Inject defaults for missing required fields
        result = {}
        for k, v in obj.items():
            result[k] = _repair_schema(v, defaults.get(k, {}))
        for k, v in defaults.items():
            if k not in result:
                result[k] = v
        return result
    return obj

# ---------------------------------------------------------------------------
# 🏗️   M A I N   S E R V I C E
# ---------------------------------------------------------------------------
class MultiLLMService:
    """
    Unified streaming-only LLM service with integrated tool orchestration.

    ARCHITECTURE:
    - Single entry point: chat_completion() always returns AsyncGenerator
    - Streaming-only: All responses yield chunks as they arrive  
    - Event-driven persistence: Messages stored at moment of occurrence
    - Integrated tools: Tool orchestration within main streaming flow
    - Provider-agnostic: Works with OpenAI, Anthropic, Ollama, LM Studio
    - Mock-injectable: Constructor accepts mock_provider for testing

    Features:
    • Automatic token truncation with context preservation
    • Multi-turn tool conversations with iterative orchestration  
    • Optional message persistence to Neo4j via MessageManager
    • File/attachment processing with audio transcription fallback
    • Provider parameter filtering and error handling
    • JSON parsing retry mechanism for structured outputs
    """
    
    # Default number of retries for JSON parsing in structured output
    DEFAULT_JSON_PARSE_RETRIES = int(os.getenv("MULTI_LLM_JSON_PARSE_RETRIES", "3"))

    def __init__(
        self,
        model: str | None = None,
        *,
        neo4j_driver: Any | None = None,
        cache_enabled: bool = True,
        timeout: int = int(os.getenv("MULTI_LLM_REQUEST_TIMEOUT", "120")),
        max_concurrent: int = int(os.getenv("MULTI_LLM_CLIENT_MAX_CONCURRENT", "3")),
        mock_provider: Optional[Callable] = None, 
    ) -> None:
        self.model = model or os.getenv("DEFAULT_LLM_MODEL_NAME", "openai/gpt-4o")
        self.cache_enabled = cache_enabled
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # persistence layer
        self.message_manager: MessageManager | None = None
        if neo4j_driver and MessageManager:
            self.message_manager = MessageManager(neo4j_driver)

        # propagate env vars for litellm
        self._prepare_env()
        litellm.modify_params = True  # needed for Anthropic tool calling quirk

        # Streaming infinite loop protection
        litellm.REPEATED_STREAMING_CHUNK_LIMIT = 1000

        # Mock provider injection for testing
        if mock_provider:
            self._acompletion = mock_provider
        else:
            self._acompletion = litellm.acompletion
            
        # Patch self._acompletion for Ollama/arguments bug
        self._patch_litellm_acompletion()

    # ------------------------------------------------------------------
    # 🗣️  P U B L I C   A P I
    # ------------------------------------------------------------------
    def set_model(self, model: str) -> None:
        """
        Update the current model and refresh any dependent state.
        """
        self.model = model
        self._prepare_env()
        # Optionally clear model-specific caches if needed

    def _filter_supported_kwargs(self, model: str, kw: dict) -> dict:
        """
        Filter kwargs to only those supported by the current model/provider.
        Logs a warning if any keys are filtered out.
        """
        if len(kw) == 0:
            return kw
        params_from_litellm = litellm.get_supported_openai_params(model)
        if params_from_litellm is None:
            logger.warning(f"Could not determine supported params for model '{model}'. Returning unfiltered.")
            return kw  # No filtering if we can't determine params
        
        params = set(params_from_litellm) if params_from_litellm else set()
        # Always allow 'api_base', 'api_key', 'api_version' for custom endpoints
        params.update({"api_base", "api_key", "api_version"})
        filtered = {k: v for k, v in kw.items() if k in params}
        removed = {k: v for k, v in kw.items() if k not in params}
        if removed:
            logger.warning(f"Filtered out unsupported kwargs for model '{model}': {removed}")
        return filtered

    async def chat_completion(
        self,
        messages: List[litellm.Message],
        *,
        persistence: bool = False,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools_prompt: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        tool_manager: Optional["ToolManagerProtocol"] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        attachments: Optional[List[str]] = None,
        **kw: Any,
    ) -> AsyncGenerator:
        """
        Always returns an async generator that yields response chunks as they arrive.
        All responses are streamed; non-streaming logic is removed.
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

        # Message Assembly & Persistence
        current_messages = []
        sys_prompt = self._augment_system_prompt(system_prompt or "", tools_prompt, tools)
        if sys_prompt and (not conversation_history or conversation_history[0].get("role") != "system"):
            current_messages.append({"role": "system", "content": sys_prompt})
            if persistence:
                await self.message_manager.add_system_message(session_id, sys_prompt)

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
                    await self.message_manager.add_user_message(session_id, msg_dict["content"])

        # File/attachment processing (persist as user messages if persistence)
        if attachments:
            import inspect
            from mcp_tools.tools.qdrant.qdrant_ingest.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            for path in attachments:
                try:
                    file_info = None
                    if inspect.iscoroutinefunction(processor.process_file):
                        file_info = await processor.process_file(path)
                    else:
                        file_info = processor.process_file(path)
                    # Audio fallback: if audio and no transcript, try Whisper
                    if file_info and file_info.get("type") == "audio" and not file_info.get("transcript"):
                        try:
                            transcript = await self._transcribe_audio_fallback(path)
                            if transcript:
                                file_info["transcript"] = transcript
                                file_info["summary"] = f"[Transcribed audio]: {transcript[:200]}"
                        except Exception as e:
                            logger.warning(f"Audio fallback transcription failed for {path}: {e}")
                    attach_msg = {
                        "role": "user",
                        "content": f"[ATTACHMENT: {os.path.basename(path)}]\n{file_info.get('summary','')}"
                    }
                    current_messages.append(attach_msg)
                    if persistence:
                        await self.message_manager.add_user_message(session_id, attach_msg["content"])
                except Exception as e:
                    logger.warning(f"Attachment processing failed for {path}: {e}")

        # Combine with history
        full_conversation = conversation_history + current_messages
        tools_spec = self._format_tools(tools) if tools else None

        filtered_kw = self._filter_supported_kwargs(self.model, kw)

        # Streaming LLM Call with Integrated Orchestration
        async with self.semaphore:
            logger.debug("Semaphore acquired")
            assistant_buffer = []
            iteration = 0
            max_iterations = 10
            current_msgs = full_conversation.copy()
            should_continue = True
            while iteration < max_iterations and should_continue:
                iteration += 1
                completion_kwargs = {
                    "model": self.model,
                    "messages": current_msgs,
                    "tools": tools_spec,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    **filtered_kw,
                }
                resp_stream = await self._acompletion(**completion_kwargs)
                tool_buffers = {}
                active_tool_ids = set()
                last_tool_id = None
                # Streaming loop
                async for chunk in resp_stream:
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        # Check for finish_reason
                        if hasattr(chunk.choices[0], "finish_reason") and chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                        # Content streaming
                        if getattr(delta, "content", None):
                            assistant_buffer.append(delta.content)
                            yield {"type": "content", "content": delta.content}
                        # Tool-call streaming (buffered)
                        if getattr(delta, "tool_calls", None) and tool_manager:
                            for tc in delta.tool_calls:
                                tc_id = getattr(tc, "id", None)
                                tc_name = getattr(tc.function, "name", None) if hasattr(tc, "function") else None
                                tc_args = getattr(tc.function, "arguments", None) if hasattr(tc, "function") else None
                                # New tool call (has both id and name)
                                if tc_id and tc_name:
                                    tool_buffers[tc_id] = {"name": tc_name, "args": ""}
                                    last_tool_id = tc_id
                                    active_tool_ids.add(tc_id)
                                # Arguments for specific tool (has id but no name)
                                elif tc_id and tc_id in tool_buffers and tc_args:
                                    tool_buffers[tc_id]["args"] += tc_args
                                # Continuation of existing tool (only arguments, no id/name)
                                elif tc_args and last_tool_id and last_tool_id in tool_buffers:
                                    tool_buffers[last_tool_id]["args"] += tc_args
                                # Fallback: append to most recent tool if we have args but no clear target
                                elif tc_args and last_tool_id:
                                    if last_tool_id not in tool_buffers:
                                        tool_buffers[last_tool_id] = {"name": "unknown", "args": ""}
                                        active_tool_ids.add(last_tool_id)
                                    tool_buffers[last_tool_id]["args"] += tc_args
                    # Process completed tool calls on finish_reason
                    if hasattr(chunk, "choices") and chunk.choices and chunk.choices[0].finish_reason in ("tool_calls", "stop"):
                        
                        # Check if there are any active tool calls to process
                        tool_calls_processed = False
                        for tool_id in list(active_tool_ids):
                            buf = tool_buffers.pop(tool_id, None)
                            if buf:
                                tool_calls_processed = True
                                try:
                                    args = json.loads(buf["args"] or "{}")
                                    # Add assistant tool call message
                                    tool_call_msg = {
                                        "role": "assistant",
                                        "tool_calls": [{
                                            "id": tool_id,
                                            "type": "function",
                                            "function": {"name": buf["name"], "arguments": json.dumps(args)}
                                        }]
                                    }
                                    current_msgs.append(tool_call_msg)
                                    # Execute tool and add to conversation
                                    result = await tool_manager.execute_tool(buf["name"], args)
                                    tool_result_msg = {
                                        "role": "tool",
                                        "name": buf["name"],
                                        "content": result,
                                        "tool_call_id": tool_id
                                    }
                                    current_msgs.append(tool_result_msg)
                                    if persistence:
                                        await self.message_manager.add_tool_message(
                                            session_id, result, buf["name"], tool_id
                                        )
                                    yield {"type": "tool_result", "name": buf["name"], "result": result}
                                except Exception as err:
                                    error_msg = {"role": "tool", "content": f"Error: {str(err)}", "tool_call_id": tool_id}
                                    current_msgs.append(error_msg)
                                    yield {"type": "tool_error", "error": str(err)}
                                active_tool_ids.remove(tool_id)
                        
                        # Decide whether to continue or break based on whether tool calls were processed
                        if tool_calls_processed or chunk.choices[0].finish_reason == "tool_calls":
                            # Either we processed tool calls or the finish reason explicitly indicates tool calls
                            break
                        else:
                            # finish_reason is "stop" and no tool calls were processed - exit the while loop
                            should_continue = False
                            break
                else:
                    # No more tool calls, break loop
                    should_continue = False
                    break
            # Persist final assistant message
            final_content = "".join(assistant_buffer)
            if persistence and final_content:
                await self.message_manager.add_assistant_message(session_id, final_content)
            yield {"type": "complete", "content": final_content}

    async def chat_completion_structured(
        self,
        messages: List[Dict[str, Any]],
        *,
        persistence: bool = False,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools_prompt: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        tool_manager: Optional["ToolManagerProtocol"] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        response_format: Optional[Any] = None,
        attachments: Optional[List[str]] = None,
        max_retries: Optional[int] = None,
        **kw: Any,
    ) -> Dict[str, Any]:
        """
        Structured output wrapper for chat_completion with retry logic for JSON parsing.
        Collects streaming response and extracts JSON when response_format is provided.
        If JSON parsing fails, retries with an error message asking for correct format.
        
        Args:
            max_retries: Maximum number of retries for JSON parsing (default: from env or 3)
            
        Returns:
            Dict[str, Any]: Parsed JSON response
            
        Raises:
            ValueError: If JSON parsing fails after all retry attempts
        """
        import json
        import re
        
        # Use default if not specified
        if max_retries is None:
            max_retries = self.DEFAULT_JSON_PARSE_RETRIES
        
        # Flatten nested lists and convert all Message objects to dicts
        def flatten_messages(msgs):
            for m in msgs:
                if isinstance(m, list):
                    yield from flatten_messages(m)
                elif hasattr(m, "role") and hasattr(m, "content"):
                    yield {"role": m.role, "content": m.content}
                elif isinstance(m, dict):
                    yield m
                else:
                    raise TypeError(f"Unexpected message type: {type(m)}")

        messages = list(flatten_messages(messages))
        
        # Keep track of messages for retries        
        retry_messages = messages.copy()
        
        for attempt in range(max_retries):
            # Collect all chunks from streaming response
            content_chunks = []
            complete_content = ""
            
            async for chunk in self.chat_completion(
                retry_messages,
                persistence=persistence,
                session_id=session_id,
                system_prompt=system_prompt,
                tools_prompt=tools_prompt,
                tools=tools,
                tool_manager=tool_manager,
                temperature=temperature,
                max_tokens=max_tokens,
                attachments=attachments,
                **kw,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "content":
                        content_chunks.append(chunk.get("content", ""))
                    elif chunk.get("type") == "complete":
                        # Use complete content if available
                        complete_content = chunk.get("content", "")
            
            # Get the final content
            result_text = complete_content if complete_content else "".join(content_chunks)
            
            # Try to extract JSON
            result = self._extract_json_with_validation(result_text, response_format)
            
            # If we got a valid result, return it
            if result is not None:
                return result
            
            # If this wasn't the last attempt, add retry message
            if attempt < max_retries - 1:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}/{max_retries}. Retrying with error message.")
                
                # Add the failed response to messages for context
                retry_messages.append({
                    "role": "assistant",
                    "content": result_text
                })
                
                # Add error message asking for correct format
                error_msg = self._create_json_retry_message(result_text, response_format)
                retry_messages.append({
                    "role": "user",
                    "content": error_msg
                })
        
        # All retries failed - raise exception
        error_msg = f"Failed to parse valid JSON after {max_retries} attempts. Last response: {result_text[:200]}..."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    def _extract_json_with_validation(self, text: str, response_format: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """
        Extract and validate JSON from text.
        Returns the parsed JSON if valid, or None if parsing fails.
        """
        result = self._extract_json(text)
        
        # If we got an empty dict, it means parsing failed
        if not result and text.strip():
            return None
        
        # TODO: Add validation against response_format schema if provided
        # For now, just return the result if we successfully parsed something
        return result if result else None
    
    def _create_json_retry_message(self, failed_response: str, response_format: Optional[Any] = None) -> str:
        """
        Create a retry message explaining the JSON parsing error and requesting correct format.
        """
        import json
        
        error_msg = "Your previous response could not be parsed as valid JSON. "
        
        # Try to identify the specific parsing error
        try:
            json.loads(failed_response)
        except json.JSONDecodeError as e:
            error_msg += f"JSON parsing error: {str(e)}. "
        
        error_msg += "\n\nPlease provide your response as valid JSON. "
        
        if response_format:
            error_msg += f"The expected format is:\n{json.dumps(response_format, indent=2)}\n\n"
        
        error_msg += "Make sure to:\n"
        error_msg += "1. Use proper JSON syntax with double quotes for strings\n"
        error_msg += "2. Ensure all brackets and braces are properly closed\n"
        error_msg += "3. Avoid trailing commas\n"
        error_msg += "4. Return ONLY the JSON object, without any additional text or markdown formatting"
        
        return error_msg
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text with multiple fallback strategies."""
        import json
        import re
        
        if not text:
            return {}
        
        # First, try parsing the raw text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object or array in the text
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # If all parsing attempts fail, log warning and return empty dict
        logger.warning(f"Failed to parse JSON from response: {text[:200]}...")
        return {}
    
    # ------------------------------------------------------------------
    # 🔒  P R O V I D E R   C A L L S
    # ------------------------------------------------------------------

    # [REMOVED: _iterative_tool_call_core, _iterative_tool_call_streaming, _iterative_tool_call_nonstreaming, _stream_with_persistence per strict refactor instructions]
    # ------------------------------------------------------------------
    # 🛠️  H E L P E R S
    # ------------------------------------------------------------------
    @staticmethod
    def _format_tools(tools: List[Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    # ------------------------------------------------------------------
    # 💾  PERSISTENT CHAT API
    # ------------------------------------------------------------------
    # [REMOVED: chat_completion_with_persistence and all duplicate persistence logic per refactor instructions]
    def _prepare_env(self):
        """Propagate provider‑specific env vars for litellm to pick up."""
        env_map = {
            "openai": ("OPENAI_API_KEY", "OPENAI_API_BASE"),
            "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_API_BASE"),
            "ollama": ("OLLAMA_API_KEY", "OLLAMA_API_BASE"),
            "lm_studio": ("LM_STUDIO_API_KEY", "LM_STUDIO_API_BASE"),
        }
        for provider, (key_var, base_var) in env_map.items():
            # Robust: set env var if not present
            if not os.environ.get(key_var) and os.getenv(key_var):
                os.environ[key_var] = os.getenv(key_var)
            if not os.environ.get(base_var) and os.getenv(base_var):
                os.environ[base_var] = os.getenv(base_var)

    def _add_to_cache(self, key: str, value: Any):
        _llm_response_cache[key] = value
        if LLM_CACHE_SIZE and len(_llm_response_cache) > LLM_CACHE_SIZE:
            # FIFO eviction
            oldest = next(iter(_llm_response_cache))
            _llm_response_cache.pop(oldest, None)

    def _supports_response_format(self, model: str) -> bool:
        # Check if model supports response_format (OpenAI, not e.g. LM Studio)
        try:
            params = litellm.get_supported_openai_params(model)
            return "response_format" in params or model.startswith("lm_studio")
        except Exception:
            return False

    def _supports_tool_calling(self, model: str) -> bool:
        # Check if model supports tool-calling
        try:
            return litellm.supports_function_calling(model) or model.startswith("lm_studio")
        except Exception:
            return False

    def supports_reasoning(self) -> bool:
        # Expose reasoning support check
        return hasattr(litellm, "supports_reasoning") and litellm.supports_reasoning(self.model)

    def _augment_system_prompt(self, sys_prompt: str, tools_prompt: Optional[str], tools: Optional[List[Tool]]) -> str:
        # Always append current date/time and merge tool prompt if tools present
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        prompt = sys_prompt.strip()
        if tools_prompt:
            prompt += "\n" + tools_prompt.strip()
        if tools:
            prompt += "\n[Tool-calling enabled]"
        prompt += f"\nCurrent date/time: {now}"
        return prompt

    def _looks_like_tool_call_json(self, text: str) -> bool:
        # Detect custom tool-call JSON or GPT-4o action/arguments pattern
        try:
            obj = json.loads(_strip_md_json(text))
            if "tool_calls" in obj:
                return True
            # GPT-4o: {"action": ..., "arguments": {...}}
            if (
                isinstance(obj, dict)
                and "action" in obj
                and "arguments" in obj
                and isinstance(obj["action"], str)
                and isinstance(obj["arguments"], dict)
            ):
                return True
            return False
        except Exception:
            return False

    def _convert_tool_call_json(self, text: str) -> str:
        # Convert custom tool-call JSON or GPT-4o action/arguments to OpenAI format
        try:
            obj = json.loads(_strip_md_json(text))
            if "tool_calls" in obj:
                return json.dumps(obj["tool_calls"])
            # GPT-4o: {"action": ..., "arguments": {...}}
            if (
                isinstance(obj, dict)
                and "action" in obj
                and "arguments" in obj
                and isinstance(obj["action"], str)
                and isinstance(obj["arguments"], dict)
            ):
                # Synthesize OpenAI-style tool_call
                return json.dumps([
                    {
                        "id": "synthetic",
                        "type": "function",
                        "function": {
                            "name": obj["action"],
                            "arguments": json.dumps(obj["arguments"]),
                        },
                    }
                ])
        except Exception:
            pass
        return text

    def analyze_content(self, content: str) -> Dict[str, Any]:
        # Document analysis stub (expand as needed)
        return {"summary": content[:200] + ("..." if len(content) > 200 else "")}

    async def _transcribe_audio_fallback(self, path: str) -> str:
        """
        Try to transcribe audio using local whisper, whisper.cpp, or speech_recognition.
        Returns transcript string or None. Does NOT use OpenAI or any remote API.
        """
        import subprocess
        import os

        # Try local whisper (if installed)
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(path)
            return result.get("text")
        except Exception as e:
            logger.warning(f"Local whisper transcription failed: {e}")

        # Try whisper.cpp via subprocess
        try:
            cmd = ["whisper", path, "--output-txt", "--language", "en"]
            subprocess.run(cmd, check=True)
            txt_path = os.path.splitext(path)[0] + ".txt"
            if os.path.exists(txt_path):
                with open(txt_path, "r") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"whisper.cpp transcription failed: {e}")

        # Try speech_recognition as a last local fallback
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
            logger.info(f"Transcribed audio using Google Speech Recognition: {text[:50]}...")
            return text
        except Exception as e:
            logger.warning(f"speech_recognition transcription failed: {e}")

        return "[Audio transcription failed. Please install whisper, whisper.cpp, or speech_recognition for local transcription]"

    def _patch_litellm_acompletion(self):
        # Patch self._acompletion to handle Ollama/arguments KeyError
        orig_acompletion = self._acompletion

        @wraps(orig_acompletion)
        async def safe_acompletion(*args, **kwargs):
            try:
                return await orig_acompletion(*args, **kwargs)
            except KeyError as e:
                if "arguments" in str(e):
                    # Patch: return synthetic function call with empty arguments
                    class DummyResp:
                        id = "fallback"
                        created = int(time.time())
                        model = kwargs.get('model', 'unknown')
                        usage = type("Usage", (), {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        })()
                        class Choice:
                            finish_reason = "stop"
                            class Message:
                                content = ""
                                tool_calls = [{"function": {"name": "unknown", "arguments": "{}"}}]
                            message = Message()
                        choices = [Choice()]
                    return DummyResp()
                raise
        self._acompletion = safe_acompletion


# ---------------------------------------------------------------------------
# 🔍  U T I L  F N S
# ---------------------------------------------------------------------------

# Helper function to add "continue" capability
def create_continue_message() -> Dict[str, Any]:
    """
    Creates a message that can be added to prompt the LLM to continue
    if it reaches the iteration limit.
    """
    return {
        "role": "user",
        "content": "Please continue with any remaining tool calls or provide your final response."
    }

def _looks_like_json(text: str) -> bool:
    text = text.strip()
    return text.startswith("{") and text.endswith("}")
