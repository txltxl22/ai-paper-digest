"""
User management models and data structures.
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import bcrypt


class UserData:
    """User data structure with backward compatibility."""
    
    def __init__(self, uid: str, user_data_dir: Path):
        self.uid = uid
        self.user_data_dir = user_data_dir
        self._user_file = user_data_dir / f"{uid}.json"
    
    def load(self) -> Dict[str, Any]:
        """Load full user data structure with backward compatibility.
        
        Shape:
        {
          "read": {arxiv_id: "YYYY-MM-DD" | null, ...},
          "favorites": {arxiv_id: "YYYY-MM-DD" | null, ...},
          "events": [ {"ts": ISO8601, "type": str, "arxiv_id": str|None, "meta": dict|None, "path": str|None, "ua": str|None}, ... ]
        }
        """
        try:
            data = json.loads(self._user_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        # migrate legacy list-based read
        raw_read = data.get("read", {})
        if isinstance(raw_read, list):
            read_map = {str(rid): None for rid in raw_read}
        elif isinstance(raw_read, dict):
            read_map = {str(k): v for k, v in raw_read.items()}
        else:
            read_map = {}

        # handle favorites
        raw_favorites = data.get("favorites", {})
        if isinstance(raw_favorites, dict):
            favorites_map = {str(k): v for k, v in raw_favorites.items()}
        else:
            favorites_map = {}

        events = data.get("events")
        if not isinstance(events, list):
            events = []

        # Preserve all other fields (like password_hash)
        result = {"read": read_map, "favorites": favorites_map, "events": events}
        
        # Add any other fields that exist in the data
        for key, value in data.items():
            if key not in result:
                result[key] = value
        
        return result
    
    def save(self, data: Dict[str, Any]) -> None:
        """Save user data to file."""
        self._user_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    
    def load_read_map(self) -> Dict[str, Optional[str]]:
        """Load read status map for the user."""
        data = self.load()
        return data.get("read", {})
    
    def save_read_map(self, read_map: Dict[str, Optional[str]]) -> None:
        """Persist read map, preserving other fields (like events)."""
        data = self.load()
        data["read"] = read_map
        self.save(data)
    
    def mark_as_read(self, arxiv_id: str) -> None:
        """Mark a paper as read with current timestamp."""
        read_map = self.load_read_map()
        read_map[str(arxiv_id)] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.save_read_map(read_map)
    
    def mark_as_unread(self, arxiv_id: str) -> None:
        """Mark a paper as unread."""
        read_map = self.load_read_map()
        read_map.pop(str(arxiv_id), None)
        self.save_read_map(read_map)
    
    def get_read_stats(self) -> Dict[str, int]:
        """Get read statistics for the user."""
        read_map = self.load_read_map()
        read_ids = set(read_map.keys())
        
        # Count how many read today
        today_iso = date.today().isoformat()
        read_today = 0
        for d in read_map.values():
            if not d:
                continue
            try:
                # match date prefix for both date-only and datetime strings
                if str(d).split('T', 1)[0] == today_iso:
                    read_today += 1
            except Exception:
                continue
        
        return {
            "read_total": len(read_ids),
            "read_today": read_today
        }
    
    def get_unread_count(self, total_entries: int) -> int:
        """Get count of unread papers."""
        read_map = self.load_read_map()
        read_ids = set(read_map.keys())
        return total_entries - len(read_ids)
    
    def load_favorites_map(self) -> Dict[str, Optional[str]]:
        """Load favorites map for the user."""
        data = self.load()
        return data.get("favorites", {})
    
    def save_favorites_map(self, favorites_map: Dict[str, Optional[str]]) -> None:
        """Persist favorites map, preserving other fields."""
        data = self.load()
        data["favorites"] = favorites_map
        self.save(data)
    
    def mark_as_favorite(self, arxiv_id: str) -> None:
        """Mark a paper as favorite with current timestamp."""
        favorites_map = self.load_favorites_map()
        favorites_map[str(arxiv_id)] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.save_favorites_map(favorites_map)
    
    def unmark_as_favorite(self, arxiv_id: str) -> None:
        """Remove a paper from favorites."""
        favorites_map = self.load_favorites_map()
        favorites_map.pop(str(arxiv_id), None)
        self.save_favorites_map(favorites_map)
    
    def get_favorites_stats(self) -> Dict[str, int]:
        """Get favorites statistics for the user."""
        favorites_map = self.load_favorites_map()
        favorites_ids = set(favorites_map.keys())
        
        # Count how many favorited today
        today_iso = date.today().isoformat()
        favorited_today = 0
        for d in favorites_map.values():
            if not d:
                continue
            try:
                # match date prefix for both date-only and datetime strings
                if str(d).split('T', 1)[0] == today_iso:
                    favorited_today += 1
            except Exception:
                continue
        
        return {
            "favorites_total": len(favorites_ids),
            "favorites_today": favorited_today
        }
    
    def migrate_legacy_records(self) -> None:
        """Migrate legacy records without timestamps to include current timestamp."""
        data = self.load()
        current_time = datetime.now().astimezone().isoformat(timespec="seconds")
        
        # Migrate read records
        read_map = data.get("read", {})
        updated_read = False
        for arxiv_id, timestamp in read_map.items():
            if timestamp is None:
                read_map[arxiv_id] = current_time
                updated_read = True
        
        # Migrate favorite records
        favorites_map = data.get("favorites", {})
        updated_favorites = False
        for arxiv_id, timestamp in favorites_map.items():
            if timestamp is None:
                favorites_map[arxiv_id] = current_time
                updated_favorites = True
        
        # Save if any updates were made
        if updated_read or updated_favorites:
            if updated_read:
                data["read"] = read_map
            if updated_favorites:
                data["favorites"] = favorites_map
            self.save(data)
    
    def set_password(self, password: str, bcrypt_rounds: int = None) -> None:
        """Set password for the user.
        
        Args:
            password: The password to set
            bcrypt_rounds: Optional bcrypt rounds (for testing). Default uses bcrypt default.
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        # Hash the password using bcrypt
        if bcrypt_rounds is not None:
            salt = bcrypt.gensalt(rounds=bcrypt_rounds)
        else:
            salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        data = self.load()
        data["password_hash"] = password_hash.decode('utf-8')
        self.save(data)
    
    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        data = self.load()
        password_hash = data.get("password_hash")
        
        if not password_hash:
            return False
        
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False
    
    def has_password(self) -> bool:
        """Check if the user has a password set."""
        data = self.load()
        return bool(data.get("password_hash"))
    
    def remove_password(self) -> None:
        """Remove the password for the user."""
        data = self.load()
        data.pop("password_hash", None)
        self.save(data)
    
    def load_todo_map(self) -> Dict[str, Optional[str]]:
        """Load todo map for the user."""
        data = self.load()
        return data.get("todo", {})
    
    def save_todo_map(self, todo_map: Dict[str, Optional[str]]) -> None:
        """Persist todo map, preserving other fields."""
        data = self.load()
        data["todo"] = todo_map
        self.save(data)
    
    def mark_as_todo(self, arxiv_id: str) -> None:
        """Mark a paper as todo with current timestamp."""
        todo_map = self.load_todo_map()
        todo_map[str(arxiv_id)] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.save_todo_map(todo_map)
    
    def unmark_as_todo(self, arxiv_id: str) -> None:
        """Remove a paper from todo list."""
        todo_map = self.load_todo_map()
        todo_map.pop(str(arxiv_id), None)
        self.save_todo_map(todo_map)
    
    def get_todo_stats(self) -> Dict[str, int]:
        """Get todo statistics for the user."""
        todo_map = self.load_todo_map()
        todo_ids = set(todo_map.keys())
        
        # Count how many added to todo today
        today_iso = date.today().isoformat()
        todo_today = 0
        for d in todo_map.values():
            if not d:
                continue
            try:
                # match date prefix for both date-only and datetime strings
                if str(d).split('T', 1)[0] == today_iso:
                    todo_today += 1
            except Exception:
                continue
        
        return {
            "todo_total": len(todo_ids),
            "todo_today": todo_today
        }