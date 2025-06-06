"""
Session management API endpoints for LLM Proxy Service

Handles chat session creation, retrieval, updates, and deletion.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

sessions_router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""
    model: Optional[str] = None
    name: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    """Request model for updating a session."""
    name: Optional[str] = None
    model: Optional[str] = None
    assistant_message: Optional[str] = None
    truncate_after_index: Optional[int] = None


class SessionResponse(BaseModel):
    """Response model for session data."""
    session_id: str
    name: str
    model: str
    created_at: str
    updated_at: str
    message_count: int


class SessionMessagesResponse(BaseModel):
    """Response model for session with messages."""
    session_id: str
    name: str
    model: str
    created_at: str
    updated_at: str
    messages: List[Dict[str, Any]]


@sessions_router.get("", response_model=List[SessionResponse])
async def get_sessions(request: Request):
    """Get all chat sessions."""
    try:
        message_manager = request.app.state.message_manager
        sessions = await message_manager.get_sessions()
        
        return [
            SessionResponse(
                session_id=session["session_id"],
                name=session["name"],
                model=session["model"],
                created_at=session["created_at"],
                updated_at=session["updated_at"],
                message_count=session.get("message_count", 0)
            )
            for session in sessions
        ]
        
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")


@sessions_router.post("", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest, req: Request):
    """Create a new chat session."""
    try:
        message_manager = req.app.state.message_manager
        
        session_data = await message_manager.create_session(request.model, request.name)
        
        return SessionResponse(
            session_id=session_data["session_id"],
            name=session_data["name"],
            model=session_data["model"],
            created_at=session_data["created_at"],
            updated_at=session_data["updated_at"],
            message_count=0
        )
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@sessions_router.get("/{session_id}", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str, request: Request):
    """Get a session with all its messages."""
    try:
        message_manager = request.app.state.message_manager
        
        session_data = await message_manager.get_session_messages(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionMessagesResponse(
            session_id=session_data["session_id"],
            name=session_data["name"],
            model=session_data["model"],
            created_at=session_data["created_at"],
            updated_at=session_data["updated_at"],
            messages=session_data["messages"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session messages: {str(e)}")


@sessions_router.put("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest, req: Request):
    """Update a chat session."""
    try:
        message_manager = req.app.state.message_manager
        
        # Handle different update types
        if request.assistant_message is not None:
            # Add assistant message
            message_id = await message_manager.add_assistant_message(
                session_id, request.assistant_message
            )
            return {"success": True, "message_id": message_id}
        
        elif request.truncate_after_index is not None:
            # Truncate messages
            success = await message_manager.truncate_session(
                session_id, request.truncate_after_index
            )
            return {"success": success, "truncated_at": request.truncate_after_index}
        
        else:
            # Regular session update
            update_data = {}
            if request.name is not None:
                update_data["name"] = request.name
            if request.model is not None:
                update_data["model"] = request.model
            
            if not update_data:
                raise HTTPException(status_code=400, detail="No update data provided")
            
            session_data = await message_manager.update_session(session_id, **update_data)
            
            return SessionResponse(
                session_id=session_data["session_id"],
                name=session_data["name"],
                model=session_data["model"],
                created_at=session_data["created_at"],
                updated_at=session_data["updated_at"],
                message_count=session_data.get("message_count", 0)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")


@sessions_router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete a chat session and all its messages."""
    try:
        message_manager = request.app.state.message_manager
        
        success = await message_manager.delete_session(session_id)
        
        if success:
            return {"success": True, "message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")