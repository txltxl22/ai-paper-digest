"""
RSS Processing Module

This module provides functionality for fetching and parsing RSS feeds to extract
paper links for processing, and generating RSS feeds from paper summaries.
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional
from glob import glob

import requests
import xml.etree.ElementTree as ET
import markdown
from feedgen.feed import FeedGenerator

_LOG = logging.getLogger(__name__)


def fetch_rss(url: str, timeout: float = 10.0) -> str:
    """
    Download the RSS feed XML from the given URL.

    Args:
        url: RSS feed URL
        timeout: Request timeout in seconds

    Returns:
        XML content as text

    Raises:
        requests.exceptions.RequestException: On network errors
    """
    _LOG.debug(f"Fetching RSS feed from {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_links(xml_content: str) -> List[str]:
    """
    Parse RSS XML content and extract all <item><link> values.

    Args:
        xml_content: RSS feed as string

    Returns:
        List of URLs found in <item><link>
    """
    root = ET.fromstring(xml_content)
    # RSS 2.0 standard: items are under channel/item
    links = []
    for item in root.findall("./channel/item"):
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            links.append(link_el.text.strip())

    _LOG.debug(f"Found {len(links)} links in RSS feed")
    return links


def get_links_from_rss(url: str, timeout: float = 10.0) -> List[str]:
    """
    Convenience wrapper: fetch + parse.

    Args:
        url: RSS feed URL
        timeout: Request timeout in seconds

    Returns:
        List of links

    Raises:
        requests.exceptions.RequestException: On network errors
        ET.ParseError: On XML parsing errors
    """
    xml = fetch_rss(url, timeout)
    return parse_links(xml)


def extract_first_header(text: str) -> str:
    """
    Extract the first header from markdown text.
    
    Args:
        text: Markdown text content
        
    Returns:
        First header text or "Unknown Title" if no header found
    """
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            # Remove the # symbols and return the title
            return line.lstrip('#').strip()
    return "Unknown Title"


def _load_existing_entries(rss_file_path: Path) -> List[str]:
    """
    Load existing RSS entries from a file.
    
    Args:
        rss_file_path: Path to the RSS file
        
    Returns:
        List of existing paper URLs
    """
    existing_entries = []
    if os.path.exists(rss_file_path):
        tree = ET.parse(rss_file_path)
        root = tree.getroot()
        
        for item in root.findall(".//item"):
            paper_url = item.find("link").text
            existing_entries.append(paper_url)
    
    return existing_entries


def _create_feed_generator(
    feed_title: str,
    feed_link: str,
    feed_description: str
) -> FeedGenerator:
    """
    Create and configure a FeedGenerator.
    
    Args:
        feed_title: Title of the RSS feed
        feed_link: Link to the website
        feed_description: Description of the RSS feed
        
    Returns:
        Configured FeedGenerator
    """
    fg = FeedGenerator()
    fg.title(feed_title)
    fg.link(href=feed_link)
    fg.description(feed_description)
    return fg


def _load_local_summaries_for_rebuild() -> List[Tuple[Path, str, str]]:
    """
    Load summaries from local markdown directory for rebuild mode.
    
    Returns:
        List of tuples (summary_path, paper_url, paper_subject)
    """
    local_summaries = []
    papers = glob("markdown/*.md")
    
    for p in papers:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
            paper_subject = extract_first_header(text)
            pdf_url = "https://arxiv.org/pdf/" + p.split(os.path.sep)[-1].replace('.md', ".pdf")
            summary_path = Path(p.replace('markdown/', 'summary/'))
            if summary_path.exists():
                local_summaries.append((summary_path, pdf_url, paper_subject))
    
    return local_summaries


def _add_new_entries(
    fg: FeedGenerator,
    successes: List[Tuple[Path, str, str]],
    existing_entries: List[str]
) -> List:
    """
    Add new entries to the RSS feed.
    
    Args:
        fg: FeedGenerator instance
        successes: List of tuples (summary_path, paper_url, paper_subject)
        existing_entries: List of existing paper URLs
        
    Returns:
        List of new entries added
    """
    new_items = []
    
    for path, paper_url, *rest in successes:
        paper_subject = rest[0] if rest else "Unknown Title"
        
        if not path.exists():
            _LOG.warning(f"Summary file {path} does not exist, skipping RSS entry")
            continue
        
        try:
            paper_summary_markdown_content = path.read_text(encoding="utf-8")
            paper_summary_html = markdown.markdown(paper_summary_markdown_content)
            
            if paper_url not in existing_entries:
                entry = fg.add_entry()
                entry.title(f"{paper_subject}")
                entry.link(href=paper_url)
                entry.description(paper_summary_html)
                new_items.append(entry)
            else:
                _LOG.debug(f"Paper {paper_url} already exists in RSS feed, skipping")
        except Exception as e:
            _LOG.error(f"Failed to process {path} for RSS: {e}")
            continue
    
    return new_items


def _recreate_existing_entries(fg: FeedGenerator, rss_file_path: Path) -> None:
    """
    Recreate existing entries from the RSS file.
    
    Args:
        fg: FeedGenerator instance
        rss_file_path: Path to the RSS file
    """
    tree = ET.parse(rss_file_path)
    root = tree.getroot()
    
    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        desc_elem = item.find("description")
        
        if title_elem is not None and link_elem is not None and desc_elem is not None:
            entry = fg.add_entry()
            entry.title(title_elem.text or "Unknown Title")
            entry.link(href=link_elem.text or "")
            entry.description(desc_elem.text or "")


def _truncate_feed(
    fg: FeedGenerator,
    max_items: int,
    feed_title: str,
    feed_link: str,
    feed_description: str
) -> FeedGenerator:
    """
    Truncate the feed to keep only the latest items.
    
    Args:
        fg: FeedGenerator instance
        max_items: Maximum number of items to keep
        feed_title: Title of the RSS feed
        feed_link: Link to the website
        feed_description: Description of the RSS feed
        
    Returns:
        Truncated FeedGenerator
    """
    current_entries = fg.entry()
    if len(current_entries) <= max_items:
        return fg
    
    _LOG.info(f"Truncating RSS feed to {max_items} items (was {len(current_entries)} items)")
    
    fg_truncated = FeedGenerator()
    fg_truncated.title(feed_title)
    fg_truncated.link(href=feed_link)
    fg_truncated.description(feed_description)
    
    for entry in current_entries[:max_items]:
        new_entry = fg_truncated.add_entry()
        new_entry.title(entry.title())
        new_entry.link(href=entry.link()[0]['href'])
        new_entry.description(entry.description())
    
    return fg_truncated


def _save_feed(fg: FeedGenerator, rss_file_path: Path) -> None:
    """
    Save the RSS feed to file.
    
    Args:
        fg: FeedGenerator instance
        rss_file_path: Path to save the RSS file
    """
    rss_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rss_file_path, 'w', encoding="utf-8") as rss_file:
        rss_file.write(fg.rss_str(pretty=True).decode('utf-8'))


def generate_rss_feed(
    successes: List[Tuple[Path, str, str]], 
    rss_file_path: Path,
    rebuild: bool = False,
    max_items: int = 30,
    feed_title: str = "Research Paper Summaries",
    feed_link: str = "https://www.wawuyu.com",
    feed_description: str = "Summaries of research papers"
) -> int:
    """
    Generate or update an RSS feed from paper summaries.
    
    Args:
        successes: List of tuples (summary_path, paper_url, paper_subject)
        rss_file_path: Path to the RSS file to create/update
        rebuild: Whether to rebuild the entire feed from local summaries
        max_items: Maximum number of items to keep in the feed
        feed_title: Title of the RSS feed
        feed_link: Link to the website
        feed_description: Description of the RSS feed
        
    Returns:
        Total number of entries in the final RSS feed
    """
    # Load existing entries if not rebuilding
    existing_entries = [] if rebuild else _load_existing_entries(rss_file_path)
    
    # Create feed generator
    fg = _create_feed_generator(feed_title, feed_link, feed_description)
    
    # Handle rebuild mode
    if rebuild:
        _LOG.info("Rebuilding RSS feed from local summaries...")
        if os.path.exists(rss_file_path):
            os.remove(rss_file_path)
        local_summaries = _load_local_summaries_for_rebuild()
        successes.extend(local_summaries)
    
    # Add new entries
    new_items = _add_new_entries(fg, successes, existing_entries)
    
    # Recreate existing entries if not rebuilding
    if not rebuild and existing_entries:
        _LOG.info(f"Found {len(existing_entries)} existing RSS entries, recreating them...")
        _recreate_existing_entries(fg, rss_file_path)
    
    # Truncate feed if needed
    fg = _truncate_feed(fg, max_items, feed_title, feed_link, feed_description)
    
    # Save the feed
    _save_feed(fg, rss_file_path)
    
    # Log results
    total_entries = len(fg.entry())
    _LOG.info(f"📢 RSS feed updated: {len(new_items)} new items added, {total_entries} total items in feed")
    
    return total_entries
