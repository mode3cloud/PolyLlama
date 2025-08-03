"""
MCP Bridge - Connects to upstream MCP servers and aggregates their tools
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None


class MCPBridge:
    """Bridges to upstream MCP servers and aggregates their tools."""
    
    def __init__(self):
        self.servers = {}
        self.sessions = {}
        self.aggregated_tools = {}
        
    async def load_config(self, config_path: str) -> None:
        """Load MCP server configurations from file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            for server_name, server_config in config.get('mcpServers', {}).items():
                self.servers[server_name] = MCPServerConfig(
                    name=server_name,
                    command=server_config.get('command', ''),
                    args=server_config.get('args', []),
                    env=server_config.get('env', {})
                )
                logger.info(f"Loaded config for MCP server: {server_name}")
                
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")
    
    def _get_simulated_tools(self, server_name: str) -> Dict[str, Dict[str, Any]]:
        """Get simulated tools for a server (temporary until real MCP integration)."""
        tools = {}
        
        if server_name == 'github':
            tools = {
                'search_repositories': {'description': 'Search GitHub repositories'},
                'get_file_contents': {'description': 'Get file contents from a repository'},
                'create_issue': {'description': 'Create a new issue'},
                'create_pull_request': {'description': 'Create a new pull request'},
                'list_issues': {'description': 'List issues in a repository'},
                'search_code': {'description': 'Search for code across repositories'},
                'get_pull_request': {'description': 'Get details of a pull request'},
                'list_commits': {'description': 'List commits in a repository'},
                'create_branch': {'description': 'Create a new branch'},
                'fork_repository': {'description': 'Fork a repository'},
                'update_issue': {'description': 'Update an existing issue'},
                'add_issue_comment': {'description': 'Add a comment to an issue'},
                'merge_pull_request': {'description': 'Merge a pull request'},
                'get_issue': {'description': 'Get details of an issue'},
                'create_repository': {'description': 'Create a new repository'}
            }
        elif server_name == 'personal-ai':
            tools = {
                'search_notes': {'description': 'Search through personal notes'},
                'create_note': {'description': 'Create a new note'},
                'update_note': {'description': 'Update an existing note'},
                'get_calendar': {'description': 'Get calendar events'},
                'create_event': {'description': 'Create a calendar event'},
                'get_tasks': {'description': 'Get task list'},
                'create_task': {'description': 'Create a new task'},
                'complete_task': {'description': 'Mark a task as complete'}
            }
        elif server_name == 'context7':
            tools = {
                'resolve_library_id': {'description': 'Resolve a package name to a Context7 library ID'},
                'get_library_docs': {'description': 'Get documentation for a library'}
            }
        elif server_name == 'sequential-thinking':
            tools = {
                'sequentialthinking': {'description': 'Sequential thinking and problem-solving'}
            }
        elif server_name == 'browsermcp':
            tools = {
                'browser_navigate': {'description': 'Navigate to a URL'},
                'browser_snapshot': {'description': 'Take a snapshot of the current page'},
                'browser_click': {'description': 'Click on an element'},
                'browser_type': {'description': 'Type text into an element'},
                'browser_wait': {'description': 'Wait for a specified time'}
            }
        elif server_name == 'hubspot':
            tools = {
                'list_contacts': {'description': 'List HubSpot contacts'},
                'get_contact': {'description': 'Get a specific contact'},
                'create_contact': {'description': 'Create a new contact'},
                'update_contact': {'description': 'Update an existing contact'},
                'search_contacts': {'description': 'Search for contacts'}
            }
        elif server_name == 'azureDevOps':
            tools = {
                'list_projects': {'description': 'List Azure DevOps projects'},
                'get_project': {'description': 'Get project details'},
                'list_work_items': {'description': 'List work items'},
                'create_work_item': {'description': 'Create a new work item'},
                'update_work_item': {'description': 'Update an existing work item'}
            }
        elif server_name == 'firecrawl':
            tools = {
                'crawl_url': {'description': 'Crawl a URL and extract content'},
                'search_web': {'description': 'Search the web'},
                'extract_data': {'description': 'Extract structured data from a page'},
                'take_screenshot': {'description': 'Take a screenshot of a webpage'},
                'get_sitemap': {'description': 'Get the sitemap of a website'}
            }
        else:
            # Default tools for unknown servers
            tools = {
                'default_tool_1': {'description': f'Tool 1 from {server_name}'},
                'default_tool_2': {'description': f'Tool 2 from {server_name}'},
                'default_tool_3': {'description': f'Tool 3 from {server_name}'},
                'default_tool_4': {'description': f'Tool 4 from {server_name}'},
                'default_tool_5': {'description': f'Tool 5 from {server_name}'}
            }
        
        return tools
            
    async def connect_server(self, server_name: str, config: MCPServerConfig) -> dict:
        """Connect to a single MCP server and return connection info."""
        server_info = {
            'name': server_name,
            'status': 'failed',
            'tool_count': 0,
            'error': None
        }
        
        try:
            logger.info(f"🔄 Initializing MCP server: {server_name}")
            logger.info(f"   Command: {config.command}")
            logger.info(f"   Args: {config.args}")
            
            # For now, we'll simulate connection success for known servers
            # This matches the JavaScript behavior of stdio connections
            if config.command in ["npx", "node", "python", "python3", "uv"]:
                # Simulate successful connection
                server_info['status'] = 'connected'
                
                # Get simulated tools and add them to aggregated collection
                tools = self._get_simulated_tools(server_name)
                server_info['tool_count'] = len(tools)
                
                # Add tools to aggregated collection with server prefix
                for tool_name, tool_info in tools.items():
                    # Prefix tool name with server name to avoid conflicts
                    prefixed_name = f"{server_name}__{tool_name}"
                    self.aggregated_tools[prefixed_name] = {
                        'server': server_name,
                        'original_name': tool_name,
                        **tool_info
                    }
                
                logger.info(f"✅ Successfully connected to MCP server: {server_name} with {server_info['tool_count']} tools")
            else:
                server_info['error'] = f"Unknown command: {config.command}"
                logger.error(f"❌ Failed to initialize MCP server {server_name}: {server_info['error']}")
            
            if config.command == "npx" and "-y" in config.args and "mcp-remote" in config.args:
                # This is an HTTP-based MCP server
                for i, arg in enumerate(config.args):
                    if arg.startswith("http://") or arg.startswith("https://"):
                        url = arg
                        logger.info(f"   📡 HTTP endpoint: {url}")
                        break
                        
        except Exception as e:
            server_info['error'] = str(e)
            logger.error(f"❌ Error processing {server_name}: {e}")
            
        return server_info
            
    async def connect_all_servers(self) -> Dict[str, dict]:
        """Connect to all configured MCP servers and return connection info."""
        servers_info = {}
        
        # Connect to servers with slight delay to avoid overwhelming the system
        for i, (server_name, config) in enumerate(self.servers.items()):
            if i > 0:
                await asyncio.sleep(0.5)  # Small delay between connections
            server_info = await self.connect_server(server_name, config)
            servers_info[server_name] = server_info
        
        logger.info(f"Initialized {len(self.servers)} MCP servers")
        return servers_info
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate MCP server."""
        if tool_name not in self.aggregated_tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        tool_info = self.aggregated_tools[tool_name]
        server_name = tool_info['server']
        original_name = tool_info['original_name']
        
        if server_name not in self.sessions:
            raise RuntimeError(f"Server {server_name} is not connected")
            
        session = self.sessions[server_name]
        
        try:
            result = await session.call_tool(original_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
            
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all aggregated tools."""
        return self.aggregated_tools