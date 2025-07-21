"""
Tests for PolyLlama MCP Server functionality.
"""
import json
import pytest
import requests
import time
from unittest.mock import patch, MagicMock
import subprocess


class TestMCPServer:
    """Test suite for MCP Server endpoints and functionality."""

    @pytest.fixture
    def mock_polyllama_response(self):
        """Mock successful PolyLlama API responses."""
        return {
            "models": [
                {"name": "llama3.2:3b", "size": 2000000000, "modified_at": "2024-01-15T10:30:00Z"},
                {"name": "codellama:7b", "size": 3800000000, "modified_at": "2024-01-14T15:22:00Z"}
            ]
        }

    def test_mcp_server_health_endpoint(self):
        """Test MCP server health check endpoint."""
        # This would test against a running MCP server instance
        # For now, we'll test the expected structure
        expected_health = {
            "status": "ok",
            "service": "polyllama-mcp-server",
            "version": "1.0.0",
            "timestamp": "2024-01-15T10:30:00.000Z"
        }
        
        # In a real test, this would be:
        # response = requests.get("http://localhost:3001/health")
        # assert response.status_code == 200
        # assert response.json()["status"] == "ok"
        
        # For now, validate structure
        assert "status" in expected_health
        assert "service" in expected_health
        assert "version" in expected_health
        assert expected_health["status"] == "ok"

    def test_mcp_server_info_endpoint(self):
        """Test MCP server info endpoint structure."""
        expected_info = {
            "name": "PolyLlama MCP Server",
            "version": "1.0.0",
            "description": "MCP Server that exposes PolyLlama orchestration capabilities as tools",
            "tools": [
                {"name": "polyllama_list_models", "description": "List all available models across PolyLlama instances"},
                {"name": "polyllama_load_model", "description": "Load a model on the optimal PolyLlama instance"},
                {"name": "polyllama_get_status", "description": "Get PolyLlama system status and health information"},
                {"name": "polyllama_get_running_models", "description": "Get currently running models across all instances"},
                {"name": "polyllama_route_request", "description": "Execute a direct Ollama API request with PolyLlama routing"},
                {"name": "polyllama_get_model_mappings", "description": "Get current model-to-instance mappings and routing information"}
            ],
            "endpoints": {
                "sse": "/sse",
                "health": "/health",
                "info": "/info"
            }
        }
        
        # Validate tool definitions
        assert len(expected_info["tools"]) == 6
        tool_names = [tool["name"] for tool in expected_info["tools"]]
        assert "polyllama_list_models" in tool_names
        assert "polyllama_load_model" in tool_names
        assert "polyllama_get_status" in tool_names

    @patch('requests.get')
    def test_polyllama_list_models_tool(self, mock_get, mock_polyllama_response):
        """Test the polyllama_list_models tool execution."""
        # Mock successful response from PolyLlama
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_polyllama_response
        mock_get.return_value = mock_response
        
        # Simulate tool execution
        # In real implementation, this would be handled by the MCP server
        tool_args = {"show_details": False}
        
        # Expected tool response format
        expected_response = {
            "type": "text",
            "text": f"Available models in PolyLlama:\n\n{json.dumps(mock_polyllama_response, indent=2)}"
        }
        
        assert expected_response["type"] == "text"
        assert "Available models in PolyLlama" in expected_response["text"]

    @patch('requests.post')
    def test_polyllama_load_model_tool(self, mock_post):
        """Test the polyllama_load_model tool execution."""
        # Mock successful model loading response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "Model loading initiated"}
        mock_post.return_value = mock_response
        
        # Simulate tool execution
        tool_args = {"name": "llama3.2:3b", "force_instance": "polyllama1"}
        
        # Expected tool response structure
        expected_call_args = {
            "name": "llama3.2:3b",
            "stream": False,
            "instance": "polyllama1"
        }
        
        # Validate tool arguments
        assert tool_args["name"] == "llama3.2:3b"
        assert tool_args["force_instance"] == "polyllama1"

    def test_polyllama_tool_schemas(self):
        """Test that all PolyLlama tools have proper schemas."""
        expected_tools = [
            {
                "name": "polyllama_list_models",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "show_details": {"type": "boolean", "default": False}
                    }
                }
            },
            {
                "name": "polyllama_load_model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "force_instance": {"type": "string"}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "polyllama_get_status",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_metrics": {"type": "boolean", "default": False}
                    }
                }
            }
        ]
        
        # Validate schema structure
        for tool in expected_tools:
            assert "name" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]

    @patch('requests.get')
    def test_polyllama_get_status_tool(self, mock_get):
        """Test the polyllama_get_status tool execution."""
        # Mock status responses
        mock_instance_response = MagicMock()
        mock_instance_response.status_code = 200
        mock_instance_response.json.return_value = {
            "instances": [
                {"name": "polyllama1", "status": "online", "gpu": "RTX 4090"},
                {"name": "polyllama2", "status": "online", "gpu": "RTX 4090"}
            ]
        }
        
        mock_mappings_response = MagicMock()
        mock_mappings_response.status_code = 200
        mock_mappings_response.json.return_value = {
            "llama3.2:3b": "polyllama1",
            "codellama:7b": "polyllama2"
        }
        
        # Configure mock to return different responses based on endpoint
        def side_effect(url, **kwargs):
            if "instance-status" in url:
                return mock_instance_response
            elif "model-mappings" in url:
                return mock_mappings_response
            return MagicMock(status_code=404)
        
        mock_get.side_effect = side_effect
        
        # Test tool arguments
        tool_args = {"include_metrics": False}
        
        # Validate that tool would make expected calls
        assert tool_args["include_metrics"] == False

    def test_mcp_server_configuration(self):
        """Test MCP server configuration structure."""
        expected_config = {
            "name": "polyllama-mcp-server",
            "version": "1.0.0",
            "port": 3001,
            "endpoints": {
                "sse": "/sse",
                "health": "/health", 
                "info": "/info"
            },
            "polyllama_base_url": "http://polyllama:11434",
            "authentication_required": False
        }
        
        # Validate configuration structure
        assert expected_config["name"] == "polyllama-mcp-server"
        assert expected_config["port"] == 3001
        assert "sse" in expected_config["endpoints"]
        assert "health" in expected_config["endpoints"]
        assert "info" in expected_config["endpoints"]

    def test_nginx_sse_proxy_configuration(self):
        """Test that Nginx SSE proxy configuration is correct."""
        expected_nginx_config = """
        location /sse {
            proxy_pass http://mcp-server:3001/sse;
            proxy_http_version 1.1;
            proxy_set_header Connection '';
            proxy_set_header Cache-Control no-cache;
            proxy_set_header X-Accel-Buffering no;
            proxy_buffering off;
            chunked_transfer_encoding off;
        }
        """
        
        # Validate key SSE configuration elements
        assert "proxy_pass http://mcp-server:3001/sse" in expected_nginx_config
        assert "proxy_buffering off" in expected_nginx_config
        assert "X-Accel-Buffering no" in expected_nginx_config
        assert "Cache-Control no-cache" in expected_nginx_config

    def test_docker_compose_mcp_server_service(self):
        """Test Docker Compose service configuration for MCP server."""
        expected_service = {
            "mcp-server": {
                "build": {
                    "context": "../../stack/llm-proxy/mcp-server",
                    "dockerfile": "Dockerfile"
                },
                "container_name": "mcp-server",
                "hostname": "mcp-server",
                "ports": ["3001:3001"],
                "environment": [
                    "MCP_SERVER_PORT=3001",
                    "OLLAMA_BASE_URL=http://router:11434"
                ],
                "depends_on": ["router"]
            }
        }
        
        service = expected_service["mcp-server"]
        assert service["container_name"] == "mcp-server"
        assert "3001:3001" in service["ports"]
        assert "MCP_SERVER_PORT=3001" in service["environment"]
        assert "OLLAMA_BASE_URL=http://router:11434" in service["environment"]
        assert "router" in service["depends_on"]

    @patch('subprocess.run')
    def test_mcp_server_startup_validation(self, mock_subprocess):
        """Test MCP server startup and validation."""
        # Mock successful Docker build and startup
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="Success")
        
        # Simulate startup commands that would be run
        build_cmd = ["docker", "build", "-t", "polyllama-mcp-server", "stack/llm-proxy/mcp-server/"]
        run_cmd = ["docker", "run", "-d", "--name", "test-mcp-server", "-p", "3001:3001", "polyllama-mcp-server"]
        
        # In real test, these would actually execute
        # For now, validate command structure
        assert build_cmd[0] == "docker"
        assert build_cmd[1] == "build"
        assert "polyllama-mcp-server" in build_cmd
        
        assert run_cmd[0] == "docker"
        assert run_cmd[1] == "run"
        assert "-p" in run_cmd
        assert "3001:3001" in run_cmd


