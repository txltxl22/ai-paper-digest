"""
pdf_processor.py - PDF processing utilities

This module provides PDF download, validation, and processing functionality.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

try:
    import pymupdf as fitz
except ImportError:
    fitz = None

_LOG = logging.getLogger("pdf_processor")


def build_session(proxy_url: Optional[str] = None) -> requests.Session:
    """Build a requests session with optional proxy configuration."""
    session = requests.Session()
    if proxy_url:
        _LOG.warning("Using proxy: %s", proxy_url)
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    else:
        _LOG.warning("No proxy configured, using direct connection")
    return session


def resolve_pdf_url(url: str, session: requests.Session) -> str:
    """Return a direct PDF link for *url*."""
    if "huggingface.co/papers" in url:
        pdf = url.replace("huggingface.co/papers", "arxiv.org/pdf") + ".pdf"
        return pdf
    elif "tldr.takara.ai/p" in url:
        pdf = url.replace("tldr.takara.ai/p", "arxiv.org/pdf") + ".pdf"
        return pdf
    elif url.endswith(".pdf"):
        return url
    elif "arxiv.org/" in url:
        return url + ".pdf"

    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            pdf = requests.compat.urljoin(url, a["href"])
            return pdf

    raise ValueError("No PDF link found on page.")


def verify_pdf_integrity(pdf_path: Path) -> bool:
    """Verify that a PDF file is complete and valid."""
    try:
        # Check file size is reasonable (at least 1KB)
        if pdf_path.stat().st_size < 1024:
            _LOG.debug(
                "PDF too small to be valid: %s (%d bytes)",
                pdf_path,
                pdf_path.stat().st_size,
            )
            return False

        # Try to open with PyMuPDF to verify it's a valid PDF
        if fitz:
            try:
                doc = fitz.open(str(pdf_path))
                page_count = len(doc)
                doc.close()

                if page_count == 0:
                    _LOG.debug("PDF has no pages: %s", pdf_path)
                    return False

                _LOG.debug(
                    "PDF validation successful: %s (%d pages)", pdf_path, page_count
                )
                return True

            except Exception as e:
                _LOG.debug("PDF validation failed with PyMuPDF: %s - %s", pdf_path, e)
                return False

        # Fallback: check if file starts with PDF magic number
        with open(pdf_path, "rb") as f:
            header = f.read(8)
            if header.startswith(b"%PDF-"):
                _LOG.debug("PDF validation successful (magic number): %s", pdf_path)
                return True
            else:
                _LOG.debug("PDF validation failed (no magic number): %s", pdf_path)
                return False

    except Exception as e:
        _LOG.debug("PDF validation error: %s - %s", pdf_path, e)
        return False


def download_pdf(
    pdf_url: str,
    output_dir: Path,
    session: requests.Session,
    max_retries: int = 3,
    skip_download: bool = False,
    max_size_mb: int = None,
    progress_callback: callable = None,
) -> Path:
    """Download the PDF or skip if already present. Ensures complete downloads only."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = pdf_url.rstrip("/").split("/")[-1]
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    outpath = output_dir / filename

    if skip_download:
        return outpath

    if outpath.exists():
        # Verify existing PDF is complete and valid
        if verify_pdf_integrity(outpath):
            _LOG.debug("PDF already exists and is valid: %s", outpath)
            return outpath
        else:
            _LOG.warning("Existing PDF appears corrupted, re-downloading: %s", outpath)
            outpath.unlink()  # Remove corrupted file

    # Retry download logic
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            _LOG.info(
                "Retry attempt %d/%d for downloading %s",
                attempt + 1,
                max_retries,
                filename,
            )
            time.sleep(2)  # Brief delay between retries

        try:
            return _download_pdf_single_attempt(
                pdf_url, output_dir, filename, session, max_size_mb, progress_callback
            )
        except Exception as e:
            last_error = e
            _LOG.warning("Download attempt %d failed: %s", attempt + 1, e)
            continue

    # All retries failed
    raise RuntimeError(
        f"Failed to download PDF after {max_retries} attempts. Last error: {last_error}"
    )


