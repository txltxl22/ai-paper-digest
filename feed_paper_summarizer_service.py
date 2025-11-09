"""
feed_paper_summarizer_service.py
================================
A lightweight *service* that orchestrates RSS feed processing and batch
paper summarization using modular components:

* ``summary_service.rss_processor`` – RSS feed parsing and link extraction
* ``summary_service.pdf_processor`` – PDF download, validation, and cleanup
* ``summary_service.markdown_processor`` – PDF text extraction to markdown
* ``summary_service.text_processor`` – Text chunking for LLM processing
* ``summary_service.llm_utils`` – LLM provider integration (DeepSeek, OpenAI, Ollama)
* ``summary_service.summary_generator`` – Progressive summarization and tag generation
* ``summary_service.record_manager`` – Service record management and legacy migration
* ``paper_summarizer`` – Single URL summarization pipeline (delegated)

The service focuses on RSS feed orchestration and batch processing, while
delegating individual paper summarization to the paper_summarizer module.

ARCHITECTURE:
- RSS feed processing → URL extraction → parallel summarization → aggregation
- Delegates single URL processing to paper_summarizer.summarize_paper_url
- Supports multiple LLM providers (DeepSeek, OpenAI-compatible APIs, Ollama)
- Thread-safe concurrent processing with configurable worker pools
- Comprehensive error handling and recovery mechanisms

FEATURES:
- Multi-provider LLM support with flexible configuration
- Extract-only mode for text extraction without LLM processing
- Tags-only mode for generating tags on existing summaries
- Local mode for processing cached papers
- Legacy summary migration to service record format
- PDF integrity validation and corrupted file cleanup
- Aggregated summary output with RSS feed generation
- Thread-safe logging with configurable verbosity
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

from tqdm import tqdm
import json

from summary_service.record_manager import (
    migrate_legacy_summaries_to_service_record,
)
from summary_service.logging_config import setup_logging, stop_logging
from config_manager import get_provider_config

# ---------------------------------------------------------------------------
# Local modules – assume we're run from the repo root or installed package
# ---------------------------------------------------------------------------
try:
    from summary_service.rss_processor import get_links_from_rss, generate_rss_feed
    import paper_summarizer as ps

    # Import the new summary service modules
    from summary_service.pdf_processor import (
        build_session,
        cleanup_corrupted_pdfs,
    )
    from summary_service.summary_generator import (
        generate_tags_from_summary,
        aggregate_summaries,
    )
except ModuleNotFoundError as _e:  # pragma: no cover
    raise SystemExit(
        "❌ Could not import project modules. Run from the repo root or make sure "
        "the package is installed in your environment."
    ) from _e


__version__ = "0.5.0"
_LOG = logging.getLogger("feed_service")





def _summarize_url(
    url: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    max_input_char: int = 50000,
    extract_only: bool = False,
    local: bool = False,
    max_workers: int = 1,
) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """Run the full summarization pipeline for *url*.

    Returns the Path to the generated summary markdown and the download url for the paper,
    or *None* on failure. Delegates to paper_summarizer.summarize_paper_url.
    """
    try:
        return ps.summarize_paper_url(
            url=url,
            api_key=api_key,
            base_url=base_url,
            provider=provider,
            model=model,
            max_input_char=max_input_char,
            extract_only=extract_only,
            local=local,
            max_workers=max_workers,
            session=ps.SESSION,  # type: ignore[attr-defined]
        )
    except Exception as exc:  # pylint: disable=broad-except
        _LOG.error("❌  %s – %s", url, exc)
        _LOG.exception(exc)
        return None, None, None


# ---------------------------------------------------------------------------
# Local discovery helpers
# ---------------------------------------------------------------------------

def _collect_local_links() -> List[str]:
    """Discover local papers and return a list of direct PDF URLs.

    Preference order: markdown files (stems) → papers PDFs (stems). For each
    stem we construct a direct arXiv PDF URL, which will hit the local cache in
    download step when available.
    """
    links: List[str] = []
    try:
        # Prefer markdown directory if present
        md_dir: Path = ps.MD_DIR  # type: ignore[attr-defined]
        md_files = sorted(md_dir.glob("*.md")) if md_dir.exists() else []
        if md_files:
            for p in md_files:
                links.append(f"https://arxiv.org/pdf/{p.stem}.pdf")
            return links
    except Exception:
        pass

    try:
        pdf_dir: Path = ps.PDF_DIR  # type: ignore[attr-defined]
        pdf_files = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
        for p in pdf_files:
            links.append(f"https://arxiv.org/pdf/{p.stem}.pdf")
    except Exception:
        pass

    return links


# ---------------------------------------------------------------------------
# Tags-only helper
# ---------------------------------------------------------------------------

def _tags_only_run(
    provider: str = "deepseek",
    base_url: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    api_key: Optional[str] = None,
) -> tuple[int, int]:
    """Generate tags for existing summaries only.

    Returns a tuple of (total_summaries, updated_count). Only summaries missing
    tags will be processed.
    """
    try:
        summary_dir: Path = ps.SUMMARY_DIR  # type: ignore[attr-defined]
    except Exception:
        _LOG.warning("Summary directory not available.")
        return 0, 0

    if not summary_dir.exists():
        _LOG.warning("Summary directory %s does not exist.", summary_dir)
        return 0, 0

    md_files = sorted(summary_dir.glob("*.md"))
    total = len(md_files)
    if total == 0:
        _LOG.info("No summaries found under %s", summary_dir)
        return 0, 0

    _LOG.info("🏷️  Tags-only mode – scanning %d summary file(s)…", total)
    updated = 0
    for md_path in md_files:
        try:
            tags_path = md_path.with_suffix("")
            tags_path = tags_path.with_name(tags_path.name + ".tags.json")
            if tags_path.exists():
                continue
            paper_id = md_path.stem
            _LOG.info("🏷️  Generating tags for %s…", paper_id)
            summary_text = md_path.read_text(encoding="utf-8", errors="ignore")
            tags = generate_tags_from_summary(
                summary_text,
                provider=provider,
                base_url=base_url,
                model=model,
                api_key=api_key,
            )
            # Convert Tags object to dictionary format
            tag_obj = (
                {"tags": tags.tags, "top": tags.top}
                if hasattr(tags, "tags")
                else {"tags": [], "top": []}
            )
            tags_path.write_text(
                json.dumps(tag_obj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _LOG.info(
                "✅  Saved %d tag(s) for %s", len(tag_obj.get("tags", [])), paper_id
            )
            updated += 1
        except Exception as exc:  # pylint: disable=broad-except
            _LOG.exception("Failed to generate tags for %s: %s", md_path.name, exc)

    _LOG.info("🏷️  Tags-only complete – %d/%d updated", updated, total)
    return total, updated


# ---------------------------------------------------------------------------
# Aggregate summaries → single Markdown file
# ---------------------------------------------------------------------------

def _aggregate_summaries(paths: List[Path], out_file: Path, feed_url: str) -> None:
    """Concatenate individual summaries to *out_file* with a brief header."""
    return aggregate_summaries(paths, out_file, feed_url)


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:  # noqa: D401
    p = argparse.ArgumentParser(
        description="Fetch an RSS feed, process papers (extract text, summarize with LLM, generate tags), and aggregate results. Supports DeepSeek, Ollama, and OpenAI-compatible LLM providers. Use --extract-only to skip LLM processing.",
        epilog="""
