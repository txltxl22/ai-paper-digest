import os
from pathlib import Path
from pprint import pprint
import paper_summarizer as ps

if __name__ == "__main__":
    pdf_link = ps.resolve_pdf_url("https://huggingface.co/papers/2508.20453")
    pdf_path = ps.download_pdf(pdf_link)
    md_path = ps.extract_markdown(pdf_path)
    text = md_path.read_text(encoding="utf-8")
    text = text[:3000]
    chunks = ps.chunk_text(text, max_chars=500, overlap_ratio=0.05)
    summary, chunks_summary = ps.progressive_summary(
        chunks,
        summary_path=Path("example_summary.json"),
        chunk_summary_path=Path("example_chunks_summary.json"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        provider="deepseek",
        model="deepseek-chat",
        max_workers=8,
        use_summary_cache=False,
        use_chunk_summary_cache=False,
    )
    tags = ps.generate_tags_from_summary(
        summary.one_sentence_summary,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        provider="deepseek",
        model="deepseek-chat",
    )
    pprint(summary)
    pprint(chunks_summary)
    pprint(tags)
