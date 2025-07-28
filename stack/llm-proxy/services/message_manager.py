"""
Message Manager for LLM Proxy Service

Handles chat session persistence and message storage.
"""

import json
import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime
import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _ensure_valid_tool_call_id(tool_id: str) -> str:
    """Ensure tool call ID is within OpenAI's 40-character limit."""
    if len(tool_id) <= 40:
        return tool_id
    
    # Hash the ID to create a consistent, shorter version
    # Use first 8 chars + SHA256 hash truncated to 32 chars
    hash_obj = hashlib.sha256(tool_id.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()[:32]  # Take first 32 chars of hash
    return f"{tool_id[:8]}{hash_hex}"[:40]  # Ensure total is exactly 40 chars


class MessageManager:
    """Redis-based message manager for persistent chat sessions."""

    def __init__(self, redis_url: str = "redis://redis:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.session_prefix = "polyllama:session:"
        self.sessions_list_key = "polyllama:sessions"
        
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                decode_responses=True,
                health_check_interval=30
            )
        return self.redis_client
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None

    async def get_session_messages(self, session_id: str) -> Dict[str, Any]:
        """Get all messages for a session."""
        try:
            client = await self._get_redis()
            session_key = f"{self.session_prefix}{session_id}"
            
            # Try to get existing session
            session_data = await client.get(session_key)
            
            if session_data:
                session = json.loads(session_data)
                # Ensure metadata field exists for backward compatibility
                if "metadata" not in session:
                    session["metadata"] = {}
                # Validate and fix any tool_call_ids that are too long (backward compatibility)
                messages_updated = False
                for message in session.get("messages", []):
                    # Fix tool_call_id in tool messages
                    if message.get("role") == "tool" and "tool_call_id" in message:
                        original_id = message["tool_call_id"]
                        validated_id = _ensure_valid_tool_call_id(original_id)
                        if original_id != validated_id:
                            message["tool_call_id"] = validated_id
                            messages_updated = True
                            logger.info(f"Fixed tool_call_id in tool message: {original_id} -> {validated_id}")
                    
                    # Fix tool_call_id in assistant messages with tool_calls
                    if message.get("role") == "assistant" and "tool_calls" in message:
                        for tool_call in message["tool_calls"]:
                            if "id" in tool_call:
                                original_id = tool_call["id"]
                                validated_id = _ensure_valid_tool_call_id(original_id)
                                if original_id != validated_id:
                                    tool_call["id"] = validated_id
                                    messages_updated = True
                                    logger.info(f"Fixed tool_call_id in assistant message: {original_id} -> {validated_id}")
                # If we fixed any IDs, save the session back to Redis
                if messages_updated:
                    await self._save_session(session_id, session)
                return session
            else:
                # Create new session
                session = {
                    "id": session_id,
                    "created_at": datetime.now().isoformat(),
                    "messages": [],
                    "metadata": {},
                }
                # Store in Redis
                await client.set(session_key, json.dumps(session))
                # Add to sessions list
                await client.sadd(self.sessions_list_key, session_id)
                return session
                
        except RedisError as e:
            logger.error(f"Redis error in get_session_messages: {e}")
            # Fallback to empty session on error
            return {
                "id": session_id,
                "created_at": datetime.now().isoformat(),
                "messages": [],
                "metadata": {},
            }

    async def _save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save session to Redis."""
        try:
            client = await self._get_redis()
            session_key = f"{self.session_prefix}{session_id}"
            await client.set(session_key, json.dumps(session))
        except RedisError as e:
            logger.error(f"Redis error in _save_session: {e}")

    async def update_session_metadata(
        self, session_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Update session metadata."""
        session = await self.get_session_messages(session_id)
        session["metadata"].update(metadata)
        await self._save_session(session_id, session)

    async def update_tool_selection(
        self, session_id: str, tool_selection: Dict[str, Dict[str, bool]]
    ) -> None:
        """Update tool selection for a session."""
        await self.update_session_metadata(session_id, {"tool_selection": tool_selection})
        logger.info(f"Updated tool selection for session {session_id}")

    async def get_tool_selection(self, session_id: str) -> Dict[str, Dict[str, bool]]:
        """Get tool selection for a session."""
        session = await self.get_session_messages(session_id)
        return session.get("metadata", {}).get("tool_selection", {})

    async def add_system_message(self, session_id: str, content: str) -> None:
        """Add a system message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "system",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        session["messages"].append(message)
        await self._save_session(session_id, session)

    async def add_user_message(self, session_id: str, content: str) -> None:
        """Add a user message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        session["messages"].append(message)
        await self._save_session(session_id, session)

    async def add_assistant_message(self, session_id: str, content: str, tool_calls: List[Dict[str, Any]] = None) -> None:
        """Add an assistant message to the session."""
        session = await self.get_session_messages(session_id)
        message = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if tool_calls:
            # Validate tool_call_ids in tool_calls
            validated_tool_calls = []
            for tool_call in tool_calls:
                validated_tool_call = tool_call.copy()
                if "id" in validated_tool_call:
                    validated_tool_call["id"] = _ensure_valid_tool_call_id(validated_tool_call["id"])
                validated_tool_calls.append(validated_tool_call)
            message["tool_calls"] = validated_tool_calls
        session["messages"].append(message)
        await self._save_session(session_id, session)
    
    async def add_assistant_message_with_tool_calls(self, session_id: str, tool_calls: List[Dict[str, Any]]) -> None:
        """Add an assistant message with tool_calls to the session."""
        session = await self.get_session_messages(session_id)
        # Validate tool_call_ids in tool_calls
        validated_tool_calls = []
        for tool_call in tool_calls:
            validated_tool_call = tool_call.copy()
            if "id" in validated_tool_call:
                validated_tool_call["id"] = _ensure_valid_tool_call_id(validated_tool_call["id"])
            validated_tool_calls.append(validated_tool_call)
        
        message = {
            "role": "assistant",
            "content": "",  # Tool call messages typically have empty content
            "tool_calls": validated_tool_calls,
            "timestamp": datetime.now().isoformat(),
        }
        session["messages"].append(message)
        await self._save_session(session_id, session)

    async def add_tool_message(
        self, session_id: str, content: str, tool_name: str, tool_call_id: str
    ) -> None:
        """Add a tool result message to the session."""
        session = await self.get_session_messages(session_id)
        # Ensure tool_call_id is within OpenAI's 40-character limit
        validated_tool_call_id = _ensure_valid_tool_call_id(tool_call_id)
        message = {
            "role": "tool",
            "content": content,
            "tool_name": tool_name,
            "tool_call_id": validated_tool_call_id,
            "timestamp": datetime.now().isoformat(),
        }
        session["messages"].append(message)
        await self._save_session(session_id, session)

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        try:
            client = await self._get_redis()
            session_ids = await client.smembers(self.sessions_list_key)
            
            sessions = []
            for session_id in session_ids:
                session_key = f"{self.session_prefix}{session_id}"
                session_data = await client.get(session_key)
                
                if session_data:
                    session = json.loads(session_data)
                    sessions.append({
                        "id": session_id,
                        "created_at": session.get("created_at", ""),
                        "message_count": len(session.get("messages", [])),
                        "metadata": session.get("metadata", {})
                    })
            
            # Sort by created_at (newest first)
            sessions.sort(key=lambda x: x["created_at"], reverse=True)
            return sessions
            
        except RedisError as e:
            logger.error(f"Redis error in list_sessions: {e}")
            return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            client = await self._get_redis()
            session_key = f"{self.session_prefix}{session_id}"
            
            # Delete from Redis
            deleted = await client.delete(session_key)
            
            # Remove from sessions list
            if deleted:
                await client.srem(self.sessions_list_key, session_id)
                return True
            
            return False
            
        except RedisError as e:
            logger.error(f"Redis error in delete_session: {e}")
            return False

    async def update_session_messages(
        self, session_id: str, messages: List[Dict[str, Any]]
    ) -> None:
        """Update/replace all messages for a session."""
        session = await self.get_session_messages(session_id)
        session["messages"] = messages
        await self._save_session(session_id, session)
