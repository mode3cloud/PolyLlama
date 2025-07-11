"""
Session management API endpoints for LLM Proxy Service

Handles chat session persistence and retrieval.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

sessions_router = APIRouter()


class SessionInfo(BaseModel):
    """Session information model."""
    id: str
    created_at: str
    message_count: int


class SessionListResponse(BaseModel):
    """Response model for session listing."""
    sessions: List[SessionInfo]


class SessionResponse(BaseModel):
    """Response model for session details."""
    id: str
    created_at: str
    messages: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateSessionRequest(BaseModel):
    """Request model for updating session messages."""
    messages: List[Dict[str, Any]]


class ToolSelectionRequest(BaseModel):
    """Request model for updating tool selection."""
    tool_selection: Dict[str, Dict[str, bool]]


class ToolSelectionResponse(BaseModel):
    """Response model for tool selection."""
    tool_selection: Dict[str, Dict[str, bool]]


@sessions_router.get("", response_model=SessionListResponse)
async def list_sessions(request: Request):
    """List all chat sessions."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            return SessionListResponse(sessions=[])
        
        sessions = await message_manager.list_sessions()
        
        session_infos = [
            SessionInfo(**session)
            for session in sessions
        ]
        
        return SessionListResponse(sessions=session_infos)
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@sessions_router.get("/{session_id}", response_model=SessionResponse, response_model_exclude_unset=False, response_model_exclude_defaults=False)
async def get_session(session_id: str, request: Request):
    """Get a specific chat session."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = await message_manager.get_session_messages(session_id)
        
        logger.info(f"Session data for {session_id}: {session_data.keys()}")
        logger.info(f"Metadata: {session_data.get('metadata', {})}")
        
        # Ensure metadata is always present
        metadata = session_data.get("metadata", {})
        
        return SessionResponse(
            id=session_data["id"],
            created_at=session_data["created_at"],
            messages=session_data["messages"],
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@sessions_router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete a chat session."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = await message_manager.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@sessions_router.put("/{session_id}")
async def update_session(session_id: str, update_request: UpdateSessionRequest, request: Request):
    """Update messages for a chat session."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            raise HTTPException(status_code=404, detail="Message manager not found")
        
        # Update the session messages
        await message_manager.update_session_messages(session_id, update_request.messages)
        
        return {"message": "Session updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")


@sessions_router.get("/{session_id}/tool-selection", response_model=ToolSelectionResponse)
async def get_session_tool_selection(session_id: str, request: Request):
    """Get tool selection for a chat session."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            raise HTTPException(status_code=404, detail="Message manager not found")
        
        # Ensure session exists (creates it if it doesn't exist)
        await message_manager.get_session_messages(session_id)
        
        tool_selection = await message_manager.get_tool_selection(session_id)
        
        return ToolSelectionResponse(tool_selection=tool_selection)
        
    except Exception as e:
        logger.error(f"Error getting tool selection for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tool selection: {str(e)}")


@sessions_router.put("/{session_id}/tool-selection")
async def update_session_tool_selection(session_id: str, tool_request: ToolSelectionRequest, request: Request):
    """Update tool selection for a chat session."""
    try:
        message_manager = request.app.state.message_manager
        
        if not message_manager:
            raise HTTPException(status_code=404, detail="Message manager not found")
        
        # Ensure session exists before updating tool selection
        # This will create the session if it doesn't exist
        await message_manager.get_session_messages(session_id)
        
        await message_manager.update_tool_selection(session_id, tool_request.tool_selection)
        
        return {"message": "Tool selection updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating tool selection for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update tool selection: {str(e)}")