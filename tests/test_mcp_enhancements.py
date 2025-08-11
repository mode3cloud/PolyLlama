"""
Tests for MCP Enhancement Features
"""

import asyncio
import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import the modules to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'stack', 'llm-proxy', 'mcp-server'))

from mcp_server_proxy import MCPServerProxy, ResilientMCPBridge, EnhancedToolManager
from session_manager import SessionManager, SessionConfig, SessionStatistics
from config_manager import ConfigurationManager, ServerConfig, TransportConfig
from transport_factory import TransportFactory, SSETransport, StreamableHTTPTransport, TransportHealthMonitor
from streaming_executor import StreamingToolExecutor, BatchToolExecutor, StreamEvent, StreamEventType


class TestMCPServerProxy:
    """Test MCP Server Proxy functionality."""
    
    @pytest.fixture
    async def mock_bridge(self):
        """Create a mock bridge with test data."""
        bridge = AsyncMock()
        bridge.servers = {
            'test_server': Mock(),
            'another_server': Mock()
        }
        bridge.server_tools = {
            'test_server': [
                {
                    'name': 'test_tool',
                    'description': 'A test tool',
                    'input_schema': {'type': 'object'}
                }
            ],
            'another_server': [
                {
                    'name': 'another_tool',
                    'description': 'Another test tool',
                    'input_schema': {'type': 'object'}
                }
            ]
        }
        bridge.get_aggregated_tools = AsyncMock(return_value={
            'test_server__test_tool': {
                'name': 'test_tool',
                'description': 'A test tool',
                'server': 'test_server',
                'input_schema': {'type': 'object'}
            },
            'another_server__another_tool': {
                'name': 'another_tool',
                'description': 'Another test tool',
                'server': 'another_server',
                'input_schema': {'type': 'object'}
            }
        })
        bridge.call_tool = AsyncMock(return_value={'result': 'success'})
        return bridge
    
    @pytest.mark.asyncio
    async def test_proxy_creation(self, mock_bridge):
        """Test creating an MCP server proxy."""
        proxy = MCPServerProxy(mock_bridge, name="test_proxy")
        
        assert proxy.bridge == mock_bridge
        assert proxy.mcp.name == "test_proxy"
        assert not proxy.tools_registered
    
    @pytest.mark.asyncio
    async def test_setup_tools(self, mock_bridge):
        """Test registering aggregated tools."""
        proxy = MCPServerProxy(mock_bridge)
        
        await proxy.setup_tools()
        
        assert proxy.tools_registered
        mock_bridge.get_aggregated_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_status(self, mock_bridge):
        """Test getting proxy status."""
        proxy = MCPServerProxy(mock_bridge)
        mock_bridge.proxies = {'test_server': Mock()}
        
        status = await proxy.get_status()
        
        assert status['status'] == 'not_initialized'
        assert status['total_tools'] == 2
        assert 'test_server' in status['servers']
        assert status['servers']['test_server']['connected']
        assert status['servers']['test_server']['tool_count'] == 1


class TestResilientMCPBridge:
    """Test resilient MCP bridge features."""
    
    @pytest.mark.asyncio
    async def test_connect_with_retry_success(self):
        """Test successful connection with retry."""
        bridge = ResilientMCPBridge()
        
        # Mock successful connection on second attempt
        with patch.object(bridge, 'connect_server') as mock_connect:
            mock_connect.side_effect = [
                {'status': 'failed', 'error': 'Connection failed'},
                {'status': 'connected', 'tool_count': 5}
            ]
            
            config = Mock()
            result = await bridge.connect_server_with_retry('test_server', config, max_retries=3)
            
            assert result['status'] == 'connected'
            assert result['tool_count'] == 5
            assert mock_connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_connect_with_retry_failure(self):
        """Test connection failure after max retries."""
        bridge = ResilientMCPBridge()
        
        with patch.object(bridge, 'connect_server') as mock_connect:
            mock_connect.side_effect = [
                {'status': 'failed', 'error': 'Connection failed'},
                {'status': 'failed', 'error': 'Connection failed'},
                {'status': 'failed', 'error': 'Connection failed'}
            ]
            
            config = Mock()
            result = await bridge.connect_server_with_retry('test_server', config, max_retries=3)
            
            assert result['status'] == 'failed'
            assert mock_connect.call_count == 3
    
    @pytest.mark.asyncio
    async def test_hot_reload_server(self):
        """Test hot-reloading a server."""
        bridge = ResilientMCPBridge()
        bridge.servers = {'test_server': Mock()}
        bridge.proxies = {'test_server': Mock()}
        bridge.server_tools = {'test_server': []}
        
        with patch.object(bridge, 'connect_server_with_retry') as mock_connect:
            mock_connect.return_value = {'status': 'connected', 'tool_count': 3}
            
            result = await bridge.hot_reload_server('test_server')
            
            assert result['status'] == 'reloaded'
            assert 'test_server' not in bridge.proxies  # Old connection removed
            mock_connect.assert_called_once()


