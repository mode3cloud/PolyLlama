"""
Streaming support for long-running tools.

This module provides capabilities for tools to stream partial results
during execution, enabling real-time feedback and progress updates.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio
import json
from datetime import datetime

from .base import ToolResult, ToolStatus


class StreamEventType(Enum):
    """Types of streaming events."""
    START = "start"
    PROGRESS = "progress"
    DATA = "data"
    ERROR = "error"
    COMPLETE = "complete"
    HEARTBEAT = "heartbeat"


@dataclass
class StreamEvent:
    """Represents a streaming event."""
    event_type: StreamEventType
    data: Optional[Any] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata or {}
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class StreamingTool(ABC):
    """Abstract base class for tools that support streaming."""
    
    @abstractmethod
    async def stream_execute(
        self,
        args: Dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute tool with streaming support.
        
        Args:
            args: Tool arguments
            
        Yields:
            StreamEvent objects with partial results and progress
        """
        pass
    
    async def execute_streaming(
        self,
        args: Dict[str, Any]
    ) -> AsyncGenerator[Union[StreamEvent, ToolResult], None]:
        """
        Execute tool with streaming, yielding events and final result.
        
        Args:
            args: Tool arguments
            
        Yields:
            StreamEvent objects and final ToolResult
        """
        start_time = datetime.now()
        
        try:
            # Send start event
            yield StreamEvent(
                event_type=StreamEventType.START,
                data={"args": args, "start_time": start_time.isoformat()}
            )
            
            # Stream execution
            final_data = []
            async for event in self.stream_execute(args):
                yield event
                
                # Collect data events for final result
                if event.event_type == StreamEventType.DATA and event.data:
                    final_data.append(event.data)
            
            # Send completion event and final result
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            yield StreamEvent(
                event_type=StreamEventType.COMPLETE,
                data={"execution_time": execution_time}
            )
            
            # Final result
            yield ToolResult(
                status=ToolStatus.SUCCESS,
                data={"stream_data": final_data},
                execution_time=execution_time
            )
            
        except Exception as e:
            # Send error event
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e)}
            )
            
            # Final error result
            yield ToolResult(
                status=ToolStatus.FAILURE,
                error=str(e),
                execution_time=(datetime.now() - start_time).total_seconds()
            )


class ProgressTracker:
    """Tracks and reports progress for streaming tools."""
    
    def __init__(self, total_steps: Optional[int] = None):
        """
        Initialize progress tracker.
        
        Args:
            total_steps: Total number of steps (if known)
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = datetime.now()
        self.step_history: List[Dict[str, Any]] = []
    
    def update(self, step_name: str, data: Optional[Any] = None) -> StreamEvent:
        """
        Update progress and return progress event.
        
        Args:
            step_name: Name of current step
            data: Optional step data
            
        Returns:
            Progress StreamEvent
        """
        self.current_step += 1
        now = datetime.now()
        
        step_info = {
            "step": self.current_step,
            "step_name": step_name,
            "timestamp": now.isoformat(),
            "data": data
        }
        self.step_history.append(step_info)
        
        # Calculate progress percentage if total is known
        progress_percent = None
        if self.total_steps:
            progress_percent = (self.current_step / self.total_steps) * 100
        
        # Calculate elapsed time and ETA
        elapsed = (now - self.start_time).total_seconds()
        eta = None
        if self.total_steps and self.current_step > 0:
            avg_time_per_step = elapsed / self.current_step
            remaining_steps = self.total_steps - self.current_step
            eta = remaining_steps * avg_time_per_step
        
        return StreamEvent(
            event_type=StreamEventType.PROGRESS,
            data={
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "step_name": step_name,
                "progress_percent": progress_percent,
                "elapsed_time": elapsed,
                "estimated_remaining": eta,
                "step_data": data
            }
        )
    
    def set_total_steps(self, total: int) -> None:
        """Update total steps count."""
        self.total_steps = total


class StreamingEmailSearchTool(StreamingTool):
    """Example streaming implementation of email search."""
    
    def __init__(self, mcp_client=None):
        """Initialize streaming email search tool."""
        self.mcp_client = mcp_client
    
    async def stream_execute(
        self,
        args: Dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream email search execution.
        
        Args:
            args: Search arguments
            
        Yields:
            StreamEvent objects with search progress and results
        """
        query = args.get("query", "")
        limit = args.get("limit", 10)
        
        progress = ProgressTracker(total_steps=5)
        
        # Step 1: Validate parameters
        yield progress.update("Validating parameters", {"query": query, "limit": limit})
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Step 2: Connect to email service
        yield progress.update("Connecting to email service")
        await asyncio.sleep(0.2)
        
        # Step 3: Execute search
        yield progress.update("Executing search query", {"query": query})
        await asyncio.sleep(0.5)
        
        # Step 4: Process results (stream partial results)
        yield progress.update("Processing results")
        
        # Simulate streaming results
        for i in range(min(3, limit)):
            await asyncio.sleep(0.2)
            
            email_result = {
                "id": f"email_{i+1}",
                "subject": f"Result {i+1} for '{query}'",
                "sender": f"sender{i+1}@example.com",
                "preview": f"This email matches your query: {query}..."
            }
            
            yield StreamEvent(
                event_type=StreamEventType.DATA,
                data=email_result,
                metadata={"result_index": i+1, "total_so_far": i+1}
            )
        
        # Step 5: Finalize results
        yield progress.update("Finalizing search results", {"total_found": min(3, limit)})
        await asyncio.sleep(0.1)


