"""
Tool result formatting and normalization utilities.

This module provides standardized formatting for tool results to ensure
consistent output across different tools and use cases.
"""

from typing import Dict, Any, List, Optional, Union
import json
from datetime import datetime
from abc import ABC, abstractmethod

from .base import ToolResult, ToolStatus


class ResultFormatter(ABC):
    """Abstract base class for result formatters."""
    
    @abstractmethod
    def format(self, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format a tool result for specific output requirements."""
        pass


class StandardFormatter(ResultFormatter):
    """Standard formatter that provides consistent result structure."""
    
    def format(self, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format result with standard structure.
        
        Args:
            result: Tool result to format
            context: Optional context information
            
        Returns:
            Formatted result dictionary
        """
        formatted = {
            "success": result.is_success(),
            "status": result.status.value,
            "timestamp": datetime.now().isoformat(),
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time,
            "metadata": result.metadata or {}
        }
        
        # Add context if provided
        if context:
            formatted["context"] = context
        
        return formatted


class AgentFormatter(ResultFormatter):
    """Formatter optimized for agent consumption."""
    
    def format(self, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format result for agent processing.
        
        Args:
            result: Tool result to format
            context: Optional context information
            
        Returns:
            Agent-optimized result dictionary
        """
        if result.is_success():
            # Successful result - focus on data
            formatted = {
                "status": "success",
                "result": result.data,
                "summary": self._generate_summary(result),
                "execution_time": result.execution_time
            }
        else:
            # Failed result - focus on error information
            formatted = {
                "status": "error",
                "error_type": result.status.value,
                "error_message": result.error,
                "suggestion": self._generate_error_suggestion(result),
                "execution_time": result.execution_time
            }
        
        # Add relevant metadata
        if result.metadata:
            formatted["metadata"] = self._filter_agent_metadata(result.metadata)
        
        return formatted
    
    def _generate_summary(self, result: ToolResult) -> str:
        """Generate a human-readable summary of the result."""
        if not result.data:
            return "Operation completed successfully"
        
        # Try to create meaningful summaries based on data content
        data = result.data
        
        if isinstance(data, dict):
            if "total_results" in data:
                return f"Found {data['total_results']} results"
            elif "count" in data:
                return f"Processed {data['count']} items"
            elif "summaries" in data:
                return f"Generated {len(data['summaries'])} summaries"
            elif "results" in data and isinstance(data["results"], list):
                return f"Retrieved {len(data['results'])} items"
            else:
                return f"Operation completed with {len(data)} data fields"
        elif isinstance(data, list):
            return f"Retrieved {len(data)} items"
        else:
            return "Operation completed successfully"
    
    def _generate_error_suggestion(self, result: ToolResult) -> str:
        """Generate helpful suggestions for error resolution."""
        if result.status == ToolStatus.TIMEOUT:
            return "Consider increasing timeout or breaking down the request"
        elif result.status == ToolStatus.FAILURE:
            if "parameter" in (result.error or "").lower():
                return "Check input parameters and their formats"
            elif "auth" in (result.error or "").lower():
                return "Verify authentication credentials"
            elif "network" in (result.error or "").lower():
                return "Check network connectivity and try again"
            else:
                return "Review error details and retry with different parameters"
        else:
            return "Check the error details and try again"
    
    def _filter_agent_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Filter metadata to include only agent-relevant information."""
        relevant_keys = [
            "search_time", "query_type", "filters_applied", 
            "source", "tool_version", "cache_hit"
        ]
        return {k: v for k, v in metadata.items() if k in relevant_keys}


class HumanFormatter(ResultFormatter):
    """Formatter optimized for human readability."""
    
    def format(self, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format result for human consumption.
        
        Args:
            result: Tool result to format
            context: Optional context information
            
        Returns:
            Human-readable result dictionary
        """
        if result.is_success():
            formatted = {
                "status": "✅ Success",
                "summary": self._create_human_summary(result),
                "details": self._format_data_for_humans(result.data),
                "completed_in": self._format_execution_time(result.execution_time)
            }
        else:
            formatted = {
                "status": "❌ Failed",
                "error": result.error,
                "help": self._get_human_help(result),
                "completed_in": self._format_execution_time(result.execution_time)
            }
        
        return formatted
    
    def _create_human_summary(self, result: ToolResult) -> str:
        """Create a human-friendly summary."""
        if not result.data:
            return "Task completed successfully"
        
        data = result.data
        if isinstance(data, dict):
            if "query" in data and "total_results" in data:
                return f"Found {data['total_results']} results for '{data['query']}'"
            elif "summaries" in data:
                count = len(data["summaries"])
                return f"Generated {count} summary{'ies' if count != 1 else ''}"
            elif "draft" in data:
                return "Email draft created successfully"
            else:
                return "Task completed with results"
        else:
            return "Task completed successfully"
    
    def _format_data_for_humans(self, data: Any) -> Any:
        """Format data in a human-friendly way."""
        if not data:
            return None
        
        if isinstance(data, dict):
            # Convert technical field names to human-friendly ones
            human_data = {}
            for key, value in data.items():
                human_key = self._humanize_key(key)
                human_data[human_key] = self._format_value_for_humans(value)
            return human_data
        elif isinstance(data, list):
            return [self._format_value_for_humans(item) for item in data[:10]]  # Limit to 10 items
        else:
            return self._format_value_for_humans(data)
    
    def _humanize_key(self, key: str) -> str:
        """Convert technical keys to human-readable ones."""
        key_map = {
            "total_results": "Total Results",
            "execution_time": "Time Taken",
            "query": "Search Query",
            "results": "Results",
            "summaries": "Summaries",
            "email_ids": "Email IDs",
            "draft": "Draft Email"
        }
        return key_map.get(key, key.replace("_", " ").title())
    
    def _format_value_for_humans(self, value: Any) -> Any:
        """Format individual values for human consumption."""
        if isinstance(value, str) and len(value) > 200:
            return value[:200] + "..."
        elif isinstance(value, float) and value < 1:
            return f"{value:.3f}"
        else:
            return value
    
    def _format_execution_time(self, execution_time: Optional[float]) -> str:
        """Format execution time in human-readable format."""
        if execution_time is None:
            return "Unknown"
        elif execution_time < 1:
            return f"{execution_time*1000:.0f}ms"
        else:
            return f"{execution_time:.2f}s"
    
    def _get_human_help(self, result: ToolResult) -> str:
        """Provide human-friendly help for errors."""
        if result.status == ToolStatus.TIMEOUT:
            return "The operation took too long. Try a simpler request or check your connection."
        elif "parameter" in (result.error or "").lower():
            return "Please check that all required information is provided correctly."
        elif "auth" in (result.error or "").lower():
            return "There seems to be an authentication issue. Please check your credentials."
        else:
            return "Something went wrong. Please try again or contact support if the issue persists."


class JsonFormatter(ResultFormatter):
    """Formatter that outputs clean JSON for API consumption."""
    
    def __init__(self, indent: Optional[int] = None, sort_keys: bool = True):
        """
        Initialize JSON formatter.
        
        Args:
            indent: JSON indentation (None for compact)
            sort_keys: Whether to sort dictionary keys
        """
        self.indent = indent
        self.sort_keys = sort_keys
    
    def format(self, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format result as clean JSON structure.
        
        Args:
            result: Tool result to format
            context: Optional context information
            
        Returns:
            JSON-serializable result dictionary
        """
        formatted = {
            "success": result.is_success(),
            "status": result.status.value,
            "data": self._make_json_serializable(result.data),
            "error": result.error,
            "execution_time": result.execution_time,
            "metadata": self._make_json_serializable(result.metadata)
        }
        
        if context:
            formatted["context"] = self._make_json_serializable(context)
        
        return formatted
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Ensure object is JSON serializable."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        else:
            # Convert unknown types to string
            return str(obj)


class ResultNormalizer:
    """Normalizes tool results to ensure consistency."""
    
    def __init__(self):
        """Initialize the result normalizer."""
        self.formatters = {
            "standard": StandardFormatter(),
            "agent": AgentFormatter(),
            "human": HumanFormatter(),
            "json": JsonFormatter()
        }
    
    def normalize(
        self, 
        result: ToolResult, 
        format_type: str = "standard",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Normalize a tool result using the specified formatter.
        
        Args:
            result: Tool result to normalize
            format_type: Type of formatting to apply
            context: Optional context information
            
        Returns:
            Normalized result dictionary
            
        Raises:
            ValueError: If format_type is not supported
        """
        if format_type not in self.formatters:
            raise ValueError(f"Unsupported format type: {format_type}")
        
        formatter = self.formatters[format_type]
        return formatter.format(result, context)
    
    def add_formatter(self, name: str, formatter: ResultFormatter) -> None:
        """
        Add a custom formatter.
        
        Args:
            name: Name for the formatter
            formatter: Formatter instance
        """
        self.formatters[name] = formatter
    
    def get_available_formats(self) -> List[str]:
        """Get list of available format types."""
        return list(self.formatters.keys())


# Global normalizer instance
_global_normalizer = ResultNormalizer()


def get_global_normalizer() -> ResultNormalizer:
    """Get the global result normalizer instance."""
    return _global_normalizer