"""
Fetch subsystem models for admin fetch operations.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FetchCommand:
    """Command configuration for fetch operations."""
    command: List[str]
    working_directory: str
    timeout: int = 300  # 5 minutes default
    feed_url: str = "https://papers.takara.ai/api/feed"


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    summary_stats: Dict[str, str]
    execution_time: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class StreamEvent:
    """Server-sent event for streaming fetch progress."""
    event_type: str  # 'status', 'log', 'complete', 'error'
    message: str
    icon: Optional[str] = None
    level: str = "info"  # 'info', 'success', 'error', 'warning'
    status: Optional[str] = None  # for 'complete' events
