"""
paper_summarizer.py – Core module for single paper summarization pipeline

This module provides both a CLI interface and a programmatic API for processing
individual academic papers from URLs to structured summaries.

FEATURES:
- PDF download and validation with caching
- Text extraction and markdown conversion
- Progressive summarization with LLM providers (DeepSeek, OpenAI, Ollama)
- Tag generation and service record management
- Extract-only mode for text extraction without LLM processing
- Local mode for processing cached files
- Comprehensive error handling and logging

ARCHITECTURE:
- URL resolution → PDF download → text extraction → chunking → LLM summarization → tag generation
- Modular design using summary_service components
- Caching at multiple levels (PDF, markdown, summaries, tags)
- Service record format for metadata and backward compatibility
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Import the new summary service
from summary_service import SummaryService


# ---------------------------------------------------------------------------
# Configuration & constants
# ---------------------------------------------------------------------------
__version__ = "0.3.0"
MODEL_NAME = "deepseek-chat"
CHUNK_LENGTH = 5000
CHUNK_OVERLAP_RATIO = 0.05

DEFAULT_PROXY_URL = "socks5://127.0.0.1:1081"

# LLM Provider configuration
DEFAULT_LLM_PROVIDER = "deepseek"  # "deepseek", "ollama", or "openai"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"  # Default model for OpenAI-compatible APIs

# Directories for caching
BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "papers"
MD_DIR = BASE_DIR / "markdown"
SUMMARY_DIR = BASE_DIR / "summary"
CHUNKS_SUMMARY_DIR = SUMMARY_DIR / "chunks"
for d in (PDF_DIR, MD_DIR, SUMMARY_DIR, CHUNKS_SUMMARY_DIR):
    d.mkdir(exist_ok=True)

_LOG = logging.getLogger("paper_summarizer")


# ---------------------------------------------------------------------------
# Import modular functions directly
# ---------------------------------------------------------------------------

from summary_service.pdf_processor import (
    build_session,
    resolve_pdf_url,
    download_pdf,
    verify_pdf_integrity,
)
from summary_service.markdown_processor import extract_markdown
from summary_service.text_processor import chunk_text
from summary_service.llm_utils import llm_invoke
from summary_service.summary_generator import (
    progressive_summary,
    generate_tags_from_summary,
)

# Create session without proxy by default
SESSION = build_session()


# ---------------------------------------------------------------------------
# Core summarization function
# ---------------------------------------------------------------------------

def summarize_paper_url(
    url: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    max_input_char: int = 50000,
    extract_only: bool = False,
    local: bool = False,
    max_workers: int = 1,
    session: Optional[object] = None,
) -> tuple[Optional[Path], Optional[str], Optional[str]]:
    """Run the full summarization pipeline for a single paper URL.
    
    Args:
        url: Paper URL (PDF or landing page)
        api_key: API key for the LLM provider
        base_url: Base URL for OpenAI-compatible APIs
        provider: LLM provider (deepseek, ollama, openai)
        model: Model name for the provider
        max_input_char: Maximum input characters for summarization
        extract_only: Only extract text, skip LLM processing
        local: Use local cached files if available
        max_workers: Number of concurrent workers for chunk processing
        session: Requests session to use (optional)
        
    Returns:
        Tuple of (summary_path, pdf_url, paper_subject) or (None, None, None) on failure
    """
    import re
    from summary_service.record_manager import save_summary_with_service_record
    
    if extract_only:
        _LOG.info("📄  Extracting text from %s", url)
    else:
        _LOG.info("📝  Summarizing %s", url)

    try:
        # Use provided session or default
        current_session = session or SESSION
        
        # Step 1: Process PDF and extract text
        pdf_url = resolve_pdf_url(url, current_session)
        
        if local:
            pdf_path = download_pdf(pdf_url, output_dir=PDF_DIR, session=current_session, skip_download=True)
        else:
            pdf_path = download_pdf(pdf_url, output_dir=PDF_DIR, session=current_session)
        
        md_path = extract_markdown(pdf_path, md_dir=MD_DIR)
        text = md_path.read_text(encoding="utf-8")
        paper_subject = extract_first_header(text)
        
        # Step 2: If extract_only mode, return immediately
        if extract_only:
            _LOG.info("✅  Extracted text saved to %s", md_path)
            return md_path, pdf_url, paper_subject

        # Step 3: Prepare text for summarization
        text = re.sub(r'\^\[\d+\](.*\n)+', '', text)  # remove references
        if max_input_char > 0:
            text = text[:max_input_char]
        chunks = chunk_text(text)

        # Step 4: Check if summary already exists
        f_name = pdf_path.stem + ".md"
        summary_path = SUMMARY_DIR / f_name
        
        if summary_path.exists():
            # Handle existing summary - generate tags if missing
            try:
                _LOG.info("🏷️  Generating tags for existing summary %s", pdf_path.stem)
                summary_text = summary_path.read_text(encoding="utf-8")
                tag_raw = generate_tags_from_summary(
                    summary_text, 
                    api_key=api_key, 
                    base_url=base_url, 
                    provider=provider, 
                    model=model
                )
                tag_obj = {"tags": tag_raw.tags, "top": tag_raw.top} if hasattr(tag_raw, 'tags') else {"tags": [], "top": []}
                
                # Save using service record format
                save_summary_with_service_record(
                    arxiv_id=pdf_path.stem,
                    summary_content=summary_text,
                    tags=tag_obj,
                    summary_dir=SUMMARY_DIR,
                    source_type="system",
                    original_url=pdf_url
                )
                _LOG.info("✅  Updated tags for existing summary %s", pdf_path.stem)
            except Exception as exc:
                _LOG.exception("Failed to generate tags for %s: %s", pdf_path.stem, exc)
            
            return summary_path, pdf_url, paper_subject
        else:
            # Generate new summary
            summary_json_path = SUMMARY_DIR / (pdf_path.stem + ".json")
            chunk_summary_path = CHUNKS_SUMMARY_DIR / (pdf_path.stem + ".json")
            
            summary, chunks_summary = progressive_summary(
                chunks,
                summary_path=summary_json_path,
                chunk_summary_path=chunk_summary_path,
                api_key=api_key,
                base_url=base_url,
                provider=provider,
                model=model,
                max_workers=max_workers,
            )

            # Save structured summary immediately after LLM generation
            if summary:
                try:
                    _LOG.info("💾 Saving structured summary for %s", pdf_path.stem)
                    
                    # Save using the new service record format immediately
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=summary,  # StructuredSummary object from LLM
                        tags={"top": [], "tags": []},  # Empty tags for now
                        summary_dir=SUMMARY_DIR,
                        source_type="system",
                        original_url=pdf_url
                    )
                    _LOG.info("✅  Saved structured summary with service record for %s", pdf_path.stem)
                except Exception as exc:
                    _LOG.exception("Failed to save structured summary for %s: %s", pdf_path.stem, exc)
                    # Fallback to markdown if service record saving fails
                    summary_markdown = summary.to_markdown() if summary else "Paper summary"
                    summary_path.write_text(summary_markdown, encoding="utf-8")
            else:
                _LOG.error("❌ LLM failed to generate structured summary for %s", pdf_path.stem)
                # Generate a basic markdown summary as fallback
                summary_markdown = f"# {pdf_path.stem}\n\nLLM failed to generate structured summary. Please try again later."
                summary_path.write_text(summary_markdown, encoding="utf-8")
            
            # Generate and persist tags alongside the summary
            if summary:  # Only generate tags if we have a structured summary
                try:
                    _LOG.info("🏷️  Generating tags for %s", pdf_path.stem)
                    
                    # Convert structured summary to markdown for tag generation
                    summary_text = summary.to_markdown()
                    
                    tag_raw = generate_tags_from_summary(
                        summary_text, 
                        api_key=api_key, 
                        base_url=base_url, 
                        provider=provider, 
                        model=model
                    )
                    tag_obj = {"tags": tag_raw.tags, "top": tag_raw.top} if hasattr(tag_raw, 'tags') else {"tags": [], "top": []}
                    
                    # Update the service record with tags
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=summary,  # StructuredSummary object
                        tags=tag_obj,
                        summary_dir=SUMMARY_DIR,
                        source_type="system",
                        original_url=pdf_url
                    )
                    _LOG.info("✅  Updated summary with tags for %s", pdf_path.stem)
                        
                except Exception as exc:
                    _LOG.exception("Failed to generate tags for %s: %s", pdf_path.stem, exc)
                    # Tags failed, but structured summary is already saved
            else:
                _LOG.warning("⚠️  Skipping tag generation for %s - no structured summary available", pdf_path.stem)

            _LOG.info("✅  Done – summary saved to %s", summary_path)
            return summary_path, pdf_url, paper_subject

    except Exception as exc:  # pylint: disable=broad-except
        _LOG.error("❌  %s – %s", url, exc)
        _LOG.exception(exc)
        return None, None, None


def extract_first_header(markdown_text: str) -> str:
    """Extract the first header from markdown text."""
    import re
    match = re.search(r'^##\s+(.+)$', markdown_text, re.MULTILINE)
    if match:
        return match.group(1).replace("**", '').strip()
    return ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize an academic paper via LLM (DeepSeek or Ollama)"
    )
    parser.add_argument("url", help="Paper URL (PDF or landing page)")
    parser.add_argument("--api-key", help="DeepSeek/OpenAI API key")
    parser.add_argument(
        "--base-url",
        help="Base URL for OpenAI-compatible LLM API (e.g., https://api.openai.com/v1)",
    )
    parser.add_argument(
        "--provider",
        choices=["deepseek", "ollama"],
        default=DEFAULT_LLM_PROVIDER,
        help=f"LLM provider to use (default: {DEFAULT_LLM_PROVIDER})",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=DEFAULT_OLLAMA_BASE_URL,
        help=f"Ollama service base URL (default: {DEFAULT_OLLAMA_BASE_URL})",
    )
    parser.add_argument(
        "--ollama-model",
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Ollama model name (default: {DEFAULT_OLLAMA_MODEL})",
    )
    parser.add_argument("--proxy", help="Proxy URL to use")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.proxy:
        global SESSION  # pylint: disable=global-statement
        SESSION = build_session(args.proxy)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        summary_path, pdf_url, paper_subject = summarize_paper_url(
            url=args.url,
            api_key=args.api_key,
            base_url=args.base_url,
            provider=args.provider,
            model=args.ollama_model if args.provider == "ollama" else "deepseek-chat",
            session=SESSION,
        )
        
        if summary_path:
            print("\n" + "=" * 80 + "\nFINAL SUMMARY saved to:\n" + str(summary_path))
            if paper_subject:
                print(f"Paper: {paper_subject}")
        else:
            print("\n" + "=" * 80 + "\nERROR: Failed to generate summary")

    except Exception as e:
        _LOG.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
