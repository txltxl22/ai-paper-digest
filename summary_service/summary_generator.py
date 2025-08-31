"""
summary_generator.py - Core summary generation service
"""

import json
import logging
import os
import re
import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from .llm_utils import llm_invoke
from .models import (
    ChunkSummary,
    StructuredSummary,
    Innovation,
    TermDefinition,
    Tags,
    parse_chunk_summary,
    parse_summary,
    parse_tags,
)

_LOG = logging.getLogger("summary_generator")

# Default configuration
DEFAULT_LLM_PROVIDER = "deepseek"


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
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            summary = parse_summary(json.dumps(summary_data))

            # Load chunk summaries if available
            chunk_summaries = []
            if chunk_summary_path.exists():
                try:
                    with open(chunk_summary_path, "r", encoding="utf-8") as f:
                        chunk_data = json.load(f)
                    chunk_summaries = [
                        parse_chunk_summary(json.dumps(chunk)) for chunk in chunk_data
                    ]
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
        resp = llm_invoke(
            [msg], api_key=api_key, base_url=base_url, provider=provider, model=model
        )

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

    chunk_data = None
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

        # Save chunk summaries and prepare chunk_data for final summary
        chunk_data = [
            {
                "main_content": cs.main_content,
                "innovations": [
                    {
                        "title": inv.title,
                        "description": inv.description,
                        "improvement": inv.improvement,
                        "significance": inv.significance,
                    }
                    for inv in cs.innovations
                ],
                "key_terms": [
                    {"term": kt.term, "definition": kt.definition}
                    for kt in cs.key_terms
                ],
            }
            for cs in chunk_summaries
        ]
        
        chunk_summary_path.write_text(
            json.dumps(chunk_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        # Load existing chunk summaries
        try:
            with open(chunk_summary_path, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)
            chunk_summaries = []
            for chunk in chunk_data:
                # Convert dictionaries to proper objects
                innovations = [Innovation(**inv) for inv in chunk["innovations"]]
                key_terms = [TermDefinition(**kt) for kt in chunk["key_terms"]]
                chunk_summaries.append(
                    ChunkSummary(
                        main_content=chunk["main_content"],
                        innovations=innovations,
                        key_terms=key_terms,
                    )
                )
        except Exception as e:
            _LOG.error(f"Failed to load chunk summaries: {e}")
            return None, []  # type: ignore

    # Generate final structured summary
    prompt_template = PromptTemplate.from_file(
        os.path.join("prompts", "summary.json.md"), encoding="utf-8"
    )
    
    # Create the complete prompt with chunk summaries
    complete_prompt = prompt_template.format(chunks_summary=json.dumps(chunk_data))

    final_msg = llm_invoke(
        [HumanMessage(content=complete_prompt)],
        api_key=api_key,
        base_url=base_url,
        provider=provider,
        model=model,
    )

    try:
        summary = parse_summary(final_msg.content)

        # Save summary cache if enabled
        if use_summary_cache:
            summary_path.write_text(
                json.dumps(
                    {
                        "paper_info": {
                            "title_zh": summary.paper_info.title_zh,
                            "title_en": summary.paper_info.title_en,
                        },
                        "one_sentence_summary": summary.one_sentence_summary,
                        "innovations": [
                            {
                                "title": inv.title,
                                "description": inv.description,
                                "improvement": inv.improvement,
                                "significance": inv.significance,
                            }
                            for inv in summary.innovations
                        ],
                        "results": {
                            "experimental_highlights": summary.results.experimental_highlights,
                            "practical_value": summary.results.practical_value,
                        },
                        "terminology": [
                            {"term": term.term, "definition": term.definition}
                            for term in summary.terminology
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        return summary, chunk_summaries
    except Exception as e:
        _LOG.error(f"Failed to parse final summary: {e}")
        _LOG.error(f"LLM response was: {final_msg.content}")
        return None, chunk_summaries  # type: ignore


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
    # Use top-level imports

    tmpl = PromptTemplate.from_file(
        os.path.join("prompts", "tags.json.md"), encoding="utf-8"
    ).format(summary_content=summary_text)

    resp = llm_invoke(
        [HumanMessage(content=tmpl)],
        api_key=api_key,
        base_url=base_url,
        provider=provider,
        model=model,
    )
    raw = (resp.content or "").strip()

    # Clean up any <think> tags that might appear in Ollama output
    if provider.lower() == "ollama":
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)

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
        allowed_top = {
            "llm",
            "nlp",
            "cv",
            "ml",
            "rl",
            "agents",
            "systems",
            "theory",
            "robotics",
            "audio",
            "multimodal",
        }
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


class SummaryGenerator:
    """Core summary generation service."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: str = DEFAULT_LLM_PROVIDER,
        model: str = None,
        max_workers: int = 4,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.provider = provider.lower()
        self.model = model
        self.max_workers = max_workers

    def generate_progressive_summary(
        self,
        chunks: Iterable[str],
        summary_path: Path,
        chunk_summary_path: Path,
        use_summary_cache: bool = True,
        use_chunk_summary_cache: bool = True,
    ) -> Tuple[StructuredSummary, List[ChunkSummary]]:
        """Generate progressive summary using instance configuration."""
        return progressive_summary(
            chunks=chunks,
            summary_path=summary_path,
            chunk_summary_path=chunk_summary_path,
            api_key=self.api_key,
            base_url=self.base_url,
            provider=self.provider,
            model=self.model,
            max_workers=self.max_workers,
            use_summary_cache=use_summary_cache,
            use_chunk_summary_cache=use_chunk_summary_cache,
        )


def aggregate_summaries(paths: List[Path], out_file: Path, feed_url: str) -> None:
    """Concatenate individual summaries to *out_file* with a brief header.
    
    Args:
        paths: List of summary file paths to aggregate
        out_file: Output file path for the aggregated summary
        feed_url: URL of the RSS feed for the header
    """
    header = (
        f"# Batch Summary – {feed_url}\n"
        f"_Generated: {datetime.datetime.now().isoformat(timespec='seconds')}_\n\n"
    )

    with out_file.open("w", encoding="utf-8") as fh:
        fh.write(header)
        for path in paths:
            fh.write(f"\n---\n\n## {path.stem}\n\n")
            fh.write(path.read_text(encoding="utf-8"))
            fh.write("\n")
    _LOG.info("📄  Aggregated summaries written to %s", out_file)