def _download_pdf_single_attempt(
    pdf_url: str,
    output_dir: Path,
    filename: str,
    session: requests.Session,
    max_size_mb: int = None,
    progress_callback: callable = None,
) -> Path:
    """Single attempt to download a PDF file."""
    outpath = output_dir / filename

    # Download to temporary file first
    temp_path = output_dir / f"{filename}.tmp"

    try:
        resp = session.get(pdf_url, stream=True, timeout=60)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))

        # Check file size limit before downloading
        if max_size_mb and total > 0:
            max_size_bytes = max_size_mb * 1024 * 1024
            if total > max_size_bytes:
                raise ValueError(
                    f"PDF file too large: {total / (1024*1024):.1f}MB exceeds limit of {max_size_mb}MB"
                )

        downloaded_size = 0
        last_progress_time = time.time()

        with (
            open(temp_path, "wb") as f,
            tqdm(
                desc=f"Downloading {filename}",
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar,
        ):
            for chunk in resp.iter_content(2048):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    bar.update(len(chunk))

                    # Call progress callback if provided
                    if progress_callback and total > 0:
                        progress_percent = int((downloaded_size / total) * 100)
                        # Call callback more frequently (every 100KB or every 2%)
                        if downloaded_size % 102400 == 0 or progress_percent % 2 == 0:
                            progress_callback(progress_percent, downloaded_size, total)

                    # Check for progress timeout (stalled download)
                    current_time = time.time()
                    if (
                        current_time - last_progress_time > 30
                    ):  # 30 seconds without progress
                        raise TimeoutError(
                            "Download stalled - no progress for 30 seconds"
                        )
                    last_progress_time = current_time

        # Verify download completeness
        if total > 0 and downloaded_size != total:
            raise ValueError(
                f"Download incomplete: expected {total} bytes, got {downloaded_size} bytes"
            )

        # Verify PDF integrity before moving to final location
        if not verify_pdf_integrity(temp_path):
            raise ValueError("Downloaded PDF failed integrity check")

        # Move temporary file to final location
        temp_path.rename(outpath)
        _LOG.info(
            "PDF downloaded successfully: %s (%d bytes)", outpath, downloaded_size
        )

        return outpath

    except Exception as e:
        # Clean up temporary file on any error
        if temp_path.exists():
            temp_path.unlink()
        _LOG.error("Failed to download PDF %s: %s", pdf_url, e)
        raise
    finally:
        # Ensure temporary file is cleaned up
        if temp_path.exists():
            temp_path.unlink()


class PDFProcessor:
    """PDF processing utilities."""

    def __init__(self, proxy_url: Optional[str] = None, max_retries: int = 3):
        self.session = build_session(proxy_url)
        self.max_retries = max_retries

    def resolve_url(self, url: str) -> str:
        """Resolve URL to direct PDF link."""
        return resolve_pdf_url(url, self.session)

    def download(self, pdf_url: str, output_dir: Path, **kwargs) -> Path:
        """Download PDF with retry logic."""
        return download_pdf(
            pdf_url, output_dir, self.session, max_retries=self.max_retries, **kwargs
        )

    def verify(self, pdf_path: Path) -> bool:
        """Verify PDF integrity."""
        return verify_pdf_integrity(pdf_path)

    def cleanup_corrupted(self, papers_dir: Path) -> int:
        """Clean up corrupted PDF files in the given directory."""
        return cleanup_corrupted_pdfs(papers_dir)


def cleanup_corrupted_pdfs(papers_dir: Path) -> int:
    """Clean up any corrupted PDF files that might exist.
    
    Args:
        papers_dir: Directory containing PDF files to check
        
    Returns:
        Number of corrupted PDF files that were removed
    """
    if not papers_dir.exists():
        return 0
    
    corrupted_count = 0
    for pdf_file in papers_dir.glob("*.pdf"):
        try:
            # Try to validate the PDF
            if not verify_pdf_integrity(pdf_file):
                _LOG.warning("Removing corrupted PDF: %s", pdf_file)
                pdf_file.unlink()
                corrupted_count += 1
        except Exception as e:
            _LOG.warning("Error checking PDF %s: %s", pdf_file, e)
    
    if corrupted_count > 0:
        _LOG.info("Cleaned up %d corrupted PDF files", corrupted_count)
    
    return corrupted_count