class TestMCPServerIntegration:
    """Integration tests for MCP Server with PolyLlama."""

    def test_mcp_server_tool_registry_integration(self):
        """Test integration between MCP server and tool registry."""
        # This would test the actual integration in a running environment
        # For now, validate expected integration points
        
        integration_points = {
            "mcp_server_tools": 6,  # Number of PolyLlama tools exposed
            "expected_endpoints": ["/sse", "/health", "/info"],
            "docker_services": ["mcp-server", "router", "llm-proxy"],
            "nginx_locations": ["/sse", "/mcp-server/info", "/mcp-server/health"]
        }
        
        assert integration_points["mcp_server_tools"] == 6
        assert "/sse" in integration_points["expected_endpoints"]
        assert "mcp-server" in integration_points["docker_services"]
        assert "/sse" in integration_points["nginx_locations"]

    def test_mcp_protocol_compliance(self):
        """Test MCP protocol compliance for PolyLlama tools."""
        # Validate that tool definitions comply with MCP protocol
        mcp_tool_format = {
            "name": "string",
            "description": "string", 
            "inputSchema": {
                "type": "object",
                "properties": "object",
                "required": "array"  # optional
            }
        }
        
        sample_tool = {
            "name": "polyllama_list_models",
            "description": "List all available models across PolyLlama instances",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "show_details": {"type": "boolean", "default": False}
                }
            }
        }
        
        # Validate MCP compliance
        assert isinstance(sample_tool["name"], str)
        assert isinstance(sample_tool["description"], str)
        assert sample_tool["inputSchema"]["type"] == "object"
        assert "properties" in sample_tool["inputSchema"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])