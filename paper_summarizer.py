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
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from typing import Iterable, List, Optional, Tuple
import re

from langchain_deepseek.chat_models import DEFAULT_API_BASE as DEEPSEEK_DEFAULT_API_BASE
import pymupdf4llm
try:
    import pymupdf as fitz
except ImportError:
    fitz = None
import requests
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from tqdm import tqdm

# Import the new summary schema
from summary_service.models import (
    ChunkSummary, StructuredSummary, Tags, Innovation, TermDefinition,
    parse_chunk_summary, parse_summary, parse_tags
)


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
# Proxy & session
# ---------------------------------------------------------------------------


def build_session(proxy_url: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    if proxy_url:
        _LOG.warning("Using proxy: %s", proxy_url)
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    else:
        _LOG.warning("No proxy configured, using direct connection")
    return session


# Create session without proxy by default
SESSION = build_session()


# ---------------------------------------------------------------------------
# PDF validation helpers
# ---------------------------------------------------------------------------

def _verify_pdf_integrity(pdf_path: Path) -> bool:
    """Verify that a PDF file is complete and valid."""
    try:
        # Check file size is reasonable (at least 1KB)
        if pdf_path.stat().st_size < 1024:
            _LOG.debug("PDF too small to be valid: %s (%d bytes)", pdf_path, pdf_path.stat().st_size)
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
                    
                _LOG.debug("PDF validation successful: %s (%d pages)", pdf_path, page_count)
                return True
                
            except Exception as e:
                _LOG.debug("PDF validation failed with PyMuPDF: %s - %s", pdf_path, e)
                return False
        
        # Fallback: check if file starts with PDF magic number
        with open(pdf_path, 'rb') as f:
            header = f.read(8)
            if header.startswith(b'%PDF-'):
                _LOG.debug("PDF validation successful (magic number): %s", pdf_path)
                return True
            else:
                _LOG.debug("PDF validation failed (no magic number): %s", pdf_path)
                return False
                
    except Exception as e:
        _LOG.debug("PDF validation error: %s - %s", pdf_path, e)
        return False


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------


def resolve_pdf_url(url: str, session: requests.Session = SESSION) -> str:
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


def download_pdf(
    pdf_url: str, output_dir: Path = PDF_DIR, session: requests.Session = SESSION, max_retries: int = 3, skip_download: bool = False, max_size_mb: int = None, progress_callback: callable = None
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
        if _verify_pdf_integrity(outpath):
            _LOG.debug("PDF already exists and is valid: %s", outpath)
            return outpath
        else:
            _LOG.warning("Existing PDF appears corrupted, re-downloading: %s", outpath)
            outpath.unlink()  # Remove corrupted file

        # Retry download logic
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            _LOG.info("Retry attempt %d/%d for downloading %s", attempt + 1, max_retries, filename)
            time.sleep(2)  # Brief delay between retries
        
        try:
            return _download_pdf_single_attempt(pdf_url, output_dir, filename, session, max_size_mb, progress_callback)
        except Exception as e:
            last_error = e
            _LOG.warning("Download attempt %d failed: %s", attempt + 1, e)
            continue
    
    # All retries failed
    raise RuntimeError(f"Failed to download PDF after {max_retries} attempts. Last error: {last_error}")


def _download_pdf_single_attempt(
    pdf_url: str, output_dir: Path, filename: str, session: requests.Session, max_size_mb: int = None, progress_callback: callable = None
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
                raise ValueError(f"PDF file too large: {total / (1024*1024):.1f}MB exceeds limit of {max_size_mb}MB")
        
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
                        # Call callback more frequently (every 1% or every 50KB)
                        if downloaded_size % 51200 == 0 or progress_percent % 5 == 0:
                            progress_callback(progress_percent, downloaded_size, total)
                    
                    # Check for progress timeout (stalled download)
                    current_time = time.time()
                    if current_time - last_progress_time > 30:  # 30 seconds without progress
                        raise TimeoutError("Download stalled - no progress for 30 seconds")
                    last_progress_time = current_time
        
        # Verify download completeness
        if total > 0 and downloaded_size != total:
            raise ValueError(f"Download incomplete: expected {total} bytes, got {downloaded_size} bytes")
        
        # Verify PDF integrity before moving to final location
        if not _verify_pdf_integrity(temp_path):
            raise ValueError("Downloaded PDF failed integrity check")
        
        # Move temporary file to final location
        temp_path.rename(outpath)
        _LOG.info("PDF downloaded successfully: %s (%d bytes)", outpath, downloaded_size)
        
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


# ---------------------------------------------------------------------------
# PDF → Markdown
# ---------------------------------------------------------------------------


def extract_markdown(pdf_path: Path, md_dir: Path = MD_DIR, max_retries: int = 3) -> Path:
    """Extract markdown text, caching if already done."""
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
                _LOG.error("Fallback PDF processing failed for %s: %s", pdf_path, error_msg)
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
                        text = re.sub(r'<[^>]+>', '', text)
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
        raise ValueError(f"All PDF processing methods failed for {pdf_path}. Errors: {error_summary}")

    md_path.write_text(md_text, encoding="utf-8")
    return md_path


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def chunk_text(
    text: str, max_chars: int = CHUNK_LENGTH, overlap_ratio: float = CHUNK_OVERLAP_RATIO
) -> List[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    overlap = int(max_chars * overlap_ratio)
    if overlap >= max_chars:
        raise ValueError("overlap must be less than chunk size")

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        start = end - overlap

        if end == len(text):
            break
    return chunks


# ---------------------------------------------------------------------------
# LLM invocation
# ---------------------------------------------------------------------------


def llm_invoke(
    messages: List[BaseMessage], 
    api_key: Optional[str] = None, 
    base_url: Optional[str] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    model: str = None,
    **kwargs
) -> AIMessage:
    """Invoke LLM with support for DeepSeek, Ollama, and OpenAI-compatible providers."""
    
    if provider.lower() == "ollama":
        # Use Ollama
        if not base_url:
            base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
        if not model:
            model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
            
        _LOG.debug("Using Ollama provider: %s at %s", model, base_url)
        
        llm = OllamaLLM(
            model=model,
            base_url=base_url,
            timeout=120,  # Ollama can be slower
        )
        
        # Convert messages to text for Ollama (simpler interface)
        if len(messages) == 1:
            prompt = messages[0].content
        else:
            # Handle conversation format
            prompt = "\n\n".join([f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}" for m in messages])
        
        response = llm.invoke(prompt)
        
        # Clean up Ollama response to extract only the actual output
        # Ollama may include <think> tags mixed with output, unlike DeepSeek Chat
        cleaned_content = response
        if isinstance(cleaned_content, str):
            # Remove <think>...</think> blocks
            cleaned_content = re.sub(r'<think>.*?</think>', '', cleaned_content, flags=re.DOTALL)
        
        return AIMessage(content=cleaned_content)
        
    elif provider.lower() == "openai":
        # Use OpenAI-compatible API (including DeepSeek, Anthropic, etc.)
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable or pass --api-key")
            
        if not base_url:
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        if not model:
            model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
            
        _LOG.debug("Using OpenAI-compatible provider: %s at %s", model, base_url)
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=None,
            timeout=120,
            max_retries=2,
        )
        return llm.invoke(messages)
        
    else:
        # Use DeepSeek (default)
        if not api_key:
            api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY environment variable or pass --api-key")
            
        _LOG.debug("Using DeepSeek provider: %s", MODEL_NAME)
        
        llm = ChatDeepSeek(
            model=MODEL_NAME,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key,
            api_base=base_url if base_url else DEEPSEEK_DEFAULT_API_BASE,
        )
        return llm.invoke(messages)


def progressive_summary(
    chunks: Iterable[str],
    summary_path: Path,
    chunk_summary_path: Path,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    model: str = None,
    max_workers: int = 4,
    use_summary_cache: bool = True,
    use_chunk_summary_cache: bool = True,
) -> Tuple[StructuredSummary, List[ChunkSummary]]:
    """Generate structured summary using JSON schema-based prompts."""
    if summary_path.exists() and use_summary_cache:
        _LOG.info(f"Summary cache hit for {summary_path}.")
        # Try to load existing structured summary
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            summary = parse_summary(json.dumps(summary_data))

            # Load chunk summaries if available
            chunk_summaries = []
            if chunk_summary_path.exists():
                try:
                    with open(chunk_summary_path, 'r', encoding='utf-8') as f:
                        chunk_data = json.load(f)
                    chunk_summaries = [parse_chunk_summary(json.dumps(chunk)) for chunk in chunk_data]
                except Exception:
                    pass

            return summary, chunk_summaries
        except Exception:
            _LOG.warning("Failed to load cached structured summary, regenerating...")

    chunks = list(chunks)
    chunk_summaries: List[ChunkSummary] = [None] * len(chunks)  # type: ignore

    def _summarize_one(idx: int, chunk: str) -> Tuple[int, ChunkSummary]:
        msg = HumanMessage(
            PromptTemplate.from_file(
                os.path.join("prompts", "chunk_summary.json.md"), encoding="utf-8"
            ).format(chunk_content=chunk)
        )
        resp = llm_invoke([msg], api_key=api_key, base_url=base_url, provider=provider, model=model)

        # Parse the JSON response
        try:
            chunk_summary = parse_chunk_summary(resp.content)
            return idx, chunk_summary
        except Exception as e:
            _LOG.error(f"Failed to parse chunk summary for chunk {idx}: {e}")
            # Return a default chunk summary
            default_summary = ChunkSummary(
                main_content=f"Error parsing chunk {idx},\n original content: {chunk},\n resp: {resp.content}",
                innovations=[],
                key_terms=[],
            )
            return idx, default_summary

    if not chunk_summary_path.exists() or not use_chunk_summary_cache:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_summarize_one, i, c): i for i, c in enumerate(chunks)
            }
            for future in tqdm(
                as_completed(futures), total=len(futures), desc="Summarizing chunks"
            ):
                i, chunk_summary = future.result()
                chunk_summaries[i] = chunk_summary

        # Save chunk summaries
        chunk_summary_path.write_text(
            json.dumps([{
                "main_content": cs.main_content,
                "innovations": [
                    {
                        "title": inv.title,
                        "description": inv.description,
                        "improvement": inv.improvement,
                        "significance": inv.significance
                    }
                    for inv in cs.innovations
                ],
                "key_terms": [
                    {
                        "term": kt.term,
                        "definition": kt.definition
                    }
                    for kt in cs.key_terms
                ]
            } for cs in chunk_summaries], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    else:
        # Load existing chunk summaries
        try:
            with open(chunk_summary_path, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
            chunk_summaries = []
            for chunk in chunk_data:
                # Convert dictionaries to proper objects
                innovations = [Innovation(**inv) for inv in chunk["innovations"]]
                key_terms = [TermDefinition(**kt) for kt in chunk["key_terms"]]
                chunk_summaries.append(ChunkSummary(
                    main_content=chunk["main_content"],
                    innovations=innovations,
                    key_terms=key_terms
                ))
        except Exception as e:
            _LOG.error(f"Failed to load chunk summaries: {e}")
            return None, []  # type: ignore

    # Combine chunk summaries for final summary
    combined_content = "\n\n".join([
        f"Chunk {i+1}:\n{cs.main_content}\n\nInnovations: {', '.join([inv.title for inv in cs.innovations])}\n\nKey Terms: {', '.join([kt.term for kt in cs.key_terms])}"
        for i, cs in enumerate(chunk_summaries)
    ])

    # Generate final structured summary
    final_msg = llm_invoke(
        [
            HumanMessage(
                PromptTemplate.from_file(
                    os.path.join("prompts", "summary.json.md"), encoding="utf-8"
                ).template
            ),
            HumanMessage(combined_content),
        ],
        api_key=api_key,
        base_url=base_url,
        provider=provider,
        model=model,
    )

    try:
        summary = parse_summary(final_msg.content)

        # Save structured summary
        summary_path.write_text(
            json.dumps({
                "paper_info": {
                    "title_zh": summary.paper_info.title_zh,
                    "title_en": summary.paper_info.title_en
                },
                "one_sentence_summary": summary.one_sentence_summary,
                "innovations": [
                    {
                        "title": innovation.title,
                        "description": innovation.description,
                        "improvement": innovation.improvement,
                        "significance": innovation.significance
                    }
                    for innovation in summary.innovations
                ],
                "results": {
                    "experimental_highlights": summary.results.experimental_highlights,
                    "practical_value": summary.results.practical_value
                },
                "terminology": [
                    {
                        "term": term.term,
                        "definition": term.definition
                    }
                    for term in summary.terminology
                ]
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return summary, chunk_summaries
    except Exception as e:
        _LOG.error(f"Failed to parse final summary: {e}")
        return None, chunk_summaries  # type: ignore


# ---------------------------------------------------------------------------
# Tag generation from summary
# ---------------------------------------------------------------------------


def generate_tags_from_summary(
    summary_text: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    model: str = None,
    max_tags: int = 8,
) -> Tags:
    """Generate AI-aware top-level and detailed tags using the LLM.

    Reads prompt from prompts/tags.json.md. Returns a Tags object.
    """
    tmpl = PromptTemplate.from_file(
        os.path.join("prompts", "tags.json.md"), encoding="utf-8"
    ).format(summary_content=summary_text)

    resp = llm_invoke([HumanMessage(content=tmpl)], api_key=api_key, base_url=base_url, provider=provider, model=model)
    raw = (resp.content or "").strip()

    # Clean up any <think> tags that might appear in Ollama output
    if provider.lower() == "ollama":
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)

    # Strip fenced code blocks if present, e.g., ```json ... ``` or ``` ... ```
    fenced_match = re.search(r"```(?:json|\w+)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fenced_match:
        raw = fenced_match.group(1).strip()

    try:
        tags = parse_tags(raw)
        
        # Normalize and cap
        normalized_tags: List[str] = []
        seen = set()
        for t in tags.tags:
            norm = " ".join(t.split()).lower()
            if norm and norm not in seen:
                seen.add(norm)
                normalized_tags.append(norm)
            if len(normalized_tags) >= max_tags:
                break

        # Ensure a minimum of 3 tags if possible by splitting slashes etc.
        if len(normalized_tags) < 3:
            extras: List[str] = []
            for t in normalized_tags:
                for part in t.replace("/", " ").split():
                    if part and part not in seen:
                        seen.add(part)
                        extras.append(part)
                    if len(normalized_tags) + len(extras) >= 3:
                        break
                if len(normalized_tags) + len(extras) >= 3:
                    break
            normalized_tags.extend(extras)

        # normalize top-level too and ensure subset of allowed set
        allowed_top = {"llm","nlp","cv","ml","rl","agents","systems","theory","robotics","audio","multimodal"}
        top_norm: List[str] = []
        seen_top = set()
        for t in tags.top:
            k = " ".join(str(t).split()).lower()
            if k in allowed_top and k not in seen_top:
                seen_top.add(k)
                top_norm.append(k)

        return Tags(top=top_norm, tags=normalized_tags)
        
    except Exception as e:
        _LOG.error(f"Failed to parse tags: {e}")
        # Return default tags
        return Tags(top=[], tags=[])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize an academic paper via LLM (DeepSeek or Ollama)"
    )
    parser.add_argument("url", help="Paper URL (PDF or landing page)")
    parser.add_argument("--api-key", help="DeepSeek/OpenAI API key")
    parser.add_argument("--base-url", help="Base URL for OpenAI-compatible LLM API (e.g., https://api.openai.com/v1)")
    parser.add_argument("--provider", choices=["deepseek", "ollama"], default=DEFAULT_LLM_PROVIDER,
                       help=f"LLM provider to use (default: {DEFAULT_LLM_PROVIDER})")
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL,
                       help=f"Ollama service base URL (default: {DEFAULT_OLLAMA_BASE_URL})")
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL,
                       help=f"Ollama model name (default: {DEFAULT_OLLAMA_MODEL})")
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
            chunks, summary_path=summary_path, chunk_summary_path=chunk_summary_path,
            api_key=args.api_key, base_url=args.base_url, provider=args.provider, 
            ollama_base_url=args.ollama_base_url, ollama_model=args.ollama_model
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
