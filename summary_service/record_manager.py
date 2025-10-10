"""
Service Record Management for Paper Summaries

This module provides functionality for creating, saving, and loading paper summary
service records with metadata about the summarization process.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, Union

from .models import (
    StructuredSummary, Tags, ServiceRecord, SummaryRecord,
    parse_summary, parse_tags, summary_to_dict, tags_to_dict,
)


def create_service_record(arxiv_id: str, source_type: str = "system", user_id: str = None, 
                         original_url: str = None, ai_judgment: dict = None, 
                         first_created_at: str = None) -> dict:
    """Create a service record for a paper summary.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        source_type: Either "system" (from background processing) or "user" (user upload)
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
    
    Returns:
        Service record dictionary
    """
    current_time = datetime.now().isoformat()
    
    record = {
        "service_data": {
            "arxiv_id": arxiv_id,
            "source_type": source_type,  # "system" or "user"
            "created_at": current_time,  # Current submission time
            "first_created_at": first_created_at or current_time,  # Original creation time
            "original_url": original_url,
            "ai_judgment": ai_judgment or {}
        }
    }
    
    if source_type == "user" and user_id:
        record["service_data"]["user_id"] = user_id
    
    return record


def save_summary_with_service_record(arxiv_id: str, summary_content: Union[str, StructuredSummary], 
                                   tags: Union[dict, Tags], summary_dir: Path, 
                                   source_type: str = "system", user_id: str = None, 
                                   original_url: str = None, ai_judgment: dict = None, 
                                   first_created_at: str = None):
    """Save a summary with its service record in JSON format.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_content: The summary content (markdown string or StructuredSummary object)
        tags: Tags dictionary or Tags object
        summary_dir: Directory where summaries are stored
        source_type: Either "system" or "user"
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
    """
    # Create the combined record
    record = create_service_record(arxiv_id, source_type, user_id, original_url, ai_judgment, first_created_at)
    
    # Handle different input types
    if isinstance(summary_content, StructuredSummary):
        summary_dict = summary_to_dict(summary_content)
        markdown_content = summary_content.to_markdown()
    else:
        # Assume it's a markdown string - try to parse as structured JSON first
        try:
            summary_dict = json.loads(summary_content)
            markdown_content = summary_content  # Keep original for backward compatibility
        except (json.JSONDecodeError, ValueError):
            # It's plain markdown - don't put markdown in structured_content
            summary_dict = {}  # Empty structured content for legacy markdown
            markdown_content = summary_content
    
    if isinstance(tags, Tags):
        tags_dict = tags_to_dict(tags)
    else:
        tags_dict = tags
    
    record["summary_data"] = {
        "structured_content": summary_dict,
        "markdown_content": markdown_content,
        "tags": tags_dict,
        "updated_at": datetime.now().isoformat()
    }
    
    # Save as JSON file
    json_path = summary_dir / f"{arxiv_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    # Also save the legacy .md and .tags.json files for backward compatibility
    md_path = summary_dir / f"{arxiv_id}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    tags_path = summary_dir / f"{arxiv_id}.tags.json"
    with open(tags_path, 'w', encoding='utf-8') as f:
        json.dump(tags_dict, f, ensure_ascii=False, indent=2)


def load_summary_with_service_record(arxiv_id: str, summary_dir: Path) -> Optional[Dict[str, Any]]:
    """Load a summary with its service record.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        Dictionary containing service_data and summary_data, or None if not found
    """
    json_path = summary_dir / f"{arxiv_id}.json"
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                record = json.load(f)
                
            # Handle new structured format
            if "summary_data" in record and "structured_content" in record["summary_data"]:
                return record
            
            # Handle legacy format
            return record
        except Exception as e:
            print(f"Error loading service record for {arxiv_id}: {e}")
    
    # Fallback to legacy format
    return load_legacy_summary(arxiv_id, summary_dir)


def load_legacy_summary(arxiv_id: str, summary_dir: Path) -> Optional[Dict[str, Any]]:
    """Load a summary in legacy format (separate .md and .tags.json files).
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        Dictionary with service_data and summary_data, defaulting to system source
    """
    md_path = summary_dir / f"{arxiv_id}.md"
    tags_path = summary_dir / f"{arxiv_id}.tags.json"
    
    if not md_path.exists():
        return None
    
    try:
        # Load summary content
        summary_content = md_path.read_text(encoding='utf-8')
        
        # Load tags
        tags = {"top": [], "tags": []}
        if tags_path.exists():
            try:
                tags = json.loads(tags_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        
        # Create service record with default system source
        service_record = create_service_record(arxiv_id, "system")
        
        return {
            "service_data": service_record["service_data"],
            "summary_data": {
                "structured_content": {"content": summary_content},
                "markdown_content": summary_content,
                "tags": tags,
                "updated_at": datetime.fromtimestamp(md_path.stat().st_mtime).isoformat()
            }
        }
    except Exception as e:
        print(f"Error loading legacy summary for {arxiv_id}: {e}")
        return None


def get_structured_summary(arxiv_id: str, summary_dir: Path) -> Optional[StructuredSummary]:
    """Get structured summary object for a paper.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        StructuredSummary object or None if not found
    """
    record = load_summary_with_service_record(arxiv_id, summary_dir)
    if not record or "summary_data" not in record:
        return None
    
    summary_data = record["summary_data"]
    
    # Try to parse structured content
    if "structured_content" in summary_data:
        structured_content = summary_data["structured_content"]
        
        # Check if it's already a structured summary
        if isinstance(structured_content, dict) and "paper_info" in structured_content:
            try:
                return parse_summary(json.dumps(structured_content))
            except Exception:
                pass
    
    # Fallback to markdown content
    if "markdown_content" in summary_data:
        # For now, return None since we can't easily parse markdown back to structured format
        # In the future, we could implement markdown to structured conversion
        return None
    
    return None


def get_tags(arxiv_id: str, summary_dir: Path) -> Optional[Tags]:
    """Get tags object for a paper.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        Tags object or None if not found
    """
    record = load_summary_with_service_record(arxiv_id, summary_dir)
    if not record or "summary_data" not in record:
        return None
    
    summary_data = record["summary_data"]
    
    if "tags" in summary_data:
        try:
            return parse_tags(json.dumps(summary_data["tags"]))
        except Exception:
            pass
    
    return None


def migrate_legacy_summaries_to_service_record(summary_dir: Path) -> Dict[str, Any]:
    """Migrate all legacy summaries (.md + .tags.json) to new service record format.
    
    This function scans for legacy format summaries and creates service records for them
    with update times based on the file creation time.
    
    Args:
        summary_dir: Directory where summaries are stored
    
    Returns:
        Dictionary with migration statistics
    """
    migration_stats = {
        "total_legacy_files": 0,
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }
    
    # Find all .md files that don't have corresponding .json files
    md_files = list(summary_dir.glob("*.md"))
    
    for md_path in md_files:
        arxiv_id = md_path.stem
        json_path = summary_dir / f"{arxiv_id}.json"
        
        # Skip if service record already exists
        if json_path.exists():
            migration_stats["skipped"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "skipped",
                "reason": "service record already exists"
            })
            continue
        
        migration_stats["total_legacy_files"] += 1
        
        try:
            # Load summary content
            summary_content = md_path.read_text(encoding="utf-8")
            
            # Load tags if available
            tags_path = summary_dir / f"{arxiv_id}.tags.json"
            tags = {"top": [], "tags": []}
            if tags_path.exists():
                try:
                    tags = json.loads(tags_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            
            # Create service record with file creation time as update time
            service_record = create_service_record(arxiv_id, "system")
            
            # Use file creation time for updated_at
            file_creation_time = datetime.fromtimestamp(md_path.stat().st_mtime)
            
            record = {
                "service_data": service_record["service_data"],
                "summary_data": {
                    "structured_content": {"content": summary_content},
                    "markdown_content": summary_content,
                    "tags": tags,
                    "updated_at": file_creation_time.isoformat()
                }
            }
            
            # Save the new service record
            json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            
            migration_stats["migrated"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "migrated",
                "update_time": file_creation_time.isoformat()
            })
            
        except Exception as e:
            migration_stats["errors"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "error",
                "error": str(e)
            })
    
    return migration_stats


def check_paper_processed_globally(paper_url: str, summary_dir: Path) -> bool:
    """Check if a paper has been processed globally by looking in the summary directory.
    
    Args:
        paper_url: The URL of the paper to check
        summary_dir: Directory where summaries are stored
        
    Returns:
        True if the paper has been processed and summary exists, False otherwise
    """
    try:
        from .paper_info_extractor import extract_arxiv_id
        import hashlib
        
        # Extract arXiv ID from URL using the centralized method
        arxiv_id = extract_arxiv_id(paper_url)
        
        # If we couldn't extract arXiv ID, use a hash of the URL as fallback
        if arxiv_id is None:
            arxiv_id = hashlib.md5(paper_url.encode()).hexdigest()[:8]
        
        # Check if summary file exists
        summary_file = summary_dir / f"{arxiv_id}.json"
        return summary_file.exists()
        
    except Exception as e:
        # Log error but don't fail - return False to allow processing to continue
        print(f"Error checking if paper processed globally: {e}")
        return False
