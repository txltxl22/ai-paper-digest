"""
Search services for paper content search functionality.
"""
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging


class SearchService:
    """Service for searching papers by content, title, and tags."""
    
    def __init__(self, summary_dir: Path):
        self.summary_dir = summary_dir
        self._cache: Dict = {
            "content_index": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
    
    def _build_content_index(self) -> List[Dict[str, Any]]:
        """Build a searchable content index from all papers."""
        # Get all .json files (new format) and .md files (legacy format)
        json_files = list(self.summary_dir.glob("*.json"))
        md_files = list(self.summary_dir.glob("*.md"))
        
        # Filter out .tags.json files from json_files
        json_files = [f for f in json_files if not f.name.endswith('.tags.json')]
        
        # Count total files for cache invalidation
        count = len(json_files) + len(md_files)
        
        # Compute latest mtime considering all relevant files
        latest_mtime = 0.0
        for p in json_files + md_files:
            try:
                latest_mtime = max(latest_mtime, p.stat().st_mtime)
            except Exception:
                continue

        if (
            self._cache.get("content_index") is not None
            and self._cache.get("count") == count
            and float(self._cache.get("latest_mtime") or 0.0) >= float(latest_mtime)
        ):
            return list(self._cache["content_index"])

        content_index: List[Dict] = []
        processed_ids = set()
        
        # Process new JSON format files first
        for json_path in json_files:
            try:
                arxiv_id = json_path.stem
                if arxiv_id in processed_ids:
                    continue
                    
                data = json.loads(json_path.read_text(encoding="utf-8"))
                service_data = data.get("service_data", {})
                summary_data = data.get("summary_data", {})
                
                # Extract searchable content
                searchable_content = self._extract_searchable_content(data, arxiv_id)
                if searchable_content:
                    content_index.append(searchable_content)
                    processed_ids.add(arxiv_id)
            except Exception as e:
                logging.error(f"Error processing JSON file {json_path} for search index: {e}")
                continue
        
        # Process legacy .md files
        for md_path in md_files:
            try:
                arxiv_id = md_path.stem
                if arxiv_id in processed_ids:
                    continue
                    
                # Load content from markdown file
                md_content = md_path.read_text(encoding="utf-8", errors="ignore")
                
                # Load tags from legacy .tags.json file
                tags: List[str] = []
                top_tags: List[str] = []
                detail_tags: List[str] = []
                tags_file = md_path.with_suffix("")
                tags_file = tags_file.with_name(tags_file.name + ".tags.json")
                try:
                    if tags_file.exists():
                        data = json.loads(tags_file.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            detail_tags = [str(t).strip().lower() for t in data if str(t).strip()]
                        elif isinstance(data, dict):
                            container = data
                            if isinstance(data.get("tags"), dict):
                                container = data.get("tags") or {}
                            if isinstance(container.get("top"), list):
                                top_tags = [str(t).strip().lower() for t in container.get("top") if str(t).strip()]
                            if isinstance(container.get("tags"), list):
                                detail_tags = [str(t).strip().lower() for t in container.get("tags") if str(t).strip()]
                        tags = (top_tags or []) + (detail_tags or [])
                except Exception:
                    tags = []

                # Extract title from markdown content
                title = self._extract_title_from_markdown(md_content)
                
                searchable_content = {
                    "id": arxiv_id,
                    "title": title,
                    "content": md_content,
                    "tags": tags,
                    "top_tags": top_tags,
                    "detail_tags": detail_tags,
                    "source_type": "system",
                    "user_id": None,
                    "original_url": None,
                }
                
                content_index.append(searchable_content)
                processed_ids.add(arxiv_id)
            except Exception as e:
                logging.error(f"Error processing legacy MD file {md_path} for search index: {e}")
                continue

        self._cache["content_index"] = list(content_index)
        self._cache["count"] = count
        self._cache["latest_mtime"] = latest_mtime
        return content_index
    
    def _extract_searchable_content(self, data: Dict, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Extract searchable content from JSON data."""
        try:
            service_data = data.get("service_data", {})
            summary_data = data.get("summary_data", {})
            
            # Extract title
            title = self._extract_title_from_data(summary_data, arxiv_id)
            
            # Extract content
            content = summary_data.get("markdown_content", summary_data.get("content", ""))
            
            # If markdown content is empty, try to generate from structured content
            if not content and "structured_content" in summary_data:
                try:
                    structured_content = summary_data.get("structured_content", {})
                    if structured_content and isinstance(structured_content, dict):
                        if "paper_info" in structured_content:
                            from summary_service.models import parse_summary
                            structured_summary = parse_summary(json.dumps(structured_content))
                            content = structured_summary.to_markdown()
                        elif "content" in structured_content:
                            content = structured_content.get("content", "")
                except Exception as e:
                    logging.error(f"Error converting structured content to markdown: {e}")
            
            # Parse tags
            tags: List[str] = []
            top_tags: List[str] = []
            detail_tags: List[str] = []
            
            tags_dict = summary_data.get("tags", {})
            if isinstance(tags_dict, dict):
                container = tags_dict
                if isinstance(tags_dict.get("tags"), dict):
                    container = tags_dict.get("tags") or {}
                
                if isinstance(container.get("top"), list):
                    top_tags = [str(t).strip().lower() for t in container.get("top") if str(t).strip()]
                if isinstance(container.get("tags"), list):
                    detail_tags = [str(t).strip().lower() for t in container.get("tags") if str(t).strip()]
            tags = (top_tags or []) + (detail_tags or [])
            
            return {
                "id": arxiv_id,
                "title": title,
                "content": content,
                "tags": tags,
                "top_tags": top_tags,
                "detail_tags": detail_tags,
                "source_type": service_data.get("source_type", "system"),
                "user_id": service_data.get("user_id"),
                "original_url": service_data.get("original_url"),
            }
        except Exception as e:
            logging.error(f"Error extracting searchable content for {arxiv_id}: {e}")
            return None
    
    def _extract_title_from_data(self, summary_data: Dict, arxiv_id: str) -> str:
        """Extract title from summary data."""
        # Try to get title from structured content first
        structured_content = summary_data.get("structured_content", {})
        if isinstance(structured_content, dict):
            paper_info = structured_content.get("paper_info", {})
            if isinstance(paper_info, dict):
                title = paper_info.get("title", "")
                if title:
                    return title
        
        # Try to extract from markdown content
        content = summary_data.get("markdown_content", summary_data.get("content", ""))
        if content:
            title = self._extract_title_from_markdown(content)
            if title:
                return title
        
        # Fallback to arxiv_id
        return f"Paper {arxiv_id}"
    
    def _extract_title_from_markdown(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Look for # title or ## title patterns
            if line.startswith('#') and len(line) > 1:
                title = line.lstrip('#').strip()
                if title:
                    return title
            # Look for **title** patterns
            elif line.startswith('**') and line.endswith('**') and len(line) > 4:
                title = line[2:-2].strip()
                if title:
                    return title
        return ""
    
    def search(self, query: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """Search papers by query across specified fields.
        
        Args:
            query: Search query string
            search_fields: List of fields to search in ['title', 'content', 'tags']
        
        Returns:
            List of matching papers with relevance scores
        """
        if not query or not query.strip():
            return []
        
        if search_fields is None:
            search_fields = ['title', 'content', 'tags']
        
        query = query.strip().lower()
        content_index = self._build_content_index()
        results = []
        
        for paper in content_index:
            score = 0
            matches = []
            
            # Search in title
            if 'title' in search_fields and paper.get('title'):
                title_matches = self._search_in_text(paper['title'], query)
                if title_matches:
                    score += title_matches * 3  # Higher weight for title matches
                    matches.extend([f"标题: {match}" for match in self._get_match_contexts(paper['title'], query)])
            
            # Search in content
            if 'content' in search_fields and paper.get('content'):
                content_matches = self._search_in_text(paper['content'], query)
                if content_matches:
                    score += content_matches
                    matches.extend([f"内容: {match}" for match in self._get_match_contexts(paper['content'], query)])
            
            # Search in tags
            if 'tags' in search_fields:
                tag_matches = 0
                for tag_list_name in ['tags', 'top_tags', 'detail_tags']:
                    tags = paper.get(tag_list_name, [])
                    for tag in tags:
                        if query in tag.lower():
                            tag_matches += 1
                            matches.append(f"标签: {tag}")
                
                if tag_matches:
                    score += tag_matches * 2  # Higher weight for tag matches
            
            if score > 0:
                results.append({
                    **paper,
                    'relevance_score': score,
                    'matches': matches[:5]  # Limit to 5 matches for display
                })
        
        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results
    
    def _search_in_text(self, text: str, query: str) -> int:
        """Count occurrences of query in text (case-insensitive)."""
        if not text:
            return 0
        return len(re.findall(re.escape(query), text.lower()))
    
    def _get_match_contexts(self, text: str, query: str, context_length: int = 50) -> List[str]:
        """Get context around matches in text."""
        if not text:
            return []
        
        text_lower = text.lower()
        query_lower = query.lower()
        contexts = []
        
        start = 0
        while True:
            pos = text_lower.find(query_lower, start)
            if pos == -1:
                break
            
            # Get context around the match
            context_start = max(0, pos - context_length)
            context_end = min(len(text), pos + len(query) + context_length)
            context = text[context_start:context_end]
            
            # Clean up context
            if context_start > 0:
                context = "..." + context
            if context_end < len(text):
                context = context + "..."
            
            contexts.append(context.strip())
            start = pos + 1
        
        return contexts[:3]  # Limit to 3 contexts
    
    def clear_cache(self):
        """Clear the search index cache."""
        self._cache = {
            "content_index": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
