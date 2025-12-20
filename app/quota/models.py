"""
Data models for the quota management system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


class UserTier(Enum):
    """User tier levels for quota management."""
    GUEST = "guest"      # Not logged in, IP-based tracking
    NORMAL = "normal"    # Logged in, free user
    PRO = "pro"          # Paid user with quota-based access
    ADMIN = "admin"      # Administrator with unlimited access


@dataclass
class QuotaResult:
    """Result of a quota check operation."""
    allowed: bool
    tier: UserTier = UserTier.GUEST
    reason: Optional[str] = None  # "ip_limit", "user_limit", "guest_limit", "pro_quota_exhausted"
    message: Optional[str] = None  # User-facing message
    pseudo_uid: Optional[str] = None  # For guests: "ip:{address}" to use as uid for tracking
    remaining_daily: Optional[int] = None  # Remaining daily quota (for GUEST/NORMAL)
    remaining_quota: Optional[int] = None  # Remaining total quota (for PRO)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "allowed": self.allowed,
            "tier": self.tier.value,
            "reason": self.reason,
            "message": self.message,
            "pseudo_uid": self.pseudo_uid,
            "remaining_daily": self.remaining_daily,
            "remaining_quota": self.remaining_quota
        }


@dataclass
class QuotaConfig:
    """Configuration for quota limits."""
    guest_daily_limit: int = 1
    normal_daily_limit: int = 3
    pro_users: List[str] = field(default_factory=list)
    admin_users: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "QuotaConfig":
        """Create QuotaConfig from dictionary."""
        return cls(
            guest_daily_limit=data.get("guest_daily_limit", 1),
            normal_daily_limit=data.get("normal_daily_limit", 3),
            pro_users=data.get("pro_users", []),
            admin_users=data.get("admin_users", [])
        )


@dataclass
class DailyUsage:
    """Daily usage record for a user or IP."""
    date: str  # ISO format date (YYYY-MM-DD)
    count: int
    
    def to_dict(self) -> dict:
        return {"date": self.date, "count": self.count}
    
    @classmethod
    def from_dict(cls, data: dict) -> "DailyUsage":
        return cls(date=data["date"], count=data["count"])


@dataclass
class ProQuota:
    """Quota record for a Pro user."""
    remaining: int
    total: int
    last_updated: Optional[str] = None  # ISO format datetime
    
    def to_dict(self) -> dict:
        return {
            "remaining": self.remaining,
            "total": self.total,
            "last_updated": self.last_updated or datetime.now().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProQuota":
        return cls(
            remaining=data["remaining"],
            total=data["total"],
            last_updated=data.get("last_updated")
        )


@dataclass
class QuotaLimitsData:
    """Complete quota limits data structure for persistence."""
    daily: dict  # "ip:{ip}" or "user:{uid}" -> DailyUsage
    pro_quota: dict  # "{uid}" -> ProQuota
    
    def to_dict(self) -> dict:
        return {
            "daily": {k: v.to_dict() if isinstance(v, DailyUsage) else v for k, v in self.daily.items()},
            "pro_quota": {k: v.to_dict() if isinstance(v, ProQuota) else v for k, v in self.pro_quota.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QuotaLimitsData":
        daily = {}
        for k, v in data.get("daily", {}).items():
            daily[k] = DailyUsage.from_dict(v) if isinstance(v, dict) else v
        
        pro_quota = {}
        for k, v in data.get("pro_quota", {}).items():
            pro_quota[k] = ProQuota.from_dict(v) if isinstance(v, dict) else v
        
        return cls(daily=daily, pro_quota=pro_quota)
    
    @classmethod
    def empty(cls) -> "QuotaLimitsData":
        return cls(daily={}, pro_quota={})

