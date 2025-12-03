"""
JSON Schema definitions for validation.

This module contains the JSON schema definitions used for
validating structured data throughout the system.
"""

# JSON Schema definitions for validation
CHUNK_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "main_content": {"type": "string"},
        "innovations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "improvement": {"type": "string"},
                    "significance": {"type": "string"}
                },
                "required": ["title", "description", "improvement", "significance"]
            }
        },
        "key_terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"}
                },
                "required": ["term", "definition"]
            }
        }
    },
    "required": ["main_content", "innovations", "key_terms"]
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_info": {
            "type": "object",
            "properties": {
                "title_zh": {"type": "string"},
                "title_en": {"type": "string"},
                "abstract": {"type": "string"}
            },
            "required": ["title_zh", "title_en"]
        },
        "one_sentence_summary": {"type": "string"},
        "innovations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "improvement": {"type": "string"},
                    "significance": {"type": "string"}
                },
                "required": ["title", "description", "improvement", "significance"]
            }
        },
        "results": {
            "type": "object",
            "properties": {
                "experimental_highlights": {"type": "array", "items": {"type": "string"}},
                "practical_value": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["experimental_highlights", "practical_value"]
        },
        "terminology": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"}
                },
                "required": ["term", "definition"]
            }
        }
    },
    "required": ["paper_info", "one_sentence_summary"]
}

TAGS_SCHEMA = {
    "type": "object",
    "properties": {
        "top": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["top", "tags"]
}