class TestEnhancedToolManager:
    """Test enhanced tool management features."""
    
    @pytest.fixture
    def tool_manager(self):
        """Create a tool manager with test data."""
        manager = EnhancedToolManager()
        
        # Initialize with mock bridge data
        mock_bridge = Mock()
        mock_bridge.server_tools = {
            'server1': [
                {'name': 'tool1', 'description': 'Tool 1', 'input_schema': {}},
                {'name': 'tool2', 'description': 'Tool 2', 'input_schema': {}}
            ],
            'server2': [
                {'name': 'tool3', 'description': 'Tool 3', 'input_schema': {}}
            ]
        }
        
        manager.initialize_from_bridge(mock_bridge)
        return manager
    
    def test_initialize_from_bridge(self, tool_manager):
        """Test initializing tool manager from bridge."""
        assert 'server1__tool1' in tool_manager.enabled_tools
        assert 'server1__tool2' in tool_manager.enabled_tools
        assert 'server2__tool3' in tool_manager.enabled_tools
        
        assert all(tool_manager.enabled_tools.values())  # All enabled by default
        assert 'server1' in tool_manager.tool_groups
        assert 'server2' in tool_manager.tool_groups
    
    def test_set_tool_enabled(self, tool_manager):
        """Test enabling/disabling specific tools."""
        assert tool_manager.set_tool_enabled('server1__tool1', False)
        assert not tool_manager.enabled_tools['server1__tool1']
        
        assert tool_manager.set_tool_enabled('server1__tool1', True)
        assert tool_manager.enabled_tools['server1__tool1']
        
        assert not tool_manager.set_tool_enabled('nonexistent_tool', False)
    
    def test_set_server_tools_enabled(self, tool_manager):
        """Test enabling/disabling all tools from a server."""
        count = tool_manager.set_server_tools_enabled('server1', False)
        
        assert count == 2
        assert not tool_manager.enabled_tools['server1__tool1']
        assert not tool_manager.enabled_tools['server1__tool2']
        assert tool_manager.enabled_tools['server2__tool3']  # Unchanged
    
    def test_get_enabled_tools(self, tool_manager):
        """Test getting list of enabled tools."""
        tool_manager.set_tool_enabled('server1__tool1', False)
        
        enabled = tool_manager.get_enabled_tools()
        
        assert 'server1__tool1' not in enabled
        assert 'server1__tool2' in enabled
        assert 'server2__tool3' in enabled
    
    def test_record_tool_usage(self, tool_manager):
        """Test recording tool usage statistics."""
        tool_manager.record_tool_usage('server1__tool1', success=True, duration_ms=100)
        tool_manager.record_tool_usage('server1__tool1', success=True, duration_ms=150)
        tool_manager.record_tool_usage('server1__tool1', success=False, duration_ms=50)
        
        stats = tool_manager.tool_usage_stats['server1__tool1']
        
        assert stats['call_count'] == 3
        assert stats['success_count'] == 2
        assert stats['error_count'] == 1
        assert stats['total_duration_ms'] == 300


