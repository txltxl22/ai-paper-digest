"""
Summary-related data models.

This module contains Pydantic models for paper summaries, including
chunk summaries, structured summaries, and their components.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PaperInfo(BaseModel):
    """Paper information."""
    title_zh: str = Field(default="", description="Chinese title")
    title_en: str = Field(default="", description="English title")
    abstract: str = Field(default="", description="Paper abstract")
    # Additional metadata fields from extraction
    url: Optional[str] = Field(default=None, description="Original paper URL")
    arxiv_id: Optional[str] = Field(default=None, description="arXiv ID")
    source: Optional[str] = Field(default=None, description="Source (arxiv, huggingface, unknown)")


class Innovation(BaseModel):
    """Innovation point structure."""
    title: str = Field(description="Innovation title")
    description: str = Field(description="Innovation description")
    improvement: str = Field(description="Improvement over previous methods")
    significance: str = Field(description="Significance of the innovation")


class Results(BaseModel):
    """Results and value structure."""
    experimental_highlights: List[str] = Field(default_factory=list, description="Experimental highlights")
    practical_value: List[str] = Field(default_factory=list, description="Practical value points")


class TermDefinition(BaseModel):
    """Terminology definition structure."""
    term: str = Field(description="Term name")
    definition: str = Field(description="Term definition")


class ChunkSummary(BaseModel):
    """Structure for individual chunk summaries."""
    main_content: str = Field(description="Main content of the chunk")
    innovations: List[Innovation] = Field(default_factory=list, description="Innovations in this chunk")
    key_terms: List[TermDefinition] = Field(default_factory=list, description="Key terms in this chunk")


class StructuredSummary(BaseModel):
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

        # Determine if there is any deep-read content
        has_deep_content = bool(
            self.innovations
            or (self.results.experimental_highlights or self.results.practical_value)
            or self.terminology
        )

        if has_deep_content:
            # Innovations
            if self.innovations:
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
            if self.results.experimental_highlights or self.results.practical_value:
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