Examples:
  Regular mode with DeepSeek LLM (default):
    %(prog)s https://papers.takara.ai/api/feed --workers 2

  Regular mode with OpenAI-compatible API:
    %(prog)s https://papers.takara.ai/api/feed --provider openai --base-url https://api.openai.com/v1 --api-key your-api-key --model gpt-4 --workers 2

  Regular mode with DeepSeek API (using OpenAI-compatible provider):
    %(prog)s https://papers.takara.ai/api/feed --provider openai --base-url https://api.deepseek.com/v1 --api-key your-deepseek-key --model deepseek-chat --workers 2

  Regular mode with Ollama LLM:
    %(prog)s https://papers.takara.ai/api/feed --provider ollama --base-url http://192.168.1.1:11434 --model qwen3:8b --workers 2

  Extract-only mode (no LLM, just text extraction):
    %(prog)s https://papers.takara.ai/api/feed --extract-only --workers 4

  Tags-only mode (only generate tags for existing summaries):
    %(prog)s --tags-only --provider openai --base-url https://api.deepseek.com/v1 --api-key your-deepseek-key --model deepseek-chat
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "rss_url",
        nargs="?",
        default="",
        help="RSS feed URL (HuggingFace papers feed, ArXiv RSS, etc.)",
    )
    p.add_argument(
        "--provider",
        choices=["deepseek", "ollama", "openai"],
        default="deepseek",
        help="LLM provider to use (default: deepseek)",
    )
    p.add_argument(
        "--api-key", dest="api_key", help="API key for the selected provider"
    )
    p.add_argument(
        "--base-url", dest="base_url", help="Base URL for the selected provider"
    )
    p.add_argument("--model", help="Model name for the selected provider")
    p.add_argument("--proxy", help="Proxy URL to use for PDF downloads (if needed)")
    p.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Concurrent workers (default: CPU count)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("output.md"),
        help="Aggregate markdown output file",
    )
    p.add_argument(
        "--output_rss_path",
        type=Path,
        default=Path("hugging-face-ai-papers-rss.xml"),
        help="RSS xml file output path.",
    )
    p.add_argument(
        "--rebuild",
        action="store_true",
        help="Whether to rebuild the rss xml file using all existing summaries.",
    )
    p.add_argument(
        "--local",
        action="store_true",
        help="Process local cached papers instead of fetching RSS.",
    )
    p.add_argument(
        "--tags-only",
        action="store_true",
        help="Only generate tags for existing summaries and exit.",
    )
    p.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract PDF text to markdown (no LLM calls, no summaries, no tags, no RSS generation).",
    )
    p.add_argument(
        "--migrate-legacy",
        action="store_true",
        help="Migrate legacy summaries to service record format and exit.",
    )
    p.add_argument("--debug", action="store_true", help="Verbose logging")
    p.add_argument(
        "--input-char-limit",
        dest="max_input_char",
        default=100000,
        help="Max allowed number of input chars",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> None:  # noqa: D401

    args = _parse_args(argv)
    setup_logging(args.debug)

    _LOG.info("🚀  feed_paper_summarizer_service %s", __version__)

    # Clean up any corrupted PDFs that might exist
    papers_dir = ps.PDF_DIR  # type: ignore[attr-defined]
    cleanup_corrupted_pdfs(papers_dir)

    # Proxy support – rebuild the session inside paper_summarizer if needed
    if args.proxy:
        ps.SESSION = build_session(args.proxy)  # type: ignore[attr-defined]
        _LOG.warning("Using proxy %s", args.proxy)
    else:
        # Ensure we have a session even without proxy
        if not hasattr(ps, "SESSION") or ps.SESSION is None:  # type: ignore[attr-defined]
            ps.SESSION = build_session()  # type: ignore[attr-defined]

    # Get provider configuration
    provider_config = get_provider_config(
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
    )

    # Short-circuit: tags-only generation
    if args.tags_only:
        _tags_only_run(
            provider=provider_config["provider"],
            base_url=provider_config["base_url"],
            model=provider_config["model"],
            api_key=provider_config["api_key"],
        )
        _LOG.info("✨  All done (tags-only).")
        # Clean up the log listener
        stop_logging()
        return

    # Short-circuit: migrate legacy summaries
    if args.migrate_legacy:
        try:
            _LOG.info("🔄  Starting legacy summaries migration...")
            migration_stats = migrate_legacy_summaries_to_service_record()
            _LOG.info("✅  Migration completed:")
            _LOG.info(
                "   Total legacy files: %d", migration_stats["total_legacy_files"]
            )
            _LOG.info("   Migrated: %d", migration_stats["migrated"])
            _LOG.info("   Skipped: %d", migration_stats["skipped"])
            _LOG.info("   Errors: %d", migration_stats["errors"])
            if migration_stats["errors"] > 0:
                _LOG.warning(
                    "Some files had errors during migration. Check the details."
                )
        except Exception as exc:
            _LOG.error("Migration failed: %s", exc)
        # Clean up the log listener
        stop_logging()
        return

    # ------------------------------------------------------------------
    # 1. Collect links
    # ------------------------------------------------------------------
    if args.local:
        _LOG.info("📦  Local mode enabled – discovering cached papers…")
        links = _collect_local_links()
        links = list(dict.fromkeys(links))
        if not links:
            _LOG.warning("No local papers discovered – nothing to do.")
            sys.exit(0)
        _LOG.info("Found %d local paper(s)", len(links))
    else:
        _LOG.info("🔗  Fetching RSS feed…")
        try:
            links = get_links_from_rss(args.rss_url, timeout=20.0)
        except Exception as exc:  # pylint: disable=broad-except
            _LOG.error("Failed to fetch RSS: %s", exc)
            sys.exit(1)

        links = list(dict.fromkeys(links))  # deduplicate while preserving order
        if not links:
            _LOG.warning("No links found – nothing to do.")
            sys.exit(0)
        _LOG.info("Found %d unique paper link(s)", len(links))

    # ------------------------------------------------------------------
    # 2. Parallel summarization
    # ------------------------------------------------------------------
    _LOG.info("🧵  Starting summarization with %d worker(s)…", args.workers)
    produced: List[Tuple[Optional[Path], Optional[str]]] = [(None, None)] * len(links)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _summarize_url,
                link,
                api_key=provider_config["api_key"],
                base_url=provider_config["base_url"],
                provider=provider_config["provider"],
                model=provider_config["model"],
                max_input_char=int(args.max_input_char),
                extract_only=args.extract_only,
                local=args.local,
                max_workers=args.workers,
            ): idx
            for idx, link in enumerate(links)
        }
        try:
            desc = "Text Extraction:" if args.extract_only else "Summaries:"
            for fut in tqdm(as_completed(futures), total=len(futures), desc=desc):
                try:
                    result = fut.result(timeout=30)  # 30 seconds timeout per task
                    produced[futures[fut]] = result
                except Exception as exc:
                    idx = futures[fut]
                    _LOG.error(
                        "Task failed for link %d (%s): %s",
                        idx,
                        links[idx] if idx < len(links) else "unknown",
                        exc,
                    )
                    produced[idx] = (None, None, None)  # Mark as failed
        except KeyboardInterrupt:
            _LOG.warning(
                "🛑  Processing interrupted by user. Cancelling remaining tasks..."
            )
            # Cancel all pending futures
            for future in futures:
                if not future.done():
                    future.cancel()
            # Wait a bit for running tasks to finish
            import time

            time.sleep(2)
            raise  # Re-raise to be caught by main handler

    successes = [p for p in produced if p[0]]
    success_summaries_paths = [s[0] for s in successes]
    if args.extract_only:
        _LOG.info(
            "✔️  %d/%d papers extracted to markdown successfully",
            len(successes),
            len(links),
        )
    else:
        _LOG.info(
            "✔️  %d/%d summaries generated successfully", len(successes), len(links)
        )
    if not successes:
        if args.extract_only:
            _LOG.error("No papers extracted successfully – aborting.")
        else:
            _LOG.error("No summaries produced – aborting.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Aggregate → single file (skip in extract_only mode)
    # ------------------------------------------------------------------
    if not args.extract_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _aggregate_summaries(success_summaries_paths, args.output, args.rss_url)

    # ------------------------------------------------------------------
    # 4. Generate rss xml file (skip in extract_only mode)
    # ------------------------------------------------------------------
    if not args.extract_only:
        total_entries = generate_rss_feed(
            successes=successes,
            rss_file_path=args.output_rss_path,
            rebuild=args.rebuild,
            max_items=30,
            feed_title="Research Paper Summaries",
            feed_link="https://www.wawuyu.com",
            feed_description="Summaries of research papers",
        )

    _LOG.info("✨  All done!")


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        _LOG.info("🛑  Process interrupted by user. Cleaning up...")
        # Clean up the log listener
        stop_logging()
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        _LOG.error("💥  Fatal error: %s", e)
        # Clean up the log listener
        stop_logging()
        sys.exit(1)
