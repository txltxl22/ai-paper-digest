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
    StructuredSummary, Tags, ServiceRecord, SummaryRecord, SummaryData,
    parse_tags,
)


def create_service_record(arxiv_id: str, source_type: str = "system", user_id: str = None, 
                         original_url: str = None, ai_judgment: dict = None, 
                         first_created_at: str = None,
                         is_abstract_only: bool = False) -> ServiceRecord:
    """Create a service record for a paper summary using Pydantic model.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        source_type: Either "system" (from background processing) or "user" (user upload)
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
        is_abstract_only: Whether this is an abstract-only summary
    
    Returns:
        ServiceRecord Pydantic model object
    """
    current_time = datetime.now().isoformat()
    
    return ServiceRecord(
        arxiv_id=arxiv_id,
        source_type=source_type,
        created_at=current_time,
        first_created_at=first_created_at or current_time,
        original_url=original_url,
        user_id=user_id if source_type == "user" else None,
        ai_judgment=ai_judgment or None,
        is_abstract_only=is_abstract_only
    )


def save_summary_with_service_record(arxiv_id: str, summary_content: StructuredSummary, 
                                   tags: Union[dict, Tags], summary_dir: Path, 
                                   source_type: str = "system", user_id: str = None, 
                                   original_url: str = None, ai_judgment: dict = None, 
                                   first_created_at: str = None,
                                   is_abstract_only: bool = False):
    """Save a summary with its service record in JSON format.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_content: The StructuredSummary object (contains PaperInfo with abstract)
        tags: Tags dictionary or Tags object
        summary_dir: Directory where summaries are stored
        source_type: Either "system" or "user"
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
        is_abstract_only: Whether this is an abstract-only summary
    """
    # Create the service record using Pydantic model
    # Abstract is stored in summary_content.paper_info.abstract, not in ServiceRecord
    service_record = create_service_record(arxiv_id, source_type, user_id, original_url, ai_judgment, first_created_at, is_abstract_only)
    
    # Convert tags to Tags object if needed
    if isinstance(tags, Tags):
        tags_obj = tags
    else:
        tags_obj = Tags.model_validate(tags)
    
    # Generate markdown content
    markdown_content = summary_content.to_markdown()
    
    # Build SummaryData using Pydantic models
    summary_data = SummaryData(
        structured_content=summary_content,  # StructuredSummary as Pydantic model
        markdown_content=markdown_content,
        tags=tags_obj,
        updated_at=datetime.now().isoformat()
    )
    
    # Build SummaryRecord
    record = SummaryRecord(
        service_data=service_record,
        summary_data=summary_data
    )
    
    # Save as JSON file using Pydantic's model_dump
    json_path = summary_dir / f"{arxiv_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(record.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
    
    # Also save the legacy .md and .tags.json files for backward compatibility
    md_path = summary_dir / f"{arxiv_id}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    tags_path = summary_dir / f"{arxiv_id}.tags.json"
    with open(tags_path, 'w', encoding='utf-8') as f:
        json.dump(tags_obj.model_dump(mode='json'), f, ensure_ascii=False, indent=2)


def load_summary_with_service_record(arxiv_id: str, summary_dir: Path) -> Optional[SummaryRecord]:
    """Load a summary with its service record as a Pydantic model.
    
    The model matches the saved JSON format exactly, so no conversion is needed.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        SummaryRecord object or None if not found
    """
    json_path = summary_dir / f"{arxiv_id}.json"
    if not json_path.exists():
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Use Pydantic's model_validate - the saved format matches SummaryRecord exactly
        return SummaryRecord.model_validate(data)
    except Exception as e:
        print(f"Error loading service record for {arxiv_id}: {e}")
        return None


def load_service_record(arxiv_id: str, summary_dir: Path) -> Optional[ServiceRecord]:
    """Load a ServiceRecord object from JSON file using Pydantic validation.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        ServiceRecord object or None if not found
    """
    record = load_summary_with_service_record(arxiv_id, summary_dir)
    if not record:
        return None
    
    return record.service_data


def load_summary_record(arxiv_id: str, summary_dir: Path) -> Optional[SummaryRecord]:
    """Load a SummaryRecord object from JSON file using Pydantic validation.
    
    Note: This requires the JSON structure to match SummaryRecord exactly.
    The current saved format may not match exactly, so this is for future use.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        SummaryRecord object or None if not found/invalid
    """
    json_path = summary_dir / f"{arxiv_id}.json"
    if not json_path.exists():
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Use Pydantic's model_validate_json for type-safe loading
        return SummaryRecord.model_validate(data)
    except Exception as e:
        print(f"Error parsing SummaryRecord for {arxiv_id}: {e}")
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
    if not record:
        return None
    
    return record.summary_data.structured_content


def get_tags(arxiv_id: str, summary_dir: Path) -> Optional[Tags]:
    """Get tags object for a paper.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_dir: Directory where summaries are stored
    
    Returns:
        Tags object or None if not found
    """
    record = load_summary_with_service_record(arxiv_id, summary_dir)
    if not record:
        return None
    
    try:
        return Tags.model_validate(record.summary_data.tags)
    except Exception:
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
                "service_data": service_record.model_dump(),
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


def update_service_record_abstract(arxiv_id: str, abstract: str, summary_dir: Path, english_title: str = None) -> bool:
    """Update the abstract and optionally English title in PaperInfo within summary_data.
    
    Uses Pydantic models to load, update, and save the record.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        abstract: The abstract text to save (updates PaperInfo in summary_data)
        summary_dir: Directory where summaries are stored
        english_title: The English title to save (optional, updates PaperInfo)
    
    Returns:
        True if successful, False otherwise
    """
    json_path = summary_dir / f"{arxiv_id}.json"
    
    if not json_path.exists():
        return False
    
    try:
        # Load existing record
        record = load_summary_with_service_record(arxiv_id, summary_dir)
        if not record:
            return False
        
        # Update StructuredSummary directly (it's already a Pydantic model)
        structured_summary = record.summary_data.structured_content
        structured_summary.paper_info.abstract = abstract
        if english_title:
            structured_summary.paper_info.title_en = english_title
        
        # Get tags (already a Tags object)
        tags = record.summary_data.tags
        
        # Re-save with updated data
        save_summary_with_service_record(
            arxiv_id=arxiv_id,
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type=record.service_data.source_type,
            user_id=record.service_data.user_id,
            original_url=record.service_data.original_url,
            ai_judgment=record.service_data.ai_judgment,
            first_created_at=record.service_data.first_created_at,
            is_abstract_only=record.service_data.is_abstract_only
        )
        
        return True
    except Exception as e:
        print(f"Error updating abstract for {arxiv_id}: {e}")
        return False


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
