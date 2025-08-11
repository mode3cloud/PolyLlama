"""
MCP Integration Module - Ties together all enhanced MCP features
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mcp_server_proxy import MCPServerProxy, ResilientMCPBridge, EnhancedToolManager
from session_manager import SessionManager, SessionStatistics
from config_manager import ConfigurationManager
from transport_factory import TransportFactory, TransportHealthMonitor
from streaming_executor import (
    StreamingToolExecutor, 
    BatchToolExecutor, 
    StreamingResponseFormatter,
    StreamEventType
)

logger = logging.getLogger(__name__)


class MCPIntegrationService:
    """Main integration service for enhanced MCP features."""
    
    def __init__(self, config_path: Optional[str] = None):
        # Initialize components
        self.bridge = ResilientMCPBridge()
        self.config_manager = ConfigurationManager()
        self.session_manager = SessionManager(self.bridge)
        self.tool_manager = EnhancedToolManager()
        self.streaming_executor = StreamingToolExecutor(self.bridge)
        self.batch_executor = BatchToolExecutor(self.streaming_executor)
        self.health_monitor = TransportHealthMonitor()
        self.proxy_server: Optional[MCPServerProxy] = None
        
        # Load configuration
        self.config_path = config_path or os.environ.get('MCP_CONFIG_PATH', 'mcp-config.json')
        
        # Session statistics
        self.session_stats = SessionStatistics(self.session_manager)
        
        # Track initialization status
        self.initialized = False
        
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP integration service."""
        logger.info("Initializing MCP Integration Service")
        
        # Load configuration
        if Path(self.config_path).exists():
            await self.bridge.load_config(self.config_path)
        else:
            # Try to auto-discover servers
            logger.info("Configuration file not found, attempting auto-discovery")
            discovered = self.config_manager.auto_discover_servers()
            
            for server in discovered:
                self.config_manager.add_server(server)
            
            # Convert to bridge format
            for server_name, server_config in self.config_manager.servers.items():
                self.bridge.servers[server_name] = server_config
        
        # Connect to all servers with resilience
        servers_info = await self.bridge.connect_all_servers()
        
        # Initialize tool manager
        self.tool_manager.initialize_from_bridge(self.bridge)
        
        # Create MCP server proxy
        self.proxy_server = MCPServerProxy(self.bridge)
        
        # Start health monitoring
        await self.health_monitor.start_monitoring()
        
        # Mark as initialized
        self.initialized = True
        
        # Return initialization summary
        return {
            'status': 'initialized',
            'servers': servers_info,
            'total_tools': len(self.tool_manager.enabled_tools),
            'config_path': self.config_path
        }
    
    async def shutdown(self):
        """Shutdown the MCP integration service."""
        logger.info("Shutting down MCP Integration Service")
        
        # Stop health monitoring
        await self.health_monitor.stop_monitoring()
        
        # Save current configuration
        self.config_manager.save_active_configuration()
        
        # Close all connections
        # (Implementation would depend on transport cleanup)
        
        self.initialized = False
    
    async def create_session(
        self,
        selected_servers: Optional[List[str]] = None,
        ttl_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new MCP session."""
        return await self.session_manager.create_session(
            selected_servers=selected_servers,
            ttl_hours=ttl_hours,
            metadata=metadata
        )
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
        stream: bool = False
    ) -> Any:
        """Execute a tool with optional session context and streaming."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if session_id:
                # Execute within session context
                result = await self.session_manager.execute_tool_in_session(
                    session_id, tool_name, arguments
                )
            elif stream:
                # Execute with streaming
                return self.streaming_executor.execute_tool_streaming(
                    tool_name, arguments
                )
            else:
                # Direct execution
                result = await self.bridge.call_tool(tool_name, arguments)
            
            # Record usage statistics
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            self.tool_manager.record_tool_usage(tool_name, success=True, duration_ms=duration_ms)
            
            if session_id:
                self.session_stats.record_execution(
                    session_id, tool_name, success=True, duration_ms=duration_ms
                )
            
            return result
            
        except Exception as e:
            # Record error statistics
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            self.tool_manager.record_tool_usage(tool_name, success=False, duration_ms=duration_ms)
            
            if session_id:
                self.session_stats.record_execution(
                    session_id, tool_name, success=False, duration_ms=duration_ms
                )
            
            raise
    
    async def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ):
        """Execute multiple tools in batch."""
        # Validate session if provided
        if session_id:
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
        
        # Execute batch with streaming
        async for event in self.batch_executor.execute_batch(tool_calls):
            yield event
    
    async def hot_reload_server(self, server_name: str) -> Dict[str, Any]:
        """Hot-reload a specific MCP server."""
        result = await self.bridge.hot_reload_server(server_name)
        
        # Reinitialize tool manager if successful
        if result['status'] == 'reloaded':
            self.tool_manager.initialize_from_bridge(self.bridge)
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the MCP integration."""
        return {
            'initialized': self.initialized,
            'servers': self.bridge.get_connection_status(),
            'sessions': {
                'active': len(self.session_manager.sessions),
                'total_executions': len(self.session_stats.tool_execution_history)
            },
            'tools': {
                'total': len(self.tool_manager.enabled_tools),
                'enabled': len(self.tool_manager.get_enabled_tools())
            },
            'health': self.health_monitor.get_health_report()
        }


# FastAPI Integration
def create_mcp_api(integration: MCPIntegrationService) -> FastAPI:
    """Create FastAPI app with MCP integration endpoints."""
    app = FastAPI(title="Enhanced MCP API", version="2.0.0")
    
    # Request/Response Models
    class ToolExecutionRequest(BaseModel):
        tool_name: str
        arguments: Dict[str, Any] = {}
        session_id: Optional[str] = None
        stream: bool = False
    
    class BatchExecutionRequest(BaseModel):
        tool_calls: List[Dict[str, Any]]
        session_id: Optional[str] = None
    
    class SessionCreateRequest(BaseModel):
        selected_servers: Optional[List[str]] = None
        ttl_hours: int = 24
        metadata: Optional[Dict[str, Any]] = None
    
    class ServerReloadRequest(BaseModel):
        server_name: str
    
    class ToolToggleRequest(BaseModel):
        tool_name: str
        enabled: bool
    
    # Endpoints
    @app.on_event("startup")
    async def startup():
        """Initialize MCP integration on startup."""
        await integration.initialize()
    
    @app.on_event("shutdown")
    async def shutdown():
        """Shutdown MCP integration."""
        await integration.shutdown()
    
    @app.get("/status")
    async def get_status():
        """Get MCP integration status."""
        return integration.get_status()
    
    @app.get("/tools")
    async def list_tools():
        """List all available tools."""
        return integration.tool_manager.get_tools_for_llm()
    
    @app.post("/tools/execute")
    async def execute_tool(request: ToolExecutionRequest):
        """Execute a single tool."""
        if request.stream:
            # Return streaming response
            async def stream_generator():
                formatter = StreamingResponseFormatter()
                async for event in integration.execute_tool(
                    request.tool_name,
                    request.arguments,
                    request.session_id,
                    stream=True
                ):
                    # Format as SSE
                    yield event.to_sse()
            
            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )
        else:
            # Return regular response
            result = await integration.execute_tool(
                request.tool_name,
                request.arguments,
                request.session_id,
                stream=False
            )
            return {"result": result}
    
    @app.post("/tools/batch")
    async def execute_batch(request: BatchExecutionRequest):
        """Execute multiple tools in batch."""
        async def stream_generator():
            formatter = StreamingResponseFormatter()
            async for event in integration.execute_batch(
                request.tool_calls,
                request.session_id
            ):
                # Format as SSE
                yield event.to_sse()
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )
    
    @app.post("/tools/toggle")
    async def toggle_tool(request: ToolToggleRequest):
        """Enable or disable a tool."""
        success = integration.tool_manager.set_tool_enabled(
            request.tool_name,
            request.enabled
        )
        return {"success": success}
    
    @app.get("/tools/statistics")
    async def get_tool_statistics():
        """Get tool usage statistics."""
        return integration.tool_manager.get_tool_statistics()
    
    @app.post("/sessions")
    async def create_session(request: SessionCreateRequest):
        """Create a new session."""
        session_id = await integration.create_session(
            selected_servers=request.selected_servers,
            ttl_hours=request.ttl_hours,
            metadata=request.metadata
        )
        return {"session_id": session_id}
    
    @app.get("/sessions")
    async def list_sessions():
        """List all active sessions."""
        return await integration.session_manager.list_sessions()
    
    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        """Get session details."""
        session = await integration.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_dict()
    
    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session."""
        success = await integration.session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True}
    
    @app.get("/sessions/{session_id}/tools")
    async def get_session_tools(session_id: str):
        """Get tools available in a session."""
        tools = await integration.session_manager.get_session_tools(session_id)
        return tools
    
    @app.get("/sessions/{session_id}/statistics")
    async def get_session_statistics(session_id: str):
        """Get statistics for a session."""
        return integration.session_stats.get_session_statistics(session_id)
    
    @app.post("/servers/reload")
    async def reload_server(request: ServerReloadRequest):
        """Hot-reload a server."""
        result = await integration.hot_reload_server(request.server_name)
        return result
    
    @app.get("/servers")
    async def list_servers():
        """List all configured servers."""
        return {
            server_name: {
                'connected': server_name in integration.bridge.proxies,
                'tool_count': len(integration.bridge.server_tools.get(server_name, []))
            }
            for server_name in integration.bridge.servers
        }
    
    @app.get("/configurations")
    async def list_configurations():
        """List saved configurations."""
        return integration.config_manager.list_configurations()
    
    @app.post("/configurations/{name}/load")
    async def load_configuration(name: str):
        """Load a saved configuration."""
        success = integration.config_manager.load_configuration(name)
        if not success:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Reinitialize with new configuration
        await integration.initialize()
        return {"success": True}
    
    @app.post("/configurations/{name}/save")
    async def save_configuration(name: str):
        """Save current configuration."""
        path = integration.config_manager.save_configuration(name)
        return {"path": str(path)}
    
    @app.get("/statistics/global")
    async def get_global_statistics():
        """Get global usage statistics."""
        return integration.session_stats.get_global_statistics()
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        status = integration.get_status()
        
        # Determine health status
        if not status['initialized']:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        connected_servers = sum(
            1 for s in status['servers'].values() if s == 'connected'
        )
        
        if connected_servers == 0:
            raise HTTPException(status_code=503, detail="No servers connected")
        
        return {
            'status': 'healthy',
            'connected_servers': connected_servers,
            'active_sessions': status['sessions']['active']
        }
    
    return app


# CLI Integration for standalone server
async def run_standalone_server(
    host: str = "0.0.0.0",
    port: int = 3003,
    config_path: Optional[str] = None
):
    """Run the enhanced MCP server as a standalone service."""
    import uvicorn
    
    # Create integration service
    integration = MCPIntegrationService(config_path)
    
    # Create FastAPI app
    app = create_mcp_api(integration)
    
    # Run server
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


# Main entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced MCP Integration Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3003, help="Port to listen on")
    parser.add_argument("--config", help="Path to MCP configuration file")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    asyncio.run(run_standalone_server(args.host, args.port, args.config))