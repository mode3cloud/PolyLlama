"""
Advanced metrics and monitoring for tool usage.

This module provides detailed analytics and monitoring capabilities
for tool execution, performance tracking, and usage patterns.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio
import time
from enum import Enum
import statistics

from .base import ToolResult, ToolStatus


class MetricType(Enum):
    """Types of metrics to track."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class MetricsCollector:
    """Collects and analyzes tool usage metrics."""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of historical records to keep
        """
        self.max_history = max_history
        self._execution_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def record_execution(
        self,
        tool_name: str,
        result: ToolResult,
        args: Dict[str, Any],
        start_time: float
    ) -> None:
        """
        Record a tool execution for metrics.
        
        Args:
            tool_name: Name of the executed tool
            result: Execution result
            args: Tool arguments
            start_time: Execution start timestamp
        """
        async with self._lock:
            execution_record = {
                "tool_name": tool_name,
                "timestamp": datetime.now(),
                "start_time": start_time,
                "execution_time": result.execution_time or 0,
                "status": result.status,
                "success": result.is_success(),
                "args_size": len(str(args)),
                "result_size": len(str(result.data)) if result.data else 0,
                "error": result.error
            }
            
            self._execution_history[tool_name].append(execution_record)
            
            # Update counters
            self._counters[f"{tool_name}.total_executions"] += 1
            if result.is_success():
                self._counters[f"{tool_name}.successful_executions"] += 1
            else:
                self._counters[f"{tool_name}.failed_executions"] += 1
            
            # Update timers
            if result.execution_time:
                self._timers[f"{tool_name}.execution_time"].append(result.execution_time)
                # Keep only recent entries
                if len(self._timers[f"{tool_name}.execution_time"]) > self.max_history:
                    self._timers[f"{tool_name}.execution_time"] = \
                        self._timers[f"{tool_name}.execution_time"][-self.max_history:]
            
            # Update gauges
            self._gauges[f"{tool_name}.last_execution_time"] = result.execution_time or 0
            self._gauges[f"{tool_name}.success_rate"] = self._calculate_success_rate(tool_name)
    
    def _calculate_success_rate(self, tool_name: str) -> float:
        """Calculate success rate for a tool."""
        total = self._counters.get(f"{tool_name}.total_executions", 0)
        successful = self._counters.get(f"{tool_name}.successful_executions", 0)
        return (successful / total) if total > 0 else 0.0
    
    async def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary containing tool metrics
        """
        async with self._lock:
            history = list(self._execution_history.get(tool_name, []))
            
            if not history:
                return {"tool_name": tool_name, "no_data": True}
            
            # Basic counters
            total_executions = len(history)
            successful_executions = sum(1 for h in history if h["success"])
            failed_executions = total_executions - successful_executions
            
            # Timing statistics
            execution_times = [h["execution_time"] for h in history if h["execution_time"] > 0]
            timing_stats = {}
            if execution_times:
                timing_stats = {
                    "avg_execution_time": statistics.mean(execution_times),
                    "median_execution_time": statistics.median(execution_times),
                    "min_execution_time": min(execution_times),
                    "max_execution_time": max(execution_times),
                    "p95_execution_time": self._percentile(execution_times, 95),
                    "p99_execution_time": self._percentile(execution_times, 99)
                }
            
            # Recent activity (last hour)
            now = datetime.now()
            recent_threshold = now - timedelta(hours=1)
            recent_executions = [h for h in history if h["timestamp"] > recent_threshold]
            
            # Error analysis
            errors = [h["error"] for h in history if h["error"]]
            error_types = {}
            for error in errors:
                error_type = self._categorize_error(error)
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return {
                "tool_name": tool_name,
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "failed_executions": failed_executions,
                "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
                "recent_executions_1h": len(recent_executions),
                "timing_statistics": timing_stats,
                "error_analysis": error_types,
                "last_execution": history[-1]["timestamp"].isoformat() if history else None,
                "first_execution": history[0]["timestamp"].isoformat() if history else None
            }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def _categorize_error(self, error: str) -> str:
        """Categorize error message into type."""
        error_lower = error.lower()
        if "timeout" in error_lower:
            return "timeout"
        elif "parameter" in error_lower or "validation" in error_lower:
            return "validation"
        elif "auth" in error_lower or "permission" in error_lower:
            return "authorization"
        elif "network" in error_lower or "connection" in error_lower:
            return "network"
        elif "not found" in error_lower:
            return "not_found"
        else:
            return "other"
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-wide metrics across all tools.
        
        Returns:
            Dictionary containing system metrics
        """
        async with self._lock:
            all_tools = list(self._execution_history.keys())
            total_executions = sum(len(history) for history in self._execution_history.values())
            
            if total_executions == 0:
                return {"no_data": True}
            
            # Aggregate statistics
            all_execution_times = []
            all_successes = 0
            tool_popularity = {}
            
            for tool_name, history in self._execution_history.items():
                tool_popularity[tool_name] = len(history)
                for record in history:
                    if record["execution_time"] > 0:
                        all_execution_times.append(record["execution_time"])
                    if record["success"]:
                        all_successes += 1
            
            # Recent activity
            now = datetime.now()
            recent_threshold = now - timedelta(hours=1)
            recent_executions = 0
            for history in self._execution_history.values():
                recent_executions += sum(
                    1 for record in history 
                    if record["timestamp"] > recent_threshold
                )
            
            # Performance statistics
            timing_stats = {}
            if all_execution_times:
                timing_stats = {
                    "avg_execution_time": statistics.mean(all_execution_times),
                    "median_execution_time": statistics.median(all_execution_times),
                    "p95_execution_time": self._percentile(all_execution_times, 95),
                    "p99_execution_time": self._percentile(all_execution_times, 99)
                }
            
            return {
                "total_tools": len(all_tools),
                "total_executions": total_executions,
                "successful_executions": all_successes,
                "overall_success_rate": all_successes / total_executions if total_executions > 0 else 0,
                "recent_executions_1h": recent_executions,
                "tool_popularity": dict(sorted(tool_popularity.items(), key=lambda x: x[1], reverse=True)),
                "performance_statistics": timing_stats,
                "active_tools": all_tools
            }
    
    async def get_performance_trends(
        self,
        tool_name: Optional[str] = None,
        time_window: timedelta = timedelta(hours=24)
    ) -> Dict[str, Any]:
        """
        Get performance trends over time.
        
        Args:
            tool_name: Specific tool name or None for all tools
            time_window: Time window for trend analysis
            
        Returns:
            Dictionary containing trend data
        """
        async with self._lock:
            now = datetime.now()
            start_time = now - time_window
            
            if tool_name:
                histories = {tool_name: self._execution_history.get(tool_name, deque())}
            else:
                histories = self._execution_history
            
            trend_data = {}
            
            for name, history in histories.items():
                # Filter to time window
                recent_records = [
                    record for record in history 
                    if record["timestamp"] > start_time
                ]
                
                if not recent_records:
                    continue
                
                # Group by hour buckets
                hourly_buckets = defaultdict(list)
                for record in recent_records:
                    hour_bucket = record["timestamp"].replace(minute=0, second=0, microsecond=0)
                    hourly_buckets[hour_bucket].append(record)
                
                # Calculate trends
                hourly_data = []
                for hour, records in sorted(hourly_buckets.items()):
                    successes = sum(1 for r in records if r["success"])
                    total = len(records)
                    avg_time = statistics.mean([r["execution_time"] for r in records if r["execution_time"] > 0]) or 0
                    
                    hourly_data.append({
                        "timestamp": hour.isoformat(),
                        "total_executions": total,
                        "successful_executions": successes,
                        "success_rate": successes / total if total > 0 else 0,
                        "avg_execution_time": avg_time
                    })
                
                trend_data[name] = hourly_data
            
            return trend_data
    
    async def clear_metrics(self, tool_name: Optional[str] = None) -> None:
        """
        Clear metrics data.
        
        Args:
            tool_name: Specific tool name or None for all tools
        """
        async with self._lock:
            if tool_name:
                if tool_name in self._execution_history:
                    self._execution_history[tool_name].clear()
                # Clear related counters and gauges
                keys_to_remove = [k for k in self._counters.keys() if k.startswith(f"{tool_name}.")]
                for key in keys_to_remove:
                    del self._counters[key]
                keys_to_remove = [k for k in self._gauges.keys() if k.startswith(f"{tool_name}.")]
                for key in keys_to_remove:
                    del self._gauges[key]
            else:
                self._execution_history.clear()
                self._counters.clear()
                self._gauges.clear()
                self._timers.clear()
                self._histograms.clear()


class PerformanceMonitor:
    """Monitors tool performance and alerts on issues."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        """
        Initialize performance monitor.
        
        Args:
            metrics_collector: Metrics collector instance
        """
        self.metrics = metrics_collector
        self.thresholds = {
            "max_execution_time": 30.0,  # seconds
            "min_success_rate": 0.8,     # 80%
            "max_error_rate": 0.2        # 20%
        }
        self.alerts: List[Dict[str, Any]] = []
    
    async def check_performance(self, tool_name: str) -> List[Dict[str, Any]]:
        """
        Check tool performance against thresholds.
        
        Args:
            tool_name: Name of tool to check
            
        Returns:
            List of performance alerts
        """
        metrics = await self.metrics.get_tool_metrics(tool_name)
        alerts = []
        
        if metrics.get("no_data"):
            return alerts
        
        # Check execution time
        timing_stats = metrics.get("timing_statistics", {})
        avg_time = timing_stats.get("avg_execution_time", 0)
        if avg_time > self.thresholds["max_execution_time"]:
            alerts.append({
                "type": "performance",
                "severity": "warning",
                "tool": tool_name,
                "message": f"Average execution time ({avg_time:.2f}s) exceeds threshold ({self.thresholds['max_execution_time']}s)",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check success rate
        success_rate = metrics.get("success_rate", 0)
        if success_rate < self.thresholds["min_success_rate"]:
            alerts.append({
                "type": "reliability",
                "severity": "error" if success_rate < 0.5 else "warning",
                "tool": tool_name,
                "message": f"Success rate ({success_rate:.2%}) below threshold ({self.thresholds['min_success_rate']:.2%})",
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def set_threshold(self, metric_name: str, value: float) -> None:
        """Set performance threshold."""
        self.thresholds[metric_name] = value
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current performance thresholds."""
        return self.thresholds.copy()


# Global metrics collector instance
_global_metrics = MetricsCollector()


def get_global_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _global_metrics