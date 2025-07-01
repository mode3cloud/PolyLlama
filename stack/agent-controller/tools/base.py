"""
Base classes and interfaces for agent tools.

This module defines the standard interface that all tools must implement
to integrate with the PolyLlama agent system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import asyncio
from datetime import datetime


class ToolStatus(Enum):
    """Status of a tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None


@dataclass
class ToolResult:
    """Result from a tool execution."""
    status: ToolStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.status == ToolStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata
        }


class ToolError(Exception):
    """Exception raised by tools during execution."""
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class Tool(ABC):
    """Abstract base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the tool."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """List of parameters this tool accepts."""
        pass
    
    @property
    def version(self) -> str:
        """Version of the tool implementation."""
        return "1.0.0"
    
    @property
    def timeout(self) -> float:
        """Default timeout in seconds for tool execution."""
        return 30.0
    
    @property
    def cacheable(self) -> bool:
        """Whether results from this tool can be cached."""
        return False
    
    @property
    def requires_auth(self) -> bool:
        """Whether this tool requires authentication."""
        return False
    
    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given arguments.
        
        Args:
            args: Dictionary of arguments matching the tool's parameters
            
        Returns:
            ToolResult containing the execution outcome
            
        Raises:
            ToolError: If the tool encounters an error during execution
        """
        pass
    
    async def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize input arguments.
        
        Args:
            args: Raw arguments to validate
            
        Returns:
            Validated and normalized arguments
            
        Raises:
            ToolError: If validation fails
        """
        validated = {}
        
        # Check all parameters
        for param in self.parameters:
            if param.name not in args:
                # Apply default if available
                if param.default is not None:
                    validated[param.name] = param.default
                elif param.required:
                    raise ToolError(f"Missing required parameter: {param.name}")
                # Skip optional parameters without defaults
            else:
                value = args[param.name]
                
                # Type validation
                if param.type == "string" and not isinstance(value, str):
                    raise ToolError(f"Parameter {param.name} must be a string")
                elif param.type == "number" and not isinstance(value, (int, float)):
                    raise ToolError(f"Parameter {param.name} must be a number")
                elif param.type == "boolean" and not isinstance(value, bool):
                    raise ToolError(f"Parameter {param.name} must be a boolean")
                
                # Enum validation
                if param.enum and value not in param.enum:
                    raise ToolError(f"Parameter {param.name} must be one of: {param.enum}")
                
                # Range validation for numbers
                if param.type == "number":
                    if param.min_value is not None and value < param.min_value:
                        raise ToolError(f"Parameter {param.name} must be >= {param.min_value}")
                    if param.max_value is not None and value > param.max_value:
                        raise ToolError(f"Parameter {param.name} must be <= {param.max_value}")
                
                validated[param.name] = value
        
        return validated
    
    async def execute_with_timeout(self, args: Dict[str, Any], timeout: Optional[float] = None) -> ToolResult:
        """
        Execute the tool with a timeout.
        
        Args:
            args: Arguments for the tool
            timeout: Override default timeout (in seconds)
            
        Returns:
            ToolResult from execution
        """
        timeout = timeout or self.timeout
        start_time = datetime.now()
        
        try:
            # Validate arguments first
            validated_args = await self.validate_args(args)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                self.execute(validated_args),
                timeout=timeout
            )
            
            # Add execution time if not already set
            if result.execution_time is None:
                result.execution_time = (datetime.now() - start_time).total_seconds()
            
            return result
            
        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolStatus.TIMEOUT,
                error=f"Tool execution timed out after {timeout} seconds",
                execution_time=timeout
            )
        except ToolError as e:
            return ToolResult(
                status=ToolStatus.FAILURE,
                error=str(e),
                metadata={"code": e.code, "details": e.details},
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.FAILURE,
                error=f"Unexpected error: {str(e)}",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema representation of the tool.
        
        Returns:
            Dictionary containing tool metadata and parameter schema
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "timeout": self.timeout,
            "cacheable": self.cacheable,
            "requires_auth": self.requires_auth,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                    "min_value": p.min_value,
                    "max_value": p.max_value
                }
                for p in self.parameters
            ]
        }