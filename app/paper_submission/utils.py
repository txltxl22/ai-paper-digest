import json
import hashlib
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Tuple, List
from flask import request

from .models import DailyLimitInfo


def get_client_ip():
    """Get client IP address, handling proxy headers."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def check_daily_limit(ip: str, limit_file: Path, daily_limit: int) -> bool:
    """Check if IP has exceeded daily limit."""
    today = date.today().isoformat()
    
    try:
        if limit_file.exists():
            with open(limit_file, 'r', encoding='utf-8') as f:
                limits = json.load(f)
        else:
            limits = {}
        
        # Clean up old entries
        limits = {k: v for k, v in limits.items() if v['date'] == today}
        
        if ip in limits:
            return limits[ip]['count'] < daily_limit
        return True
        
    except Exception:
        return True


def increment_daily_limit(ip: str, limit_file: Path):
    """Increment daily limit counter for IP."""
    today = date.today().isoformat()
    
    try:
        if limit_file.exists():
            with open(limit_file, 'r', encoding='utf-8') as f:
                limits = json.load(f)
        else:
            limits = {}
        
        # Clean up old entries
        limits = {k: v for k, v in limits.items() if v['date'] == today}
        
        if ip in limits:
            limits[ip]['count'] += 1
        else:
            limits[ip] = {'date': today, 'count': 1}
        
        with open(limit_file, 'w', encoding='utf-8') as f:
            json.dump(limits, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error updating daily limit: {e}")


def create_content_hash(text_content: str) -> str:
    """Create a hash from text content for caching."""
    return hashlib.md5(text_content[:1000].encode()).hexdigest()
