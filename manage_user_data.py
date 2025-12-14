#!/usr/bin/env python3
"""
User data management script for handling separate lists:
- favorites (interested papers)
- read (not interested papers)
- todo (papers to read later)

This script validates, migrates, and cleans up user data files.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UserDataManager:
    """Manages user data migration and validation."""

    def __init__(self, user_data_dir: Path):
        self.user_data_dir = user_data_dir
        self.backup_dir = user_data_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)

    def get_user_files(self) -> List[Path]:
        """Get all user data JSON files."""
        all_files = list(self.user_data_dir.glob("*.json"))

        # Skip non-user data files (these contain lists or other data)
        skip_files = {"page_views.json", "visitor_stats.json", "anonymous_sessions.json", "action_events.json"}
        user_files = [f for f in all_files if f.name not in skip_files and "backup" not in f.name]

        return user_files

    def backup_user_file(self, user_file: Path) -> Path:
        """Create a backup of a user file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{user_file.stem}_backup_{timestamp}.json"
        backup_path = self.backup_dir / backup_name

        backup_path.write_text(user_file.read_text(), encoding="utf-8")
        logger.info(f"Created backup: {backup_path}")
        return backup_path

    def validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize user data structure."""
        issues = []

        # Ensure required sections exist
        required_sections = ["read", "favorites", "todo", "events"]
        for section in required_sections:
            if section not in data:
                data[section] = {} if section != "events" else []
                issues.append(f"Added missing section: {section}")

        # Validate read section (should be dict)
        if not isinstance(data["read"], dict):
            if isinstance(data["read"], list):
                # Convert legacy list format to dict
                data["read"] = {str(rid): None for rid in data["read"]}
                issues.append("Converted legacy read list to dict format")
            else:
                data["read"] = {}
                issues.append("Fixed invalid read section")

        # Validate favorites section (should be dict)
        if not isinstance(data["favorites"], dict):
            data["favorites"] = {}
            issues.append("Fixed invalid favorites section")

        # Validate todo section (should be dict)
        if not isinstance(data["todo"], dict):
            data["todo"] = {}
            issues.append("Fixed invalid todo section")

        # Validate events section (should be list)
        if not isinstance(data["events"], list):
            data["events"] = []
            issues.append("Fixed invalid events section")

        # Ensure all paper IDs are strings
        for section in ["read", "favorites", "todo"]:
            section_data = data[section]
            if isinstance(section_data, dict):
                fixed_section = {}
                for key, value in section_data.items():
                    fixed_section[str(key)] = value
                if fixed_section != section_data:
                    data[section] = fixed_section
                    issues.append(f"Converted paper IDs to strings in {section}")

        # Check for overlapping entries between lists
        read_ids = set(data["read"].keys())
        favorite_ids = set(data["favorites"].keys())
        todo_ids = set(data["todo"].keys())

        overlap_read_fav = read_ids & favorite_ids
        overlap_read_todo = read_ids & todo_ids
        overlap_fav_todo = favorite_ids & todo_ids

        if overlap_read_fav:
            # Papers can't be both read (not interested) and favorite (interested)
            # Always prioritize favorites over read - remove from read
            for paper_id in overlap_read_fav:
                del data["read"][paper_id]
                issues.append(f"Removed {paper_id} from read (conflicts with favorite)")

        if overlap_read_todo:
            # Papers can't be both read (not interested) and todo
            # Always prioritize todo over read - remove from read
            for paper_id in overlap_read_todo:
                del data["read"][paper_id]
                issues.append(f"Removed {paper_id} from read (conflicts with todo)")

        if overlap_fav_todo:
            # Papers can't be both favorite and todo
            # This is allowed - user can mark favorite papers as todo too
            pass

        # Validate timestamps
        current_time = datetime.now(timezone.utc).isoformat()
        for section in ["read", "favorites", "todo"]:
            section_data = data[section]
            if isinstance(section_data, dict):
                for paper_id, timestamp in list(section_data.items()):
                    if timestamp is None:
                        # Add current timestamp for null values
                        section_data[paper_id] = current_time
                        issues.append(f"Added timestamp to {section}.{paper_id}")
                    elif isinstance(timestamp, str):
                        try:
                            # Validate timestamp format
                            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except ValueError:
                            section_data[paper_id] = current_time
                            issues.append(f"Fixed invalid timestamp for {section}.{paper_id}")

        # Validate events
        valid_events = []
        for event in data["events"]:
            if isinstance(event, dict) and "ts" in event and "type" in event:
                valid_events.append(event)
            else:
                issues.append(f"Removed invalid event: {event}")

        if len(valid_events) != len(data["events"]):
            data["events"] = valid_events
            issues.append(f"Cleaned up {len(data['events']) - len(valid_events)} invalid events")

        return data, issues

    def migrate_user_file(self, user_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate a single user file."""
        logger.info(f"Processing user file: {user_file}")

        try:
            data = json.loads(user_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load {user_file}: {e}")
            return {"error": str(e)}

        original_data = data.copy()

        # Validate and migrate data
        migrated_data, issues = self.validate_user_data(data)

        if issues:
            logger.info(f"Found {len(issues)} issues:")
            for issue in issues:
                logger.info(f"  - {issue}")

            if not dry_run:
                # Create backup
                self.backup_user_file(user_file)

                # Save migrated data
                user_file.write_text(
                    json.dumps(migrated_data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                logger.info(f"Migrated user file: {user_file}")
            else:
                logger.info("Dry run - no changes made")
        else:
            logger.info("User file is already valid")

        return {
            "file": str(user_file),
            "issues": issues,
            "changed": bool(issues),
            "dry_run": dry_run
        }

    def migrate_all_users(self, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate all user files."""
        user_files = self.get_user_files()
        results = []

        logger.info(f"Found {len(user_files)} user files")

        for user_file in user_files:
            # Skip backup files
            if "backup" in user_file.name:
                continue

            result = self.migrate_user_file(user_file, dry_run)
            results.append(result)

        # Summary
        changed_files = [r for r in results if r.get("changed", False)]
        total_issues = sum(len(r.get("issues", [])) for r in results)

        summary = {
            "total_files": len(results),
            "changed_files": len(changed_files),
            "total_issues": total_issues,
            "dry_run": dry_run,
            "results": results
        }

        logger.info(f"Migration complete: {summary['changed_files']}/{summary['total_files']} files changed, {summary['total_issues']} issues fixed")

        return summary

    def get_user_stats(self, user_file: Path) -> Dict[str, Any]:
        """Get statistics for a user file."""
        try:
            data = json.loads(user_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"error": "Failed to load file"}

        # Handle case where data might be a list or invalid format
        if not isinstance(data, dict):
            return {
                "file": str(user_file),
                "error": f"Invalid data structure: expected dict, got {type(data)}"
            }

        stats = {
            "file": str(user_file),
            "read_count": len(data.get("read", {})),
            "favorites_count": len(data.get("favorites", {})),
            "todo_count": len(data.get("todo", {})),
            "events_count": len(data.get("events", [])),
            "has_password": "password_hash" in data,
            "has_uploaded_urls": "uploaded_urls" in data
        }

        # Check for overlaps
        read_ids = set(data.get("read", {}).keys())
        favorite_ids = set(data.get("favorites", {}).keys())
        todo_ids = set(data.get("todo", {}).keys())

        stats["overlaps"] = {
            "read_and_favorites": len(read_ids & favorite_ids),
            "read_and_todo": len(read_ids & todo_ids),
            "favorites_and_todo": len(favorite_ids & todo_ids)
        }

        return stats

    def get_all_user_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all user files."""
        user_files = self.get_user_files()
        stats = []

        for user_file in user_files:
            # Skip backup files
            if "backup" in user_file.name:
                continue

            stat = self.get_user_stats(user_file)
            stats.append(stat)

        return stats


def main():
    parser = argparse.ArgumentParser(description="User data management script")
    parser.add_argument("--user-data-dir", type=Path, default=Path("user_data"),
                       help="Directory containing user data files")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be changed without making changes")
    parser.add_argument("--stats", action="store_true",
                       help="Show statistics for all user files")
    parser.add_argument("--user-file", type=Path,
                       help="Process only specific user file")

    args = parser.parse_args()

    manager = UserDataManager(args.user_data_dir)

    if args.stats:
        # Show statistics
        stats = manager.get_all_user_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    if args.user_file:
        # Process single file
        result = manager.migrate_user_file(args.user_file, args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Process all files
        summary = manager.migrate_all_users(args.dry_run)
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
