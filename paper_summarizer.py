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
from typing import Optional, Dict, Any

# Import the new summary service
from summary_service import SummaryService, load_summary_with_service_record
from summary_service.models import PaperInfo, SummarizationResult


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
    generate_abstract_summary,
)
from summary_service.paper_info_extractor import PaperInfoExtractor

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
    abstract_only: bool = False,
    local: bool = False,
    max_workers: int = 1,
    session: Optional[object] = None,
) -> SummarizationResult:
    """Run the full summarization pipeline for a single paper URL.
    
    Args:
        url: Paper URL (PDF or landing page)
        api_key: API key for the LLM provider
        base_url: Base URL for OpenAI-compatible APIs
        provider: LLM provider (deepseek, ollama, openai)
        model: Model name for the provider
        max_input_char: Maximum input characters for summarization
        extract_only: Only extract text, skip LLM processing
        abstract_only: Only generate one sentence summary for abstract
        local: Use local cached files if available
        max_workers: Number of concurrent workers for chunk processing
        session: Requests session to use (optional)
        
    Returns:
        SummarizationResult object with summary path, PDF URL, paper subject, and structured summary
    """
    import re
    from summary_service.record_manager import save_summary_with_service_record

    paper_info_cache: Optional[PaperInfo] = None

    def _get_paper_info_once() -> PaperInfo:
        """Fetch paper metadata once per summarization run."""
        nonlocal paper_info_cache
        if paper_info_cache is not None:
            return paper_info_cache
        extractor = PaperInfoExtractor()
        try:
            paper_info_cache = extractor.get_paper_info(url)
        except Exception as extract_exc:  # pylint: disable=broad-except
            _LOG.warning("Failed to extract paper info for %s: %s", url, extract_exc)
            from summary_service.models import PaperInfo
            paper_info_cache = PaperInfo(title_en="", abstract="")
        finally:
            extractor.close()
        return paper_info_cache
    
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
        summary_path = SUMMARY_DIR / f"{pdf_path.stem}.md"  # Define summary_path early
        
        # Step 2: If extract_only mode, save paper info if extracted and return
        if extract_only:
            paper_info = _get_paper_info_once()
            # Save paper info if we extracted it
            if paper_info and (paper_info.title_en or paper_info.abstract):
                try:
                    from summary_service.models import StructuredSummary, Results, Tags
                    # Create a minimal structured summary with just paper info
                    minimal_summary = StructuredSummary(
                        paper_info=PaperInfo(
                            title_zh="",  # Will be filled by LLM later
                            title_en=paper_info.title_en or "",
                            abstract=paper_info.abstract or ""
                        ),
                        one_sentence_summary="",
                        innovations=[],
                        results=Results(experimental_highlights=[], practical_value=[]),
                        terminology=[]
                    )
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=minimal_summary,
                        tags=Tags(top=[], tags=[]),
                        summary_dir=SUMMARY_DIR,
                        source_type="system",
                        original_url=pdf_url
                    )
                    _LOG.info("💾 Saved extracted paper info for %s", pdf_path.stem)
                except Exception as exc:
                    _LOG.warning("Failed to save paper info in extract_only mode: %s", exc)
            
            _LOG.info("✅  Extracted text saved to %s", md_path)
            return SummarizationResult.success(
                summary_path=md_path,
                pdf_url=pdf_url,
                paper_subject=paper_subject,
                arxiv_id=pdf_path.stem
            )

        # Step 3: Prepare text for summarization
        text = re.sub(r'\^\[\d+\](.*\n)+', '', text)  # remove references
        if max_input_char > 0:
            text = text[:max_input_char]
        chunks = chunk_text(text)

        # Step 4: Check if summary already exists
        existing_summary_record = load_summary_with_service_record(pdf_path.stem, SUMMARY_DIR)
        
        # If user requested full deep read (abstract_only=False) but existing summary is abstract-only,
        # we need to regenerate the full summary instead of returning the existing one
        should_regenerate_full = (
            existing_summary_record and
            not abstract_only and  # User wants full deep read
            existing_summary_record.service_data.is_abstract_only  # But existing is abstract-only
        )
        
        if existing_summary_record and not should_regenerate_full:
            # Handle existing summary - update title/abstract if extracted, generate tags if empty
            existing_structured_summary = existing_summary_record.summary_data.structured_content
            existing_tags = existing_summary_record.summary_data.tags
            
            try:
                # Check if paper info is missing 
                paper_info = None
                if existing_structured_summary.paper_info.title_en:
                    paper_info = existing_structured_summary.paper_info
                
                # If paper info is missing, extract and save it
                updated_abstract = False
                if not paper_info:
                    _LOG.info("📄 Paper info missing for %s, extracting and saving...", pdf_path.stem)
                    paper_info = _get_paper_info_once()
                    # Save paper info if we extracted it
                    if paper_info and paper_info.abstract:
                        try:
                            existing_structured_summary.paper_info.title_en = paper_info.title_en
                            existing_structured_summary.paper_info.abstract = paper_info.abstract
                            updated_abstract = True
                            _LOG.info("💾 Saved extracted paper info for %s", pdf_path.stem)
                        except Exception as exc:
                            _LOG.warning("Failed to save paper info in extract_only mode: %s", exc)
                
                # Generate tags if they are empty (always, not just in local mode)
                tags_to_save = existing_tags
                if not existing_tags.tags and not existing_tags.top:
                    _LOG.info("🏷️  Generating tags for existing summary %s (tags are empty)", pdf_path.stem)
                    if abstract_only:
                        tags_raw = generate_abstract_summary(paper_info.abstract, paper_info.title_en, api_key=api_key, base_url=base_url, provider=provider, model=model)
                    else:
                        summary_text = existing_structured_summary.to_markdown()
                        tags_raw = generate_tags_from_summary(
                            summary_text, 
                            api_key=api_key, 
                            base_url=base_url, 
                            provider=provider, 
                            model=model
                        )
                    tags_to_save = tags_raw
                
                # Save updated summary if title/abstract were updated or tags were generated
                if updated_abstract or (tags_to_save != existing_tags):
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=existing_structured_summary,
                        tags=tags_to_save,
                        summary_dir=SUMMARY_DIR,
                        source_type=existing_summary_record.service_data.source_type,
                        user_id=existing_summary_record.service_data.user_id,
                        original_url=existing_summary_record.service_data.original_url or pdf_url,
                        ai_judgment=existing_summary_record.service_data.ai_judgment,
                        first_created_at=existing_summary_record.service_data.first_created_at,
                        is_abstract_only=existing_summary_record.service_data.is_abstract_only
                    )
                    
                    if updated_abstract:
                        update_msg = "✅  Updated abstract for existing summary %s"
                    if tags_to_save != existing_tags:
                        update_msg += " and tags generated"
                    
                    _LOG.info(update_msg, pdf_path.stem)
                else:
                    _LOG.info("✅  Existing summary %s is up to date", pdf_path.stem)   
            except Exception as exc:
                _LOG.exception("Failed to process existing summary for %s: %s", pdf_path.stem, exc)
            
            return SummarizationResult.success(
                summary_path=summary_path,
                pdf_url=pdf_url,
                paper_subject=paper_subject,
                arxiv_id=pdf_path.stem,
                structured_summary=existing_structured_summary
            )
        else:
            # Generate new summary (or regenerate from abstract-only)
            # Always check if a record exists to preserve first_created_at
            if existing_summary_record:
                # Preserve original metadata from existing record
                preserved_source_type = existing_summary_record.service_data.source_type
                preserved_user_id = existing_summary_record.service_data.user_id
                preserved_original_url = existing_summary_record.service_data.original_url or pdf_url
                preserved_ai_judgment = existing_summary_record.service_data.ai_judgment
                preserved_first_created_at = existing_summary_record.service_data.first_created_at
                if should_regenerate_full:
                    _LOG.info("🔄 Regenerating full deep read summary for %s (was abstract-only)", pdf_path.stem)
            else:
                # Truly new summary - check if a record file exists to preserve first_created_at
                preserved_first_created_at = None
                try:
                    existing_check = load_summary_with_service_record(pdf_path.stem, SUMMARY_DIR)
                    if existing_check and existing_check.service_data.first_created_at:
                        preserved_first_created_at = existing_check.service_data.first_created_at
                        _LOG.info("📅 Preserving first_created_at from existing record: %s", preserved_first_created_at)
                except Exception:
                    pass
                
                preserved_source_type = "system"
                preserved_user_id = None
                preserved_original_url = pdf_url
                preserved_ai_judgment = None
            
            summary_json_path = SUMMARY_DIR / (pdf_path.stem + ".json")
            chunk_summary_path = CHUNKS_SUMMARY_DIR / (pdf_path.stem + ".json")

            # Extract paper metadata before running LLM summary
            paper_info = _get_paper_info_once()
            paper_title = paper_info.title_en
            paper_abstract = paper_info.abstract
            
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

                    # Apply extracted metadata if available
                    if paper_title:
                        original_title_en = summary.paper_info.title_en
                        summary.paper_info.title_en = paper_title
                        _LOG.info(
                            "🔄 Updated generated summary title '%s' with extracted title '%s' for %s",
                            original_title_en,
                            paper_title,
                            pdf_path.stem,
                        )
                    if paper_abstract:
                        summary.paper_info.abstract = paper_abstract
                        _LOG.info("📄 Extracted abstract for %s", pdf_path.stem)
                    
                    # Save using the new service record format immediately
                    # Abstract is already in summary.paper_info.abstract
                    from summary_service.models import Tags
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=summary,  # StructuredSummary object from LLM
                        tags=Tags(top=[], tags=[]),  # Empty tags for now
                        summary_dir=SUMMARY_DIR,
                        source_type=preserved_source_type,
                        user_id=preserved_user_id,
                        original_url=preserved_original_url,
                        ai_judgment=preserved_ai_judgment,
                        first_created_at=preserved_first_created_at,
                        is_abstract_only=False  # This is a full deep read
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
                    # Update the service record with tags
                    # Abstract is already in summary.paper_info.abstract
                    save_summary_with_service_record(
                        arxiv_id=pdf_path.stem,
                        summary_content=summary,  # StructuredSummary object
                        tags=tag_raw,  # Tags object
                        summary_dir=SUMMARY_DIR,
                        source_type=preserved_source_type,
                        user_id=preserved_user_id,
                        original_url=preserved_original_url,
                        ai_judgment=preserved_ai_judgment,
                        first_created_at=preserved_first_created_at,
                        is_abstract_only=False  # This is a full deep read
                    )
                    _LOG.info("✅  Updated summary with tags for %s", pdf_path.stem)
                        
                except Exception as exc:
                    _LOG.exception("Failed to generate tags for %s: %s", pdf_path.stem, exc)
                    # Tags failed, but structured summary is already saved
            else:
                _LOG.warning("⚠️  Skipping tag generation for %s - no structured summary available", pdf_path.stem)

            _LOG.info("✅  Done – summary saved to %s", summary_path)
            return SummarizationResult.success(
                summary_path=summary_path,
                pdf_url=pdf_url,
                paper_subject=paper_subject,
                arxiv_id=pdf_path.stem,
                structured_summary=summary
            )

    except Exception as exc:  # pylint: disable=broad-except
        _LOG.error("❌  %s – %s", url, exc)
        _LOG.exception(exc)
        return SummarizationResult.failure()


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
        result = summarize_paper_url(
            url=args.url,
            api_key=args.api_key,
            base_url=args.base_url,
            provider=args.provider,
            model=args.ollama_model if args.provider == "ollama" else "deepseek-chat",
            session=SESSION,
        )
        
        if result.is_success:
            print("\n" + "=" * 80 + "\nFINAL SUMMARY saved to:\n" + str(result.summary_path))
            if result.paper_subject:
                print(f"Paper: {result.paper_subject}")
        else:
            print("\n" + "=" * 80 + "\nERROR: Failed to generate summary")

    except Exception as e:
        _LOG.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
