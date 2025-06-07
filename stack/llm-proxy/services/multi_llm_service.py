"""
Multi-LLM Service for PolyLlama

Unified streaming LLM service using LiteLLM for provider abstraction.
"""

import os
import json
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator
from functools import wraps

import litellm
import httpx

logger = logging.getLogger(__name__)


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
        default_model = "ollama/llama3.2:latest" if not os.getenv("OPENAI_API_KEY") else "openai/gpt-4o"
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
        messages: List[Dict[str, Any]],
        *,
        session_id: Optional[str] = None,
        persistence: bool = False,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tool_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion using LiteLLM.
        
        Args:
            messages: List of message dictionaries
            session_id: Session ID for persistence
            persistence: Whether to persist messages
            system_prompt: System prompt to prepend
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tool_manager: Tool manager for function calling
            **kwargs: Additional arguments passed to LiteLLM
        
        Yields:
            Dict containing chunk type and content
        """
        if persistence and not session_id:
            raise ValueError("session_id required when persistence=True")
        if persistence and not self.message_manager:
            raise ValueError("MessageManager required when persistence=True")
        
        # Prepare messages
        current_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            current_messages.append({"role": "system", "content": system_prompt})
            if persistence:
                await self.message_manager.add_system_message(session_id, system_prompt)
        
        # Add conversation history if persistence enabled
        if persistence and session_id:
            session_data = await self.message_manager.get_session_messages(session_id)
            conversation_history = session_data.get("messages", [])
            # Filter out system messages to avoid duplication
            conversation_history = [m for m in conversation_history if m.get("role") != "system"]
            current_messages.extend(conversation_history)
        
        # Add new messages
        for msg in messages:
            current_messages.append(msg)
            if persistence and msg.get("role") == "user":
                await self.message_manager.add_user_message(session_id, msg.get("content", ""))
        
        # Filter supported parameters for this model
        filtered_kwargs = self._filter_supported_kwargs(self.model, kwargs)
        
        # Prepare completion arguments
        completion_kwargs = {
            "model": self.model,
            "messages": current_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **filtered_kwargs,
        }
        
        assistant_content = []
        
        async with self.semaphore:
            try:
                logger.info(f"Starting chat completion with model: {self.model}")
                logger.debug(f"Messages: {current_messages}")
                logger.debug(f"Completion kwargs: {completion_kwargs}")
                
                # Make LiteLLM call
                try:
                    response = await litellm.acompletion(**completion_kwargs)
                    
                    if response is None:
                        raise ValueError("LiteLLM returned None response")
                    
                    # Check if response is an async generator
                    import inspect
                    if not inspect.isasyncgen(response):
                        logger.warning(f"Response is not an async generator: {type(response)}")
                        
                except Exception as e:
                    logger.error(f"Error calling litellm.acompletion: {e}", exc_info=True)
                    raise
                
                # Stream response
                chunk_count = 0
                async for chunk in response:
                    chunk_count += 1
                    logger.debug(f"Received chunk {chunk_count}: {chunk}")
                    
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        
                        # Handle content streaming
                        if hasattr(delta, "content") and delta.content:
                            content = delta.content
                            assistant_content.append(content)
                            yield {"type": "content", "content": content}
                        
                        # Handle finish reason
                        if hasattr(chunk.choices[0], "finish_reason") and chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                            if finish_reason == "stop":
                                break
                
                logger.info(f"Received {chunk_count} chunks from LiteLLM")
                
                # Persist final assistant message
                final_content = "".join(assistant_content)
                if persistence and final_content:
                    await self.message_manager.add_assistant_message(session_id, final_content)
                
                yield {"type": "complete", "content": final_content}
                
            except Exception as e:
                logger.error(f"Error in chat completion: {e}", exc_info=True)
                yield {"type": "error", "error": str(e)}
    
    async def get_available_models(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available models from all providers or a specific provider."""
        models = []
        
        if provider == "ollama" or provider is None:
            # Get Ollama models from PolyLlama router
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://router:11434/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        for model in data.get("models", []):
                            models.append({
                                "id": f"ollama/{model['name']}",
                                "name": model["name"],
                                "provider": "ollama",
                                "size": model.get("size", 0)
                            })
            except Exception as e:
                logger.warning(f"Failed to get Ollama models: {e}")
        
        if provider == "openai" or provider is None:
            # Add known OpenAI models if API key is available
            if os.getenv("OPENAI_API_KEY"):
                openai_models = [
                    "gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"
                ]
                for model in openai_models:
                    models.append({
                        "id": f"openai/{model}",
                        "name": model,
                        "provider": "openai"
                    })
        
        if provider == "anthropic" or provider is None:
            # Add known Anthropic models if API key is available
            if os.getenv("ANTHROPIC_API_KEY"):
                anthropic_models = [
                    "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"
                ]
                for model in anthropic_models:
                    models.append({
                        "id": f"anthropic/{model}",
                        "name": model,
                        "provider": "anthropic"
                    })
        
        if provider == "google" or provider is None:
            # Add known Google models if API key is available
            if os.getenv("GOOGLE_API_KEY"):
                google_models = ["gemini-pro", "gemini-pro-vision"]
                for model in google_models:
                    models.append({
                        "id": f"google/{model}",
                        "name": model,
                        "provider": "google"
                    })
        
        if provider == "groq" or provider is None:
            # Add known Groq models if API key is available
            if os.getenv("GROQ_API_KEY"):
                groq_models = ["mixtral-8x7b-32768", "llama2-70b-4096"]
                for model in groq_models:
                    models.append({
                        "id": f"groq/{model}",
                        "name": model,
                        "provider": "groq"
                    })
        
        return models
    
    def _filter_supported_kwargs(self, model: str, kwargs: dict) -> dict:
        """Filter kwargs to only those supported by the model/provider."""
        try:
            supported_params = litellm.get_supported_openai_params(model)
            if supported_params is None:
                return kwargs
            
            # Always allow these common parameters
            always_allowed = {"api_base", "api_key", "api_version"}
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
            
        logger.info(f"Environment variables set - OLLAMA_API_BASE: {os.environ.get('OLLAMA_API_BASE')}")
    
    async def close(self):
        """Clean up resources."""
        pass