class TestSessionManager:
    """Test session management functionality."""
    
    @pytest.fixture
    async def session_manager(self, tmp_path):
        """Create a session manager with test data."""
        mock_bridge = AsyncMock()
        mock_bridge.servers = {
            'server1': Mock(),
            'server2': Mock()
        }
        mock_bridge.server_tools = {
            'server1': [
                {'name': 'tool1', 'description': 'Tool 1'},
                {'name': 'tool2', 'description': 'Tool 2'}
            ],
            'server2': [
                {'name': 'tool3', 'description': 'Tool 3'}
            ]
        }
        mock_bridge.call_tool = AsyncMock(return_value={'result': 'success'})
        
        manager = SessionManager(mock_bridge, storage_dir=tmp_path)
        return manager
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating a new session."""
        session_id = await session_manager.create_session(
            selected_servers=['server1'],
            ttl_hours=1,
            metadata={'user': 'test'}
        )
        
        assert session_id in session_manager.sessions
        session = session_manager.sessions[session_id]
        
        assert session.selected_servers == ['server1']
        assert session.metadata == {'user': 'test'}
        assert session.expires_at is not None
        
        # Check tools are initialized
        assert 'server1__tool1' in session_manager.session_tools[session_id]
        assert 'server1__tool2' in session_manager.session_tools[session_id]
        assert 'server2__tool3' not in session_manager.session_tools[session_id]
    
    @pytest.mark.asyncio
    async def test_execute_tool_in_session(self, session_manager):
        """Test executing a tool within a session."""
        session_id = await session_manager.create_session(selected_servers=['server1'])
        
        result = await session_manager.execute_tool_in_session(
            session_id,
            'server1__tool1',
            {'arg': 'value'}
        )
        
        assert result == {'result': 'success'}
        session_manager.bridge.call_tool.assert_called_once_with('server1__tool1', {'arg': 'value'})
    
    @pytest.mark.asyncio
    async def test_execute_disabled_tool(self, session_manager):
        """Test executing a disabled tool raises error."""
        session_id = await session_manager.create_session(selected_servers=['server1'])
        
        # Disable the tool
        await session_manager.update_session(
            session_id,
            enabled_tools={'server1__tool1': False}
        )
        
        with pytest.raises(ValueError, match="disabled"):
            await session_manager.execute_tool_in_session(
                session_id,
                'server1__tool1',
                {}
            )
    
    @pytest.mark.asyncio
    async def test_session_expiration(self, session_manager):
        """Test session expiration handling."""
        # Create session with short TTL
        session_id = await session_manager.create_session(ttl_hours=0.0001)  # Very short TTL
        
        # Wait for expiration
        await asyncio.sleep(0.5)
        
        # Try to get expired session
        session = await session_manager.get_session(session_id)
        assert session is None
        assert session_id not in session_manager.sessions


class TestConfigurationManager:
    """Test configuration management functionality."""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Create a configuration manager."""
        return ConfigurationManager(config_dir=tmp_path)
    
    def test_save_and_load_configuration(self, config_manager):
        """Test saving and loading configurations."""
        # Create test server config
        transport = TransportConfig(
            type='stdio',
            command='node',
            args=['server.js'],
            env={'KEY': 'value'}
        )
        server = ServerConfig(
            name='test_server',
            transport=transport,
            enabled=True,
            metadata={'version': '1.0'}
        )
        
        # Add server and save configuration
        config_manager.add_server(server)
        config_path = config_manager.save_configuration('test_config')
        
        assert config_path.exists()
        
        # Clear and reload
        config_manager.servers = {}
        assert config_manager.load_configuration('test_config')
        
        # Verify loaded correctly
        assert 'test_server' in config_manager.servers
        loaded_server = config_manager.servers['test_server']
        assert loaded_server.name == 'test_server'
        assert loaded_server.transport.type == 'stdio'
        assert loaded_server.transport.command == 'node'
    
    def test_auto_discover_env_servers(self):
        """Test discovering servers from environment variables."""
        config_manager = ConfigurationManager()
        
        # Set test environment variable
        test_servers = {
            'env_test': {
                'command': 'python',
                'args': ['server.py'],
                'env': {'TEST': '1'}
            }
        }
        
        with patch.dict(os.environ, {'MCP_SERVERS': json.dumps(test_servers)}):
            discovered = config_manager._discover_env_servers()
            
            assert len(discovered) == 1
            assert discovered[0].name == 'env_env_test'
            assert discovered[0].transport.type == 'stdio'
            assert discovered[0].transport.command == 'python'
    
    def test_export_to_claude_format(self, config_manager):
        """Test exporting configuration to Claude Desktop format."""
        # Add test servers
        stdio_transport = TransportConfig(type='stdio', command='node', args=['server.js'])
        http_transport = TransportConfig(type='streamable_http', url='http://localhost:3000')
        
        config_manager.add_server(ServerConfig('stdio_server', stdio_transport))
        config_manager.add_server(ServerConfig('http_server', http_transport))
        
        claude_config = config_manager.export_to_claude_format()
        
        assert 'mcpServers' in claude_config
        assert 'stdio_server' in claude_config['mcpServers']
        assert 'http_server' in claude_config['mcpServers']
        
        assert claude_config['mcpServers']['stdio_server']['command'] == 'node'
        assert claude_config['mcpServers']['http_server']['args'] == ['http://localhost:3000']


