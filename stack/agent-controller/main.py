import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import structlog

from agents.chat import ChatAgent
from config import settings

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(title="PolyLlama Agent Controller", version="1.0.0")

# Add CORS middleware for internal service communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Internal only, so allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRequest(BaseModel):
    userPrompt: str
    sessionId: Optional[str] = None
    model: Optional[str] = None

# Initialize agents
chat_agent = ChatAgent()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "agent-controller"}

@app.post("/agent/chat")
async def agent_chat(request: AgentRequest):
    """Chat agent endpoint with streaming response"""
    try:
        async def generate():
            async for chunk in chat_agent.process(request.dict()):
                yield f"data: {json.dumps(chunk)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        logger.error("Error in agent chat", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/status")
async def agent_status():
    """Get agent controller status"""
    return {
        "status": "running",
        "llm_proxy_url": settings.llm_proxy_url,
        "available_agents": ["chat"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11436)