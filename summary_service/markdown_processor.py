"""
markdown_processor.py - Markdown processing utilities

This module provides PDF to markdown conversion functionality.
"""

import logging
import re
from pathlib import Path

import pymupdf4llm

try:
    import pymupdf as fitz
except ImportError:
    fitz = None

_LOG = logging.getLogger("markdown_processor")


def extract_markdown(pdf_path: Path, md_dir: Path, max_retries: int = 3) -> Path:
    """Extract markdown text from PDF, caching if already done."""
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / (pdf_path.stem + ".md")

    if md_path.exists():
        return md_path

    # Try multiple PDF processing approaches with retries
    md_text = None
    all_errors = []

    for attempt in range(max_retries):
        if attempt > 0:
            _LOG.info(f"Retry attempt {attempt + 1}/{max_retries} for {pdf_path}")
            import time

            time.sleep(1)  # Brief pause between retries

        errors = []

        # Method 1: Primary - pymupdf4llm
        try:
            md_text = pymupdf4llm.to_markdown(str(pdf_path))
            if md_text and md_text.strip():
                break  # Success!
        except Exception as e:
            error_msg = f"MuPDF error: {e}"
            _LOG.error("Primary PDF processing failed for %s: %s", pdf_path, error_msg)
            errors.append(error_msg)

        # Method 2: Fallback - try with different MuPDF settings
        if not md_text and fitz:
            try:
                doc = fitz.open(str(pdf_path))
                md_text = ""
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    md_text += f"## Page {page_num + 1}\n\n{text}\n\n"
                doc.close()
                if md_text and md_text.strip():
                    break  # Success!
            except Exception as e:
                error_msg = f"Fallback MuPDF error: {e}"
                _LOG.error(
                    "Fallback PDF processing failed for %s: %s", pdf_path, error_msg
                )
                errors.append(error_msg)

        # Method 3: Last resort - try extracting raw text
        if not md_text and fitz:
            try:
                doc = fitz.open(str(pdf_path))
                md_text = ""
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    # Try different extraction methods
                    try:
                        text = page.get_text("text")
                    except:
                        text = page.get_text("html")
                        # Basic HTML to text conversion
                        text = re.sub(r"<[^>]+>", "", text)
                    md_text += f"## Page {page_num + 1}\n\n{text}\n\n"
                doc.close()
                if md_text and md_text.strip():
                    break  # Success!
            except Exception as e:
                error_msg = f"Raw text extraction error: {e}"
                _LOG.error("Raw text extraction failed for %s: %s", pdf_path, error_msg)
                errors.append(error_msg)

        all_errors.extend(errors)

    if not md_text or not md_text.strip():
        error_summary = " | ".join(all_errors)
        raise ValueError(
            f"All PDF processing methods failed for {pdf_path}. Errors: {error_summary}"
        )

    md_path.write_text(md_text, encoding="utf-8")
    return md_path


def clean_markdown_text(text: str) -> str:
    """Clean and normalize markdown text."""
    # Remove excessive whitespace
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def extract_text_from_markdown(md_path: Path) -> str:
    """Extract plain text from markdown file."""
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    text = md_path.read_text(encoding="utf-8")
    return clean_markdown_text(text)


class MarkdownProcessor:
    """Markdown processing utilities."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def extract_from_pdf(self, pdf_path: Path, md_dir: Path) -> Path:
        """Extract markdown from PDF."""
        return extract_markdown(pdf_path, md_dir, self.max_retries)

    def clean_text(self, text: str) -> str:
        """Clean markdown text."""
        return clean_markdown_text(text)

    def read_text(self, md_path: Path) -> str:
        """Read and clean text from markdown file."""
        return extract_text_from_markdown(md_path)
