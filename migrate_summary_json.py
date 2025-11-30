#!/usr/bin/env python3
"""
Migration script for summary JSON files to match new Pydantic model structure.

This script fixes structural issues in existing summary JSON files:
- Removes invalid 'abstract' field from service_data
- Ensures all required ServiceRecord fields are present
- Validates and fixes tags structure
- Reports migration statistics
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from summary_service.models import SummaryRecord, ServiceRecord, Tags
from config_manager import ConfigManager


def fix_service_data(service_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fix service_data to match ServiceRecord model.
    
    Args:
        service_data: Original service_data dictionary
        
    Returns:
        Fixed service_data dictionary
    """
    fixed = service_data.copy()
    
    # Remove invalid 'abstract' field (abstract belongs in paper_info, not service_data)
    if 'abstract' in fixed:
        del fixed['abstract']
    
    # Ensure first_created_at exists (use created_at if missing)
    if 'first_created_at' not in fixed or not fixed['first_created_at']:
        if 'created_at' in fixed:
            fixed['first_created_at'] = fixed['created_at']
        else:
            fixed['first_created_at'] = datetime.now().isoformat()
    
    # Ensure is_abstract_only exists (default to False)
    if 'is_abstract_only' not in fixed:
        fixed['is_abstract_only'] = False
    
    # Ensure ai_judgment exists (default to None or empty dict)
    if 'ai_judgment' not in fixed:
        fixed['ai_judgment'] = None
    
    return fixed


def fix_tags(tags: Any) -> Dict[str, List[str]]:
    """Fix tags structure to match Tags model.
    
    Args:
        tags: Original tags (can be dict, list, or other)
        
    Returns:
        Fixed tags dictionary with 'top' and 'tags' lists
    """
    if isinstance(tags, dict):
        # Ensure it has the right structure
        fixed = {
            'top': tags.get('top', []) if isinstance(tags.get('top'), list) else [],
            'tags': tags.get('tags', []) if isinstance(tags.get('tags'), list) else []
        }
        return fixed
    elif isinstance(tags, list):
        # If it's a list, put it in 'tags' field
        return {'top': [], 'tags': tags}
    else:
        # Default empty structure
        return {'top': [], 'tags': []}


