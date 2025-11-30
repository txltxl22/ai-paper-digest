"""
Paper Info Extractor Module

This module provides functionality for extracting paper titles, abstracts, and metadata 
from arXiv and Hugging Face URLs.
"""

import re
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import logging
import time
from summary_service.models import PaperInfo

logger = logging.getLogger(__name__)


class PaperInfoExtractor:
    """Extract paper titles, abstracts, and metadata from various URL sources."""
    
    def __init__(self, timeout: int = 10, retry_delay: float = 1.0):
        """Initialize the paper info extractor.
        
        Args:
            timeout: Request timeout in seconds
            retry_delay: Delay in seconds between retries (default: 1.0)
        """
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.session = requests.Session()
        # Set a user agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _fetch_url_content(self, url: str, max_retries: int = 3, retry_delay: Optional[float] = None) -> Optional[str]:
        """Fetch HTML content from URL with retry logic.
        
        Args:
            url: URL to fetch content from
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay in seconds between retries (default: uses self.retry_delay)
            
        Returns:
            HTML content as string, or None if fetching fails
        """
        if retry_delay is None:
            retry_delay = self.retry_delay
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch content from {url} after {max_retries} attempts: {e}")
                    return None
                logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying...")
                time.sleep(retry_delay)  # Wait before retry
        return None
    
    def _extract_title_from_url(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract paper title from a URL.
        
        Args:
            url: The URL to extract title from
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted title or None if extraction fails
        """
        try:
            parsed_url = urlparse(url)
            
            if "arxiv.org" in parsed_url.netloc:
                return self._extract_arxiv_title(url, content)
            elif "huggingface.co" in parsed_url.netloc:
                return self._extract_huggingface_title(url, content)
            else:
                logger.warning(f"Unsupported URL domain: {parsed_url.netloc}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting title from {url}: {e}")
            return None
    
    def _extract_abstract_from_url(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract paper abstract from a URL.
        
        Args:
            url: The URL to extract abstract from
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted abstract or None if extraction fails
        """
        try:
            parsed_url = urlparse(url)
            
            if "arxiv.org" in parsed_url.netloc:
                return self._extract_arxiv_abstract(url, content)
            elif "huggingface.co" in parsed_url.netloc:
                return self._extract_huggingface_abstract(url, content)
            else:
                logger.warning(f"Unsupported URL domain: {parsed_url.netloc}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting abstract from {url}: {e}")
            return None
    
    def _extract_arxiv_title(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract title from arXiv URL.
        
        Args:
            url: arXiv URL
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted title or None
        """
        try:
            if content is None:
                content = self._fetch_url_content(url)
                if content is None:
                    return None
            
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
    
    def _extract_arxiv_abstract(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract abstract from arXiv URL.
        
        Args:
            url: arXiv URL
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted abstract or None
        """
        try:
            if content is None:
                content = self._fetch_url_content(url)
                if content is None:
                    return None
            
            # Try multiple patterns for arXiv abstract extraction
            abstract_patterns = [
                # Look for abstract in blockquote with mathjax
                r'<blockquote[^>]*class="abstract mathjax"[^>]*>(.*?)</blockquote>',
                # Look for abstract in blockquote
                r'<blockquote[^>]*class="abstract"[^>]*>(.*?)</blockquote>',
                # Look for abstract in div with mathjax
                r'<div[^>]*class="abstract[^"]*"[^>]*>(.*?)</div>',
                # Look for abstract in span
                r'<span[^>]*class="abstract[^"]*"[^>]*>(.*?)</span>',
                # Look for abstract in meta description (fallback)
                r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                # Look for abstract in og:description (fallback)
                r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"',
                # Fallback: look for any text between "Abstract" and next section
                r'Abstract[^>]*>(.*?)(?:<h[1-6]|$)',
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    abstract = match.group(1).strip()
                    # Clean up the abstract
                    abstract = self._clean_abstract(abstract)
                    if abstract and len(abstract) > 50:  # Ensure it's substantial
                        return abstract
            
            logger.warning(f"Could not extract abstract from arXiv URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting arXiv abstract from {url}: {e}")
            return None
    
    def _extract_huggingface_title(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract title from Hugging Face URL.
        
        Args:
            url: Hugging Face URL
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted title or None
        """
        try:
            if content is None:
                content = self._fetch_url_content(url, max_retries=3)
                if content is None:
                    return None
            
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
    
    def _extract_huggingface_abstract(self, url: str, content: Optional[str] = None) -> Optional[str]:
        """Extract abstract from Hugging Face URL.
        
        Args:
            url: Hugging Face URL
            content: Optional HTML content (if None, will be fetched)
            
        Returns:
            Extracted abstract or None
        """
        try:
            if content is None:
                content = self._fetch_url_content(url, max_retries=3)
                if content is None:
                    return None
            
            # Try multiple patterns for Hugging Face abstract extraction
            abstract_patterns = [
                # Look for abstract in meta description
                r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                # Look for abstract in og:description
                r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"',
                # Look for abstract in twitter:description
                r'<meta[^>]*name="twitter:description"[^>]*content="([^"]+)"',
                # Look for abstract in div with specific classes
                r'<div[^>]*class="[^"]*text-[^"]*"[^>]*>(.*?)</div>',
                # Look for abstract in p tags
                r'<p[^>]*class="[^"]*text-[^"]*"[^>]*>(.*?)</p>',
                # Fallback: look for any text that might be abstract
                r'<div[^>]*class="[^"]*prose[^"]*"[^>]*>(.*?)</div>',
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    abstract = match.group(1).strip()
                    # Clean up the abstract
                    abstract = self._clean_abstract(abstract)
                    if abstract and len(abstract) > 50:  # Ensure it's substantial
                        return abstract
            
            logger.warning(f"Could not extract abstract from Hugging Face URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Hugging Face abstract from {url}: {e}")
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
    
    def _clean_abstract(self, abstract: str) -> str:
        """Clean and normalize extracted abstract.
        
        Args:
            abstract: Raw extracted abstract
            
        Returns:
            Cleaned abstract
        """
        if not abstract:
            return ""
        
        # Remove HTML tags
        abstract = re.sub(r'<[^>]+>', '', abstract)
        
        # Remove extra whitespace and normalize
        abstract = re.sub(r'\s+', ' ', abstract.strip())
        
        # Remove HTML entities
        abstract = abstract.replace('&amp;', '&')
        abstract = abstract.replace('&lt;', '<')
        abstract = abstract.replace('&gt;', '>')
        abstract = abstract.replace('&quot;', '"')
        abstract = abstract.replace('&#39;', "'")
        abstract = abstract.replace('&nbsp;', ' ')
        
        # Remove common prefixes/suffixes
        abstract = re.sub(r'^Abstract[:\s]*', '', abstract, flags=re.IGNORECASE)
        abstract = re.sub(r'^Summary[:\s]*', '', abstract, flags=re.IGNORECASE)
        
        return abstract
    
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
    
    def get_paper_info(self, url: str) -> PaperInfo:
        """Get comprehensive paper information from URL.
        
        Args:
            url: Paper URL
            
        Returns:
            PaperInfo model containing paper information. Returns PaperInfo with empty/None fields if extraction fails.
        """
        # Initialize with defaults
        paper_info = PaperInfo(
            url=url,
            title_en="",
            abstract="",
            arxiv_id=None,
            source=None
        )
        
        try:
            # Extract arXiv ID
            arxiv_id = self.extract_arxiv_id_from_url(url)
            paper_info.arxiv_id = arxiv_id
            
            # Determine source
            if "arxiv.org" in url:
                paper_info.source = "arxiv"
            elif "huggingface.co" in url:
                paper_info.source = "huggingface"
            else:
                paper_info.source = "unknown"

            # Convert url to abs url
            abs_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            # Fetch HTML content once
            content = self._fetch_url_content(abs_url)
            if content is None:
                logger.warning(f"Failed to fetch content from {url}")
                return paper_info
            
            # Extract title and abstract using the same content
            title = self._extract_title_from_url(abs_url, content)
            paper_info.title_en = title or ""
            
            abstract = self._extract_abstract_from_url(abs_url, content)
            paper_info.abstract = abstract or ""
                
        except Exception as e:
            logger.error(f"Error getting paper info from {url}: {e}")
        
        return paper_info
    
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
    extractor = PaperInfoExtractor(timeout=timeout)
    try:
        info = extractor.get_paper_info(url)
        return info.title_en if info.title_en else None
    finally:
        extractor.close()


def extract_abstract(url: str, timeout: int = 10) -> Optional[str]:
    """Extract abstract from URL using default settings.
    
    Args:
        url: URL to extract abstract from
        timeout: Request timeout in seconds
        
    Returns:
        Extracted abstract or None
    """
    extractor = PaperInfoExtractor(timeout=timeout)
    try:
        info = extractor.get_paper_info(url)
        return info.abstract if info.abstract else None
    finally:
        extractor.close()


def get_paper_info(url: str, timeout: int = 10) -> PaperInfo:
    """Get paper information from URL using default settings.
    
    Args:
        url: URL to get information from
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary containing paper information
    """
    extractor = PaperInfoExtractor(timeout=timeout)
    try:
        return extractor.get_paper_info(url)
    finally:
        extractor.close()


def extract_arxiv_id(url: str) -> Optional[str]:
    """Extract arXiv ID from URL using default settings.
    
    Args:
        url: URL to extract arXiv ID from
        
    Returns:
        Extracted arXiv ID or None
    """
    extractor = PaperInfoExtractor()
    try:
        return extractor.extract_arxiv_id_from_url(url)
    finally:
        extractor.close()
