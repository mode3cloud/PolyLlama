#!/usr/bin/env python3
"""Test Redis persistence for the message manager."""

import asyncio
import sys
import os
from pathlib import Path
import pytest

# Add llm-proxy directory to path
llm_proxy_path = Path(__file__).parent.parent / "stack" / "llm-proxy"
sys.path.insert(0, str(llm_proxy_path))

from services.message_manager import MessageManager


@pytest.mark.asyncio
async def test_redis_persistence():
    """Test that messages persist across message manager instances."""
    
    print("🔧 Testing Redis persistence...")
    
    # Test with Redis URL from environment or default
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    print(f"📍 Using Redis URL: {redis_url}")
    
    # First instance - create session and add messages
    print("\n📝 Creating first message manager instance...")
    manager1 = MessageManager(redis_url=redis_url)
    
    session_id = "test-persistence-session"
    
    # Add some messages
    await manager1.add_user_message(session_id, "Hello, this is a test message")
    await manager1.add_assistant_message(session_id, "Hello! I received your test message.")
    await manager1.add_user_message(session_id, "Can you remember this conversation?")
    await manager1.add_assistant_message(
        session_id, 
        "Yes, I can access our conversation history through Redis persistence."
    )
    
    # Update metadata
    await manager1.update_session_metadata(session_id, {
        "test_key": "test_value",
        "timestamp": "2025-01-03T10:00:00"
    })
    
    # Get session data
    session1 = await manager1.get_session_messages(session_id)
    print(f"✅ Added {len(session1['messages'])} messages to session")
    print(f"✅ Session metadata: {session1['metadata']}")
    
    # List sessions
    sessions1 = await manager1.list_sessions()
    print(f"✅ Total sessions: {len(sessions1)}")
    
    # Close first instance
    await manager1.close()
    print("🔌 Closed first message manager instance")
    
    # Second instance - verify persistence
    print("\n📝 Creating second message manager instance...")
    manager2 = MessageManager(redis_url=redis_url)
    
    # Get the same session
    session2 = await manager2.get_session_messages(session_id)
    
    # Verify data persisted
    print("\n🔍 Verifying persistence...")
    
    assert len(session2['messages']) == len(session1['messages']), \
        f"Message count mismatch: {len(session2['messages'])} vs {len(session1['messages'])}"
    print(f"✅ Message count matches: {len(session2['messages'])}")
    
    # Verify message content
    for i, (msg1, msg2) in enumerate(zip(session1['messages'], session2['messages'])):
        assert msg1['content'] == msg2['content'] and msg1['role'] == msg2['role'], \
            f"Message {i+1} mismatch"
        print(f"✅ Message {i+1} matches: {msg2['role']}: {msg2['content'][:50]}...")
    
    # Verify metadata
    assert session2['metadata'] == session1['metadata'], "Metadata mismatch"
    print(f"✅ Metadata matches: {session2['metadata']}")
    
    # List sessions from second instance
    sessions2 = await manager2.list_sessions()
    found_session = any(s['id'] == session_id for s in sessions2)
    assert found_session, "Session not found in list from second instance"
    print(f"✅ Session found in list from second instance")
    
    # Cleanup - delete test session
    deleted = await manager2.delete_session(session_id)
    if deleted:
        print(f"🧹 Cleaned up test session")
    
    await manager2.close()
    
    print("\n✅ Redis persistence test passed!")


if __name__ == "__main__":
    asyncio.run(test_redis_persistence())