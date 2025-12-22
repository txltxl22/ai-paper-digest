"""
Trending service for analyzing tag trends over time periods.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter


class TrendingService:
    """Service for calculating trending tags based on paper submission dates."""
    
    def __init__(self, entry_scanner):
        """
        Initialize TrendingService.
        
        Args:
            entry_scanner: EntryScanner instance to get entries metadata
        """
        self.entry_scanner = entry_scanner
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
    
    def _get_entries_in_period(self, entries_meta: List[Dict], days: int) -> List[Dict]:
        """Filter entries to those within the specified time period."""
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = []
        for entry in entries_meta:
            submission_time = entry.get("submission_time")
            if submission_time:
                # Handle both datetime objects and None
                if isinstance(submission_time, datetime):
                    if submission_time >= cutoff:
                        filtered.append(entry)
        return filtered
    
    def _aggregate_tags(self, entries: List[Dict], include_top: bool = True) -> Counter:
        """Aggregate tag counts from entries."""
        tag_counter = Counter()
        
        for entry in entries:
            # Count detail tags
            detail_tags = entry.get("detail_tags", [])
            for tag in detail_tags:
                tag_counter[tag] += 1
            
            # Optionally include top tags
            if include_top:
                top_tags = entry.get("top_tags", [])
                for tag in top_tags:
                    tag_counter[tag] += 1
        
        return tag_counter
    
    def get_trending_tags(
        self, 
        period_days: int = 7, 
        limit: int = 20,
        include_growth: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get trending tags for the specified time period.
        
        Args:
            period_days: Number of days to analyze (default 7)
            limit: Maximum number of tags to return (default 20)
            include_growth: Whether to calculate growth compared to previous period
        
        Returns:
            List of tag dictionaries with name, count, and optional growth info
        """
        # Check cache
        cache_key = f"{period_days}_{limit}_{include_growth}"
        if (
            self._cache_time 
            and datetime.now() - self._cache_time < self._cache_ttl
            and cache_key in self._cache
        ):
            return self._cache[cache_key]
        
        # Get all entries
        all_entries = self.entry_scanner.scan_entries_meta()
        
        # Get entries in current period
        current_entries = self._get_entries_in_period(all_entries, period_days)
        current_tags = self._aggregate_tags(current_entries)
        
        # Get entries in previous period for growth calculation
        previous_tags = Counter()
        if include_growth:
            # Get entries from the period before (e.g., 7-14 days ago for 7-day period)
            cutoff_start = datetime.now() - timedelta(days=period_days * 2)
            cutoff_end = datetime.now() - timedelta(days=period_days)
            
            previous_entries = []
            for entry in all_entries:
                submission_time = entry.get("submission_time")
                if submission_time and isinstance(submission_time, datetime):
                    if cutoff_start <= submission_time < cutoff_end:
                        previous_entries.append(entry)
            
            previous_tags = self._aggregate_tags(previous_entries)
        
        # Build result list
        result = []
        for tag, count in current_tags.most_common(limit):
            tag_data = {
                "name": tag,
                "count": count,
            }
            
            if include_growth:
                prev_count = previous_tags.get(tag, 0)
                growth_data = self._calculate_growth(count, prev_count)
                tag_data.update(growth_data)
            
            result.append(tag_data)
        
        # Update cache
        self._cache[cache_key] = result
        self._cache_time = datetime.now()
        
        return result
    
    def _calculate_growth(self, current: int, previous: int) -> Dict[str, Any]:
        """
        Calculate growth metrics between two periods.
        
        Args:
            current: Current period count
            previous: Previous period count
        
        Returns:
            Dictionary with growth_percent, growth_direction, growth_diff
        """
        if previous == 0:
            if current > 0:
                return {
                    "growth_percent": 100,
                    "growth_direction": "up",
                    "growth_diff": current,
                    "is_new": True
                }
            return {
                "growth_percent": 0,
                "growth_direction": "neutral",
                "growth_diff": 0,
                "is_new": False
            }
        
        diff = current - previous
        percent = round((diff / previous) * 100)
        
        if diff > 0:
            direction = "up"
        elif diff < 0:
            direction = "down"
        else:
            direction = "neutral"
        
        return {
            "growth_percent": abs(percent),
            "growth_direction": direction,
            "growth_diff": diff,
            "is_new": False
        }
    
    def get_trending_summary(self) -> Dict[str, Any]:
        """
        Get a summary of trending data for multiple periods.
        
        Returns:
            Dictionary with trending data for 7-day and 30-day periods
        """
        return {
            "period_7d": self.get_trending_tags(period_days=7, limit=15),
            "period_30d": self.get_trending_tags(period_days=30, limit=15),
            "generated_at": datetime.now().isoformat()
        }
    
    def clear_cache(self):
        """Clear the trending cache."""
        self._cache = {}
        self._cache_time = None

