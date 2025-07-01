"""
Unit tests for the base tool interface.
"""

import pytest
import asyncio
from typing import Dict, Any, List

from tools.base import (
    Tool, ToolResult, ToolError, ToolStatus, ToolParameter
)


class MockTool(Tool):
    """Mock tool implementation for testing."""
    
    def __init__(self, name: str = "mock_tool", fail: bool = False):
        self._name = name
        self._fail = fail
        self._execute_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type="string",
                description="Test input",
                required=True
            ),
            ToolParameter(
                name="count",
                type="number",
                description="Test count",
                required=False,
                default=1,
                min_value=1,
                max_value=10
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Test mode",
                required=False,
                enum=["fast", "slow", "normal"]
            )
        ]
    
    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        self._execute_count += 1
        
        if self._fail:
            raise ToolError("Mock execution failed", code="MOCK_ERROR")
        
        # Simulate some work
        await asyncio.sleep(0.1)
        
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "output": f"Processed: {args.get('input')}",
                "count": args.get("count", 1),
                "execute_count": self._execute_count
            },
            execution_time=0.1
        )


class SlowTool(MockTool):
    """Mock tool that takes longer to execute."""
    
    @property
    def timeout(self) -> float:
        return 0.5
    
    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        # Simulate slow execution
        await asyncio.sleep(1.0)  # This will timeout
        return await super().execute(args)


@pytest.mark.asyncio
class TestToolBase:
    """Test cases for the base Tool class."""
    
    async def test_tool_properties(self):
        """Test basic tool properties."""
        tool = MockTool()
        
        assert tool.name == "mock_tool"
        assert tool.description == "A mock tool for testing"
        assert tool.version == "1.0.0"
        assert tool.timeout == 30.0
        assert tool.cacheable is False
        assert tool.requires_auth is False
        assert len(tool.parameters) == 3
    
    async def test_successful_execution(self):
        """Test successful tool execution."""
        tool = MockTool()
        result = await tool.execute({"input": "test data", "count": 5})
        
        assert result.is_success()
        assert result.status == ToolStatus.SUCCESS
        assert result.data["output"] == "Processed: test data"
        assert result.data["count"] == 5
        assert result.error is None
    
    async def test_execution_with_error(self):
        """Test tool execution that raises an error."""
        tool = MockTool(fail=True)
        
        with pytest.raises(ToolError) as exc_info:
            await tool.execute({"input": "test"})
        
        assert exc_info.value.code == "MOCK_ERROR"
        assert str(exc_info.value) == "Mock execution failed"
    
    async def test_parameter_validation(self):
        """Test parameter validation."""
        tool = MockTool()
        
        # Valid args
        validated = await tool.validate_args({
            "input": "test",
            "count": 5,
            "mode": "fast"
        })
        assert validated["input"] == "test"
        assert validated["count"] == 5
        assert validated["mode"] == "fast"
        
        # Missing required parameter
        with pytest.raises(ToolError) as exc_info:
            await tool.validate_args({"count": 5})
        assert "Missing required parameter: input" in str(exc_info.value)
        
        # Invalid type
        with pytest.raises(ToolError) as exc_info:
            await tool.validate_args({"input": "test", "count": "not a number"})
        assert "must be a number" in str(exc_info.value)
        
        # Invalid enum value
        with pytest.raises(ToolError) as exc_info:
            await tool.validate_args({"input": "test", "mode": "invalid"})
        assert "must be one of" in str(exc_info.value)
        
        # Out of range
        with pytest.raises(ToolError) as exc_info:
            await tool.validate_args({"input": "test", "count": 20})
        assert "must be <=" in str(exc_info.value)
    
    async def test_default_parameter_values(self):
        """Test that default parameter values are applied."""
        tool = MockTool()
        
        # Only provide required parameter
        validated = await tool.validate_args({"input": "test"})
        assert validated["input"] == "test"
        assert validated["count"] == 1  # Default value
        assert "mode" not in validated  # Optional without default
    
    async def test_execute_with_timeout(self):
        """Test tool execution with timeout."""
        tool = MockTool()
        
        # Normal execution within timeout
        result = await tool.execute_with_timeout({"input": "test"}, timeout=1.0)
        assert result.is_success()
        assert result.execution_time is not None
        
        # Execution that times out
        slow_tool = SlowTool()
        result = await slow_tool.execute_with_timeout({"input": "test"})
        assert result.status == ToolStatus.TIMEOUT
        assert "timed out" in result.error
        assert result.execution_time == slow_tool.timeout
    
    async def test_execute_with_timeout_validation_error(self):
        """Test that validation errors are properly handled in execute_with_timeout."""
        tool = MockTool()
        
        # Invalid args should result in failure status
        result = await tool.execute_with_timeout({"invalid": "args"})
        assert result.status == ToolStatus.FAILURE
        assert "Missing required parameter" in result.error
    
    async def test_get_schema(self):
        """Test tool schema generation."""
        tool = MockTool()
        schema = tool.get_schema()
        
        assert schema["name"] == "mock_tool"
        assert schema["description"] == "A mock tool for testing"
        assert schema["version"] == "1.0.0"
        assert schema["timeout"] == 30.0
        assert schema["cacheable"] is False
        assert schema["requires_auth"] is False
        assert len(schema["parameters"]) == 3
        
        # Check parameter schema
        input_param = next(p for p in schema["parameters"] if p["name"] == "input")
        assert input_param["type"] == "string"
        assert input_param["required"] is True
        
        count_param = next(p for p in schema["parameters"] if p["name"] == "count")
        assert count_param["type"] == "number"
        assert count_param["required"] is False
        assert count_param["default"] == 1
        assert count_param["min_value"] == 1
        assert count_param["max_value"] == 10


