import os
from pathlib import Path
from pprint import pprint

# Import functions from the modular services
from summary_service.pdf_processor import resolve_pdf_url, download_pdf
from summary_service.markdown_processor import extract_markdown
from summary_service.text_processor import chunk_text
from summary_service.summary_generator import progressive_summary, generate_tags_from_summary

if __name__ == "__main__":
    # Create a session for PDF operations
    from summary_service.pdf_processor import build_session
    session = build_session()
    
    pdf_link = resolve_pdf_url("https://huggingface.co/papers/2508.20453", session)
    pdf_path = download_pdf(pdf_link, output_dir=Path("papers"), session=session)
    md_path = extract_markdown(pdf_path, md_dir=Path("markdown"))
    text = md_path.read_text(encoding="utf-8")
    text = text[:3000]
    chunks = chunk_text(text, max_chars=500, overlap_ratio=0.05)
    summary, chunks_summary = progressive_summary(
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
    tags = generate_tags_from_summary(
        summary.one_sentence_summary,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        provider="deepseek",
        model="deepseek-chat",
    )
    pprint(summary)
    pprint(chunks_summary)
    pprint(tags)
