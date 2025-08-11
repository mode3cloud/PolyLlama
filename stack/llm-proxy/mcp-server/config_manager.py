"""
Configuration Manager for MCP - Handles configuration persistence and auto-discovery
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import platform

logger = logging.getLogger(__name__)


@dataclass
class TransportConfig:
    """Configuration for MCP transport."""
    type: str  # 'stdio', 'sse', 'streamable_http'
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TransportConfig':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ServerConfig:
    """Configuration for an MCP server."""
    name: str
    transport: TransportConfig
    enabled: bool = True
    auto_connect: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'transport': self.transport.to_dict(),
            'enabled': self.enabled,
            'auto_connect': self.auto_connect,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ServerConfig':
        """Create from dictionary."""
        transport_data = data.get('transport', {})
        transport = TransportConfig.from_dict(transport_data)
        
        return cls(
            name=data['name'],
            transport=transport,
            enabled=data.get('enabled', True),
            auto_connect=data.get('auto_connect', True),
            metadata=data.get('metadata')
        )


class ConfigurationManager:
    """Manages MCP configuration with persistence and auto-discovery."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        # Setup configuration directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / '.polyllama' / 'configs'
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.active_config_file = self.config_dir / 'active_config.json'
        
        # Load active configuration if exists
        self.servers: Dict[str, ServerConfig] = {}
        self.load_active_configuration()
    
    def save_configuration(self, name: str, servers: Optional[Dict[str, ServerConfig]] = None) -> Path:
        """Save current or provided configuration with a name."""
        config_file = self.config_dir / f"{name}.json"
        
        # Use provided servers or current configuration
        servers_to_save = servers or self.servers
        
        # Convert to serializable format
        config_data = {
            'name': name,
            'servers': {
                name: server.to_dict()
                for name, server in servers_to_save.items()
            }
        }
        
        # Save to file
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Saved configuration '{name}' to {config_file}")
        return config_file
    
    def load_configuration(self, name: str) -> bool:
        """Load a named configuration."""
        config_file = self.config_dir / f"{name}.json"
        
        if not config_file.exists():
            logger.error(f"Configuration '{name}' not found at {config_file}")
            return False
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Parse servers
            self.servers = {}
            for server_name, server_data in config_data.get('servers', {}).items():
                self.servers[server_name] = ServerConfig.from_dict(server_data)
            
            # Mark as active configuration
            self.save_active_configuration()
            
            logger.info(f"Loaded configuration '{name}' with {len(self.servers)} servers")
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration '{name}': {e}")
            return False
    
    def save_active_configuration(self):
        """Save the current configuration as the active one."""
        self.save_configuration('active_config', self.servers)
        logger.info("Saved active configuration")
    
    def load_active_configuration(self) -> bool:
        """Load the active configuration if it exists."""
        if self.active_config_file.exists():
            return self.load_configuration('active_config')
        return False
    
    def list_configurations(self) -> List[str]:
        """List all saved configurations."""
        configs = []
        for config_file in self.config_dir.glob("*.json"):
            # Skip active_config as it's internal
            if config_file.stem != 'active_config':
                configs.append(config_file.stem)
        return sorted(configs)
    
    def delete_configuration(self, name: str) -> bool:
        """Delete a saved configuration."""
        if name == 'active_config':
            logger.error("Cannot delete active configuration")
            return False
        
        config_file = self.config_dir / f"{name}.json"
        if config_file.exists():
            config_file.unlink()
            logger.info(f"Deleted configuration '{name}'")
            return True
        
        return False
    
    def add_server(self, server: ServerConfig) -> bool:
        """Add a server to the current configuration."""
        if server.name in self.servers:
            logger.warning(f"Server '{server.name}' already exists, updating...")
        
        self.servers[server.name] = server
        self.save_active_configuration()
        logger.info(f"Added server '{server.name}' to configuration")
        return True
    
    def remove_server(self, server_name: str) -> bool:
        """Remove a server from the current configuration."""
        if server_name in self.servers:
            del self.servers[server_name]
            self.save_active_configuration()
            logger.info(f"Removed server '{server_name}' from configuration")
            return True
        
        return False
    
    def auto_discover_servers(self) -> List[ServerConfig]:
        """Auto-discover MCP servers from various sources."""
        discovered = []
        
        # 1. Check Claude Desktop configuration
        discovered.extend(self._discover_claude_desktop_servers())
        
        # 2. Check environment variables
        discovered.extend(self._discover_env_servers())
        
        # 3. Check VS Code configuration
        discovered.extend(self._discover_vscode_servers())
        
        # 4. Check for local MCP server manifests
        discovered.extend(self._discover_local_manifests())
        
        logger.info(f"Auto-discovered {len(discovered)} MCP servers")
        return discovered
    
    def _discover_claude_desktop_servers(self) -> List[ServerConfig]:
        """Discover servers from Claude Desktop configuration."""
        servers = []
        
        # Determine Claude config path based on platform
        system = platform.system()
        if system == 'Darwin':  # macOS
            config_path = Path.home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json'
        elif system == 'Windows':
            config_path = Path.home() / 'AppData' / 'Roaming' / 'Claude' / 'claude_desktop_config.json'
        else:  # Linux
            config_path = Path.home() / '.config' / 'Claude' / 'claude_desktop_config.json'
        
        if not config_path.exists():
            logger.debug(f"Claude Desktop config not found at {config_path}")
            return servers
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            mcp_servers = config.get('mcpServers', {})
            
            for server_name, server_data in mcp_servers.items():
                # Determine transport type
                command = server_data.get('command')
                args = server_data.get('args', [])
                env = server_data.get('env', {})
                
                # Check if it's an HTTP-based server
                url = None
                for arg in args:
                    if arg.startswith('http://') or arg.startswith('https://'):
                        url = arg
                        break
                
                if url:
                    transport = TransportConfig(
                        type='streamable_http',
                        url=url,
                        headers={}
                    )
                else:
                    transport = TransportConfig(
                        type='stdio',
                        command=command,
                        args=args,
                        env=env
                    )
                
                server = ServerConfig(
                    name=f"claude_{server_name}",
                    transport=transport,
                    metadata={'source': 'claude_desktop'}
                )
                
                servers.append(server)
                logger.info(f"Discovered Claude Desktop server: {server_name}")
                
        except Exception as e:
            logger.error(f"Error reading Claude Desktop config: {e}")
        
        return servers
    
    def _discover_env_servers(self) -> List[ServerConfig]:
        """Discover servers from environment variables."""
        servers = []
        
        # Check for MCP_SERVERS environment variable
        mcp_servers_env = os.environ.get('MCP_SERVERS')
        if not mcp_servers_env:
            return servers
        
        try:
            # Parse JSON from environment variable
            mcp_servers = json.loads(mcp_servers_env)
            
            for server_name, server_data in mcp_servers.items():
                if 'url' in server_data:
                    transport = TransportConfig(
                        type='streamable_http',
                        url=server_data['url'],
                        headers=server_data.get('headers', {})
                    )
                else:
                    transport = TransportConfig(
                        type='stdio',
                        command=server_data.get('command'),
                        args=server_data.get('args', []),
                        env=server_data.get('env', {})
                    )
                
                server = ServerConfig(
                    name=f"env_{server_name}",
                    transport=transport,
                    metadata={'source': 'environment'}
                )
                
                servers.append(server)
                logger.info(f"Discovered environment server: {server_name}")
                
        except Exception as e:
            logger.error(f"Error parsing MCP_SERVERS environment variable: {e}")
        
        return servers
    
    def _discover_vscode_servers(self) -> List[ServerConfig]:
        """Discover servers from VS Code configuration."""
        servers = []
        
        # Check VS Code settings
        vscode_config_paths = [
            Path.home() / '.config' / 'Code' / 'User' / 'settings.json',
            Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'settings.json',
            Path.home() / 'AppData' / 'Roaming' / 'Code' / 'User' / 'settings.json',
        ]
        
        for config_path in vscode_config_paths:
            if not config_path.exists():
                continue
            
            try:
                with open(config_path, 'r') as f:
                    settings = json.load(f)
                
                # Look for MCP-related settings
                mcp_settings = settings.get('mcp', {})
                servers_config = mcp_settings.get('servers', {})
                
                for server_name, server_data in servers_config.items():
                    transport = TransportConfig(
                        type=server_data.get('type', 'stdio'),
                        command=server_data.get('command'),
                        args=server_data.get('args', []),
                        env=server_data.get('env', {})
                    )
                    
                    server = ServerConfig(
                        name=f"vscode_{server_name}",
                        transport=transport,
                        metadata={'source': 'vscode'}
                    )
                    
                    servers.append(server)
                    logger.info(f"Discovered VS Code server: {server_name}")
                    
            except Exception as e:
                logger.debug(f"Error reading VS Code config from {config_path}: {e}")
        
        return servers
    
    def _discover_local_manifests(self) -> List[ServerConfig]:
        """Discover servers from local MCP manifest files."""
        servers = []
        
        # Check common locations for MCP manifests
        manifest_locations = [
            Path.home() / '.mcp' / 'servers',
            Path('/usr/local/share/mcp/servers'),
            Path('/opt/mcp/servers'),
        ]
        
        for location in manifest_locations:
            if not location.exists():
                continue
            
            for manifest_file in location.glob('*/manifest.json'):
                try:
                    with open(manifest_file, 'r') as f:
                        manifest = json.load(f)
                    
                    server_name = manifest.get('name', manifest_file.parent.name)
                    
                    # Create transport based on manifest
                    if 'command' in manifest:
                        transport = TransportConfig(
                            type='stdio',
                            command=manifest['command'],
                            args=manifest.get('args', []),
                            env=manifest.get('env', {})
                        )
                    elif 'url' in manifest:
                        transport = TransportConfig(
                            type='streamable_http',
                            url=manifest['url'],
                            headers=manifest.get('headers', {})
                        )
                    else:
                        continue
                    
                    server = ServerConfig(
                        name=f"local_{server_name}",
                        transport=transport,
                        metadata={
                            'source': 'local_manifest',
                            'manifest_path': str(manifest_file)
                        }
                    )
                    
                    servers.append(server)
                    logger.info(f"Discovered local manifest server: {server_name}")
                    
                except Exception as e:
                    logger.debug(f"Error reading manifest {manifest_file}: {e}")
        
        return servers
    
    def import_claude_config(self) -> int:
        """Import all servers from Claude Desktop configuration."""
        discovered = self._discover_claude_desktop_servers()
        
        count = 0
        for server in discovered:
            # Remove 'claude_' prefix for cleaner names
            server.name = server.name.replace('claude_', '')
            if self.add_server(server):
                count += 1
        
        logger.info(f"Imported {count} servers from Claude Desktop")
        return count
    
    def export_to_claude_format(self) -> dict:
        """Export current configuration to Claude Desktop format."""
        claude_config = {'mcpServers': {}}
        
        for server_name, server in self.servers.items():
            transport = server.transport
            
            if transport.type == 'stdio':
                claude_server = {
                    'command': transport.command,
                    'args': transport.args or [],
                }
                if transport.env:
                    claude_server['env'] = transport.env
            
            elif transport.type in ['streamable_http', 'sse']:
                # For HTTP servers, put URL in args
                claude_server = {
                    'command': 'node',
                    'args': [transport.url],
                }
                if transport.headers:
                    claude_server['env'] = {
                        'HTTP_HEADERS': json.dumps(transport.headers)
                    }
            else:
                continue
            
            claude_config['mcpServers'][server_name] = claude_server
        
        return claude_config