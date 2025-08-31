# Summary service package for paper summary management

from .summary_generator import (
    SummaryGenerator,
    progressive_summary,
    generate_tags_from_summary,
    aggregate_summaries,
)
from .text_processor import TextProcessor, chunk_text
from .service import SummaryService, process_paper_text
from .llm_utils import (
    LLMProvider,
    llm_invoke,
    clean_ollama_response,
    extract_json_from_response,
)
from .pdf_processor import (
    PDFProcessor,
    build_session,
    resolve_pdf_url,
    download_pdf,
    verify_pdf_integrity,
    cleanup_corrupted_pdfs,
)
from .markdown_processor import (
    MarkdownProcessor,
    extract_markdown,
    clean_markdown_text,
    extract_text_from_markdown,
)
from .rss_processor import (
    fetch_rss,
    parse_links,
    get_links_from_rss,
    extract_first_header,
    generate_rss_feed,
)
from .logging_config import (
    setup_logging,
    stop_logging,
    get_logger,
    ThreadSafeLoggingConfig,
)

__all__ = [
    "SummaryGenerator",
    "progressive_summary",
    "generate_tags_from_summary",
    "aggregate_summaries",
    "TextProcessor",
    "chunk_text",
    "SummaryService",
    "process_paper_text",
    "LLMProvider",
    "llm_invoke",
    "clean_ollama_response",
    "extract_json_from_response",
    "PDFProcessor",
    "build_session",
    "resolve_pdf_url",
    "download_pdf",
    "verify_pdf_integrity",
    "cleanup_corrupted_pdfs",
    "MarkdownProcessor",
    "extract_markdown",
    "clean_markdown_text",
    "extract_text_from_markdown",
    "fetch_rss",
    "parse_links",
    "get_links_from_rss",
    "extract_first_header",
    "generate_rss_feed",
    "setup_logging",
    "stop_logging",
    "get_logger",
    "ThreadSafeLoggingConfig",
]
