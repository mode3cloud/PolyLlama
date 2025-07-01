"""
Tool registry for managing and discovering available tools.

This module provides a central registry for all tools available to agents,
including registration, discovery, and execution capabilities.
"""

from typing import Dict, List, Optional, Set, Any
import asyncio
from datetime import datetime
import logging
from collections import defaultdict

from .base import Tool, ToolResult, ToolError, ToolStatus


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for managing agent tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, Set[str]] = defaultdict(set)
        self._usage_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_execution_time": 0.0,
            "last_used": None
        })
        self._lock = asyncio.Lock()
    
    def register(self, tool: Tool, category: Optional[str] = None) -> None:
        """
        Register a new tool in the registry.
        
        Args:
            tool: Tool instance to register
            category: Optional category for grouping tools
            
        Raises:
            ValueError: If a tool with the same name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
        
        if category:
            self._categories[category].add(tool.name)
        
        logger.info(f"Registered tool: {tool.name} (version: {tool.version})")
    
    def unregister(self, tool_name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Args:
            tool_name: Name of the tool to remove
            
        Returns:
            True if the tool was removed, False if it didn't exist
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            
            # Remove from categories
            for category_tools in self._categories.values():
                category_tools.discard(tool_name)
            
            logger.info(f"Unregistered tool: {tool_name}")
            return True
        
        return False
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available tools with their metadata.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of tool information dictionaries
        """
        tools = []
        
        if category:
            tool_names = self._categories.get(category, set())
            tool_list = [self._tools[name] for name in tool_names if name in self._tools]
        else:
            tool_list = list(self._tools.values())
        
        for tool in tool_list:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "version": tool.version,
                "cacheable": tool.cacheable,
                "requires_auth": tool.requires_auth,
                "timeout": tool.timeout,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required
                    }
                    for p in tool.parameters
                ]
            })
        
        return tools
    
    def get_categories(self) -> List[str]:
        """
        Get list of all tool categories.
        
        Returns:
            List of category names
        """
        return list(self._categories.keys())
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """
        Get tool names in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of tool names in the category
        """
        return list(self._categories.get(category, set()))
    
    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        timeout: Optional[float] = None,
        track_usage: bool = True
    ) -> ToolResult:
        """
        Execute a tool by name with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            timeout: Optional timeout override
            track_usage: Whether to track usage statistics
            
        Returns:
            ToolResult from the execution
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                status=ToolStatus.FAILURE,
                error=f"Tool '{tool_name}' not found in registry"
            )
        
        # Track usage before execution
        if track_usage:
            async with self._lock:
                stats = self._usage_stats[tool_name]
                stats["total_calls"] += 1
                stats["last_used"] = datetime.now().isoformat()
        
        # Execute the tool
        result = await tool.execute_with_timeout(args, timeout)
        
        # Track usage after execution
        if track_usage:
            async with self._lock:
                stats = self._usage_stats[tool_name]
                if result.is_success():
                    stats["successful_calls"] += 1
                else:
                    stats["failed_calls"] += 1
                
                if result.execution_time:
                    stats["total_execution_time"] += result.execution_time
        
        return result
    
    def get_usage_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage statistics for tools.
        
        Args:
            tool_name: Optional specific tool name, or None for all tools
            
        Returns:
            Dictionary of usage statistics
        """
        if tool_name:
            stats = self._usage_stats.get(tool_name, {})
            if stats and stats["total_calls"] > 0:
                stats["average_execution_time"] = (
                    stats["total_execution_time"] / stats["total_calls"]
                )
            return {tool_name: stats}
        else:
            all_stats = {}
            for name, stats in self._usage_stats.items():
                stats_copy = stats.copy()
                if stats_copy["total_calls"] > 0:
                    stats_copy["average_execution_time"] = (
                        stats_copy["total_execution_time"] / stats_copy["total_calls"]
                    )
                all_stats[name] = stats_copy
            return all_stats
    
    def clear_usage_stats(self, tool_name: Optional[str] = None) -> None:
        """
        Clear usage statistics.
        
        Args:
            tool_name: Optional specific tool name, or None to clear all
        """
        if tool_name:
            if tool_name in self._usage_stats:
                self._usage_stats[tool_name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_execution_time": 0.0,
                    "last_used": None
                }
        else:
            self._usage_stats.clear()
    
    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for tools by name or description.
        
        Args:
            query: Search query (case-insensitive)
            
        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        matching_tools = []
        
        for tool in self._tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                matching_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "version": tool.version
                })
        
        return matching_tools
    
    async def validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate arguments for a tool without executing it.
        
        Args:
            tool_name: Name of the tool
            args: Arguments to validate
            
        Returns:
            Validated arguments
            
        Raises:
            ToolError: If validation fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ToolError(f"Tool '{tool_name}' not found")
        
        return await tool.validate_args(args)
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the schema for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool schema or None if not found
        """
        tool = self.get_tool(tool_name)
        return tool.get_schema() if tool else None
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Get schemas for all registered tools.
        
        Returns:
            Dictionary mapping tool names to their schemas
        """
        return {
            name: tool.get_schema()
            for name, tool in self._tools.items()
        }


# Global registry instance
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _global_registry