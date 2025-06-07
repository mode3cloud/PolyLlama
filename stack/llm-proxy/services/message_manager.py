"""
Message Manager for LLM Proxy Service

Handles chat session persistence and message storage.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageManager:
    """Simple in-memory message manager (can be extended with Neo4j later)."""
    
    def __init__(self, neo4j_driver=None):
        """Initialize message manager."""
        self.neo4j_driver = neo4j_driver
        # In-memory storage for sessions
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    async def get_session_messages(self, session_id: str) -> Dict[str, Any]:
        """Get all messages for a session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
        return self.sessions[session_id]
    
    async def add_system_message(self, session_id: str, content: str) -> None:
        """Add a system message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "system",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        session["messages"].append(message)
    
    async def add_user_message(self, session_id: str, content: str) -> None:
        """Add a user message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        session["messages"].append(message)
    
    async def add_assistant_message(self, session_id: str, content: str) -> None:
        """Add an assistant message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        session["messages"].append(message)
    
    async def add_tool_message(self, session_id: str, content: str, tool_name: str, tool_call_id: str) -> None:
        """Add a tool result message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "tool",
            "content": content,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "timestamp": datetime.now().isoformat()
        }
        session["messages"].append(message)
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return [
            {
                "id": session_id,
                "created_at": session_data["created_at"],
                "message_count": len(session_data["messages"])
            }
            for session_id, session_data in self.sessions.items()
        ]
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False