def migrate_summary_file(json_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Migrate a single summary JSON file.
    
    Args:
        json_path: Path to the JSON file
        dry_run: If True, don't save changes
        
    Returns:
        Dictionary with migration result
    """
    arxiv_id = json_path.stem
    result = {
        'arxiv_id': arxiv_id,
        'status': 'unknown',
        'changes': [],
        'error': None
    }
    
    try:
        # Load JSON data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        
        # Check if it's the old format with 'content' field
        if 'summary_data' in data and 'content' in data['summary_data']:
            result['status'] = 'skipped'
            result['error'] = 'Old format with content field - requires manual migration'
            return result
        
        # Check for issues and fix them
        needs_fix = False
        
        # Check for abstract in service_data
        if 'service_data' in data and 'abstract' in data['service_data']:
            needs_fix = True
            result['changes'].append("Removed 'abstract' from service_data")
        
        # Check for missing required fields
        if 'service_data' in data:
            if 'first_created_at' not in data['service_data'] or not data['service_data'].get('first_created_at'):
                needs_fix = True
                result['changes'].append("Added missing 'first_created_at' field")
            
            if 'is_abstract_only' not in data['service_data']:
                needs_fix = True
                result['changes'].append("Added missing 'is_abstract_only' field")
        
        # Try to validate with SummaryRecord
        validation_passed = False
        try:
            record = SummaryRecord.model_validate(data)
            validation_passed = True
            if not needs_fix:
                result['status'] = 'ok'
                return result
        except Exception as e:
            # Validation failed, need to fix structure
            result['changes'].append(f"Validation failed: {str(e)[:100]}")
        
        # Fix service_data
        if 'service_data' in data:
            data['service_data'] = fix_service_data(data['service_data'])
            if not validation_passed or needs_fix:
                result['changes'].append("Fixed service_data structure")
        
        # Fix tags if needed
        if 'summary_data' in data and 'tags' in data['summary_data']:
            original_tags = data['summary_data']['tags']
            fixed_tags = fix_tags(original_tags)
            if fixed_tags != original_tags:
                data['summary_data']['tags'] = fixed_tags
                result['changes'].append("Fixed tags structure")
        
        # Try to validate again
        try:
            record = SummaryRecord.model_validate(data)
            result['status'] = 'fixed'
            
            # Save if not dry run
            if not dry_run:
                new_data = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
                if new_data != original_data:
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    result['status'] = 'saved'
                else:
                    result['status'] = 'fixed'  # Fixed but no changes needed to save
            else:
                result['status'] = 'fixed (dry-run)'
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = f"Still invalid after fixes: {str(e)}"
            return result
        
    except json.JSONDecodeError as e:
        result['status'] = 'error'
        result['error'] = f"Invalid JSON: {str(e)}"
    except Exception as e:
        result['status'] = 'error'
        result['error'] = f"Unexpected error: {str(e)}"
    
    return result


def main():
    """Main entry point for migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate summary JSON files to match new Pydantic model structure'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (don\'t save changes)'
    )
    parser.add_argument(
        '--summary-dir',
        type=str,
        default=None,
        help='Path to summary directory (default: from config)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Remove JSON and tags JSON files that cannot be migrated (skipped/error status). Works with --dry-run to preview what would be removed.'
    )
    args = parser.parse_args()
    
    # Get summary directory
    if args.summary_dir:
        summary_dir = Path(args.summary_dir)
    else:
        config = ConfigManager()
        paths_config = config.get_paths_config()
        summary_dir = Path(paths_config.summary_dir)
    
    if not summary_dir.exists():
        print(f"Error: Summary directory does not exist: {summary_dir}")
        sys.exit(1)
    
    print(f"Scanning summary directory: {summary_dir}")
    if args.dry_run:
        print("Running in DRY-RUN mode (changes will not be saved)")
    if args.clean:
        print("CLEAN mode enabled (will remove unmigratable files)")
    print()
    
    # Find all JSON files
    json_files = list(summary_dir.glob("*.json"))
    # Exclude files in subdirectories like chunks/
    json_files = [f for f in json_files if f.parent == summary_dir]
    
    if not json_files:
        print("No JSON files found in summary directory")
        return
    
    print(f"Found {len(json_files)} JSON files")
    print()
    
    # Migration statistics
    stats = {
        'total': len(json_files),
        'ok': 0,
        'fixed': 0,
        'saved': 0,
        'skipped': 0,
        'errors': 0,
        'cleaned': 0,
        'details': []
    }
    
    # Process each file
    for json_path in sorted(json_files):
        result = migrate_summary_file(json_path, dry_run=args.dry_run)
        stats['details'].append(result)
        
        status = result['status']
        if status == 'ok':
            stats['ok'] += 1
            print(f"✓ {result['arxiv_id']}: OK")
        elif status == 'fixed' or status == 'fixed (dry-run)':
            stats['fixed'] += 1
            print(f"✓ {result['arxiv_id']}: Fixed")
            if result['changes']:
                for change in result['changes']:
                    print(f"  - {change}")
        elif status == 'saved':
            stats['saved'] += 1
            print(f"✓ {result['arxiv_id']}: Fixed and saved")
            if result['changes']:
                for change in result['changes']:
                    print(f"  - {change}")
        elif status == 'skipped':
            stats['skipped'] += 1
            print(f"⊘ {result['arxiv_id']}: Skipped - {result.get('error', 'unknown reason')}")
            # Clean if requested
            if args.clean:
                arxiv_id = result['arxiv_id']
                json_file = summary_dir / f"{arxiv_id}.json"
                tags_file = summary_dir / f"{arxiv_id}.tags.json"
                if args.dry_run:
                    print(f"  → Would remove {arxiv_id}.json and {arxiv_id}.tags.json (dry-run)")
                    stats['cleaned'] += 1
                else:
                    try:
                        removed = False
                        if json_file.exists():
                            json_file.unlink()
                            removed = True
                        if tags_file.exists():
                            tags_file.unlink()
                            removed = True
                        if removed:
                            stats['cleaned'] += 1
                            print(f"  → Removed {arxiv_id}.json and {arxiv_id}.tags.json")
                    except Exception as e:
                        print(f"  → Error removing files: {e}")
        elif status == 'error':
            stats['errors'] += 1
            print(f"✗ {result['arxiv_id']}: Error - {result.get('error', 'unknown error')}")
            # Clean if requested
            if args.clean:
                arxiv_id = result['arxiv_id']
                json_file = summary_dir / f"{arxiv_id}.json"
                tags_file = summary_dir / f"{arxiv_id}.tags.json"
                if args.dry_run:
                    print(f"  → Would remove {arxiv_id}.json and {arxiv_id}.tags.json (dry-run)")
                    stats['cleaned'] += 1
                else:
                    try:
                        removed = False
                        if json_file.exists():
                            json_file.unlink()
                            removed = True
                        if tags_file.exists():
                            tags_file.unlink()
                            removed = True
                        if removed:
                            stats['cleaned'] += 1
                            print(f"  → Removed {arxiv_id}.json and {arxiv_id}.tags.json")
                    except Exception as e:
                        print(f"  → Error removing files: {e}")
    
    # Calculate success and failure counts
    success_count = stats['ok'] + stats['fixed'] + stats['saved']
    failure_count = stats['skipped'] + stats['errors']
    
    # Print summary
    print()
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Total files:     {stats['total']}")
    print()
    print("Success:")
    print(f"  ✓ OK (no changes): {stats['ok']}")
    print(f"  ✓ Fixed:           {stats['fixed']}")
    print(f"  ✓ Saved:           {stats['saved']}")
    print(f"  ─────────────────────────────")
    print(f"  Total Success:     {success_count}")
    print()
    print("Failure:")
    print(f"  ⊘ Skipped:         {stats['skipped']}")
    print(f"  ✗ Errors:          {stats['errors']}")
    print(f"  ─────────────────────────────")
    print(f"  Total Failure:     {failure_count}")
    print()
    if args.clean:
        print(f"Cleaned (removed):  {stats['cleaned']}")
        print()
    
    if stats['errors'] > 0:
        print("Files with errors:")
        for detail in stats['details']:
            if detail['status'] == 'error':
                print(f"  - {detail['arxiv_id']}: {detail.get('error', 'unknown')}")
        print()
    
    if stats['skipped'] > 0 and not args.clean:
        print("Skipped files (may need manual migration):")
        for detail in stats['details']:
            if detail['status'] == 'skipped':
                print(f"  - {detail['arxiv_id']}: {detail.get('error', 'unknown')}")
        print()


if __name__ == '__main__':
    main()

