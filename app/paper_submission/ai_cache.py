import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, List

# Global cache for AI judgment results
_AI_JUDGMENT_CACHE = {}


class AICacheManager:
    """Manages AI judgment cache for paper submissions."""
    
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self._load_cache()
    
    def _load_cache(self):
        """Load AI judgment cache from file."""
        global _AI_JUDGMENT_CACHE
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    _AI_JUDGMENT_CACHE = json.load(f)
            else:
                _AI_JUDGMENT_CACHE = {}
        except Exception as e:
            print(f"Error loading AI cache: {e}")
            _AI_JUDGMENT_CACHE = {}
    
    def _save_cache(self):
        """Save AI judgment cache to file."""
        try:
            # Ensure directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(_AI_JUDGMENT_CACHE, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving AI cache: {e}")
    
    def get_cached_result(self, cache_key: str) -> Tuple[bool, float, List[str]]:
        """Get cached AI judgment result."""
        if cache_key in _AI_JUDGMENT_CACHE:
            cached_result = _AI_JUDGMENT_CACHE[cache_key]
            return (
                cached_result['is_ai'], 
                cached_result['confidence'], 
                cached_result.get('tags', [])
            )
        return None
    
    def cache_result(self, cache_key: str, is_ai: bool, confidence: float, tags: List[str]):
        """Cache AI judgment result."""
        _AI_JUDGMENT_CACHE[cache_key] = {
            'is_ai': is_ai,
            'confidence': confidence,
            'tags': tags,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get AI cache statistics for maintenance."""
        try:
            return {
                "cache_size": len(_AI_JUDGMENT_CACHE),
                "cache_file": str(self.cache_file),
                "cache_file_exists": self.cache_file.exists(),
                "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
                "sample_entries": list(_AI_JUDGMENT_CACHE.keys())[:5] if _AI_JUDGMENT_CACHE else []
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear AI cache for maintenance."""
        global _AI_JUDGMENT_CACHE
        try:
            _AI_JUDGMENT_CACHE.clear()
            self._save_cache()
            return {"success": True, "message": "AI cache cleared successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_cache_entry(self, url_or_hash: str) -> Dict[str, Any]:
        """Get specific AI cache entry for maintenance."""
        try:
            if url_or_hash in _AI_JUDGMENT_CACHE:
                return {
                    "found": True,
                    "entry": _AI_JUDGMENT_CACHE[url_or_hash]
                }
            else:
                return {
                    "found": False,
                    "message": "Entry not found in cache"
                }
        except Exception as e:
            return {"error": str(e)}
    
    def reload_cache(self) -> Dict[str, Any]:
        """Reload AI cache from file for maintenance."""
        try:
            self._load_cache()
            return {
                "success": True, 
                "message": "AI cache reloaded successfully",
                "cache_size": len(_AI_JUDGMENT_CACHE)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
