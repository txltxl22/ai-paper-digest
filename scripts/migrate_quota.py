#!/usr/bin/env python3
"""
Migration script for the new tiered quota system.

This script migrates data from the old daily_limits.json format to the new quota_limits.json format.

Old format (data/daily_limits.json):
{
  "127.0.0.1": {"date": "2025-12-20", "count": 3},
  "192.168.1.1": {"date": "2025-12-20", "count": 1}
}

New format (data/quota_limits.json):
{
  "daily": {
    "ip:127.0.0.1": {"date": "2025-12-20", "count": 3},
    "ip:192.168.1.1": {"date": "2025-12-20", "count": 1}
  },
  "pro_quota": {}
}

Usage:
    python scripts/migrate_quota.py [--dry-run] [--data-dir DATA_DIR]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


def migrate_quota(data_dir: Path, dry_run: bool = False) -> dict:
    """
    Migrate from old daily_limits.json to new quota_limits.json format.
    
    Args:
        data_dir: Path to the data directory
        dry_run: If True, only show what would be done without making changes
        
    Returns:
        Migration result dict with statistics
    """
    old_file = data_dir / "daily_limits.json"
    new_file = data_dir / "quota_limits.json"
    
    result = {
        "migrated_entries": 0,
        "skipped_entries": 0,
        "old_file_exists": old_file.exists(),
        "new_file_exists": new_file.exists(),
        "errors": []
    }
    
    # Check if old file exists
    if not old_file.exists():
        print(f"ℹ️  No old daily_limits.json found at {old_file}")
        print("   Nothing to migrate.")
        return result
    
    # Load old data
    try:
        with open(old_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except Exception as e:
        result["errors"].append(f"Failed to load old file: {e}")
        print(f"❌ Error loading {old_file}: {e}")
        return result
    
    print(f"📂 Found {len(old_data)} entries in old daily_limits.json")
    
    # Prepare new data structure
    new_data = {
        "daily": {},
        "pro_quota": {}
    }
    
    # Load existing new file if it exists
    if new_file.exists():
        try:
            with open(new_file, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            print(f"📂 Existing quota_limits.json has {len(new_data.get('daily', {}))} daily entries")
        except Exception as e:
            print(f"⚠️  Warning: Could not load existing quota_limits.json: {e}")
            print("   Will create fresh file.")
    
    # Migrate entries
    for ip, entry in old_data.items():
        # Skip entries that already have the new prefix format
        if ip.startswith("ip:") or ip.startswith("user:"):
            result["skipped_entries"] += 1
            continue
        
        # Add ip: prefix
        new_key = f"ip:{ip}"
        
        # Skip if already exists in new file
        if new_key in new_data.get("daily", {}):
            print(f"   ⏭️  Skipping {ip} (already exists as {new_key})")
            result["skipped_entries"] += 1
            continue
        
        # Migrate
        new_data["daily"][new_key] = entry
        result["migrated_entries"] += 1
        print(f"   ✅ Migrated {ip} → {new_key}")
    
    # Save new file
    if not dry_run:
        try:
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Saved {len(new_data['daily'])} entries to {new_file}")
            
            # Optionally backup and remove old file
            backup_file = data_dir / f"daily_limits.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            old_file.rename(backup_file)
            print(f"📦 Backed up old file to {backup_file}")
            
        except Exception as e:
            result["errors"].append(f"Failed to save new file: {e}")
            print(f"❌ Error saving {new_file}: {e}")
    else:
        print("\n🔍 DRY RUN - No changes made")
        print(f"   Would save {len(new_data['daily'])} entries to {new_file}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Migrate from old daily_limits.json to new quota_limits.json format"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Path to data directory (default: ./data)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Quota Migration Tool")
    print("=" * 50)
    print(f"Data directory: {args.data_dir}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    result = migrate_quota(args.data_dir, args.dry_run)
    
    print()
    print("📊 Migration Summary:")
    print(f"   - Migrated entries: {result['migrated_entries']}")
    print(f"   - Skipped entries: {result['skipped_entries']}")
    print(f"   - Errors: {len(result['errors'])}")
    
    if result["errors"]:
        print("\n❌ Errors encountered:")
        for error in result["errors"]:
            print(f"   - {error}")
        sys.exit(1)
    
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    main()

