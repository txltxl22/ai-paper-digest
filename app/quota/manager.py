"""
Quota manager for handling tiered user access control.
"""

import json
import logging
from pathlib import Path
from datetime import date, datetime
from typing import Optional
from threading import Lock

from flask import request

from .models import (
    UserTier, 
    QuotaResult, 
    QuotaConfig, 
    DailyUsage, 
    ProQuota,
    QuotaLimitsData
)

logger = logging.getLogger(__name__)


class QuotaManager:
    """
    Manages quota checking and consumption for all user tiers.
    
    Tier behavior:
    - GUEST: IP-based, 1/day default
    - NORMAL: Both IP and user limits checked, 3/day default
    - PRO: Quota-based (not daily), no IP limit
    - ADMIN: Unlimited access
    """
    
    def __init__(
        self,
        config: QuotaConfig,
        quota_file: Path,
    ):
        """
        Initialize QuotaManager.
        
        Args:
            config: QuotaConfig with limits and user lists
            quota_file: Path to quota_limits.json file
        """
        self.config = config
        self.quota_file = quota_file
        self._lock = Lock()
        
        # Ensure quota file exists
        if not self.quota_file.exists():
            self._save_data(QuotaLimitsData.empty())
    
    def get_client_ip(self) -> str:
        """Get client IP address, handling proxy headers."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or "unknown"
    
    def get_user_tier(self, uid: Optional[str]) -> UserTier:
        """
        Determine user tier based on uid.
        
        Args:
            uid: User ID or None for guest
            
        Returns:
            UserTier enum value
        """
        if not uid:
            return UserTier.GUEST
        
        if uid in self.config.admin_users:
            return UserTier.ADMIN
        
        if uid in self.config.pro_users:
            return UserTier.PRO
        
        return UserTier.NORMAL
    
    def check_and_consume(self, ip: str, uid: Optional[str]) -> QuotaResult:
        """
        Main entry point - check quota and consume if allowed.
        
        Args:
            ip: Client IP address
            uid: User ID or None for guest
            
        Returns:
            QuotaResult with allowed status and details
        """
        tier = self.get_user_tier(uid)
        
        logger.info(f"Quota check: ip={ip}, uid={uid}, tier={tier.value}")
        
        if tier == UserTier.ADMIN:
            return QuotaResult(
                allowed=True,
                tier=tier,
                message="管理员无限制"
            )
        
        if tier == UserTier.PRO:
            return self._check_and_consume_pro(uid)
        
        if tier == UserTier.NORMAL:
            return self._check_and_consume_normal(ip, uid)
        
        # GUEST
        return self._check_and_consume_guest(ip)
    
    def check_only(self, ip: str, uid: Optional[str]) -> QuotaResult:
        """
        Check quota without consuming. Useful for UI display.
        
        Args:
            ip: Client IP address
            uid: User ID or None for guest
            
        Returns:
            QuotaResult with current status
        """
        tier = self.get_user_tier(uid)
        
        if tier == UserTier.ADMIN:
            return QuotaResult(allowed=True, tier=tier, message="管理员无限制")
        
        if tier == UserTier.PRO:
            return self._check_pro(uid)
        
        if tier == UserTier.NORMAL:
            return self._check_normal(ip, uid)
        
        return self._check_guest(ip)
    
    def get_quota_info(self, ip: str, uid: Optional[str]) -> dict:
        """
        Get detailed quota information for display.
        
        Returns dict with:
        - tier: User tier name
        - daily_limit: Daily limit (for GUEST/NORMAL)
        - used_today: Count used today
        - remaining: Remaining quota
        - is_unlimited: True for ADMIN
        """
        tier = self.get_user_tier(uid)
        
        if tier == UserTier.ADMIN:
            return {
                "tier": "admin",
                "is_unlimited": True,
                "daily_limit": None,
                "used_today": 0,
                "remaining": None,
                "message": "管理员无限制"
            }
        
        if tier == UserTier.PRO:
            data = self._load_data()
            quota = data.pro_quota.get(uid)
            if quota:
                return {
                    "tier": "pro",
                    "is_unlimited": False,
                    "quota_total": quota.total,
                    "quota_remaining": quota.remaining,
                    "message": f"剩余配额: {quota.remaining}/{quota.total}"
                }
            return {
                "tier": "pro",
                "is_unlimited": False,
                "quota_total": 0,
                "quota_remaining": 0,
                "message": "Pro用户配额未设置"
            }
        
        today = date.today().isoformat()
        data = self._load_data()
        
        if tier == UserTier.NORMAL:
            ip_key = f"ip:{ip}"
            user_key = f"user:{uid}"
            
            ip_usage = data.daily.get(ip_key)
            user_usage = data.daily.get(user_key)
            
            ip_count = ip_usage.count if ip_usage and ip_usage.date == today else 0
            user_count = user_usage.count if user_usage and user_usage.date == today else 0
            
            # Use the higher of the two counts
            used = max(ip_count, user_count)
            remaining = max(0, self.config.normal_daily_limit - used)
            
            return {
                "tier": "normal",
                "is_unlimited": False,
                "daily_limit": self.config.normal_daily_limit,
                "used_today": used,
                "remaining": remaining,
                "ip_count": ip_count,
                "user_count": user_count,
                "message": f"今日剩余: {remaining}/{self.config.normal_daily_limit}"
            }
        
        # GUEST
        ip_key = f"ip:{ip}"
        ip_usage = data.daily.get(ip_key)
        ip_count = ip_usage.count if ip_usage and ip_usage.date == today else 0
        remaining = max(0, self.config.guest_daily_limit - ip_count)
        
        return {
            "tier": "guest",
            "is_unlimited": False,
            "daily_limit": self.config.guest_daily_limit,
            "used_today": ip_count,
            "remaining": remaining,
            "message": f"游客今日剩余: {remaining}/{self.config.guest_daily_limit}，登录获取更多"
        }
    
    # =====================
    # Private helper methods
    # =====================
    
    def _load_data(self) -> QuotaLimitsData:
        """Load quota data from file."""
        try:
            if self.quota_file.exists():
                with open(self.quota_file, 'r', encoding='utf-8') as f:
                    return QuotaLimitsData.from_dict(json.load(f))
        except Exception as e:
            logger.error(f"Error loading quota data: {e}")
        return QuotaLimitsData.empty()
    
    def _save_data(self, data: QuotaLimitsData) -> None:
        """Save quota data to file."""
        try:
            self.quota_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.quota_file, 'w', encoding='utf-8') as f:
                json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving quota data: {e}")
    
    def _clean_old_entries(self, data: QuotaLimitsData) -> QuotaLimitsData:
        """Remove entries from previous days."""
        today = date.today().isoformat()
        cleaned_daily = {}
        
        for key, usage in data.daily.items():
            if isinstance(usage, DailyUsage) and usage.date == today:
                cleaned_daily[key] = usage
            elif isinstance(usage, dict) and usage.get("date") == today:
                cleaned_daily[key] = DailyUsage.from_dict(usage)
        
        data.daily = cleaned_daily
        return data
    
    def _check_ip_limit(self, ip: str, limit: int) -> tuple[bool, int]:
        """
        Check if IP is under the daily limit.
        
        Returns:
            Tuple of (allowed, current_count)
        """
        today = date.today().isoformat()
        data = self._load_data()
        data = self._clean_old_entries(data)
        
        ip_key = f"ip:{ip}"
        usage = data.daily.get(ip_key)
        
        if usage:
            count = usage.count
            return count < limit, count
        
        return True, 0
    
    def _check_user_limit(self, uid: str, limit: int) -> tuple[bool, int]:
        """
        Check if user is under the daily limit.
        
        Returns:
            Tuple of (allowed, current_count)
        """
        today = date.today().isoformat()
        data = self._load_data()
        data = self._clean_old_entries(data)
        
        user_key = f"user:{uid}"
        usage = data.daily.get(user_key)
        
        if usage:
            count = usage.count
            return count < limit, count
        
        return True, 0
    
    def _increment_ip(self, ip: str) -> None:
        """Increment IP daily counter."""
        with self._lock:
            today = date.today().isoformat()
            data = self._load_data()
            data = self._clean_old_entries(data)
            
            ip_key = f"ip:{ip}"
            usage = data.daily.get(ip_key)
            
            if usage:
                usage.count += 1
            else:
                data.daily[ip_key] = DailyUsage(date=today, count=1)
            
            self._save_data(data)
            logger.info(f"Incremented IP quota: {ip_key} -> {data.daily[ip_key].count}")
    
    def _increment_user(self, uid: str) -> None:
        """Increment user daily counter."""
        with self._lock:
            today = date.today().isoformat()
            data = self._load_data()
            data = self._clean_old_entries(data)
            
            user_key = f"user:{uid}"
            usage = data.daily.get(user_key)
            
            if usage:
                usage.count += 1
            else:
                data.daily[user_key] = DailyUsage(date=today, count=1)
            
            self._save_data(data)
            logger.info(f"Incremented user quota: {user_key} -> {data.daily[user_key].count}")
    
    def _decrement_pro_quota(self, uid: str) -> bool:
        """
        Decrement Pro user quota.
        
        Returns:
            True if quota was decremented, False if exhausted
        """
        with self._lock:
            data = self._load_data()
            quota = data.pro_quota.get(uid)
            
            if not quota or quota.remaining <= 0:
                return False
            
            quota.remaining -= 1
            quota.last_updated = datetime.now().isoformat()
            self._save_data(data)
            
            logger.info(f"Decremented Pro quota: {uid} -> {quota.remaining}/{quota.total}")
            return True
    
    # =====================
    # Tier-specific checks
    # =====================
    
    def _check_guest(self, ip: str) -> QuotaResult:
        """Check guest quota without consuming."""
        allowed, count = self._check_ip_limit(ip, self.config.guest_daily_limit)
        remaining = max(0, self.config.guest_daily_limit - count)
        
        if allowed:
            return QuotaResult(
                allowed=True,
                tier=UserTier.GUEST,
                pseudo_uid=f"ip:{ip}",
                remaining_daily=remaining,
                message=f"游客剩余 {remaining} 次，登录获取更多额度"
            )
        
        return QuotaResult(
            allowed=False,
            tier=UserTier.GUEST,
            reason="guest_limit",
            pseudo_uid=f"ip:{ip}",
            remaining_daily=0,
            message="游客每日限额已用完，请登录获取更多免费额度"
        )
    
    def _check_and_consume_guest(self, ip: str) -> QuotaResult:
        """Check and consume guest quota."""
        allowed, count = self._check_ip_limit(ip, self.config.guest_daily_limit)
        
        if not allowed:
            return QuotaResult(
                allowed=False,
                tier=UserTier.GUEST,
                reason="guest_limit",
                pseudo_uid=f"ip:{ip}",
                remaining_daily=0,
                message="游客每日限额已用完，请登录获取更多免费额度"
            )
        
        self._increment_ip(ip)
        remaining = max(0, self.config.guest_daily_limit - count - 1)
        
        return QuotaResult(
            allowed=True,
            tier=UserTier.GUEST,
            pseudo_uid=f"ip:{ip}",
            remaining_daily=remaining,
            message=f"游客剩余 {remaining} 次" if remaining > 0 else "游客今日额度已用完"
        )
    
    def _check_normal(self, ip: str, uid: str) -> QuotaResult:
        """Check normal user quota without consuming."""
        ip_allowed, ip_count = self._check_ip_limit(ip, self.config.normal_daily_limit)
        user_allowed, user_count = self._check_user_limit(uid, self.config.normal_daily_limit)
        
        # Use the higher count to determine remaining
        used = max(ip_count, user_count)
        remaining = max(0, self.config.normal_daily_limit - used)
        
        if not ip_allowed:
            return QuotaResult(
                allowed=False,
                tier=UserTier.NORMAL,
                reason="ip_limit",
                remaining_daily=0,
                message="当前网络今日限额已用完，请明天再试"
            )
        
        if not user_allowed:
            return QuotaResult(
                allowed=False,
                tier=UserTier.NORMAL,
                reason="user_limit",
                remaining_daily=0,
                message="您今日的免费额度已用完，升级Pro获取更多"
            )
        
        return QuotaResult(
            allowed=True,
            tier=UserTier.NORMAL,
            remaining_daily=remaining,
            message=f"今日剩余 {remaining} 次"
        )
    
    def _check_and_consume_normal(self, ip: str, uid: str) -> QuotaResult:
        """Check and consume normal user quota."""
        ip_allowed, ip_count = self._check_ip_limit(ip, self.config.normal_daily_limit)
        
        if not ip_allowed:
            return QuotaResult(
                allowed=False,
                tier=UserTier.NORMAL,
                reason="ip_limit",
                remaining_daily=0,
                message="当前网络今日限额已用完，请明天再试"
            )
        
        user_allowed, user_count = self._check_user_limit(uid, self.config.normal_daily_limit)
        
        if not user_allowed:
            return QuotaResult(
                allowed=False,
                tier=UserTier.NORMAL,
                reason="user_limit",
                remaining_daily=0,
                message="您今日的免费额度已用完，升级Pro获取更多"
            )
        
        # Both allowed, consume from both
        self._increment_ip(ip)
        self._increment_user(uid)
        
        # Calculate remaining based on higher count
        used = max(ip_count + 1, user_count + 1)
        remaining = max(0, self.config.normal_daily_limit - used)
        
        return QuotaResult(
            allowed=True,
            tier=UserTier.NORMAL,
            remaining_daily=remaining,
            message=f"今日剩余 {remaining} 次" if remaining > 0 else "今日额度已用完"
        )
    
    def _check_pro(self, uid: str) -> QuotaResult:
        """Check Pro user quota without consuming."""
        data = self._load_data()
        quota = data.pro_quota.get(uid)
        
        if not quota:
            # Pro user without quota set - treat as having 0 remaining
            return QuotaResult(
                allowed=False,
                tier=UserTier.PRO,
                reason="pro_quota_exhausted",
                remaining_quota=0,
                message="Pro用户配额未设置，请联系管理员"
            )
        
        if quota.remaining <= 0:
            return QuotaResult(
                allowed=False,
                tier=UserTier.PRO,
                reason="pro_quota_exhausted",
                remaining_quota=0,
                message="Pro配额已用完，请联系管理员充值"
            )
        
        return QuotaResult(
            allowed=True,
            tier=UserTier.PRO,
            remaining_quota=quota.remaining,
            message=f"Pro剩余配额: {quota.remaining}"
        )
    
    def _check_and_consume_pro(self, uid: str) -> QuotaResult:
        """Check and consume Pro user quota."""
        check_result = self._check_pro(uid)
        
        if not check_result.allowed:
            return check_result
        
        # Consume quota
        success = self._decrement_pro_quota(uid)
        
        if not success:
            return QuotaResult(
                allowed=False,
                tier=UserTier.PRO,
                reason="pro_quota_exhausted",
                remaining_quota=0,
                message="Pro配额已用完，请联系管理员充值"
            )
        
        # Reload to get updated remaining
        data = self._load_data()
        quota = data.pro_quota.get(uid)
        remaining = quota.remaining if quota else 0
        
        return QuotaResult(
            allowed=True,
            tier=UserTier.PRO,
            remaining_quota=remaining,
            message=f"Pro剩余配额: {remaining}"
        )
    
    # =====================
    # Admin methods
    # =====================
    
    def set_pro_quota(self, uid: str, total: int, remaining: Optional[int] = None) -> None:
        """
        Set or update Pro user quota.
        
        Args:
            uid: User ID
            total: Total quota amount
            remaining: Remaining quota (defaults to total if not specified)
        """
        with self._lock:
            data = self._load_data()
            data.pro_quota[uid] = ProQuota(
                remaining=remaining if remaining is not None else total,
                total=total,
                last_updated=datetime.now().isoformat()
            )
            self._save_data(data)
            logger.info(f"Set Pro quota for {uid}: {remaining or total}/{total}")
    
    def add_pro_quota(self, uid: str, amount: int) -> int:
        """
        Add quota to an existing Pro user.
        
        Args:
            uid: User ID
            amount: Amount to add
            
        Returns:
            New remaining quota
        """
        with self._lock:
            data = self._load_data()
            quota = data.pro_quota.get(uid)
            
            if quota:
                quota.remaining += amount
                quota.total += amount
                quota.last_updated = datetime.now().isoformat()
            else:
                data.pro_quota[uid] = ProQuota(
                    remaining=amount,
                    total=amount,
                    last_updated=datetime.now().isoformat()
                )
            
            self._save_data(data)
            new_remaining = data.pro_quota[uid].remaining
            logger.info(f"Added {amount} quota to {uid}, new remaining: {new_remaining}")
            return new_remaining
    
    def reset_daily_limits(self) -> None:
        """Reset all daily limits (for admin/testing)."""
        with self._lock:
            data = self._load_data()
            data.daily = {}
            self._save_data(data)
            logger.info("Reset all daily limits")
    
    def get_all_usage_stats(self) -> dict:
        """Get all usage statistics for admin dashboard."""
        data = self._load_data()
        today = date.today().isoformat()
        
        ip_count = sum(1 for k in data.daily.keys() if k.startswith("ip:"))
        user_count = sum(1 for k in data.daily.keys() if k.startswith("user:"))
        
        return {
            "date": today,
            "total_ip_entries": ip_count,
            "total_user_entries": user_count,
            "pro_users_with_quota": len(data.pro_quota),
            "daily_entries": {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in data.daily.items()},
            "pro_quotas": {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in data.pro_quota.items()}
        }

