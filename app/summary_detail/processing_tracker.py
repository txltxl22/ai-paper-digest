"""
Processing tracker for deep read operations.
Tracks which papers are being processed and by which users.
"""
import threading
import time
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessingJob:
    """Represents a single processing job."""
    arxiv_id: str
    user_id: str
    status: str  # 'processing', 'completed', 'failed'
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'arxiv_id': self.arxiv_id,
            'user_id': self.user_id,
            'status': self.status,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }


class ProcessingTracker:
    """Thread-safe tracker for deep read processing jobs."""
    
    def __init__(self, persistence_file: Optional[Path] = None):
        """Initialize the tracker.
        
        Args:
            persistence_file: Optional path to JSON file for persistence across restarts
        """
        self._lock = threading.RLock()  # Use reentrant lock to allow nested calls
        # Key: (arxiv_id, user_id), Value: ProcessingJob
        self._jobs: Dict[tuple, ProcessingJob] = {}
        self._persistence_file = persistence_file
        self._load_persistence()
    
    def _load_persistence(self):
        """Load persisted jobs from file."""
        if not self._persistence_file or not self._persistence_file.exists():
            return
        
        try:
            with open(self._persistence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self._lock:
                for key_str, job_data in data.items():
                    arxiv_id, user_id = key_str.split('|', 1)
                    job = ProcessingJob(
                        arxiv_id=arxiv_id,
                        user_id=user_id,
                        status=job_data['status'],
                        started_at=datetime.fromisoformat(job_data['started_at']),
                        completed_at=datetime.fromisoformat(job_data['completed_at']) if job_data.get('completed_at') else None,
                        error_message=job_data.get('error_message')
                    )
                    # Only keep completed/failed jobs, not processing ones (they should restart)
                    if job.status in ('completed', 'failed'):
                        self._jobs[(arxiv_id, user_id)] = job
        except Exception as e:
            logger.warning(f"Failed to load processing tracker persistence: {e}")
    
    def _save_persistence(self):
        """Save jobs to persistence file."""
        if not self._persistence_file:
            return
        
        try:
            # Don't acquire lock again - caller should already hold it
            data = {}
            for (arxiv_id, user_id), job in self._jobs.items():
                key = f"{arxiv_id}|{user_id}"
                data[key] = job.to_dict()
            
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persistence_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(data)} jobs to persistence file")
        except Exception as e:
            logger.warning(f"Failed to save processing tracker persistence: {e}", exc_info=True)
    
    def is_processing(self, arxiv_id: str, user_id: str) -> bool:
        """Check if a paper is currently being processed for a user."""
        with self._lock:
            key = (arxiv_id, user_id)
            job = self._jobs.get(key)
            return job is not None and job.status == 'processing'
    
    def start_processing(self, arxiv_id: str, user_id: str) -> bool:
        """Start tracking a processing job.
        
        Returns:
            True if job was started, False if already processing
        """
        with self._lock:
            key = (arxiv_id, user_id)
            existing_job = self._jobs.get(key)
            
            # If already processing, return False
            if existing_job and existing_job.status == 'processing':
                logger.info(f"Job already processing for {arxiv_id} by user {user_id}")
                return False
            
            # Start new job
            job = ProcessingJob(
                arxiv_id=arxiv_id,
                user_id=user_id,
                status='processing',
                started_at=datetime.now()
            )
            self._jobs[key] = job
            logger.info(f"Created processing job for {arxiv_id} by user {user_id}, total jobs: {len(self._jobs)}")
            self._save_persistence()
            logger.info(f"Started tracking deep read for {arxiv_id} by user {user_id}")
            return True
    
    def mark_completed(self, arxiv_id: str, user_id: str):
        """Mark a processing job as completed."""
        with self._lock:
            key = (arxiv_id, user_id)
            job = self._jobs.get(key)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.now()
                self._save_persistence()
                logger.info(f"Marked deep read as completed for {arxiv_id} by user {user_id}")
    
    def mark_failed(self, arxiv_id: str, user_id: str, error_message: str = None):
        """Mark a processing job as failed."""
        with self._lock:
            key = (arxiv_id, user_id)
            job = self._jobs.get(key)
            if job:
                job.status = 'failed'
                job.completed_at = datetime.now()
                job.error_message = error_message
                self._save_persistence()
                logger.info(f"Marked deep read as failed for {arxiv_id} by user {user_id}: {error_message}")
    
    def get_user_jobs(self, user_id: str) -> List[ProcessingJob]:
        """Get all jobs for a specific user, sorted by started_at (newest first)."""
        with self._lock:
            jobs = [job for (_, uid), job in self._jobs.items() if uid == user_id]
            # Sort by started_at descending (newest first)
            jobs.sort(key=lambda j: j.started_at, reverse=True)
            return jobs
    
    def get_processing_jobs(self, user_id: str) -> List[ProcessingJob]:
        """Get only processing (in-progress) jobs for a user."""
        with self._lock:
            jobs = [job for (_, uid), job in self._jobs.items() if uid == user_id and job.status == 'processing']
            logger.debug(f"get_processing_jobs for {user_id}: found {len(jobs)} jobs, total jobs in tracker: {len(self._jobs)}")
            return jobs
    
    def get_completed_jobs(self, user_id: str, limit: int = 10) -> List[ProcessingJob]:
        """Get recently completed jobs for a user."""
        completed = [job for job in self.get_user_jobs(user_id) if job.status == 'completed']
        return completed[:limit]
    
    def dismiss_job(self, arxiv_id: str, user_id: str):
        """Remove a job from tracking (user dismissed it from UI)."""
        with self._lock:
            key = (arxiv_id, user_id)
            if key in self._jobs:
                del self._jobs[key]
                self._save_persistence()
                logger.info(f"Dismissed job tracking for {arxiv_id} by user {user_id}")
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed/failed jobs to prevent memory bloat."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self._lock:
            to_remove = []
            for key, job in self._jobs.items():
                if job.status in ('completed', 'failed') and job.completed_at:
                    if job.completed_at.timestamp() < cutoff:
                        to_remove.append(key)
            
            for key in to_remove:
                del self._jobs[key]
            
            if to_remove:
                self._save_persistence()
                logger.info(f"Cleaned up {len(to_remove)} old processing jobs")


# Global instance
_processing_tracker: Optional[ProcessingTracker] = None


def get_processing_tracker(persistence_file: Optional[Path] = None) -> ProcessingTracker:
    """Get or create the global processing tracker instance."""
    global _processing_tracker
    if _processing_tracker is None:
        _processing_tracker = ProcessingTracker(persistence_file)
    return _processing_tracker

