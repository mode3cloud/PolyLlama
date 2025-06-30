#!/usr/bin/env python3
"""
Graphiti MCP Server

A Model Context Protocol (MCP) server that provides knowledge graph ingestion capabilities
using the Graphiti library. This server provides the add_episodes tool for ingesting
content into a knowledge graph from various sources.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        TextContent,
        Tool,
    )
except ImportError:
    print("Error: MCP SDK not found. Please install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("graphiti-mcp-server")

# Server instance
server = Server("graphiti-mcp-server")

# Simulated Graphiti client (placeholder for actual implementation)
class GraphitiClient:
    """
    Placeholder Graphiti client for knowledge graph operations.
    
    In a real implementation, this would connect to an actual Graphiti instance
    and perform knowledge graph operations. For now, it provides a compatible
    interface for testing and development.
    """
    
    def __init__(self):
        self.episodes_store = []  # Simple in-memory store for development
        logger.info("Graphiti client initialized (placeholder implementation)")
    
    async def add_episode(self, source_type: str, content: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Add an episode to the knowledge graph.
        
        Args:
            source_type: Type of source (email, meeting_notes, document, etc.)
            content: The text content to process
            metadata: Optional metadata about the episode
            
        Returns:
            Dictionary with episode information and processing results
        """
        try:
            episode_id = f"ep_{len(self.episodes_store) + 1}_{int(datetime.now().timestamp())}"
            
            episode = {
                "id": episode_id,
                "source_type": source_type,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat(),
                "processed": True,
                "entities_extracted": len(content.split()) // 10,  # Simulate entity extraction
                "relationships_created": len(content.split()) // 20,  # Simulate relationship creation
            }
            
            # Store episode (in real implementation, this would be stored in Graphiti)
            self.episodes_store.append(episode)
            
            logger.info(f"Added episode {episode_id} from source type {source_type}")
            
            # Simulate processing results
            return {
                "success": True,
                "episode_id": episode_id,
                "entities_extracted": episode["entities_extracted"],
                "relationships_created": episode["relationships_created"],
                "processed_at": episode["timestamp"],
                "message": f"Successfully processed {source_type} content with {len(content)} characters"
            }
            
        except Exception as e:
            logger.error(f"Error adding episode: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to process {source_type} content"
            }
    
    async def get_episodes(self) -> List[Dict[str, Any]]:
        """Get all episodes (for testing purposes)."""
        return self.episodes_store
    
    async def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific episode by ID."""
        for episode in self.episodes_store:
            if episode["id"] == episode_id:
                return episode
        return None

# Initialize Graphiti client
graphiti_client = GraphitiClient()

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools provided by this MCP server."""
    return [
        Tool(
            name="add_episodes",
            description="Add content episodes to the Graphiti knowledge graph for processing and analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_type": {
                        "type": "string",
                        "description": "Type of content source (email, meeting_notes, document, chat, web_content, file_upload)",
                        "enum": ["email", "meeting_notes", "document", "chat", "web_content", "file_upload"]
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to be processed and added to the knowledge graph"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata about the content (author, timestamp, tags, etc.)",
                        "properties": {
                            "title": {"type": "string", "description": "Content title or subject"},
                            "author": {"type": "string", "description": "Content author or creator"},
                            "timestamp": {"type": "string", "description": "Content creation timestamp"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Content tags or categories"},
                            "source_url": {"type": "string", "description": "Source URL if applicable"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Content priority level"}
                        },
                        "additionalProperties": True
                    }
                },
                "required": ["source_type", "content"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_episodes",
            description="Retrieve all episodes from the knowledge graph (for testing and debugging)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of episodes to return",
                        "default": 100
                    }
                },
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool execution requests."""
    
    if name == "add_episodes":
        # Extract required parameters
        source_type = arguments.get("source_type")
        content = arguments.get("content")
        metadata = arguments.get("metadata", {})
        
        # Validate required parameters
        if not source_type:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Missing required parameter: source_type"
                })
            )]
        
        if not content:
            return [TextContent(
                type="text", 
                text=json.dumps({
                    "success": False,
                    "error": "Missing required parameter: content"
                })
            )]
        
        # Add episode to knowledge graph
        result = await graphiti_client.add_episode(source_type, content, metadata)
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    elif name == "get_episodes":
        # Retrieve episodes (mainly for testing)
        limit = arguments.get("limit", 100)
        episodes = await graphiti_client.get_episodes()
        
        # Apply limit
        limited_episodes = episodes[-limit:] if len(episodes) > limit else episodes
        
        result = {
            "success": True,
            "episodes": limited_episodes,
            "total_count": len(episodes),
            "returned_count": len(limited_episodes)
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Unknown tool: {name}"
            })
        )]

async def main():
    """Main entry point for the Graphiti MCP server."""
    logger.info("Starting Graphiti MCP Server...")
    
    try:
        # Run server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)