"""
paper_summarizer.py – A small CLI tool that reads an academic paper from a URL
and produces a concise summary with DeepSeek-v3 (or any OpenAI-compatible) LLM.

This revision:
- Caches intermediate files (PDF, markdown, chunk summaries)
- Graceful error handling
- Uses structured JSON schema for summaries
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
# Tag generation from summary
# ---------------------------------------------------------------------------


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
        _LOG.info("Resolving PDF URL for %s", args.url)
        pdf_url = resolve_pdf_url(args.url)
        _LOG.info("PDF URL: %s", pdf_url)

        pdf_path = download_pdf(pdf_url)
        _LOG.info("PDF cached at %s", pdf_path)

        md_path = extract_markdown(pdf_path)
        _LOG.info("Markdown at %s", md_path)

        text = md_path.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        _LOG.info("Split into %d chunks", len(chunks))

        summary_path = SUMMARY_DIR / (pdf_path.stem + ".json")
        chunk_summary_path = CHUNKS_SUMMARY_DIR / (pdf_path.stem + ".json")

        summary, chunk_summaries = progressive_summary(
            chunks,
            summary_path=summary_path,
            chunk_summary_path=chunk_summary_path,
            api_key=args.api_key,
            base_url=args.base_url,
            provider=args.provider,
            ollama_base_url=args.ollama_base_url,
            ollama_model=args.ollama_model,
        )

        if summary:
            print("\n" + "=" * 80 + "\nFINAL SUMMARY saved to:\n" + str(summary_path))
            print(f"Paper: {summary.paper_info.title_zh}")
            print(f"Summary: {summary.one_sentence_summary}")
        else:
            print("\n" + "=" * 80 + "\nERROR: Failed to generate structured summary")

    except Exception as e:
        _LOG.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
