"""
Tool execution wrapper with error handling, retry logic, and caching.

This module provides enhanced tool execution capabilities including
automatic retries, result caching, and detailed error handling.
"""

from typing import Dict, Any, Optional, Callable, List
import asyncio
import time
import hashlib
import json
from datetime import datetime, timedelta
from functools import wraps
import logging

from .base import Tool, ToolResult, ToolError, ToolStatus


logger = logging.getLogger(__name__)


class ToolExecutor:
    """Enhanced tool executor with retry logic and caching."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        exponential_backoff: bool = True,
        cache_ttl: int = 300,  # 5 minutes
        enable_cache: bool = True
    ):
        """
        Initialize the tool executor.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            exponential_backoff: Whether to use exponential backoff for retries
            cache_ttl: Cache time-to-live in seconds
            enable_cache: Whether to enable result caching
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.exponential_backoff = exponential_backoff
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    def _generate_cache_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate a cache key for tool execution."""
        # Create a deterministic string representation of args
        args_str = json.dumps(args, sort_keys=True)
        key_data = f"{tool_name}:{args_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def _get_cached_result(self, cache_key: str) -> Optional[ToolResult]:
        """Get cached result if available and not expired."""
        if not self.enable_cache:
            return None
        
        async with self._lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                expires_at = cached["expires_at"]
                
                if datetime.now() < expires_at:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached["result"]
                else:
                    # Remove expired entry
                    del self._cache[cache_key]
        
        return None
    
    async def _cache_result(self, cache_key: str, result: ToolResult) -> None:
        """Cache a tool execution result."""
        if not self.enable_cache:
            return
        
        async with self._lock:
            self._cache[cache_key] = {
                "result": result,
                "expires_at": datetime.now() + timedelta(seconds=self.cache_ttl)
            }
    
    async def _clean_expired_cache(self) -> None:
        """Remove expired cache entries."""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, value in self._cache.items()
                if value["expires_at"] < now
            ]
            for key in expired_keys:
                del self._cache[key]
    
    async def execute_with_retry(
        self,
        tool: Tool,
        args: Dict[str, Any],
        on_retry: Optional[Callable[[int, Exception], None]] = None
    ) -> ToolResult:
        """
        Execute a tool with automatic retry on failure.
        
        Args:
            tool: Tool instance to execute
            args: Arguments for the tool
            on_retry: Optional callback called on each retry with (attempt, exception)
            
        Returns:
            ToolResult from execution
        """
        # Check cache if tool is cacheable
        cache_key = None
        if tool.cacheable:
            cache_key = self._generate_cache_key(tool.name, args)
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Execute the tool
                result = await tool.execute_with_timeout(args)
                
                # If successful, cache the result if applicable
                if result.is_success() and cache_key:
                    await self._cache_result(cache_key, result)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Don't retry if it's the last attempt
                if attempt < self.max_retries:
                    # Calculate retry delay
                    delay = self.retry_delay
                    if self.exponential_backoff:
                        delay *= (2 ** attempt)
                    
                    logger.warning(
                        f"Tool execution failed, retrying in {delay}s",
                        tool=tool.name,
                        attempt=attempt + 1,
                        error=str(e)
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
        
        # All retries failed
        error_msg = f"Tool execution failed after {self.max_retries + 1} attempts"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        
        return ToolResult(
            status=ToolStatus.FAILURE,
            error=error_msg,
            metadata={"attempts": self.max_retries + 1}
        )
    
    async def execute_batch(
        self,
        executions: List[Dict[str, Any]],
        parallel: bool = True,
        max_concurrent: int = 5
    ) -> List[ToolResult]:
        """
        Execute multiple tools in batch.
        
        Args:
            executions: List of dicts with 'tool' and 'args' keys
            parallel: Whether to execute in parallel or sequentially
            max_concurrent: Maximum concurrent executions (for parallel mode)
            
        Returns:
            List of ToolResults in the same order as input
        """
        if parallel:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def execute_with_semaphore(tool: Tool, args: Dict[str, Any]) -> ToolResult:
                async with semaphore:
                    return await self.execute_with_retry(tool, args)
            
            # Execute all tools concurrently
            tasks = [
                execute_with_semaphore(exec_dict["tool"], exec_dict["args"])
                for exec_dict in executions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to ToolResults
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    final_results.append(
                        ToolResult(
                            status=ToolStatus.FAILURE,
                            error=str(result)
                        )
                    )
                else:
                    final_results.append(result)
            
            return final_results
        else:
            # Execute sequentially
            results = []
            for exec_dict in executions:
                result = await self.execute_with_retry(
                    exec_dict["tool"],
                    exec_dict["args"]
                )
                results.append(result)
            
            return results
    
    def clear_cache(self, tool_name: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            tool_name: Optional tool name to clear cache for, or None for all
        """
        if tool_name:
            # Clear cache for specific tool
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{tool_name}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            # Clear all cache
            self._cache.clear()


class ToolChain:
    """Execute tools in a chained sequence, passing results between them."""
    
    def __init__(self, executor: Optional[ToolExecutor] = None):
        """
        Initialize tool chain.
        
        Args:
            executor: Tool executor to use (creates default if not provided)
        """
        self.executor = executor or ToolExecutor()
        self.steps: List[Dict[str, Any]] = []
    
    def add_step(
        self,
        tool: Tool,
        args: Dict[str, Any],
        transform: Optional[Callable[[ToolResult], Dict[str, Any]]] = None
    ) -> "ToolChain":
        """
        Add a step to the chain.
        
        Args:
            tool: Tool to execute
            args: Arguments for the tool (can reference previous results)
            transform: Optional function to transform result for next step
            
        Returns:
            Self for chaining
        """
        self.steps.append({
            "tool": tool,
            "args": args,
            "transform": transform
        })
        return self
    
    async def execute(self) -> List[ToolResult]:
        """
        Execute the tool chain.
        
        Returns:
            List of all tool results in order
        """
        results = []
        context = {}
        
        for i, step in enumerate(self.steps):
            # Resolve arguments (replace placeholders with previous results)
            resolved_args = self._resolve_args(step["args"], context)
            
            # Execute tool
            result = await self.executor.execute_with_retry(
                step["tool"],
                resolved_args
            )
            results.append(result)
            
            # Store result in context
            context[f"step_{i}"] = result
            context[f"{step['tool'].name}_result"] = result
            
            # Apply transformation if provided
            if step["transform"] and result.is_success():
                transformed = step["transform"](result)
                context[f"step_{i}_transformed"] = transformed
            
            # Stop chain if step failed
            if not result.is_success():
                logger.warning(
                    f"Tool chain stopped at step {i} due to failure",
                    tool=step["tool"].name,
                    error=result.error
                )
                break
        
        return results
    
    def _resolve_args(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve argument placeholders with values from context."""
        resolved = {}
        
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$"):
                # This is a placeholder, resolve from context
                context_key = value[1:]  # Remove $
                if context_key in context:
                    resolved[key] = context[context_key]
                else:
                    resolved[key] = value  # Keep as-is if not found
            else:
                resolved[key] = value
        
        return resolved


# Global executor instance
_global_executor = ToolExecutor()


def get_global_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    return _global_executor