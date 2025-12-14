# User Data Management Script

This script (`manage_user_data.py`) handles user data for the system, ensuring that the separate lists for favorites (interested papers), read (not interested papers), and todo (papers to read later) are properly maintained.

## Features

- **Data Validation**: Ensures all user data files have the correct structure
- **Overlap Resolution**: Removes conflicting entries between lists
- **Migration**: Adds missing sections and fixes data inconsistencies
- **Backup Creation**: Automatically creates backups before making changes
- **Statistics**: Provides detailed statistics about user data

## User Data Structure

Each user data file contains:

```json
{
  "read": {
    "paper_id": "timestamp",
    ...
  },
  "favorites": {
    "paper_id": "timestamp",
    ...
  },
  "todo": {
    "paper_id": "timestamp",
    ...
  },
  "events": [
    {
      "ts": "ISO8601 timestamp",
      "type": "event_type",
      "arxiv_id": "paper_id",
      "meta": {...},
      "path": "url_path",
      "ua": "user_agent"
    },
    ...
  ],
  "password_hash": "...",
  "uploaded_urls": [...]
}
```

## List Semantics

- **`read`**: Papers marked as "not interested" - these will be filtered out from main index
- **`favorites`**: Papers marked as "interested" - these will be shown in favorites/interested view
- **`todo`**: Papers to read later - these will be shown in todo view

## Conflict Resolution

The script ensures:
- A paper cannot be both "read" (not interested) and "favorites" (interested) - prioritizes favorites
- A paper cannot be both "read" (not interested) and "todo" - prioritizes todo
- A paper can be both "favorites" (interested) and "todo" (user wants to read favorite papers later)

## Usage

```bash
# Show statistics for all users
uv run python manage_user_data.py --stats

# Dry run migration (show what would be changed)
uv run python manage_user_data.py --dry-run

# Migrate all user data (make actual changes)
uv run python manage_user_data.py

# Process specific user file
uv run python manage_user_data.py --user-file user_data/username.json
```

## Options

- `--stats`: Show statistics for all user files
- `--dry-run`: Show what changes would be made without making them
- `--user-file PATH`: Process only the specified user file
- `--user-data-dir PATH`: Specify custom user data directory (default: user_data/)

## Backups

The script automatically creates timestamped backups in `user_data/backups/` before making any changes. Backup files are named `{username}_backup_{timestamp}.json`.

## Recent Changes

- Added `todo` list support
- Fixed overlap resolution logic
- Improved data validation
- Added comprehensive statistics