class TestTransportFactory:
    """Test transport factory functionality."""
    
    @pytest.mark.asyncio
    async def test_create_stdio_transport(self):
        """Test creating STDIO transport."""
        config = {
            'type': 'stdio',
            'command': 'python',
            'args': ['server.py'],
            'env': {'KEY': 'value'}
        }
        
        transport = await TransportFactory.create_transport(config)
        
        assert transport is not None
        # StdioTransport from fastmcp
        assert hasattr(transport, 'command')
    
    @pytest.mark.asyncio
    async def test_create_sse_transport(self):
        """Test creating SSE transport."""
        config = {
            'type': 'sse',
            'url': 'http://localhost:3000/events',
            'headers': {'Authorization': 'Bearer token'}
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_get.return_value.__aenter__.return_value = mock_response
            
            transport = await TransportFactory.create_transport(config)
            
            assert isinstance(transport, SSETransport)
            assert transport.url == 'http://localhost:3000/events'
            assert transport.headers == {'Authorization': 'Bearer token'}
    
    def test_detect_transport_type(self):
        """Test auto-detecting transport type."""
        # WebSocket URL
        assert TransportFactory.detect_transport_type({'url': 'ws://localhost:3000'}) == 'websocket'
        assert TransportFactory.detect_transport_type({'url': 'wss://localhost:3000'}) == 'websocket'
        
        # SSE URL
        assert TransportFactory.detect_transport_type({'url': 'http://localhost/events'}) == 'sse'
        assert TransportFactory.detect_transport_type({'url': 'http://localhost/sse'}) == 'sse'
        
        # HTTP URL
        assert TransportFactory.detect_transport_type({'url': 'http://localhost:3000'}) == 'streamable_http'
        
        # STDIO
        assert TransportFactory.detect_transport_type({'command': 'python'}) == 'stdio'
        
        # Explicit type
        assert TransportFactory.detect_transport_type({'type': 'custom', 'url': 'http://localhost'}) == 'custom'


class TestStreamingToolExecutor:
    """Test streaming tool execution."""
    
    @pytest.fixture
    def executor(self):
        """Create a streaming executor with mock bridge."""
        mock_bridge = AsyncMock()
        mock_bridge.call_tool = AsyncMock(return_value={'result': 'success'})
        return StreamingToolExecutor(mock_bridge)
    
    @pytest.mark.asyncio
    async def test_execute_tool_streaming(self, executor):
        """Test executing a tool with streaming updates."""
        events = []
        
        async for event in executor.execute_tool_streaming('test_tool', {'arg': 'value'}):
            events.append(event)
        
        # Check we got the expected events
        event_types = [e.type for e in events]
        assert StreamEventType.START in event_types
        assert StreamEventType.COMPLETE in event_types
        
        # Check start event
        start_event = next(e for e in events if e.type == StreamEventType.START)
        assert start_event.data['tool_name'] == 'test_tool'
        
        # Check data event
        data_events = [e for e in events if e.type == StreamEventType.DATA]
        assert len(data_events) > 0
        assert data_events[0].data == {'result': 'success'}
    
    @pytest.mark.asyncio
    async def test_batch_execution(self, executor):
        """Test batch tool execution."""
        batch_executor = BatchToolExecutor(executor)
        
        tool_calls = [
            {'name': 'tool1', 'arguments': {'arg': '1'}},
            {'name': 'tool2', 'arguments': {'arg': '2'}},
            {'name': 'tool3', 'arguments': {'arg': '3'}}
        ]
        
        events = []
        async for event in batch_executor.execute_batch(tool_calls):
            events.append(event)
        
        # Check batch events
        event_types = [e.type for e in events]
        assert StreamEventType.START in event_types
        assert StreamEventType.COMPLETE in event_types
        
        # Check completion event
        complete_event = next(e for e in events if e.type == StreamEventType.COMPLETE)
        assert complete_event.data['total_tools'] == 3
        assert complete_event.data['successful'] == 3
    
    def test_supports_streaming(self, executor):
        """Test checking if tools support streaming."""
        assert executor._supports_streaming('github__search_repositories')
        assert executor._supports_streaming('web_search')
        assert not executor._supports_streaming('random_tool')


class TestTransportHealthMonitor:
    """Test transport health monitoring."""
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """Test transport health monitoring."""
        monitor = TransportHealthMonitor(check_interval=0.1)
        
        # Add mock transport
        mock_transport = AsyncMock()
        monitor.add_transport('test_transport', mock_transport)
        
        # Start monitoring
        await monitor.start_monitoring()
        
        # Wait for at least one check
        await asyncio.sleep(0.2)
        
        # Check health status
        report = monitor.get_health_report()
        assert report['monitoring']
        assert 'test_transport' in report['transports']
        
        # Stop monitoring
        await monitor.stop_monitoring()
        
        report = monitor.get_health_report()
        assert not report['monitoring']


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])