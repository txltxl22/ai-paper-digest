"""
Service-related data models.

This module contains Pydantic models for service metadata and record management.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from .summary_models import StructuredSummary
from .tags import Tags


class ServiceRecord(BaseModel):
    """Service metadata record for tracking paper processing."""
    arxiv_id: str = Field(description="The arXiv ID of the paper")
    source_type: str = Field(description="Either 'system' (from background processing) or 'user' (user upload)")
    created_at: str = Field(description="Current submission time (ISO format)")
    first_created_at: str = Field(description="Original creation time (ISO format)")
    original_url: Optional[str] = Field(default=None, description="The original URL of the paper")
    user_id: Optional[str] = Field(default=None, description="The user ID who uploaded the paper (if source_type is 'user')")
    ai_judgment: Optional[Dict[str, Any]] = Field(default=None, description="AI judgment data if available")
    is_abstract_only: Optional[bool] = Field(default=False, description="Whether this is an abstract-only summary")


class SummaryData(BaseModel):
    """Summary data container matching the saved JSON format."""
    structured_content: StructuredSummary = Field(description="Structured summary content")
    markdown_content: Optional[str] = Field(default=None, description="Markdown representation of the summary")
    tags: Tags = Field(description="Tags object")
    updated_at: str = Field(description="Last update time (ISO format)")


class SummaryRecord(BaseModel):
    """Complete summary record matching the saved JSON format."""
    service_data: ServiceRecord = Field(description="Service metadata record")
    summary_data: SummaryData = Field(description="Summary data container")


class SummarizationResult(BaseModel):
    """Result of paper summarization."""
    summary_path: Optional[Path] = Field(default=None, description="Path to the generated summary markdown file")
    pdf_url: Optional[str] = Field(default=None, description="URL of the downloaded PDF")
    paper_subject: Optional[str] = Field(default=None, description="Extracted paper subject/title")
    arxiv_id: Optional[str] = Field(default=None, description="arXiv ID of the paper")
    structured_summary: Optional[StructuredSummary] = Field(default=None, description="Structured summary object if available")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True  # Allow Path objects
    
    @classmethod
    def success(cls, summary_path: Path, pdf_url: str, paper_subject: str, 
                arxiv_id: str, structured_summary: Optional[StructuredSummary] = None) -> "SummarizationResult":
        """Create a successful result."""
        return cls(
            summary_path=summary_path,
            pdf_url=pdf_url,
            paper_subject=paper_subject,
            arxiv_id=arxiv_id,
            structured_summary=structured_summary
        )
    
    @classmethod
    def failure(cls) -> "SummarizationResult":
        """Create a failure result."""
        return cls()
    
    @property
    def is_success(self) -> bool:
        """Check if summarization was successful."""
        return self.summary_path is not None
