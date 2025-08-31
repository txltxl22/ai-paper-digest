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

from .tag_models import Tags

from .service_models import (
    ServiceRecord,
    SummaryRecord
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
    summary_to_dict,
    tags_to_dict,
    summary_to_markdown,
    get_schema_version,
    export_schema_definitions,
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
    
    # Schemas
    "CHUNK_SUMMARY_SCHEMA",
    "SUMMARY_SCHEMA", 
    "TAGS_SCHEMA",
    
    # Utilities
    "validate_json_schema",
    "parse_chunk_summary",
    "parse_summary",
    "parse_tags",
    "summary_to_dict",
    "tags_to_dict",
    "summary_to_markdown",
    "get_schema_version",
    "export_schema_definitions",
    "clean_json_response"
]
