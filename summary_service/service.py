"""
service.py - Unified summary service interface
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

_LOG = logging.getLogger("summary_service")


class SummaryService:
    """Unified summary service for complete paper processing pipeline."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: str = "deepseek",
        model: str = None,
        max_workers: int = 4,
        chunk_length: int = 5000,
        overlap_ratio: float = 0.05,
    ):
        """Initialize the summary service."""
        pass


# Placeholder function for backward compatibility
def process_paper_text(*args, **kwargs):
    """Placeholder - moved to SummaryService class."""
    pass