@pytest.mark.asyncio
class TestToolResult:
    """Test cases for ToolResult class."""
    
    async def test_tool_result_success(self):
        """Test successful tool result."""
        result = ToolResult(
            status=ToolStatus.SUCCESS,
            data={"key": "value"},
            execution_time=1.5
        )
        
        assert result.is_success()
        assert result.status == ToolStatus.SUCCESS
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.execution_time == 1.5
    
    async def test_tool_result_failure(self):
        """Test failed tool result."""
        result = ToolResult(
            status=ToolStatus.FAILURE,
            error="Something went wrong",
            metadata={"code": "ERROR_001"}
        )
        
        assert not result.is_success()
        assert result.status == ToolStatus.FAILURE
        assert result.error == "Something went wrong"
        assert result.data is None
        assert result.metadata["code"] == "ERROR_001"
    
    async def test_tool_result_to_dict(self):
        """Test converting tool result to dictionary."""
        result = ToolResult(
            status=ToolStatus.SUCCESS,
            data={"output": "test"},
            execution_time=0.5,
            metadata={"source": "test"}
        )
        
        result_dict = result.to_dict()
        assert result_dict["status"] == "success"
        assert result_dict["data"] == {"output": "test"}
        assert result_dict["execution_time"] == 0.5
        assert result_dict["metadata"] == {"source": "test"}
        assert result_dict["error"] is None


@pytest.mark.asyncio
class TestToolError:
    """Test cases for ToolError class."""
    
    async def test_tool_error_basic(self):
        """Test basic tool error."""
        error = ToolError("Test error")
        assert str(error) == "Test error"
        assert error.code is None
        assert error.details == {}
    
    async def test_tool_error_with_code_and_details(self):
        """Test tool error with code and details."""
        error = ToolError(
            "Test error",
            code="TEST_001",
            details={"field": "value", "count": 42}
        )
        
        assert str(error) == "Test error"
        assert error.code == "TEST_001"
        assert error.details == {"field": "value", "count": 42}