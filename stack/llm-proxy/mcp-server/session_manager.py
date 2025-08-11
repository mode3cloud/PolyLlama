"""
Session Manager for MCP - Handles multi-tenant sessions with tool selection and persistence
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for a session."""
    session_id: str
    created_at: float
    updated_at: float
    selected_servers: List[str]
    enabled_tools: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionConfig':
        """Create from dictionary."""
        return cls(**data)


class SessionManager:
    """Manages MCP sessions with tool selection and persistence."""
    
    def __init__(self, bridge, storage_dir: Optional[Path] = None):
        self.bridge = bridge
        self.sessions: Dict[str, SessionConfig] = {}
        self.session_tools: Dict[str, Set[str]] = {}  # Session -> available tools
        self.session_connections: Dict[str, Dict[str, Any]] = {}  # Session -> server connections
        
        # Setup persistent storage
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / '.polyllama' / 'sessions'
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions
        self._load_sessions()
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_expired_sessions())
    
    def _load_sessions(self):
        """Load sessions from persistent storage."""
        for session_file in self.storage_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    session = SessionConfig.from_dict(data)
                    
                    # Skip expired sessions
                    if not session.is_expired():
                        self.sessions[session.session_id] = session
                        logger.info(f"Loaded session: {session.session_id}")
                    else:
                        # Clean up expired session file
                        session_file.unlink()
                        
            except Exception as e:
                logger.error(f"Error loading session from {session_file}: {e}")
    
    def _save_session(self, session: SessionConfig):
        """Save session to persistent storage."""
        session_file = self.storage_dir / f"{session.session_id}.json"
        try:
            with open(session_file, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}")
    
    def _delete_session_file(self, session_id: str):
        """Delete session file from storage."""
        session_file = self.storage_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
    
    async def create_session(
        self,
        selected_servers: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        ttl_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new session with specific servers."""
        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Use all servers if none selected
        if selected_servers is None:
            selected_servers = list(self.bridge.servers.keys())
        
        # Validate servers exist
        invalid_servers = [s for s in selected_servers if s not in self.bridge.servers]
        if invalid_servers:
            raise ValueError(f"Invalid servers: {invalid_servers}")
        
        # Create session config
        current_time = time.time()
        session = SessionConfig(
            session_id=session_id,
            created_at=current_time,
            updated_at=current_time,
            selected_servers=selected_servers,
            metadata=metadata or {},
            expires_at=current_time + (ttl_hours * 3600) if ttl_hours > 0 else None
        )
        
        # Initialize tools for this session
        session_tools = set()
        for server_name in selected_servers:
            if server_name in self.bridge.server_tools:
                for tool in self.bridge.server_tools[server_name]:
                    tool_name = f"{server_name}__{tool['name']}"
                    session_tools.add(tool_name)
                    session.enabled_tools[tool_name] = True  # Enable by default
        
        # Store session
        self.sessions[session_id] = session
        self.session_tools[session_id] = session_tools
        self.session_connections[session_id] = {}
        
        # Save to persistent storage
        self._save_session(session)
        
        logger.info(f"Created session {session_id} with {len(selected_servers)} servers and {len(session_tools)} tools")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionConfig]:
        """Get session configuration."""
        session = self.sessions.get(session_id)
        
        if session and session.is_expired():
            # Clean up expired session
            await self.delete_session(session_id)
            return None
        
        return session
    
    async def update_session(
        self,
        session_id: str,
        enabled_tools: Optional[Dict[str, bool]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update session configuration."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        # Update configuration
        session.updated_at = time.time()
        
        if enabled_tools is not None:
            session.enabled_tools.update(enabled_tools)
        
        if metadata is not None:
            session.metadata.update(metadata)
        
        # Save changes
        self._save_session(session)
        
        logger.info(f"Updated session {session_id}")
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id not in self.sessions:
            return False
        
        # Clean up session data
        del self.sessions[session_id]
        
        if session_id in self.session_tools:
            del self.session_tools[session_id]
        
        if session_id in self.session_connections:
            del self.session_connections[session_id]
        
        # Delete from storage
        self._delete_session_file(session_id)
        
        logger.info(f"Deleted session {session_id}")
        return True
    
    async def execute_tool_in_session(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Execute a tool within a specific session context."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")
        
        # Check if tool is available in this session
        if tool_name not in self.session_tools.get(session_id, set()):
            raise ValueError(f"Tool {tool_name} not available in session {session_id}")
        
        # Check if tool is enabled
        if not session.enabled_tools.get(tool_name, True):
            raise ValueError(f"Tool {tool_name} is disabled in session {session_id}")
        
        # Extract server name from tool name
        parts = tool_name.split('__', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid tool name format: {tool_name}")
        
        server_name = parts[0]
        
        # Check if server is in session's selected servers
        if server_name not in session.selected_servers:
            raise ValueError(f"Server {server_name} not selected for session {session_id}")
        
        # Execute the tool
        start_time = time.time()
        try:
            result = await self.bridge.call_tool(tool_name, arguments)
            
            # Update session activity
            session.updated_at = time.time()
            self._save_session(session)
            
            # Record success metrics
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Tool {tool_name} executed successfully in session {session_id} ({duration_ms:.2f}ms)")
            
            return result
            
        except Exception as e:
            # Record error metrics
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Tool {tool_name} failed in session {session_id} ({duration_ms:.2f}ms): {e}")
            raise
    
    async def get_session_tools(self, session_id: str) -> List[Dict[str, Any]]:
        """Get available tools for a session."""
        session = await self.get_session(session_id)
        if not session:
            return []
        
        tools = []
        for tool_name in self.session_tools.get(session_id, set()):
            if tool_name in session.enabled_tools:
                # Get tool metadata from bridge
                parts = tool_name.split('__', 1)
                if len(parts) == 2:
                    server_name, original_name = parts
                    
                    # Find tool info
                    for tool in self.bridge.server_tools.get(server_name, []):
                        if tool['name'] == original_name:
                            tools.append({
                                'name': tool_name,
                                'enabled': session.enabled_tools.get(tool_name, True),
                                'description': tool['description'],
                                'server': server_name,
                                'input_schema': tool.get('input_schema', {})
                            })
                            break
        
        return tools
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        sessions = []
        
        for session_id, session in list(self.sessions.items()):
            if session.is_expired():
                # Clean up expired session
                await self.delete_session(session_id)
                continue
            
            sessions.append({
                'session_id': session_id,
                'created_at': datetime.fromtimestamp(session.created_at).isoformat(),
                'updated_at': datetime.fromtimestamp(session.updated_at).isoformat(),
                'expires_at': datetime.fromtimestamp(session.expires_at).isoformat() if session.expires_at else None,
                'selected_servers': session.selected_servers,
                'tool_count': len(self.session_tools.get(session_id, set())),
                'enabled_tool_count': sum(1 for enabled in session.enabled_tools.values() if enabled),
                'metadata': session.metadata
            })
        
        return sessions
    
    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                # Check every hour
                await asyncio.sleep(3600)
                
                expired_count = 0
                for session_id, session in list(self.sessions.items()):
                    if session.is_expired():
                        await self.delete_session(session_id)
                        expired_count += 1
                
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions")
                    
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")


class SessionStatistics:
    """Track and report session statistics."""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.tool_execution_history = []  # List of execution records
        self.max_history_size = 10000
    
    def record_execution(
        self,
        session_id: str,
        tool_name: str,
        success: bool,
        duration_ms: float,
        timestamp: float = None
    ):
        """Record a tool execution."""
        record = {
            'session_id': session_id,
            'tool_name': tool_name,
            'success': success,
            'duration_ms': duration_ms,
            'timestamp': timestamp or time.time()
        }
        
        self.tool_execution_history.append(record)
        
        # Trim history if too large
        if len(self.tool_execution_history) > self.max_history_size:
            self.tool_execution_history = self.tool_execution_history[-self.max_history_size:]
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a specific session."""
        executions = [r for r in self.tool_execution_history if r['session_id'] == session_id]
        
        if not executions:
            return {
                'session_id': session_id,
                'total_executions': 0,
                'success_rate': 0.0,
                'avg_duration_ms': 0.0,
                'most_used_tools': []
            }
        
        # Calculate statistics
        total = len(executions)
        successes = sum(1 for e in executions if e['success'])
        avg_duration = sum(e['duration_ms'] for e in executions) / total
        
        # Find most used tools
        tool_counts = {}
        for e in executions:
            tool_counts[e['tool_name']] = tool_counts.get(e['tool_name'], 0) + 1
        
        most_used = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'session_id': session_id,
            'total_executions': total,
            'success_rate': successes / total,
            'avg_duration_ms': avg_duration,
            'most_used_tools': [{'tool': t, 'count': c} for t, c in most_used]
        }
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global statistics across all sessions."""
        if not self.tool_execution_history:
            return {
                'total_sessions': len(self.session_manager.sessions),
                'total_executions': 0,
                'global_success_rate': 0.0,
                'avg_duration_ms': 0.0,
                'executions_per_hour': []
            }
        
        # Calculate global metrics
        total = len(self.tool_execution_history)
        successes = sum(1 for e in self.tool_execution_history if e['success'])
        avg_duration = sum(e['duration_ms'] for e in self.tool_execution_history) / total
        
        # Calculate executions per hour for the last 24 hours
        current_time = time.time()
        hour_buckets = {}
        
        for e in self.tool_execution_history:
            hours_ago = int((current_time - e['timestamp']) / 3600)
            if hours_ago < 24:
                hour_buckets[hours_ago] = hour_buckets.get(hours_ago, 0) + 1
        
        executions_per_hour = [
            {'hours_ago': i, 'count': hour_buckets.get(i, 0)}
            for i in range(24)
        ]
        
        return {
            'total_sessions': len(self.session_manager.sessions),
            'total_executions': total,
            'global_success_rate': successes / total,
            'avg_duration_ms': avg_duration,
            'executions_per_hour': executions_per_hour
        }