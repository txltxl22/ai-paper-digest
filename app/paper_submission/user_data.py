import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from .models import UploadRecord, AIJudgment, ProcessResult


class UserDataManager:
    """Manages user data for paper submissions."""
    
    def __init__(self, user_data_dir: Path):
        self.user_data_dir = user_data_dir
        self.user_data_dir.mkdir(exist_ok=True)
    
    def _user_file(self, uid: str) -> Path:
        """Get user data file path."""
        return self.user_data_dir / f"{uid}.json"
    
    def save_uploaded_url(self, uid: str, url: str, ai_result: tuple, process_result: dict):
        """Save uploaded URL information to user data."""
        try:
            user_file = self._user_file(uid)
            
            # Load existing user data
            if user_file.exists():
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
            else:
                user_data = {"read": {}, "events": [], "uploaded_urls": []}
            
            # Initialize uploaded_urls section if not exists
            if "uploaded_urls" not in user_data:
                user_data["uploaded_urls"] = []
            
            # Create upload record
            upload_record = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "ai_judgment": {
                    "is_ai": ai_result[0],
                    "confidence": ai_result[1],
                    "tags": ai_result[2] if len(ai_result) > 2 else []
                },
                "process_result": {
                    "success": process_result.get("success", False),
                    "error": process_result.get("error", None),
                    "summary_path": process_result.get("summary_path", None),
                    "paper_subject": process_result.get("paper_subject", None)
                }
            }
            
            # Add to uploaded_urls list
            user_data["uploaded_urls"].append(upload_record)
            
            # Save updated user data
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error saving uploaded URL: {e}")
    
    def get_uploaded_urls(self, uid: str) -> List[Dict[str, Any]]:
        """Get uploaded URLs for a user."""
        try:
            user_file = self._user_file(uid)
            
            if user_file.exists():
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                return user_data.get("uploaded_urls", [])
            else:
                return []
                
        except Exception as e:
            print(f"Error getting uploaded URLs: {e}")
            return []
    
    def has_processed_paper(self, uid: str, paper_url: str) -> bool:
        """Check if a paper has already been processed successfully."""
        try:
            user_file = self._user_file(uid)
            
            if user_file.exists():
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                uploaded_urls = user_data.get("uploaded_urls", [])
                
                # Check if this URL has been processed successfully
                for record in uploaded_urls:
                    if record.get("url") == paper_url:
                        process_result = record.get("process_result", {})
                        if process_result.get("success", False):
                            return True
                
            return False
                
        except Exception as e:
            print(f"Error checking processed paper: {e}")
            return False