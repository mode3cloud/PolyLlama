from typing import Dict, AsyncGenerator
import structlog
from .base import BaseAgent

logger = structlog.get_logger()

class ChatAgent(BaseAgent):
    async def process(self, request: Dict) -> AsyncGenerator[Dict, None]:
        """Process chat request with streaming response"""
        session_id = request.get("sessionId")
        user_prompt = request.get("userPrompt", "")
        
        # Load or create session
        session = await self.session_manager.load_session(session_id) if session_id else None
        if not session:
            session_id = await self.session_manager.create_session("chat")
            session = await self.session_manager.load_session(session_id)
        
        # Add user message to context
        await self.session_manager.add_to_context(session_id, {
            "role": "user",
            "content": user_prompt
        })
        
        # Build prompt with context
        prompt = self.build_prompt(session, user_prompt)
        
        # Stream thinking step
        yield {
            "type": "thinking",
            "content": "Processing your request..."
        }
        
        # Stream LLM response
        response_content = ""
        try:
            logger.info("starting_llm_stream", prompt_preview=prompt[:100])
            chunk_count = 0
            async for chunk in self.llm_client.stream(prompt):
                chunk_count += 1
                logger.debug("received_chunk", chunk_num=chunk_count, content=chunk)
                response_content += chunk
                yield {
                    "type": "llm_output", 
                    "content": chunk
                }
            logger.info("llm_stream_complete", total_chunks=chunk_count)
        except Exception as e:
            logger.error("llm_error", error=str(e))
            yield {
                "type": "error",
                "content": f"LLM Error: {str(e)}"
            }
        
        # Add assistant response to context
        await self.session_manager.add_to_context(session_id, {
            "role": "assistant",
            "content": response_content
        })
        
        # Final completion message
        yield {
            "type": "complete",
            "sessionId": session_id
        }