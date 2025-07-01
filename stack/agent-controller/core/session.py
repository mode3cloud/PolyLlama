import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import redis.asyncio as redis
from config import settings

class SessionManager:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url)
    
    async def create_session(self, agent_type: str = "chat") -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "agent_type": agent_type,
            "context": [],
            "tools_used": [],
            "state": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        await self.redis.set(
            f"session:{session_id}",
            json.dumps(session_data),
            ex=3600  # 1 hour expiry
        )
        return session_id
    
    async def load_session(self, session_id: str) -> Optional[Dict]:
        """Load session data by ID"""
        data = await self.redis.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return None
    
    async def save_session(self, session_data: Dict) -> None:
        """Save session data"""
        session_data["updated_at"] = datetime.utcnow().isoformat()
        await self.redis.set(
            f"session:{session_data['session_id']}",
            json.dumps(session_data),
            ex=3600
        )
    
    async def add_to_context(self, session_id: str, message: Dict) -> None:
        """Add message to session context"""
        session = await self.load_session(session_id)
        if session:
            session["context"].append(message)
            await self.save_session(session)