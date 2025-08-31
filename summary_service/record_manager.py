"""
Service Record Management for Paper Summaries

This module provides functionality for creating, saving, and loading paper summary
service records with metadata about the summarization process.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any


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


def save_summary_with_service_record(arxiv_id: str, summary_content: str, tags: dict, 
                                   summary_dir: Path, source_type: str = "system", 
                                   user_id: str = None, original_url: str = None, 
                                   ai_judgment: dict = None, first_created_at: str = None):
    """Save a summary with its service record in JSON format.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_content: The markdown summary content
        tags: Tags dictionary with top and detail tags
        summary_dir: Directory where summaries are stored
        source_type: Either "system" or "user"
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
    """
    # Create the combined record
    record = create_service_record(arxiv_id, source_type, user_id, original_url, ai_judgment, first_created_at)
    record["summary_data"] = {
        "content": summary_content,
        "tags": tags,
        "updated_at": datetime.now().isoformat()
    }
    
    # Save as JSON file
    json_path = summary_dir / f"{arxiv_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    # Also save the legacy .md and .tags.json files for backward compatibility
    md_path = summary_dir / f"{arxiv_id}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(summary_content)
    
    tags_path = summary_dir / f"{arxiv_id}.tags.json"
    with open(tags_path, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


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
                return json.load(f)
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
                "content": summary_content,
                "tags": tags,
                "updated_at": datetime.fromtimestamp(md_path.stat().st_mtime).isoformat()
            }
        }
    except Exception as e:
        print(f"Error loading legacy summary for {arxiv_id}: {e}")
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
                    "content": summary_content,
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
