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
from tools import get_global_registry
from tools.email import EmailSearchTool, EmailSummarizeTool, EmailDraftTool
from tools.search import WebSearchTool, WebScrapeTool, NewsSearchTool
from tools.data import DatabaseQueryTool, DataAnalysisTool, FileDataTool

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

# Initialize tool registry and register tools
tool_registry = get_global_registry()

# Register email tools
tool_registry.register(EmailSearchTool(), category="email")
tool_registry.register(EmailSummarizeTool(), category="email")
tool_registry.register(EmailDraftTool(), category="email")

# Register search tools
tool_registry.register(WebSearchTool(), category="search")
tool_registry.register(WebScrapeTool(), category="search")
tool_registry.register(NewsSearchTool(), category="search")

# Register data tools
tool_registry.register(DatabaseQueryTool(), category="data")
tool_registry.register(DataAnalysisTool(), category="data")
tool_registry.register(FileDataTool(), category="data")

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

@app.get("/tools")
async def list_tools(category: Optional[str] = None):
    """List all available tools"""
    tools = tool_registry.list_tools(category)
    return {
        "total": len(tools),
        "tools": tools,
        "categories": tool_registry.get_categories()
    }

@app.get("/tools/{tool_name}")
async def get_tool(tool_name: str):
    """Get details for a specific tool"""
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return tool.get_schema()

@app.get("/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str):
    """Get schema for a specific tool"""
    schema = tool_registry.get_tool_schema(tool_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return schema

@app.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, args: dict):
    """Execute a tool with given arguments"""
    try:
        result = await tool_registry.execute_tool(tool_name, args)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Tool execution failed", tool=tool_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools/stats")
async def get_tool_stats(tool_name: Optional[str] = None):
    """Get usage statistics for tools"""
    stats = tool_registry.get_usage_stats(tool_name)
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11436)