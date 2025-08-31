"""
Summary-related data models.

This module contains dataclasses for paper summaries, including
chunk summaries, structured summaries, and their components.
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class PaperInfo:
    """Paper title information."""
    title_zh: str
    title_en: str


@dataclass
class Innovation:
    """Innovation point structure."""
    title: str
    description: str
    improvement: str
    significance: str


@dataclass
class Results:
    """Results and value structure."""
    experimental_highlights: List[str]
    practical_value: List[str]


@dataclass
class TermDefinition:
    """Terminology definition structure."""
    term: str
    definition: str


@dataclass
class ChunkSummary:
    """Structure for individual chunk summaries."""
    main_content: str
    innovations: List[Innovation]
    key_terms: List[TermDefinition]


@dataclass
class StructuredSummary:
    """Complete structured summary."""
    paper_info: PaperInfo
    one_sentence_summary: str
    innovations: List[Innovation]
    results: Results
    terminology: List[TermDefinition]
