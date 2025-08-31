"""
Service-related data models.

This module contains dataclasses for service metadata and record management.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from .summary_models import StructuredSummary
from .tag_models import Tags


@dataclass
class ServiceRecord:
    """Service metadata record for tracking paper processing."""
    arxiv_id: str
    source_type: str  # "system" or "user"
    created_at: str
    first_created_at: str
    original_url: Optional[str] = None
    user_id: Optional[str] = None
    ai_judgment: Optional[Dict[str, Any]] = None


@dataclass
class SummaryRecord:
    """Complete summary record with service data and structured content."""
    service_data: ServiceRecord
    summary_data: StructuredSummary
    tags: Tags
    updated_at: str
