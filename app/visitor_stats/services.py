"""
Visitor Stats Service

Provides analytics and statistics functionality for admin users.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter

from .models import VisitorStats, PageView, ActionEvent


class VisitorStatsService:
    """Service for managing visitor statistics and analytics."""
    
    def __init__(self, user_data_dir: Path):
        """Initialize the visitor stats service.
        
        Args:
            user_data_dir: Directory containing user data and event tracking files
        """
        self.user_data_dir = user_data_dir
        self.stats_file = user_data_dir / "visitor_stats.json"
        self.page_views_file = user_data_dir / "page_views.json"
        self.action_events_file = user_data_dir / "action_events.json"
        self.anonymous_sessions_file = user_data_dir / "anonymous_sessions.json"
        
        # Ensure files exist
        self._ensure_files_exist()
    
    def _parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """Parse user agent string to extract browser and device information.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Dictionary with browser, os, and device information
        """
        if not user_agent:
            return {"browser": "Unknown", "os": "Unknown", "device": "Unknown"}
        
        browser = "Unknown"
        os_info = "Unknown"
        device = "Desktop"
        
        # Browser detection
        if "Chrome" in user_agent and "Edg" not in user_agent:
            browser = "Chrome"
        elif "Firefox" in user_agent:
            browser = "Firefox"
        elif "Safari" in user_agent and "Chrome" not in user_agent:
            browser = "Safari"
        elif "Edg" in user_agent:
            browser = "Edge"
        elif "Opera" in user_agent or "OPR" in user_agent:
            browser = "Opera"
        
        # OS detection
        if "Windows" in user_agent:
            os_info = "Windows"
        elif "Mac OS X" in user_agent or "MacOS" in user_agent:
            os_info = "macOS"
        elif "Linux" in user_agent:
            os_info = "Linux"
        elif "Android" in user_agent:
            os_info = "Android"
        elif "iPhone" in user_agent or "iPad" in user_agent:
            os_info = "iOS"
        
        # Device detection
        if "Mobile" in user_agent or "Android" in user_agent:
            device = "Mobile"
        elif "Tablet" in user_agent or "iPad" in user_agent:
            device = "Tablet"
        elif "iPhone" in user_agent:
            device = "Mobile"
        
        return {
            "browser": browser,
            "os": os_info,
            "device": device
        }
    
    def _ensure_files_exist(self):
        """Ensure all required files exist."""
        for file_path in [self.stats_file, self.page_views_file, self.action_events_file, self.anonymous_sessions_file]:
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
    
    def _generate_anonymous_id(self, ip_address: str, user_agent: str) -> str:
        """Generate a unique anonymous ID based on IP and user agent.
        
        Args:
            ip_address: IP address of the visitor
            user_agent: User agent string
            
        Returns:
            Anonymous ID string
        """
        import hashlib
        # Create a hash from IP + user agent + some salt
        combined = f"{ip_address}:{user_agent}:anonymous_salt"
        return f"anon_{hashlib.md5(combined.encode()).hexdigest()[:12]}"
    
    def _get_or_create_anonymous_id(self, ip_address: str, user_agent: str, session_id: Optional[str] = None) -> str:
        """Get or create an anonymous visitor ID.
        
        Args:
            ip_address: IP address of the visitor
            user_agent: User agent string
            session_id: Optional session ID from cookie
            
        Returns:
            Anonymous visitor ID
        """
        if not session_id:
            return self._generate_anonymous_id(ip_address, user_agent)
        
        # Check if we have this session ID
        sessions = self._load_anonymous_sessions()
        for session in sessions:
            if session.get('session_id') == session_id:
                return session['anonymous_id']
        
        # Create new anonymous ID and session
        anonymous_id = self._generate_anonymous_id(ip_address, user_agent)
        new_session = {
            'session_id': session_id,
            'anonymous_id': anonymous_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'created_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        
        sessions.append(new_session)
        self._save_anonymous_sessions(sessions)
        
        return anonymous_id
    
    def track_page_view(self, user_id: str, page: str, referrer: Optional[str] = None, 
                       user_agent: Optional[str] = None, ip_address: Optional[str] = None,
                       session_id: Optional[str] = None):
        """Track a page view.
        
        Args:
            user_id: The user ID (can be 'anonymous' for non-logged users)
            page: The page being viewed
            referrer: The referring page
            user_agent: User agent string
            ip_address: IP address
            session_id: Session ID for anonymous users
        """
        # Handle anonymous users
        if user_id == 'anonymous' and ip_address and user_agent:
            user_id = self._get_or_create_anonymous_id(ip_address, user_agent, session_id)
        
        # Parse user agent for device information
        device_info = self._parse_user_agent(user_agent) if user_agent else {}
        
        page_view = PageView(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            page=page,
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address,
            browser=device_info.get('browser'),
            os=device_info.get('os'),
            device=device_info.get('device')
        )
        
        # Load existing page views
        page_views = self._load_page_views()
        page_views.append(page_view.to_dict())
        
        # Save updated page views
        self._save_page_views(page_views)
    
    def track_action(self, user_id: str, action_type: str, page: Optional[str] = None,
                    arxiv_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                    user_agent: Optional[str] = None, ip_address: Optional[str] = None,
                    session_id: Optional[str] = None):
        """Track an action event.
        
        Args:
            user_id: The user ID (can be 'anonymous' for non-logged users)
            action_type: The type of action
            page: The page where action occurred
            arxiv_id: Related arXiv ID if applicable
            metadata: Additional metadata
            user_agent: User agent string
            ip_address: IP address
            session_id: Session ID for anonymous users
        """
        # Handle anonymous users
        if user_id == 'anonymous' and ip_address and user_agent:
            user_id = self._get_or_create_anonymous_id(ip_address, user_agent, session_id)
        
        action_event = ActionEvent(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            action_type=action_type,
            page=page,
            arxiv_id=arxiv_id,
            metadata=metadata or {}
        )
        
        # Load existing action events
        action_events = self._load_action_events()
        action_events.append(action_event.to_dict())
        
        # Save updated action events
        self._save_action_events(action_events)
    
    def get_visitor_stats(self, days: int = 30) -> VisitorStats:
        """Get comprehensive visitor statistics.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            VisitorStats object with comprehensive analytics
        """
        page_views = self._load_page_views()
        action_events = self._load_action_events()
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_page_views = [
            pv for pv in page_views 
            if datetime.fromisoformat(pv['timestamp']) >= cutoff_date
        ]
        filtered_action_events = [
            ae for ae in action_events 
            if datetime.fromisoformat(ae['timestamp']) >= cutoff_date
        ]
        
        # Calculate statistics
        stats = VisitorStats()
        
        # Total PV and UV
        stats.total_pv = len(filtered_page_views)
        unique_visitors = set(pv['user_id'] for pv in filtered_page_views)
        stats.total_uv = len(unique_visitors)
        stats.unique_visitors = list(unique_visitors)
        
        # Action distribution
        action_counter = Counter(ae['action_type'] for ae in filtered_action_events)
        stats.action_distribution = {k: int(v) for k, v in action_counter.items()}
        
        # Daily stats
        daily_stats = defaultdict(lambda: {'pv': 0, 'uv': 0, 'actions': 0})
        
        for pv in filtered_page_views:
            date_str = datetime.fromisoformat(pv['timestamp']).date().isoformat()
            daily_stats[date_str]['pv'] += 1
        
        for pv in filtered_page_views:
            date_str = datetime.fromisoformat(pv['timestamp']).date().isoformat()
            daily_stats[date_str]['uv'] = len(set(
                pv2['user_id'] for pv2 in filtered_page_views 
                if datetime.fromisoformat(pv2['timestamp']).date().isoformat() == date_str
            ))
        
        for ae in filtered_action_events:
            date_str = datetime.fromisoformat(ae['timestamp']).date().isoformat()
            daily_stats[date_str]['actions'] += 1
        
        stats.daily_stats = {k: dict(v) for k, v in daily_stats.items()}
        
        # Top pages
        page_counter = Counter(pv['page'] for pv in filtered_page_views)
        stats.top_pages = [
            {'page': page, 'views': count} 
            for page, count in page_counter.most_common(10)
        ]
        
        # Top actions
        stats.top_actions = [
            {'action': action, 'count': count} 
            for action, count in action_counter.most_common(10)
        ]
        
        # Recent page views (last 100)
        stats.page_views = filtered_page_views[-100:]
        
        return stats
    
    def get_daily_stats(self, days: int = 7) -> Dict[str, Dict[str, int]]:
        """Get daily statistics for the specified number of days.
        
        Args:
            days: Number of days to analyze (default: 7)
            
        Returns:
            Dictionary with daily statistics
        """
        stats = self.get_visitor_stats(days)
        return stats.daily_stats
    
    def get_action_distribution(self, days: int = 30) -> Dict[str, int]:
        """Get action distribution for the specified number of days.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary with action counts
        """
        stats = self.get_visitor_stats(days)
        return stats.action_distribution
    
    def get_top_pages(self, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top pages by views.
        
        Args:
            days: Number of days to analyze (default: 30)
            limit: Number of top pages to return (default: 10)
            
        Returns:
            List of top pages with view counts
        """
        stats = self.get_visitor_stats(days)
        return stats.top_pages[:limit]
    
    def get_device_stats(self, days: int = 30) -> Dict[str, Dict[str, int]]:
        """Get device and browser statistics.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary with device, browser, and OS statistics
        """
        page_views = self._load_page_views()
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_page_views = [
            pv for pv in page_views 
            if datetime.fromisoformat(pv['timestamp']) >= cutoff_date
        ]
        
        # Count devices, browsers, and OS
        device_counter = Counter()
        browser_counter = Counter()
        os_counter = Counter()
        
        for pv in filtered_page_views:
            if pv.get('device'):
                device_counter[pv['device']] += 1
            if pv.get('browser'):
                browser_counter[pv['browser']] += 1
            if pv.get('os'):
                os_counter[pv['os']] += 1
        
        return {
            'devices': dict(device_counter),
            'browsers': dict(browser_counter),
            'operating_systems': dict(os_counter)
        }
    
    def get_anonymous_visitor_details(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get detailed information about anonymous visitors.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            List of anonymous visitor details with IP, device info, and activity
        """
        page_views = self._load_page_views()
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_page_views = [
            pv for pv in page_views 
            if datetime.fromisoformat(pv['timestamp']) >= cutoff_date and pv['user_id'].startswith('anon_')
        ]
        
        # Group by anonymous user ID
        visitor_groups = defaultdict(list)
        for pv in filtered_page_views:
            visitor_groups[pv['user_id']].append(pv)
        
        # Create visitor details
        visitor_details = []
        for user_id, page_views_list in visitor_groups.items():
            if not page_views_list:
                continue
                
            # Get the most recent page view for device info
            latest_pv = max(page_views_list, key=lambda x: x['timestamp'])
            
            visitor_details.append({
                'user_id': user_id,
                'ip_address': latest_pv.get('ip_address', 'Unknown'),
                'browser': latest_pv.get('browser', 'Unknown'),
                'os': latest_pv.get('os', 'Unknown'),
                'device': latest_pv.get('device', 'Unknown'),
                'user_agent': latest_pv.get('user_agent', 'Unknown'),
                'first_seen': min(pv['timestamp'] for pv in page_views_list),
                'last_seen': max(pv['timestamp'] for pv in page_views_list),
                'page_views': len(page_views_list),
                'pages_visited': list(set(pv['page'] for pv in page_views_list))
            })
        
        # Sort by last seen (most recent first)
        visitor_details.sort(key=lambda x: x['last_seen'], reverse=True)
        
        return visitor_details
    
    def get_logged_user_details(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get detailed information about logged-in users.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            List of logged-in user details with activity and device info
        """
        page_views = self._load_page_views()
        
        # Filter by date range and logged-in users
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_page_views = [
            pv for pv in page_views 
            if datetime.fromisoformat(pv['timestamp']) >= cutoff_date and not pv['user_id'].startswith('anon_')
        ]
        
        # Group by user ID
        user_groups = defaultdict(list)
        for pv in filtered_page_views:
            user_groups[pv['user_id']].append(pv)
        
        # Create user details
        user_details = []
        for user_id, page_views_list in user_groups.items():
            if not page_views_list:
                continue
                
            # Get the most recent page view for device info
            latest_pv = max(page_views_list, key=lambda x: x['timestamp'])
            
            # Get user data to extract additional information
            user_data_file = self.user_data_dir / f"{user_id}.json"
            user_stats = {}
            if user_data_file.exists():
                try:
                    with open(user_data_file, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                    
                    # Get read statistics
                    read_map = user_data.get('read', {})
                    if isinstance(read_map, list):
                        read_map = {str(rid): None for rid in read_map}
                    
                    user_stats = {
                        'papers_read': len(read_map),
                        'papers_read_today': len([d for d in read_map.values() 
                                                if d and str(d).split('T', 1)[0] == date.today().isoformat()]),
                        'total_events': len(user_data.get('events', [])),
                        'uploaded_urls': len(user_data.get('uploaded_urls', []))
                    }
                except (json.JSONDecodeError, KeyError):
                    pass
            
            user_details.append({
                'user_id': user_id,
                'browser': latest_pv.get('browser', 'Unknown'),
                'os': latest_pv.get('os', 'Unknown'),
                'device': latest_pv.get('device', 'Unknown'),
                'user_agent': latest_pv.get('user_agent', 'Unknown'),
                'first_seen': min(pv['timestamp'] for pv in page_views_list),
                'last_seen': max(pv['timestamp'] for pv in page_views_list),
                'page_views': len(page_views_list),
                'pages_visited': list(set(pv['page'] for pv in page_views_list)),
                'papers_read': user_stats.get('papers_read', 0),
                'papers_read_today': user_stats.get('papers_read_today', 0),
                'total_events': user_stats.get('total_events', 0),
                'uploaded_urls': user_stats.get('uploaded_urls', 0)
            })
        
        # Sort by last seen (most recent first)
        user_details.sort(key=lambda x: x['last_seen'], reverse=True)
        
        return user_details
    
    def _load_page_views(self) -> List[Dict[str, Any]]:
        """Load page views from file."""
        try:
            with open(self.page_views_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_page_views(self, page_views: List[Dict[str, Any]]):
        """Save page views to file."""
        with open(self.page_views_file, 'w', encoding='utf-8') as f:
            json.dump(page_views, f, indent=2, ensure_ascii=False)
    
    def _load_action_events(self) -> List[Dict[str, Any]]:
        """Load action events from file."""
        try:
            with open(self.action_events_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_action_events(self, action_events: List[Dict[str, Any]]):
        """Save action events to file."""
        with open(self.action_events_file, 'w', encoding='utf-8') as f:
            json.dump(action_events, f, indent=2, ensure_ascii=False)
    
    def _load_anonymous_sessions(self) -> List[Dict[str, Any]]:
        """Load anonymous sessions from file."""
        try:
            with open(self.anonymous_sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_anonymous_sessions(self, sessions: List[Dict[str, Any]]):
        """Save anonymous sessions to file."""
        with open(self.anonymous_sessions_file, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
