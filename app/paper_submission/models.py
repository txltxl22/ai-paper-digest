from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class AIJudgment:
    """AI judgment result for paper content."""
    is_ai: bool
    confidence: float
    tags: List[str]
    timestamp: datetime


@dataclass
class ProcessResult:
    """Result of paper processing."""
    success: bool
    error: Optional[str] = None
    summary_path: Optional[str] = None
    paper_subject: Optional[str] = None


@dataclass
class UploadRecord:
    """Record of uploaded URL."""
    url: str
    timestamp: datetime
    ai_judgment: AIJudgment
    process_result: ProcessResult


@dataclass
class PaperSubmissionResult:
    """Result of paper submission."""
    success: bool
    message: str
    summary_path: Optional[str] = None
    paper_subject: Optional[str] = None
    error: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class DailyLimitInfo:
    """Daily limit information for an IP."""
    date: str
    count: int
