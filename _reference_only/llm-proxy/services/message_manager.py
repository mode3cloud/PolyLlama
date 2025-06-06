"""
Message Manager - Centralized management of chat messages and sessions
"""

import logging
import datetime
import uuid
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MessageManager:
    """
    Centralized manager for chat messages and sessions.
    Handles all persistence operations for chat functionality.
    """
    
    def __init__(self, neo4j_driver):
        """
        Initialize the message manager with a Neo4j driver.
        
        Args:
            neo4j_driver: Neo4j driver instance for database operations
        """
        self.driver = neo4j_driver
        self.chat_history_group_id = "_chat_history"
    
    async def create_session(self, model: str = None) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        Args:
            model: The model to use for this session
            
        Returns:
            Dict containing the session information
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    CREATE (s:ChatSession {
                        id: $id,
                        name: $name,
                        model: $model,
                        created_at: $timestamp,
                        updated_at: $timestamp,
                        group_id: $group_id
                    })
                    RETURN s
                    """,
                    {
                        "id": session_id,
                        "name": "New conversation",
                        "model": model,
                        "timestamp": timestamp,
                        "group_id": self.chat_history_group_id,
                    },
                )
                
                record = result.single()
                if not record:
                    raise Exception("Failed to create chat session")
                
                session_data = record["s"]
                
                return {
                    "id": session_data.get("id"),
                    "name": session_data.get("name"),
                    "model": session_data.get("model"),
                    "created_at": session_data.get("created_at"),
                    "updated_at": session_data.get("updated_at"),
                }
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise
    
    async def get_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all chat sessions.
        
        Returns:
            List of session dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (s:ChatSession {group_id: $group_id})
                    RETURN s
                    ORDER BY s.updated_at DESC
                    """,
                    {"group_id": self.chat_history_group_id},
                )
                
                sessions = []
                for record in result:
                    session_data = record["s"]
                    sessions.append({
                        "id": session_data.get("id"),
                        "name": session_data.get("name"),
                        "model": session_data.get("model"),
                        "created_at": session_data.get("created_at"),
                        "updated_at": session_data.get("updated_at"),
                    })
                
                return sessions
        except Exception as e:
            logger.error(f"Error getting chat sessions: {e}")
            raise
    
    async def get_session_messages(self, session_id: str) -> Dict[str, Any]:
        """
        Get all messages for a session.
        
        Args:
            session_id: The ID of the session to get messages for
            
        Returns:
            Dict containing session info and messages
        """
        try:
            with self.driver.session() as session:
                # First get the session info
                session_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id, group_id: $group_id})
                    RETURN s
                    """,
                    {"session_id": session_id, "group_id": self.chat_history_group_id},
                )
                
                session_record = session_result.single()
                if not session_record:
                    raise Exception(f"Session not found: {session_id}")
                
                session_data = session_record["s"]
                
                # Then get the messages
                message_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                    OPTIONAL MATCH (m)-[:HAS_ATTACHMENT]->(a:ChatAttachment)
                    WITH s, m, collect(a) as attachments
                    ORDER BY m.timestamp, CASE WHEN m.role = 'user' THEN 0 ELSE 1 END
                    RETURN m, attachments
                    """,
                    {"session_id": session_id},
                )
                
                messages = []
                for record in message_result:
                    message_data = record["m"]
                    attachment_data = record["attachments"]
                    
                    attachments = []
                    for attachment in attachment_data:
                        if attachment:
                            attachments.append({
                                "id": attachment.get("id"),
                                "name": attachment.get("name"),
                                "content_type": attachment.get("content_type"),
                                "file_path": attachment.get("file_path"),
                            })
                    
                    message = {
                        "id": message_data.get("id"),
                        "role": message_data.get("role"),
                        "content": message_data.get("content"),
                        "timestamp": message_data.get("timestamp"),
                        "attachments": attachments,
                    }
                    
                    # Handle tool_calls for assistant messages
                    if message_data.get("role") == "assistant" and message_data.get("tool_calls"):
                        import json
                        try:
                            tool_calls_json = message_data.get("tool_calls")
                            # Ensure we have a string to parse
                            if isinstance(tool_calls_json, str):
                                message["tool_calls"] = json.loads(tool_calls_json)
                                logger.info(f"Successfully parsed tool_calls JSON for message {message_data.get('id')}")
                            elif isinstance(tool_calls_json, list):
                                # Already a list, no need to parse
                                message["tool_calls"] = tool_calls_json
                                logger.info(f"Tool calls already in list format for message {message_data.get('id')}")
                            else:
                                logger.error(f"Unexpected tool_calls type: {type(tool_calls_json)}")
                        except Exception as e:
                            logger.error(f"Error parsing tool_calls JSON: {e}, content: {tool_calls_json[:100] if isinstance(tool_calls_json, str) else 'not a string'}")
                    
                    # Handle tool message properties
                    if message_data.get("role") == "tool":
                        # Make sure these properties are always included
                        message["name"] = message_data.get("name", "")
                        message["tool_call_id"] = message_data.get("tool_call_id", "")
                        logger.info(f"Processing tool message: name={message['name']}, tool_call_id={message['tool_call_id']}")
                    
                    messages.append(message)
                
                return {
                    "id": session_data.get("id"),
                    "name": session_data.get("name"),
                    "model": session_data.get("model"),
                    "created_at": session_data.get("created_at"),
                    "updated_at": session_data.get("updated_at"),
                    "messages": messages,
                }
        except Exception as e:
            logger.error(f"Error getting session messages: {e}")
            raise
    
    async def add_user_message(self, session_id: str, content: str, attachments: List[Dict[str, Any]] = None) -> str:
        """
        Add a user message to a session.
        
        Args:
            session_id: The ID of the session to add the message to
            content: The message content
            attachments: List of attachment dictionaries
            
        Returns:
            The ID of the created message
        """
        message_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        logger.info(f"[MessageManager] add_user_message: session_id={session_id}, message_id={message_id}, content={content[:100]}")
        
        try:
            with self.driver.session() as session:
                # Check if this exact message already exists to prevent duplicates
                check_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                    WHERE m.role = 'user' AND m.content = $content
                    RETURN m.id as id
                    ORDER BY m.timestamp DESC
                    LIMIT 1
                    """,
                    {
                        "session_id": session_id,
                        "content": content,
                    },
                )
                
                existing = check_result.single()
                if existing:
                    logger.info(f"[MessageManager] add_user_message: duplicate found, returning existing id={existing['id']}")
                    # Message already exists, return its ID
                    return existing["id"]
                
                # Store the user message
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id, group_id: $group_id})
                    CREATE (m:ChatMessage {
                        id: $message_id,
                        role: 'user',
                        content: $content,
                        timestamp: $timestamp
                    })
                    CREATE (s)-[:CONTAINS]->(m)
                    """,
                    {
                        "session_id": session_id,
                        "message_id": message_id,
                        "content": content,
                        "timestamp": timestamp,
                        "group_id": self.chat_history_group_id,
                    },
                )
                
                # Store file attachments if any
                if attachments:
                    for attachment in attachments:
                        session.run(
                            """
                            MATCH (m:ChatMessage {id: $message_id})
                            CREATE (a:ChatAttachment {
                                id: $attachment_id,
                                name: $name,
                                content_type: $content_type,
                                file_path: $file_path
                            })
                            CREATE (m)-[:HAS_ATTACHMENT]->(a)
                            """,
                            {
                                "message_id": message_id,
                                "attachment_id": attachment["id"],
                                "name": attachment["name"],
                                "content_type": attachment["content_type"],
                                "file_path": attachment["file_path"],
                            },
                        )
                        logger.info(f"[MessageManager] add_user_message: stored attachment id={attachment['id']}")
                
                # Update session timestamp
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    SET s.updated_at = $timestamp
                    """,
                    {"session_id": session_id, "timestamp": timestamp},
                )
                
                logger.info(f"[MessageManager] add_user_message: successfully stored user message id={message_id}")
                return message_id
        except Exception as e:
            logger.error(f"Error adding user message: {e}")
            raise
    
    async def add_assistant_message(self, session_id: str, content: str, tool_calls: Optional[str] = None) -> str:
        """
        Add an assistant message to a session, optionally including tool_calls as JSON.

        Args:
            session_id: The ID of the session to add the message to
            content: The message content
            tool_calls: (Optional) JSON string of tool_calls

        Returns:
            The ID of the created message
        """
        import json as _json
        message_id = str(uuid.uuid4())
        # Add a small delay to the timestamp to ensure it's after the user message
        timestamp = (datetime.datetime.now() + datetime.timedelta(seconds=1)).isoformat()
        logger.info(f"[MessageManager] add_assistant_message: session_id={session_id}, message_id={message_id}, content={content[:100]}, tool_calls={'yes' if tool_calls else 'no'}")

        try:
            with self.driver.session() as session:
                # Check if this exact message already exists to prevent duplicates
                check_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                    WHERE m.role = 'assistant' AND m.content = $content
                    RETURN m.id as id
                    ORDER BY m.timestamp DESC
                    LIMIT 1
                    """,
                    {
                        "session_id": session_id,
                        "content": content,
                    },
                )

                existing = check_result.single()
                if existing:
                    logger.info(f"[MessageManager] add_assistant_message: duplicate found, returning existing id={existing['id']}")
                    # Message already exists, return its ID
                    return existing["id"]

                # Store the assistant message, including tool_calls if present
                if tool_calls is not None:
                    session.run(
                        """
                        MATCH (s:ChatSession {id: $session_id})
                        CREATE (m:ChatMessage {
                            id: $message_id,
                            role: 'assistant',
                            content: $content,
                            tool_calls: $tool_calls,
                            timestamp: $timestamp
                        })
                        CREATE (s)-[:CONTAINS]->(m)
                        """,
                        {
                            "session_id": session_id,
                            "message_id": message_id,
                            "content": content,
                            "tool_calls": tool_calls,
                            "timestamp": timestamp,
                        },
                    )
                else:
                    session.run(
                        """
                        MATCH (s:ChatSession {id: $session_id})
                        CREATE (m:ChatMessage {
                            id: $message_id,
                            role: 'assistant',
                            content: $content,
                            timestamp: $timestamp
                        })
                        CREATE (s)-[:CONTAINS]->(m)
                        """,
                        {
                            "session_id": session_id,
                            "message_id": message_id,
                            "content": content,
                            "timestamp": timestamp,
                        },
                    )

                # Update session timestamp
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    SET s.updated_at = $timestamp
                    """,
                    {"session_id": session_id, "timestamp": timestamp},
                )

                logger.info(f"[MessageManager] add_assistant_message: successfully stored assistant message id={message_id}")
                return message_id
        except Exception as e:
            logger.error(f"Error adding assistant message: {e}")
            raise

    async def add_structured_assistant_message(self, session_id: str, message: dict) -> str:
        """
        Add a fully structured assistant message (including tool_calls and any other fields).

        Args:
            session_id: The ID of the session to add the message to
            message: The full assistant message dict (should include at least 'content', may include 'tool_calls', etc.)

        Returns:
            The ID of the created message
        """
        import json as _json
        message_id = str(uuid.uuid4())
        timestamp = (datetime.datetime.now() + datetime.timedelta(seconds=1)).isoformat()
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", None)
        # Store as JSON string for tool_calls if present
        tool_calls_json = _json.dumps(tool_calls) if tool_calls is not None else None

        try:
            with self.driver.session() as session:
                if tool_calls_json is not None:
                    session.run(
                        """
                        MATCH (s:ChatSession {id: $session_id})
                        CREATE (m:ChatMessage {
                            id: $message_id,
                            role: 'assistant',
                            content: $content,
                            tool_calls: $tool_calls,
                            timestamp: $timestamp
                        })
                        CREATE (s)-[:CONTAINS]->(m)
                        """,
                        {
                            "session_id": session_id,
                            "message_id": message_id,
                            "content": content,
                            "tool_calls": tool_calls_json,
                            "timestamp": timestamp,
                        },
                    )
                else:
                    session.run(
                        """
                        MATCH (s:ChatSession {id: $session_id})
                        CREATE (m:ChatMessage {
                            id: $message_id,
                            role: 'assistant',
                            content: $content,
                            timestamp: $timestamp
                        })
                        CREATE (s)-[:CONTAINS]->(m)
                        """,
                        {
                            "session_id": session_id,
                            "message_id": message_id,
                            "content": content,
                            "timestamp": timestamp,
                        },
                    )
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    SET s.updated_at = $timestamp
                    """,
                    {"session_id": session_id, "timestamp": timestamp},
                )
                return message_id
        except Exception as e:
            logger.error(f"Error adding structured assistant message: {e}")
            raise

    async def add_tool_message(
        self,
        session_id: str,
        content: str,
        name: str = "",
        tool_call_id: str = "",
        index: int = 0,
        timestamp: float = None,
    ) -> str:
        """
        Add a tool message to a session.

        Args:
            session_id: The ID of the session to add the message to
            content: The message content (tool result or error)
            name: The name of the tool
            tool_call_id: The tool call ID (if any)
            index: The index/order of the message in the session
            timestamp: The timestamp (float, seconds since epoch). If None, use now.

        Returns:
            The ID of the created message
        """
        message_id = str(uuid.uuid4())
        if timestamp is None:
            timestamp_str = datetime.datetime.now().isoformat()
        else:
            # Accept both float (epoch) and iso string
            if isinstance(timestamp, (float, int)):
                timestamp_str = datetime.datetime.fromtimestamp(timestamp).isoformat()
            else:
                timestamp_str = str(timestamp)
        logger.info(f"[MessageManager] add_tool_message: session_id={session_id}, message_id={message_id}, name={name}, tool_call_id={tool_call_id}, content={content[:100]}")
        try:
            with self.driver.session() as session:
                # Store the tool message
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    CREATE (m:ChatMessage {
                        id: $message_id,
                        role: 'tool',
                        content: $content,
                        name: $name,
                        tool_call_id: $tool_call_id,
                        index: $index,
                        timestamp: $timestamp
                    })
                    CREATE (s)-[:CONTAINS]->(m)
                    """,
                    {
                        "session_id": session_id,
                        "message_id": message_id,
                        "content": content,
                        "name": name,
                        "tool_call_id": tool_call_id,
                        "index": index,
                        "timestamp": timestamp_str,
                    },
                )
                # Update session timestamp
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    SET s.updated_at = $timestamp
                    """,
                    {"session_id": session_id, "timestamp": timestamp_str},
                )
                logger.info(f"[MessageManager] add_tool_message: successfully stored tool message id={message_id}")
                return message_id
        except Exception as e:
            logger.error(f"Error adding tool message: {e}")
            raise
    
    async def update_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update session properties.
        
        Args:
            session_id: The ID of the session to update
            **kwargs: Key-value pairs of properties to update
            
        Returns:
            Dict containing the updated session information
        """
        try:
            # Add updated_at timestamp
            kwargs["updated_at"] = datetime.datetime.now().isoformat()
            
            # Build the Cypher query dynamically based on what's being updated
            set_clause = ", ".join([f"s.{key} = ${key}" for key in kwargs.keys()])
            query = f"""
            MATCH (s:ChatSession {{id: $session_id, group_id: $group_id}})
            SET {set_clause}
            RETURN s
            """
            
            # Add session_id to the parameters
            params = {
                **kwargs,
                "session_id": session_id,
                "group_id": self.chat_history_group_id,
            }
            
            with self.driver.session() as session:
                result = session.run(query, params)
                
                record = result.single()
                if not record:
                    raise Exception(f"Session not found: {session_id}")
                
                session_data = record["s"]
                
                return {
                    "id": session_data.get("id"),
                    "name": session_data.get("name"),
                    "model": session_data.get("model"),
                    "updated_at": session_data.get("updated_at"),
                }
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            raise
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages and attachments.
        
        Args:
            session_id: The ID of the session to delete
            
        Returns:
            True if successful
        """
        try:
            with self.driver.session() as session:
                # First, get the session to confirm it exists
                session_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id, group_id: $group_id})
                    RETURN s
                    """,
                    {"session_id": session_id, "group_id": self.chat_history_group_id},
                )
                
                session_record = session_result.single()
                if not session_record:
                    raise Exception(f"Session not found: {session_id}")
                
                # Delete all attachments related to messages in this session
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)-[:HAS_ATTACHMENT]->(a:ChatAttachment)
                    DETACH DELETE a
                    """,
                    {"session_id": session_id},
                )
                
                # Delete all messages in this session
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                    DETACH DELETE m
                    """,
                    {"session_id": session_id},
                )
                
                # Finally, delete the session itself
                session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})
                    DETACH DELETE s
                    """,
                    {"session_id": session_id},
                )
                
                return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise
    
    async def truncate_session(self, session_id: str, index: int) -> bool:
        """
        Delete all messages after a specific index.
        
        Args:
            session_id: The ID of the session to truncate
            index: The index after which to delete messages
            
        Returns:
            True if successful
        """
        try:
            timestamp = datetime.datetime.now().isoformat()
            
            with self.driver.session() as session:
                # Get all messages for this session
                messages_result = session.run(
                    """
                    MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                    RETURN m
                    ORDER BY m.timestamp
                    """,
                    {"session_id": session_id}
                )
                
                messages = list(messages_result)
                
                # If index is valid, delete all messages after that index
                if index >= 0 and index < len(messages):
                    # Get the IDs of messages to delete
                    message_ids_to_delete = [
                        record["m"]["id"] for record in messages[index + 1:]
                    ]
                    
                    if message_ids_to_delete:
                        # Delete attachments for these messages
                        session.run(
                            """
                            MATCH (m:ChatMessage)-[:HAS_ATTACHMENT]->(a:ChatAttachment)
                            WHERE m.id IN $message_ids
                            DETACH DELETE a
                            """,
                            {"message_ids": message_ids_to_delete}
                        )
                        
                        # Delete the messages
                        session.run(
                            """
                            MATCH (s:ChatSession {id: $session_id})-[:CONTAINS]->(m:ChatMessage)
                            WHERE m.id IN $message_ids
                            DETACH DELETE m
                            """,
                            {"session_id": session_id, "message_ids": message_ids_to_delete}
                        )
                        
                        # Update session timestamp
                        session.run(
                            """
                            MATCH (s:ChatSession {id: $session_id})
                            SET s.updated_at = $timestamp
                            RETURN s
                            """,
                            {"session_id": session_id, "timestamp": timestamp}
                        )
                
                return True
        except Exception as e:
            logger.error(f"Error truncating session: {e}")
            raise
