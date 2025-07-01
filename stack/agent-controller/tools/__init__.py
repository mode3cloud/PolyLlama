"""
PolyLlama Agent Tools Package

This package provides a standardized interface for integrating external tools
and services with the agent controller.
"""

from .base import Tool, ToolResult, ToolError, ToolStatus, ToolParameter
from .registry import ToolRegistry, get_global_registry
from .executor import ToolExecutor, ToolChain, get_global_executor
from .formatter import ResultNormalizer, get_global_normalizer
from .metrics import MetricsCollector, get_global_metrics
from .auth import AuthManager, get_global_auth_manager, User, Role, Permission
from .streaming import StreamingTool, StreamEvent, StreamEventType, StreamingExecutor
from .docs import DocumentationGenerator

__all__ = [
    # Core interfaces
    "Tool", 
    "ToolResult", 
    "ToolError", 
    "ToolStatus",
    "ToolParameter",
    
    # Registry and execution
    "ToolRegistry",
    "get_global_registry",
    "ToolExecutor",
    "ToolChain",
    "get_global_executor",
    
    # Result formatting
    "ResultNormalizer",
    "get_global_normalizer",
    
    # Metrics and monitoring
    "MetricsCollector",
    "get_global_metrics",
    
    # Authentication and authorization
    "AuthManager",
    "get_global_auth_manager",
    "User",
    "Role", 
    "Permission",
    
    # Streaming support
    "StreamingTool",
    "StreamEvent",
    "StreamEventType",
    "StreamingExecutor",
    
    # Documentation
    "DocumentationGenerator"
]