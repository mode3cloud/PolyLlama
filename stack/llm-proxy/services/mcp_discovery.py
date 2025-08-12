"""
MCP Server Discovery Module

Handles parsing and validation of MCP server configurations from mcp-config.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_mcp_config(config_path: str = "/app/mcp-config.json") -> List[Dict[str, Any]]:
    """
    Parse and validate MCP server configurations from a JSON file.
    
    Args:
        config_path: Path to the mcp-config.json file
        
    Returns:
        List of validated server configurations ready for connection
    """
    servers = []
    
    # Check if config file exists
    if not os.path.exists(config_path):
        logger.warning(f"MCP config file not found at {config_path}")
        return servers
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        mcp_servers = config.get('mcpServers', {})
        
        for name, server_config in mcp_servers.items():
            # Skip disabled servers
            if server_config.get('disabled', False):
                logger.info(f"Skipping disabled server: {name}")
                continue
            
            # Determine server type based on configuration
            server_type = _determine_server_type(server_config)
            
            # Create server configuration object
            server = {
                "name": name,
                "type": server_type,
                "config": server_config
            }
            
            # Add command and args for STDIO servers
            if server_type == "stdio":
                server["command"] = server_config.get("command", "npx")
                server["args"] = server_config.get("args", [])
                server["env"] = server_config.get("env", {})
            
            # Add URL for SSE/HTTP servers  
            elif server_type in ["sse", "streamable_http"]:
                # Extract URL from config or args (for mcp-remote servers)
                url = _extract_url_from_config(server_config)
                if url:
                    server["url"] = url
                    server["headers"] = server_config.get("headers", {})
                else:
                    logger.warning(f"No URL found for {server_type} server: {name}")
                    continue
            
            servers.append(server)
            logger.info(f"Discovered MCP server: {name} (type: {server_type})")
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse MCP config file: {e}")
    except Exception as e:
        logger.error(f"Error loading MCP configurations: {e}")
    
    return servers


def _determine_server_type(config: Dict[str, Any]) -> str:
    """
    Determine the server type based on configuration.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        Server type: "stdio", "sse", or "streamable_http"
    """
    # Check if type is explicitly specified
    if "type" in config:
        return config["type"]
    
    # Check if it has a URL field (SSE/HTTP servers)
    if "url" in config:
        url = config["url"]
        if "sse" in url.lower() or "/sse" in url.lower():
            return "sse"
        return "streamable_http"
    
    # Check if using mcp-remote (HTTP proxy servers)
    args = config.get("args", [])
    if args and "mcp-remote" in str(args):
        # mcp-remote servers are HTTP-based
        for i, arg in enumerate(args):
            if arg == "--transport" and i + 1 < len(args):
                transport = args[i + 1].lower()
                if transport == "sse":
                    return "sse"
                elif transport == "http":
                    return "streamable_http"
        # Default to streamable_http for mcp-remote
        return "streamable_http"
    
    # Default to STDIO for command-based servers
    return "stdio"


def _extract_url_from_config(config: Dict[str, Any]) -> Optional[str]:
    """
    Extract URL from server configuration.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        URL string or None if not found
    """
    # Direct URL field
    if "url" in config:
        return config["url"]
    
    # Check args for mcp-remote URL
    args = config.get("args", [])
    for arg in args:
        if arg.startswith("http://") or arg.startswith("https://"):
            return arg
    
    return None


def validate_server_config(server: Dict[str, Any]) -> bool:
    """
    Validate a server configuration.
    
    Args:
        server: Server configuration to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Check required fields
    if not server.get("name"):
        logger.error("Server configuration missing name")
        return False
    
    server_type = server.get("type")
    if not server_type:
        logger.error(f"Server {server['name']} missing type")
        return False
    
    # Validate based on type
    if server_type == "stdio":
        if not server.get("command"):
            logger.error(f"STDIO server {server['name']} missing command")
            return False
    
    elif server_type in ["sse", "streamable_http"]:
        if not server.get("url"):
            logger.error(f"{server_type} server {server['name']} missing URL")
            return False
    
    return True


def get_server_display_info(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get display information about discovered servers.
    
    Args:
        servers: List of server configurations
        
    Returns:
        Dictionary with server statistics and details
    """
    info = {
        "total": len(servers),
        "by_type": {},
        "servers": []
    }
    
    # Count by type
    for server in servers:
        server_type = server.get("type", "unknown")
        info["by_type"][server_type] = info["by_type"].get(server_type, 0) + 1
        
        # Add basic server info
        info["servers"].append({
            "name": server.get("name"),
            "type": server_type,
            "command": server.get("command") if server_type == "stdio" else None,
            "url": server.get("url") if server_type != "stdio" else None
        })
    
    return info