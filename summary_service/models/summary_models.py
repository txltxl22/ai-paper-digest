"""
Summary-related data models.

This module contains dataclasses for paper summaries, including
chunk summaries, structured summaries, and their components.
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class PaperInfo:
    """Paper information."""
    title_zh: str
    title_en: str
    abstract: str


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
    
    def to_markdown(self) -> str:
        """Convert StructuredSummary to markdown format for backward compatibility."""
        md_lines = []
        
        md_lines.append("## 📄 论文总结")
        
        # Paper title
        md_lines.append("")
        md_lines.append(f"**{self.paper_info.title_zh}** / ")
        md_lines.append(f"**{self.paper_info.title_en}**")
        md_lines.append("\n---\n")
        
        # One sentence summary
        md_lines.append("### 1️⃣ 一句话总结")
        md_lines.append("")
        md_lines.append(self.one_sentence_summary)
        md_lines.append("\n---\n")
        
        # Innovations
        md_lines.append("### 2️⃣ 论文创新点")
        md_lines.append("")
        for i, innovation in enumerate(self.innovations, 1):
            md_lines.append(f"#### {i}. {innovation.title}")
            md_lines.append("")
            md_lines.append(f"* **创新点**：{innovation.description}")
            md_lines.append(f"* **区别/改进**：{innovation.improvement}")
            md_lines.append(f"* **意义**：{innovation.significance}")
            md_lines.append("")
        md_lines.append("\n---\n")
        
        # Results
        md_lines.append("### 3️⃣ 主要结果与价值")
        md_lines.append("")
        
        if self.results.experimental_highlights:
            md_lines.append("#### **结果亮点**")
            md_lines.append("")
            for highlight in self.results.experimental_highlights:
                md_lines.append(f"* {highlight}")
            md_lines.append("")
        
        if self.results.practical_value:
            md_lines.append("#### **实际价值**")
            md_lines.append("")
            for value in self.results.practical_value:
                md_lines.append(f"* {value}")
            md_lines.append("")
        
        md_lines.append("\n---\n")

        # Terminology
        if self.terminology:
            md_lines.append("### 4️⃣ 术语表")
            md_lines.append("")
            for term in self.terminology:
                md_lines.append(f"* **{term.term}**：{term.definition}")
            md_lines.append("")
        
        return "\n".join(md_lines)