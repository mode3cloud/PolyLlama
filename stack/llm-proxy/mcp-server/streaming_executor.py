"""
Streaming Tool Executor for MCP - Handles long-running tools with progress updates
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of events in a tool execution stream."""
    START = "start"
    PROGRESS = "progress"
    DATA = "data"
    LOG = "log"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class StreamEvent:
    """An event in the tool execution stream."""
    type: StreamEventType
    timestamp: float
    data: Any
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'type': self.type.value,
            'timestamp': self.timestamp,
            'data': self.data,
            'metadata': self.metadata or {}
        }
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


class StreamingToolExecutor:
    """Execute MCP tools with streaming response support."""
    
    def __init__(self, bridge):
        self.bridge = bridge
        self.active_executions = {}  # Track active tool executions
        self.execution_logs = {}  # Store execution logs
        
    async def execute_tool_streaming(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        execution_id: Optional[str] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a tool with streaming progress updates."""
        if execution_id is None:
            execution_id = f"{tool_name}_{int(time.time() * 1000)}"
        
        # Store execution info
        self.active_executions[execution_id] = {
            'tool_name': tool_name,
            'arguments': arguments,
            'start_time': time.time(),
            'status': 'running'
        }
        
        try:
            # Send start event
            yield StreamEvent(
                type=StreamEventType.START,
                timestamp=time.time(),
                data={
                    'execution_id': execution_id,
                    'tool_name': tool_name,
                    'arguments': arguments
                }
            )
            
            # Create task for tool execution
            task = asyncio.create_task(
                self._execute_with_monitoring(tool_name, arguments, execution_id)
            )
            
            # Stream progress while task is running
            while not task.done():
                # Check for any intermediate results or logs
                if execution_id in self.execution_logs:
                    for log in self.execution_logs[execution_id]:
                        yield StreamEvent(
                            type=StreamEventType.LOG,
                            timestamp=time.time(),
                            data=log
                        )
                    # Clear processed logs
                    self.execution_logs[execution_id] = []
                
                # Send progress heartbeat
                elapsed = time.time() - self.active_executions[execution_id]['start_time']
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    timestamp=time.time(),
                    data={
                        'execution_id': execution_id,
                        'elapsed_seconds': elapsed,
                        'message': f"Tool {tool_name} executing... ({elapsed:.1f}s)"
                    }
                )
                
                # Wait before next update
                await asyncio.sleep(0.5)
            
            # Get final result
            try:
                result = await task
                
                # Send result data
                yield StreamEvent(
                    type=StreamEventType.DATA,
                    timestamp=time.time(),
                    data=result
                )
                
                # Send completion event
                yield StreamEvent(
                    type=StreamEventType.COMPLETE,
                    timestamp=time.time(),
                    data={
                        'execution_id': execution_id,
                        'duration_seconds': time.time() - self.active_executions[execution_id]['start_time'],
                        'status': 'success'
                    }
                )
                
                self.active_executions[execution_id]['status'] = 'completed'
                
            except Exception as e:
                # Send error event
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    timestamp=time.time(),
                    data={
                        'execution_id': execution_id,
                        'error': str(e),
                        'tool_name': tool_name
                    }
                )
                
                self.active_executions[execution_id]['status'] = 'failed'
                raise
                
        finally:
            # Cleanup
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
            if execution_id in self.execution_logs:
                del self.execution_logs[execution_id]
    
    async def _execute_with_monitoring(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        execution_id: str
    ) -> Any:
        """Execute tool with monitoring and logging."""
        # Initialize log storage
        self.execution_logs[execution_id] = []
        
        try:
            # Add logging wrapper if tool supports it
            if self._supports_streaming(tool_name):
                # For tools that support streaming, capture intermediate results
                return await self._execute_streaming_tool(tool_name, arguments, execution_id)
            else:
                # For regular tools, just execute
                return await self.bridge.call_tool(tool_name, arguments)
                
        except Exception as e:
            # Log error
            self.execution_logs[execution_id].append({
                'level': 'error',
                'message': str(e)
            })
            raise
    
    def _supports_streaming(self, tool_name: str) -> bool:
        """Check if a tool supports streaming execution."""
        # List of tools known to support streaming
        streaming_tools = [
            'github__search_repositories',
            'github__search_code',
            'github__get_file_contents',
            'web_search',
            'fetch_url',
            'personal-ai__chat'
        ]
        
        # Check if tool name matches any streaming tool
        for streaming_tool in streaming_tools:
            if streaming_tool in tool_name:
                return True
        
        return False
    
    async def _execute_streaming_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        execution_id: str
    ) -> Any:
        """Execute a tool that supports streaming with progress capture."""
        # This would integrate with tools that can provide progress updates
        # For now, we'll simulate with regular execution
        
        # Log start
        self.execution_logs[execution_id].append({
            'level': 'info',
            'message': f'Starting streaming execution of {tool_name}'
        })
        
        # Execute tool
        result = await self.bridge.call_tool(tool_name, arguments)
        
        # Log completion
        self.execution_logs[execution_id].append({
            'level': 'info',
            'message': f'Completed execution of {tool_name}'
        })
        
        return result
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active tool execution."""
        if execution_id in self.active_executions:
            # In a real implementation, this would cancel the actual task
            self.active_executions[execution_id]['status'] = 'cancelled'
            return True
        return False
    
    def get_active_executions(self) -> Dict[str, Any]:
        """Get information about all active executions."""
        return {
            execution_id: {
                'tool_name': info['tool_name'],
                'status': info['status'],
                'elapsed_seconds': time.time() - info['start_time']
            }
            for execution_id, info in self.active_executions.items()
        }


class BatchToolExecutor:
    """Execute multiple tools in parallel with progress tracking."""
    
    def __init__(self, executor: StreamingToolExecutor):
        self.executor = executor
        
    async def execute_batch(
        self,
        tool_calls: list[Dict[str, Any]]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute multiple tools in parallel with streaming updates."""
        batch_id = f"batch_{int(time.time() * 1000)}"
        start_time = time.time()
        
        # Send batch start event
        yield StreamEvent(
            type=StreamEventType.START,
            timestamp=time.time(),
            data={
                'batch_id': batch_id,
                'tool_count': len(tool_calls)
            }
        )
        
        # Create tasks for all tools
        tasks = []
        for i, tool_call in enumerate(tool_calls):
            execution_id = f"{batch_id}_{i}"
            task = asyncio.create_task(
                self._collect_tool_results(
                    tool_call['name'],
                    tool_call.get('arguments', {}),
                    execution_id
                )
            )
            tasks.append((execution_id, tool_call['name'], task))
        
        # Track completion
        completed = 0
        results = {}
        
        # Process results as they complete
        while tasks:
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                [task for _, _, task in tasks],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Process completed tasks
            for task in done:
                # Find which tool this was
                for execution_id, tool_name, t in tasks:
                    if t == task:
                        try:
                            result = await task
                            results[execution_id] = result
                            completed += 1
                            
                            # Send progress update
                            yield StreamEvent(
                                type=StreamEventType.PROGRESS,
                                timestamp=time.time(),
                                data={
                                    'batch_id': batch_id,
                                    'completed': completed,
                                    'total': len(tool_calls),
                                    'tool_name': tool_name,
                                    'execution_id': execution_id
                                }
                            )
                            
                        except Exception as e:
                            # Send error event for this tool
                            yield StreamEvent(
                                type=StreamEventType.ERROR,
                                timestamp=time.time(),
                                data={
                                    'batch_id': batch_id,
                                    'execution_id': execution_id,
                                    'tool_name': tool_name,
                                    'error': str(e)
                                }
                            )
                        
                        # Remove from tasks list
                        tasks = [(eid, tn, tsk) for eid, tn, tsk in tasks if tsk != task]
                        break
        
        # Send batch results
        yield StreamEvent(
            type=StreamEventType.DATA,
            timestamp=time.time(),
            data={
                'batch_id': batch_id,
                'results': results
            }
        )
        
        # Send batch completion
        yield StreamEvent(
            type=StreamEventType.COMPLETE,
            timestamp=time.time(),
            data={
                'batch_id': batch_id,
                'duration_seconds': time.time() - start_time,
                'total_tools': len(tool_calls),
                'successful': len(results)
            }
        )
    
    async def _collect_tool_results(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        execution_id: str
    ) -> Any:
        """Collect results from a single tool execution."""
        # For now, use non-streaming execution
        # Could be enhanced to use streaming if needed
        return await self.executor.bridge.call_tool(tool_name, arguments)


class StreamingResponseFormatter:
    """Format streaming responses for different output formats."""
    
    @staticmethod
    def to_openai_format(event: StreamEvent) -> str:
        """Convert stream event to OpenAI streaming format."""
        if event.type == StreamEventType.START:
            return json.dumps({
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": f"Starting tool execution: {event.data.get('tool_name', 'unknown')}\n"
                    },
                    "finish_reason": None,
                    "index": 0
                }]
            })
            
        elif event.type == StreamEventType.PROGRESS:
            return json.dumps({
                "choices": [{
                    "delta": {
                        "content": f"Progress: {event.data.get('message', 'Processing...')}\n"
                    },
                    "finish_reason": None,
                    "index": 0
                }]
            })
            
        elif event.type == StreamEventType.DATA:
            # Format the actual result
            content = json.dumps(event.data, indent=2) if isinstance(event.data, (dict, list)) else str(event.data)
            return json.dumps({
                "choices": [{
                    "delta": {
                        "content": f"\nResult:\n{content}\n"
                    },
                    "finish_reason": None,
                    "index": 0
                }]
            })
            
        elif event.type == StreamEventType.ERROR:
            return json.dumps({
                "choices": [{
                    "delta": {
                        "content": f"\nError: {event.data.get('error', 'Unknown error')}\n"
                    },
                    "finish_reason": None,
                    "index": 0
                }]
            })
            
        elif event.type == StreamEventType.COMPLETE:
            return json.dumps({
                "choices": [{
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0
                }]
            })
            
        else:
            return ""
    
    @staticmethod
    def to_sse_format(event: StreamEvent) -> str:
        """Convert stream event to SSE format."""
        return event.to_sse()
    
    @staticmethod
    def to_json_lines(event: StreamEvent) -> str:
        """Convert stream event to JSON lines format."""
        return json.dumps(event.to_dict()) + "\n"