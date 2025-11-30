"""
Utility functions for schema management and data conversion.

This module contains functions for parsing, validating, and converting
structured summary data.
"""

from typing import Dict, Any
import json
from .summary_models import ChunkSummary, StructuredSummary, PaperInfo, Innovation, Results, TermDefinition
from .tags import Tags
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
    """Parse structured summary from JSON string using Pydantic validation."""
    try:
        cleaned_json = clean_json_response(json_str)
        data = json.loads(cleaned_json)
        if not validate_json_schema(data, SUMMARY_SCHEMA):
            raise ValueError("Invalid summary schema")
        
        # Use Pydantic's model_validate for type-safe parsing
        return StructuredSummary.model_validate(data)
    except Exception as e:
        raise ValueError(f"Failed to parse summary: {e}")


def parse_tags(json_str: str) -> Tags:
    """Parse tags from JSON string using Pydantic model validation."""
    try:
        # Clean up the response first
        cleaned_json = clean_json_response(json_str)
        
        # Use Pydantic's model_validate_json for better validation and error handling
        return Tags.model_validate_json(cleaned_json)
    except Exception as e:
        raise ValueError(f"Failed to parse tags: {e}")


