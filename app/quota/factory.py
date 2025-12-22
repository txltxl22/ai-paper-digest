"""
Factory for creating quota management components.
"""

from pathlib import Path
from typing import List

from .models import QuotaConfig
from .manager import QuotaManager


def create_quota_module(
    data_dir: Path,
    guest_daily_limit: int = 1,
    normal_daily_limit: int = 3,
    pro_users: List[str] = None,
    admin_users: List[str] = None,
) -> dict:
    """
    Create quota management module.
    
    Args:
        data_dir: Directory for quota data files
        guest_daily_limit: Daily limit for guests (IP-based)
        normal_daily_limit: Daily limit for normal logged-in users
        pro_users: List of Pro user IDs
        admin_users: List of admin user IDs
        
    Returns:
        Dictionary with:
        - manager: QuotaManager instance
        - config: QuotaConfig instance
    """
    config = QuotaConfig(
        guest_daily_limit=guest_daily_limit,
        normal_daily_limit=normal_daily_limit,
        pro_users=pro_users or [],
        admin_users=admin_users or []
    )
    
    quota_file = data_dir / "quota_limits.json"
    
    manager = QuotaManager(
        config=config,
        quota_file=quota_file
    )
    
    return {
        "manager": manager,
        "config": config
    }

