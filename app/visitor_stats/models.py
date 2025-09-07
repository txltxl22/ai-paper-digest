"""
Data Models for Visitor Stats

Defines the data structures used by the visitor stats system.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Any, Optional


@dataclass
class VisitorStats:
    """Visitor statistics data structure."""
    
    total_pv: int = 0
    total_uv: int = 0
    unique_visitors: List[str] = field(default_factory=list)
    page_views: List[Dict[str, Any]] = field(default_factory=list)
    action_distribution: Dict[str, int] = field(default_factory=dict)
    daily_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    top_pages: List[Dict[str, Any]] = field(default_factory=list)
    top_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_pv": self.total_pv,
            "total_uv": self.total_uv,
            "unique_visitors": self.unique_visitors,
            "page_views": self.page_views,
            "action_distribution": self.action_distribution,
            "daily_stats": self.daily_stats,
            "top_pages": self.top_pages,
            "top_actions": self.top_actions
        }


@dataclass
class PageView:
    """Individual page view data."""
    
    timestamp: str
    user_id: str
    page: str
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "page": self.page,
            "referrer": self.referrer,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "browser": self.browser,
            "os": self.os,
            "device": self.device
        }


@dataclass
class ActionEvent:
    """Individual action event data."""
    
    timestamp: str
    user_id: str
    action_type: str
    page: Optional[str] = None
    arxiv_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "page": self.page,
            "arxiv_id": self.arxiv_id,
            "metadata": self.metadata
        }
