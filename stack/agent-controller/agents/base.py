from abc import ABC, abstractmethod
from typing import Dict, AsyncGenerator
from core.llm_client import LLMProxyClient
from core.session import SessionManager

class BaseAgent(ABC):
    def __init__(self):
        self.llm_client = LLMProxyClient()
        self.session_manager = SessionManager()
    
    @abstractmethod
    async def process(self, request: Dict) -> AsyncGenerator[Dict, None]:
        """Process user request and yield streaming responses"""
        pass
    
    def build_prompt(self, session: Dict, user_prompt: str) -> str:
        """Build prompt with context from session"""
        context_str = ""
        if session and session.get("context"):
            context_str = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in session["context"][-5:]  # Last 5 messages
            ])
        
        return f"""Previous conversation:
{context_str}

Current request: {user_prompt}

Please provide a helpful response."""