class StreamingDataAnalysisTool(StreamingTool):
    """Example streaming implementation of data analysis."""
    
    def __init__(self, analytics_engine=None):
        """Initialize streaming data analysis tool."""
        self.analytics_engine = analytics_engine
    
    async def stream_execute(
        self,
        args: Dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream data analysis execution.
        
        Args:
            args: Analysis arguments
            
        Yields:
            StreamEvent objects with analysis progress and results
        """
        data_source = args.get("data_source", "")
        analysis_type = args.get("analysis_type", "summary")
        
        # Analysis steps vary by type
        if analysis_type == "correlation":
            steps = ["load_data", "calculate_correlations", "generate_matrix", "format_results"]
        elif analysis_type == "trend":
            steps = ["load_data", "time_series_analysis", "trend_calculation", "forecast", "format_results"]
        else:
            steps = ["load_data", "calculate_statistics", "format_results"]
        
        progress = ProgressTracker(total_steps=len(steps))
        
        # Execute each step
        for step_name in steps:
            yield progress.update(step_name, {"data_source": data_source})
            
            # Simulate processing time based on step
            if step_name == "load_data":
                await asyncio.sleep(1.0)
                
                # Stream data loading progress
                for chunk in range(5):
                    await asyncio.sleep(0.2)
                    yield StreamEvent(
                        event_type=StreamEventType.DATA,
                        data={
                            "loading_progress": (chunk + 1) * 20,
                            "chunk": chunk + 1,
                            "status": "loading"
                        }
                    )
                
            elif "calculate" in step_name or "analysis" in step_name:
                await asyncio.sleep(0.8)
                
                # Stream intermediate calculations
                if analysis_type == "correlation":
                    correlations = [
                        {"var1": "age", "var2": "income", "correlation": 0.65},
                        {"var1": "education", "var2": "income", "correlation": 0.78}
                    ]
                    for corr in correlations:
                        yield StreamEvent(
                            event_type=StreamEventType.DATA,
                            data=corr,
                            metadata={"data_type": "correlation"}
                        )
                        await asyncio.sleep(0.1)
                
            else:
                await asyncio.sleep(0.3)
        
        # Send final summary
        yield StreamEvent(
            event_type=StreamEventType.DATA,
            data={
                "analysis_complete": True,
                "analysis_type": analysis_type,
                "data_source": data_source
            },
            metadata={"data_type": "summary"}
        )


class StreamBuffer:
    """Buffers streaming events for efficient transmission."""
    
    def __init__(self, buffer_size: int = 10, flush_interval: float = 1.0):
        """
        Initialize stream buffer.
        
        Args:
            buffer_size: Number of events to buffer before flushing
            flush_interval: Time interval to force flush (seconds)
        """
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer: List[StreamEvent] = []
        self.last_flush = datetime.now()
    
    def add_event(self, event: StreamEvent) -> Optional[List[StreamEvent]]:
        """
        Add event to buffer and return events if buffer should be flushed.
        
        Args:
            event: Event to add
            
        Returns:
            List of events to flush, or None if no flush needed
        """
        self.buffer.append(event)
        
        # Check if we should flush
        should_flush = (
            len(self.buffer) >= self.buffer_size or
            (datetime.now() - self.last_flush).total_seconds() >= self.flush_interval or
            event.event_type in [StreamEventType.ERROR, StreamEventType.COMPLETE]
        )
        
        if should_flush:
            events_to_flush = self.buffer.copy()
            self.buffer.clear()
            self.last_flush = datetime.now()
            return events_to_flush
        
        return None
    
    def flush(self) -> List[StreamEvent]:
        """Force flush all buffered events."""
        events_to_flush = self.buffer.copy()
        self.buffer.clear()
        self.last_flush = datetime.now()
        return events_to_flush


class StreamingExecutor:
    """Executor for streaming tools with buffering and error handling."""
    
    def __init__(self, buffer_size: int = 10, heartbeat_interval: float = 30.0):
        """
        Initialize streaming executor.
        
        Args:
            buffer_size: Events to buffer before flushing
            heartbeat_interval: Interval for heartbeat events (seconds)
        """
        self.buffer_size = buffer_size
        self.heartbeat_interval = heartbeat_interval
    
    async def execute_streaming_tool(
        self,
        tool: StreamingTool,
        args: Dict[str, Any]
    ) -> AsyncGenerator[List[StreamEvent], None]:
        """
        Execute streaming tool with buffering and heartbeat.
        
        Args:
            tool: Streaming tool to execute
            args: Tool arguments
            
        Yields:
            Lists of buffered StreamEvents
        """
        buffer = StreamBuffer(self.buffer_size)
        last_heartbeat = datetime.now()
        
        try:
            async for event_or_result in tool.execute_streaming(args):
                if isinstance(event_or_result, StreamEvent):
                    # Buffer the event
                    events_to_flush = buffer.add_event(event_or_result)
                    if events_to_flush:
                        yield events_to_flush
                    
                    # Send heartbeat if needed
                    now = datetime.now()
                    if (now - last_heartbeat).total_seconds() >= self.heartbeat_interval:
                        heartbeat = StreamEvent(
                            event_type=StreamEventType.HEARTBEAT,
                            data={"timestamp": now.isoformat()}
                        )
                        heartbeat_flush = buffer.add_event(heartbeat)
                        if heartbeat_flush:
                            yield heartbeat_flush
                        last_heartbeat = now
                
                elif isinstance(event_or_result, ToolResult):
                    # Final result - flush any remaining events
                    remaining_events = buffer.flush()
                    if remaining_events:
                        yield remaining_events
                    
                    # Convert result to final event
                    final_event = StreamEvent(
                        event_type=StreamEventType.COMPLETE,
                        data=event_or_result.to_dict()
                    )
                    yield [final_event]
                    break
            
        except Exception as e:
            # Flush buffer and send error
            remaining_events = buffer.flush()
            if remaining_events:
                yield remaining_events
            
            error_event = StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e)}
            )
            yield [error_event]


# Example usage functions
async def stream_to_sse(
    events: AsyncGenerator[List[StreamEvent], None]
) -> AsyncGenerator[str, None]:
    """
    Convert streaming events to Server-Sent Events format.
    
    Args:
        events: Stream of event lists
        
    Yields:
        SSE-formatted strings
    """
    async for event_list in events:
        for event in event_list:
            sse_data = f"data: {event.to_json()}\n\n"
            yield sse_data


async def stream_to_websocket(
    events: AsyncGenerator[List[StreamEvent], None],
    websocket
) -> None:
    """
    Send streaming events to WebSocket.
    
    Args:
        events: Stream of event lists
        websocket: WebSocket connection
    """
    try:
        async for event_list in events:
            for event in event_list:
                await websocket.send_text(event.to_json())
    except Exception as e:
        # Send error and close
        error_event = StreamEvent(
            event_type=StreamEventType.ERROR,
            data={"error": str(e)}
        )
        await websocket.send_text(error_event.to_json())
        await websocket.close()