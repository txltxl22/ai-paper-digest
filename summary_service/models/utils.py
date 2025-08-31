"""
Utility functions for schema management and data conversion.

This module contains functions for parsing, validating, and converting
structured summary data.
"""

from typing import Dict, Any
import json
from .summary_models import ChunkSummary, StructuredSummary, PaperInfo, Innovation, Results, TermDefinition
from .tag_models import Tags
from .schemas import CHUNK_SUMMARY_SCHEMA, SUMMARY_SCHEMA, TAGS_SCHEMA


def get_schema_version() -> str:
    """Get the current schema version for tracking changes."""
    return "1.0.0"


def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validate data against JSON schema."""
    try:
        # Basic validation - in production you might want to use jsonschema library
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                return False
        
        # For now, just check required fields exist
        # In production, you might want to use jsonschema library for full validation
        return True
    except Exception:
        return False


def parse_chunk_summary(json_str: str) -> ChunkSummary:
    """Parse chunk summary from JSON string."""
    try:
        cleaned_json = clean_json_response(json_str)
        data = json.loads(cleaned_json)
        if not validate_json_schema(data, CHUNK_SUMMARY_SCHEMA):
            raise ValueError("Invalid chunk summary schema")
        
        return ChunkSummary(
            main_content=data["main_content"],
            innovations=[Innovation(**innovation) for innovation in data["innovations"]],
            key_terms=[TermDefinition(**term) for term in data["key_terms"]]
        )
    except Exception as e:
        raise ValueError(f"Failed to parse chunk summary: {e}")


def clean_json_response(response: str) -> str:
    """Clean up LLM response to extract JSON content."""
    # Remove markdown code blocks - minimal cleaning only
    response = response.strip()
    if response.startswith('```json'):
        response = response[7:]  # Remove ```json
    if response.startswith('```'):
        response = response[3:]  # Remove ```
    if response.endswith('```'):
        response = response[:-3]  # Remove trailing ```
    
    return response.strip()


def safe_parse_json(json_str: str, fallback_data: dict = None) -> dict:
    """Safely parse JSON with fallback handling."""
    try:
        cleaned_json = clean_json_response(json_str)
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Cleaned JSON: {repr(cleaned_json)}")
        
        # Try to extract JSON using regex as last resort
        import re
        json_match = re.search(r'\{.*\}', cleaned_json, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        # Return fallback data if provided
        if fallback_data:
            print("Using fallback data")
            return fallback_data
        
        raise ValueError(f"Failed to parse JSON: {e}")


def parse_summary(json_str: str) -> StructuredSummary:
    """Parse structured summary from JSON string."""
    try:
        cleaned_json = clean_json_response(json_str)
        data = json.loads(cleaned_json)
        if not validate_json_schema(data, SUMMARY_SCHEMA):
            raise ValueError("Invalid summary schema")
        
        return StructuredSummary(
            paper_info=PaperInfo(
                title_zh=data["paper_info"]["title_zh"],
                title_en=data["paper_info"]["title_en"]
            ),
            one_sentence_summary=data["one_sentence_summary"],
            innovations=[
                Innovation(**innovation) for innovation in data["innovations"]
            ],
            results=Results(**data["results"]),
            terminology=[
                TermDefinition(**term) for term in data["terminology"]
            ]
        )
    except Exception as e:
        raise ValueError(f"Failed to parse summary: {e}")


def parse_tags(json_str: str) -> Tags:
    """Parse tags from JSON string."""
    try:
        # Clean up the response first
        cleaned_json = clean_json_response(json_str)
        data = json.loads(cleaned_json)
        if not validate_json_schema(data, TAGS_SCHEMA):
            raise ValueError("Invalid tags schema")
        
        return Tags(
            top=data["top"],
            tags=data["tags"]
        )
    except Exception as e:
        raise ValueError(f"Failed to parse tags: {e}")


def summary_to_dict(summary: StructuredSummary) -> Dict[str, Any]:
    """Convert StructuredSummary to dictionary."""
    return {
        "paper_info": {
            "title_zh": summary.paper_info.title_zh,
            "title_en": summary.paper_info.title_en
        },
        "one_sentence_summary": summary.one_sentence_summary,
        "innovations": [
            {
                "title": innovation.title,
                "description": innovation.description,
                "improvement": innovation.improvement,
                "significance": innovation.significance
            }
            for innovation in summary.innovations
        ],
        "results": {
            "experimental_highlights": summary.results.experimental_highlights,
            "practical_value": summary.results.practical_value
        },
        "terminology": [
            {
                "term": term.term,
                "definition": term.definition
            }
            for term in summary.terminology
        ]
    }


def tags_to_dict(tags: Tags) -> Dict[str, Any]:
    """Convert Tags to dictionary."""
    return {
        "top": tags.top,
        "tags": tags.tags
    }


def summary_to_markdown(summary: StructuredSummary) -> str:
    """Convert StructuredSummary to markdown format for backward compatibility."""
    md_lines = []
    
    md_lines.append("## 📄 论文总结")
    
    # Paper title
    md_lines.append("")
    md_lines.append(f"**{summary.paper_info.title_zh}**")
    md_lines.append("")
    md_lines.append(f"**{summary.paper_info.title_en}**")
    md_lines.append("\n---\n")
    
    # One sentence summary
    md_lines.append("### 1️⃣ 一句话总结")
    md_lines.append("")
    md_lines.append(summary.one_sentence_summary)
    md_lines.append("\n---\n")
    
    # Innovations
    md_lines.append("### 2️⃣ 论文创新点")
    md_lines.append("")
    for i, innovation in enumerate(summary.innovations, 1):
        md_lines.append(f"#### {i}. {innovation.title}")
        md_lines.append("")
        md_lines.append(f"* **创新点是什么**：{innovation.description}")
        md_lines.append(f"* **与已有方法的区别/改进**：{innovation.improvement}")
        md_lines.append(f"* **为什么有意义**：{innovation.significance}")
        md_lines.append("")
    md_lines.append("\n---\n")
    
    # Results
    md_lines.append("### 3️⃣ 主要结果与价值")
    md_lines.append("")
    
    if summary.results.experimental_highlights:
        md_lines.append("#### **实验结果亮点**")
        md_lines.append("")
        for highlight in summary.results.experimental_highlights:
            md_lines.append(f"* {highlight}")
        md_lines.append("")
    
    if summary.results.practical_value:
        md_lines.append("#### **实际应用价值**")
        md_lines.append("")
        for value in summary.results.practical_value:
            md_lines.append(f"* {value}")
        md_lines.append("")
    
    md_lines.append("\n---\n")

    # Terminology
    if summary.terminology:
        md_lines.append("### 4️⃣ 术语表")
        md_lines.append("")
        for term in summary.terminology:
            md_lines.append(f"* **{term.term}**：{term.definition}")
        md_lines.append("")
    
    return "\n".join(md_lines)


def export_schema_definitions() -> Dict[str, Any]:
    """Export all schema definitions for external use."""
    return {
        "version": get_schema_version(),
        "schemas": {
            "chunk_summary": CHUNK_SUMMARY_SCHEMA,
            "summary": SUMMARY_SCHEMA,
            "tags": TAGS_SCHEMA
        },
        "dataclass_names": {
            "ChunkSummary": "ChunkSummary",
            "StructuredSummary": "StructuredSummary",
            "Tags": "Tags",
            "PaperInfo": "PaperInfo",
            "Innovation": "Innovation",
            "Results": "Results",
            "TermDefinition": "TermDefinition"
        }
    }
