"""
Unit tests for the tool registry.
"""

import pytest
import asyncio
from typing import Dict, Any

from tools.registry import ToolRegistry
from tools.base import Tool, ToolResult, ToolStatus, ToolParameter
from tests.agent_controller.tools.test_base import MockTool


@pytest.mark.asyncio
class TestToolRegistry:
    """Test cases for the ToolRegistry class."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return ToolRegistry()
    
    @pytest.fixture
    def mock_tools(self):
        """Create a set of mock tools for testing."""
        return {
            "tool1": MockTool("tool1"),
            "tool2": MockTool("tool2"),
            "tool3": MockTool("tool3", fail=True),
        }
    
    async def test_register_tool(self, registry, mock_tools):
        """Test registering tools in the registry."""
        tool1 = mock_tools["tool1"]
        
        # Register tool
        registry.register(tool1)
        assert registry.get_tool("tool1") == tool1
        
        # Register with category
        registry.register(mock_tools["tool2"], category="test_category")
        assert registry.get_tool("tool2") == mock_tools["tool2"]
        assert "tool2" in registry.get_tools_by_category("test_category")
    
    async def test_register_duplicate_tool(self, registry, mock_tools):
        """Test that registering duplicate tools raises an error."""
        tool1 = mock_tools["tool1"]
        
        registry.register(tool1)
        
        # Try to register same tool again
        with pytest.raises(ValueError) as exc_info:
            registry.register(tool1)
        assert "already registered" in str(exc_info.value)
    
    async def test_unregister_tool(self, registry, mock_tools):
        """Test unregistering tools."""
        tool1 = mock_tools["tool1"]
        
        # Register and then unregister
        registry.register(tool1, category="test")
        assert registry.unregister("tool1") is True
        assert registry.get_tool("tool1") is None
        assert "tool1" not in registry.get_tools_by_category("test")
        
        # Unregister non-existent tool
        assert registry.unregister("non_existent") is False
    
    async def test_list_tools(self, registry, mock_tools):
        """Test listing all tools."""
        # Register multiple tools
        registry.register(mock_tools["tool1"], category="category1")
        registry.register(mock_tools["tool2"], category="category1")
        registry.register(mock_tools["tool3"], category="category2")
        
        # List all tools
        all_tools = registry.list_tools()
        assert len(all_tools) == 3
        tool_names = [t["name"] for t in all_tools]
        assert "tool1" in tool_names
        assert "tool2" in tool_names
        assert "tool3" in tool_names
        
        # List by category
        cat1_tools = registry.list_tools(category="category1")
        assert len(cat1_tools) == 2
        cat1_names = [t["name"] for t in cat1_tools]
        assert "tool1" in cat1_names
        assert "tool2" in cat1_names
        
        # List non-existent category
        empty_tools = registry.list_tools(category="non_existent")
        assert len(empty_tools) == 0
    
    async def test_get_categories(self, registry, mock_tools):
        """Test getting tool categories."""
        # Initially no categories
        assert registry.get_categories() == []
        
        # Add tools with categories
        registry.register(mock_tools["tool1"], category="email")
        registry.register(mock_tools["tool2"], category="search")
        registry.register(mock_tools["tool3"], category="email")
        
        categories = registry.get_categories()
        assert len(categories) == 2
        assert "email" in categories
        assert "search" in categories
    
    async def test_execute_tool(self, registry, mock_tools):
        """Test executing tools through the registry."""
        tool1 = mock_tools["tool1"]
        registry.register(tool1)
        
        # Execute existing tool
        result = await registry.execute_tool("tool1", {"input": "test data"})
        assert result.is_success()
        assert result.data["output"] == "Processed: test data"
        
        # Execute non-existent tool
        result = await registry.execute_tool("non_existent", {"input": "test"})
        assert result.status == ToolStatus.FAILURE
        assert "not found" in result.error
    
    async def test_usage_tracking(self, registry, mock_tools):
        """Test usage statistics tracking."""
        tool1 = mock_tools["tool1"]
        tool3 = mock_tools["tool3"]  # Failing tool
        registry.register(tool1)
        registry.register(tool3)
        
        # Initial stats should be empty
        stats = registry.get_usage_stats()
        assert len(stats) == 0
        
        # Execute tool successfully
        await registry.execute_tool("tool1", {"input": "test"})
        stats = registry.get_usage_stats("tool1")
        assert stats["tool1"]["total_calls"] == 1
        assert stats["tool1"]["successful_calls"] == 1
        assert stats["tool1"]["failed_calls"] == 0
        assert stats["tool1"]["last_used"] is not None
        
        # Execute tool that fails
        await registry.execute_tool("tool3", {"input": "test"})
        stats = registry.get_usage_stats("tool3")
        assert stats["tool3"]["total_calls"] == 1
        assert stats["tool3"]["successful_calls"] == 0
        assert stats["tool3"]["failed_calls"] == 1
        
        # Execute multiple times
        await registry.execute_tool("tool1", {"input": "test2"})
        await registry.execute_tool("tool1", {"input": "test3"})
        stats = registry.get_usage_stats("tool1")
        assert stats["tool1"]["total_calls"] == 3
        assert stats["tool1"]["successful_calls"] == 3
        assert stats["tool1"]["average_execution_time"] > 0
    
    async def test_disable_usage_tracking(self, registry, mock_tools):
        """Test executing tools without usage tracking."""
        tool1 = mock_tools["tool1"]
        registry.register(tool1)
        
        # Execute without tracking
        await registry.execute_tool("tool1", {"input": "test"}, track_usage=False)
        
        # Stats should be empty or have 0 calls
        stats = registry.get_usage_stats("tool1")
        tool_stats = stats.get("tool1", {})
        assert tool_stats.get("total_calls", 0) == 0
    
    async def test_clear_usage_stats(self, registry, mock_tools):
        """Test clearing usage statistics."""
        tool1 = mock_tools["tool1"]
        tool2 = mock_tools["tool2"]
        registry.register(tool1)
        registry.register(tool2)
        
        # Execute tools
        await registry.execute_tool("tool1", {"input": "test"})
        await registry.execute_tool("tool2", {"input": "test"})
        
        # Clear specific tool stats
        registry.clear_usage_stats("tool1")
        stats = registry.get_usage_stats()
        assert "tool1" not in stats or stats.get("tool1", {}).get("total_calls", 0) == 0
        assert stats.get("tool2", {}).get("total_calls", 0) == 1
        
        # Clear all stats
        registry.clear_usage_stats()
        stats = registry.get_usage_stats()
        assert all(s.get("total_calls", 0) == 0 for s in stats.values())
    
    async def test_search_tools(self, registry, mock_tools):
        """Test searching for tools."""
        # Create tools with specific names/descriptions
        class SearchableTool(MockTool):
            def __init__(self, name: str, description: str):
                super().__init__(name)
                self._description = description
            
            @property
            def description(self) -> str:
                return self._description
        
        tool1 = SearchableTool("email_sender", "Send emails to recipients")
        tool2 = SearchableTool("email_reader", "Read emails from inbox")
        tool3 = SearchableTool("web_search", "Search the web for information")
        
        registry.register(tool1)
        registry.register(tool2)
        registry.register(tool3)
        
        # Search by name
        results = registry.search_tools("email")
        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "email_sender" in names
        assert "email_reader" in names
        
        # Search by description
        results = registry.search_tools("inbox")
        assert len(results) == 1
        assert results[0]["name"] == "email_reader"
        
        # Case-insensitive search
        results = registry.search_tools("EMAIL")
        assert len(results) == 2
        
        # No results
        results = registry.search_tools("nonexistent")
        assert len(results) == 0
    
    async def test_validate_tool_args(self, registry, mock_tools):
        """Test validating tool arguments without execution."""
        tool1 = mock_tools["tool1"]
        registry.register(tool1)
        
        # Valid args
        validated = await registry.validate_tool_args("tool1", {
            "input": "test",
            "count": 5
        })
        assert validated["input"] == "test"
        assert validated["count"] == 5
        
        # Invalid args
        with pytest.raises(Exception) as exc_info:
            await registry.validate_tool_args("tool1", {"count": 5})
        assert "Missing required parameter" in str(exc_info.value)
        
        # Non-existent tool
        with pytest.raises(Exception) as exc_info:
            await registry.validate_tool_args("non_existent", {"input": "test"})
        assert "not found" in str(exc_info.value)
    
    async def test_get_tool_schema(self, registry, mock_tools):
        """Test getting tool schemas."""
        tool1 = mock_tools["tool1"]
        registry.register(tool1)
        
        # Get specific tool schema
        schema = registry.get_tool_schema("tool1")
        assert schema is not None
        assert schema["name"] == "tool1"
        assert "parameters" in schema
        
        # Non-existent tool
        schema = registry.get_tool_schema("non_existent")
        assert schema is None
    
    async def test_get_all_schemas(self, registry, mock_tools):
        """Test getting all tool schemas."""
        registry.register(mock_tools["tool1"])
        registry.register(mock_tools["tool2"])
        
        schemas = registry.get_all_schemas()
        assert len(schemas) == 2
        assert "tool1" in schemas
        assert "tool2" in schemas
        assert schemas["tool1"]["name"] == "tool1"
        assert schemas["tool2"]["name"] == "tool2"
    
    async def test_concurrent_tool_execution(self, registry):
        """Test executing multiple tools concurrently."""
        # Create tools with different execution times
        class TimedTool(MockTool):
            def __init__(self, name: str, delay: float):
                super().__init__(name)
                self.delay = delay
            
            async def execute(self, args: Dict[str, Any]) -> ToolResult:
                await asyncio.sleep(self.delay)
                return await super().execute(args)
        
        tool1 = TimedTool("fast", 0.1)
        tool2 = TimedTool("medium", 0.2)
        tool3 = TimedTool("slow", 0.3)
        
        registry.register(tool1)
        registry.register(tool2)
        registry.register(tool3)
        
        # Execute tools concurrently
        start_time = asyncio.get_event_loop().time()
        
        tasks = [
            registry.execute_tool("fast", {"input": "test1"}),
            registry.execute_tool("medium", {"input": "test2"}),
            registry.execute_tool("slow", {"input": "test3"})
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time
        
        # All should succeed
        assert all(r.is_success() for r in results)
        
        # Should execute in parallel (total time < sum of individual times)
        assert elapsed < 0.6  # Would be 0.6 if sequential
        assert elapsed > 0.3  # Should take at least as long as slowest