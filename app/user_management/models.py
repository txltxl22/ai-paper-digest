"""
User management models and data structures.
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path
import json


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

        events = data.get("events")
        if not isinstance(events, list):
            events = []

        return {"read": read_map, "events": events}
    
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