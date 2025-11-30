"""
Models package for structured summary data.

This package contains all the dataclass definitions and schemas
for the paper summarization system.
"""

from .summary_models import (
    ChunkSummary,
    StructuredSummary,
    PaperInfo,
    Innovation,
    Results,
    TermDefinition
)

from .tags import Tags

from .service_models import (
    ServiceRecord,
    SummaryRecord,
    SummaryData,
    SummarizationResult
)

from .schemas import (
    CHUNK_SUMMARY_SCHEMA,
    SUMMARY_SCHEMA,
    TAGS_SCHEMA
)

from .utils import (
    validate_json_schema,
    parse_chunk_summary,
    parse_summary,
    parse_tags,
    get_schema_version,
    clean_json_response
)

__all__ = [
    # Summary models
    "ChunkSummary",
    "StructuredSummary", 
    "PaperInfo",
    "Innovation",
    "Results",
    "TermDefinition",
    
    # Tag models
    "Tags",
    
    # Service models
    "ServiceRecord",
    "SummaryRecord",
    "SummaryData",
    "SummarizationResult",
    
    # Schemas
    "CHUNK_SUMMARY_SCHEMA",
    "SUMMARY_SCHEMA", 
    "TAGS_SCHEMA",
    
    # Utilities
    "validate_json_schema",
    "parse_chunk_summary",
    "parse_summary",
    "parse_tags",
    "get_schema_version",
    "clean_json_response"
]
