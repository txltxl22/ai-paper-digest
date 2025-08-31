"""
Title Extractor Module

This module provides functionality for extracting paper titles from arXiv and Hugging Face URLs.
"""

import re
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class TitleExtractor:
    """Extract paper titles from various URL sources."""
    
    def __init__(self, timeout: int = 10):
        """Initialize the title extractor.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        # Set a user agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract paper title from a URL.
        
        Args:
            url: The URL to extract title from
            
        Returns:
            Extracted title or None if extraction fails
        """
        try:
            parsed_url = urlparse(url)
            
            if "arxiv.org" in parsed_url.netloc:
                return self._extract_arxiv_title(url)
            elif "huggingface.co" in parsed_url.netloc:
                return self._extract_huggingface_title(url)
            else:
                logger.warning(f"Unsupported URL domain: {parsed_url.netloc}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting title from {url}: {e}")
            return None
    
    def _extract_arxiv_title(self, url: str) -> Optional[str]:
        """Extract title from arXiv URL.
        
        Args:
            url: arXiv URL
            
        Returns:
            Extracted title or None
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Look for title in the HTML
            content = response.text
            
            # Try multiple patterns for arXiv title extraction
            title_patterns = [
                r'<title[^>]*>([^<]+)</title>',
                r'<h1[^>]*class="title"[^>]*>([^<]+)</h1>',
                r'<h1[^>]*>([^<]+)</h1>',
                r'<meta[^>]*name="citation_title"[^>]*content="([^"]+)"',
                r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    # Clean up the title
                    title = self._clean_title(title)
                    if title and not title.startswith("arXiv:"):
                        return title
            
            logger.warning(f"Could not extract title from arXiv URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting arXiv title from {url}: {e}")
            return None
    
    def _extract_huggingface_title(self, url: str) -> Optional[str]:
        """Extract title from Hugging Face URL.
        
        Args:
            url: Hugging Face URL
            
        Returns:
            Extracted title or None
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            content = response.text
            
            # Try multiple patterns for Hugging Face title extraction
            title_patterns = [
                r'<title[^>]*>([^<]+)</title>',
                r'<h1[^>]*>([^<]+)</h1>',
                r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
                r'<meta[^>]*name="twitter:title"[^>]*content="([^"]+)"',
                # Look for paper title in the content
                r'<h1[^>]*class="[^"]*text-[^"]*"[^>]*>([^<]+)</h1>',
                r'<div[^>]*class="[^"]*text-[^"]*"[^>]*>([^<]+)</div>'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    # Clean up the title
                    title = self._clean_title(title)
                    if title and not title.startswith("Hugging Face"):
                        return title
            
            logger.warning(f"Could not extract title from Hugging Face URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Hugging Face title from {url}: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize extracted title.
        
        Args:
            title: Raw extracted title
            
        Returns:
            Cleaned title
        """
        if not title:
            return ""
        
        # Remove common prefixes
        title = re.sub(r'^arXiv:\s*', '', title)
        title = re.sub(r'^Hugging Face\s*[-|]\s*', '', title)
        
        # Remove arXiv ID prefix like [2508.18966]
        title = re.sub(r'^\[\d+\.\d+\]\s*', '', title)
        
        # Remove extra whitespace and normalize
        title = re.sub(r'\s+', ' ', title.strip())
        
        # Remove HTML entities
        title = title.replace('&amp;', '&')
        title = title.replace('&lt;', '<')
        title = title.replace('&gt;', '>')
        title = title.replace('&quot;', '"')
        title = title.replace('&#39;', "'")
        
        return title
    
    def extract_arxiv_id_from_url(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL.
        
        Args:
            url: URL containing arXiv ID
            
        Returns:
            Extracted arXiv ID or None
        """
        try:
            # Extract arXiv ID from various URL formats
            patterns = [
                r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)',
                r'papers/(\d+\.\d+)',  # Hugging Face format
                r'(\d+\.\d+)'  # Fallback for any format
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting arXiv ID from {url}: {e}")
            return None
    
    def get_paper_info(self, url: str) -> Dict[str, Any]:
        """Get comprehensive paper information from URL.
        
        Args:
            url: Paper URL
            
        Returns:
            Dictionary containing paper information
        """
        info = {
            "url": url,
            "title": None,
            "arxiv_id": None,
            "source": None,
            "success": False,
            "error": None
        }
        
        try:
            # Extract arXiv ID
            arxiv_id = self.extract_arxiv_id_from_url(url)
            info["arxiv_id"] = arxiv_id
            
            # Determine source
            if "arxiv.org" in url:
                info["source"] = "arxiv"
            elif "huggingface.co" in url:
                info["source"] = "huggingface"
            else:
                info["source"] = "unknown"
            
            # Extract title
            title = self.extract_title_from_url(url)
            info["title"] = title
            
            if title:
                info["success"] = True
            else:
                info["error"] = "Failed to extract title"
                
        except Exception as e:
            info["error"] = str(e)
            logger.error(f"Error getting paper info from {url}: {e}")
        
        return info
    
    def close(self):
        """Close the session."""
        self.session.close()


# Convenience functions for easy use
def extract_title(url: str, timeout: int = 10) -> Optional[str]:
    """Extract title from URL using default settings.
    
    Args:
        url: URL to extract title from
        timeout: Request timeout in seconds
        
    Returns:
        Extracted title or None
    """
    extractor = TitleExtractor(timeout=timeout)
    try:
        return extractor.extract_title_from_url(url)
    finally:
        extractor.close()


def get_paper_info(url: str, timeout: int = 10) -> Dict[str, Any]:
    """Get paper information from URL using default settings.
    
    Args:
        url: URL to get information from
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary containing paper information
    """
    extractor = TitleExtractor(timeout=timeout)
    try:
        return extractor.get_paper_info(url)
    finally:
        extractor.close()
