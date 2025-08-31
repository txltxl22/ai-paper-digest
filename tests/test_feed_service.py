import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*Swig.*")

from pathlib import Path
from types import SimpleNamespace

# Import the module under test – relative import assuming tests run from repo root
import feed_paper_summarizer_service as svc

################################################################################
# Helpers / fixtures
################################################################################

class DummyAIMessage(SimpleNamespace):
    """Mimic the minimal part of langchain_core.messages.AIMessage we rely on."""
    content: str


################################################################################
# _parse_args
################################################################################

def test_parse_args_defaults():
    argv = [
        "https://example.com/rss.xml",
    ]
    args = svc._parse_args(argv)  # type: ignore[attr-defined]
    assert args.rss_url == "https://example.com/rss.xml"
    # Defaults
    assert args.workers == (svc.os.cpu_count() or 4)
    assert args.output == Path("output.md")
    assert args.api_key is None

################################################################################
# _aggregate_summaries
################################################################################

def test_aggregate_summaries(tmp_path: Path):
    # Two fake summary files
    s1 = tmp_path / "2506.00001.md"
    s2 = tmp_path / "2506.00002.md"
    s1.write_text("Summary 1", encoding="utf-8")
    s2.write_text("Summary 2", encoding="utf-8")

    out_file = tmp_path / "aggregate.md"
    from summary_service import aggregate_summaries
    aggregate_summaries([s1, s2], out_file, "https://example.com/rss.xml")

    output = out_file.read_text(encoding="utf-8")
    # Header present
    assert "# Batch Summary – https://example.com/rss.xml" in output
    # Each individual summary included under its own heading
    assert "## 2506.00001" in output and "Summary 1" in output
    assert "## 2506.00002" in output and "Summary 2" in output

################################################################################
# _summarize_url – success & failure paths
################################################################################

def test_summarize_url_success(monkeypatch, tmp_path: Path):
    """_summarize_url should return a Path when everything works."""
    # Patch paper_summarizer functions used inside _summarize_url
    class DummyPS:
        SUMMARY_DIR = tmp_path
        CHUNKS_SUMMARY_DIR = tmp_path / 'chunks'
        PDF_DIR = tmp_path / 'papers'
        MD_DIR = tmp_path / 'markdown'
        SESSION = "dummy_session"  # Add SESSION attribute

        @staticmethod
        def resolve_pdf_url(url):  # noqa: D401
            return "https://example.com/dummy.pdf"

        @staticmethod
        def download_pdf(url):  # noqa: D401
            # Create a fake PDF path inside tmp_dir
            p = tmp_path / "dummy.pdf"
            p.write_bytes(b"%PDF-1.4")
            return p

        @staticmethod
        def extract_markdown(pdf_path):  # noqa: D401
            p = tmp_path / "markdown"
            os.makedirs(p)
            md = p / "dummy.md"
            md.write_text("Some markdown", encoding="utf-8")
            return md

        @staticmethod
        def chunk_text(text):  # noqa: D401
            return [text]

        @staticmethod
        def progressive_summary(
            chunks, summary_path, chunk_summary_path, api_key=None, base_url=None, provider=None, model=None, max_workers=1
        ):  # noqa: D401
            os.makedirs(DummyPS.CHUNKS_SUMMARY_DIR, exist_ok=True)
            # Return a mock StructuredSummary object
            from summary_service.models import StructuredSummary, PaperInfo, Innovation, Results, TermDefinition
            summary = StructuredSummary(
                paper_info=PaperInfo(title_zh="测试论文", title_en="Test Paper"),
                one_sentence_summary="This is a test summary.",
                innovations=[
                    Innovation(
                        title="Test Innovation",
                        description="A test innovation",
                        improvement="Improves upon existing methods",
                        significance="Has important implications"
                    )
                ],
                results=Results(
                    experimental_highlights=["Test result"],
                    practical_value=["Test value"]
                ),
                terminology=[
                    TermDefinition(term="Test Term", definition="A test term")
                ]
            )
            return summary, []

        @staticmethod
        def generate_tags_from_summary(summary, api_key=None, base_url=None, provider=None, model=None, max_tags=8):  # noqa: D401
            from summary_service.models import Tags
            return Tags(top=["llm"], tags=["llm", "reasoning"])

    # Mock the summary_service functions directly
    def mock_resolve_pdf_url(url, session):
        return "https://example.com/dummy.pdf"
    
    def mock_download_pdf(url, output_dir, session, **kwargs):
        p = tmp_path / "dummy.pdf"
        p.write_bytes(b"%PDF-1.4")
        return p
    
    def mock_extract_markdown(pdf_path, md_dir):
        p = tmp_path / "markdown"
        os.makedirs(p, exist_ok=True)
        md = p / "dummy.md"
        md.write_text("Some markdown", encoding="utf-8")
        return md
    
    def mock_chunk_text(text):
        return [text]
    
    def mock_progressive_summary(chunks, summary_path, chunk_summary_path, **kwargs):
        os.makedirs(tmp_path / 'chunks', exist_ok=True)
        from summary_service.models import StructuredSummary, PaperInfo, Innovation, Results, TermDefinition
        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试论文", title_en="Test Paper"),
            one_sentence_summary="This is a test summary.",
            innovations=[
                Innovation(
                    title="Test Innovation",
                    description="A test innovation",
                    improvement="Improves upon existing methods",
                    significance="Has important implications"
                )
            ],
            results=Results(
                experimental_highlights=["Test result"],
                practical_value=["Test value"]
            ),
            terminology=[
                TermDefinition(term="Test Term", definition="A test term")
            ]
        )
        return summary, []
    
    def mock_generate_tags_from_summary(summary, **kwargs):
        from summary_service.models import Tags
        return Tags(top=["llm"], tags=["llm", "reasoning"])
    
    def mock_save_summary_with_service_record(arxiv_id, summary_content, tags, **kwargs):
        import json
        record = {
            "service_data": {
                "arxiv_id": arxiv_id,
                "source_type": "system",
                "created_at": "2025-08-30T15:01:22.214751",
                "original_url": kwargs.get("original_url"),
                "ai_judgment": kwargs.get("ai_judgment") or {}
            },
            "summary_data": {
                "content": summary_content,
                "tags": tags,
                "updated_at": "2025-08-30T15:01:22.214751"
            }
        }
        json_path = tmp_path / f"{arxiv_id}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Also create legacy files for backward compatibility
        md_path = tmp_path / f"{arxiv_id}.md"
        md_path.write_text(str(summary_content), encoding="utf-8")
        
        tags_path = tmp_path / f"{arxiv_id}.tags.json"
        tags_path.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")

    # Mock the summarize_paper_url function
    def mock_summarize_paper_url(url, api_key=None, base_url=None, provider="deepseek", model="deepseek-chat", 
                                max_input_char=50000, extract_only=False, local=False, max_workers=1, session=None):
        # Create the expected output files
        summary_path = tmp_path / "dummy.md"
        summary_path.write_text("测试论文\nTest Paper\nThis is a test summary.", encoding="utf-8")
        
        # Create tags file
        tags_path = tmp_path / "dummy.tags.json"
        import json
        tags_data = {"tags": ["llm", "reasoning"], "top": ["llm"]}
        tags_path.write_text(json.dumps(tags_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Create service record
        json_path = tmp_path / "dummy.json"
        record = {
            "service_data": {
                "arxiv_id": "dummy",
                "source_type": "system",
                "created_at": "2025-08-30T15:01:22.214751",
                "original_url": "https://example.com/dummy.pdf",
                "ai_judgment": {}
            },
            "summary_data": {
                "content": "测试论文\nTest Paper\nThis is a test summary.",
                "tags": tags_data,
                "updated_at": "2025-08-30T15:01:22.214751"
            }
        }
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return summary_path, "https://example.com/dummy.pdf", "Test Paper"
    
    # Mock the paper_summarizer module
    monkeypatch.setattr(svc.ps, "summarize_paper_url", mock_summarize_paper_url)

    out_path, _, _ = svc._summarize_url("https://example.com/paper", api_key="dummy")  # type: ignore[attr-defined]

    assert out_path is not None and out_path.exists()
    
    # Check that the summary file contains the expected content
    summary_content = out_path.read_text(encoding="utf-8")
    assert "测试论文" in summary_content
    assert "Test Paper" in summary_content
    assert "This is a test summary" in summary_content

    # tags file should be produced alongside summary
    tags_path = tmp_path / "dummy.tags.json"
    assert tags_path.exists()
    import json as _json
    data = _json.loads(tags_path.read_text(encoding="utf-8"))
    assert data.get("tags") == ["llm", "reasoning"]
    assert data.get("top") == ["llm"]


def test_summarize_url_backfills_tags_on_cached_summary(monkeypatch, tmp_path: Path):
    class DummyPS:
        SUMMARY_DIR = tmp_path
        CHUNKS_SUMMARY_DIR = tmp_path / 'chunks'
        PDF_DIR = tmp_path / 'papers'
        MD_DIR = tmp_path / 'markdown'
        SESSION = "dummy_session"  # Add SESSION attribute

        @staticmethod
        def resolve_pdf_url(url):
            return "https://example.com/dummy.pdf"

        @staticmethod
        def download_pdf(url):
            p = tmp_path / "dummy.pdf"
            p.write_bytes(b"%PDF-1.4")
            return p

        @staticmethod
        def extract_markdown(pdf_path):
            p = tmp_path / "markdown"
            os.makedirs(p, exist_ok=True)
            md = p / "dummy.md"
            md.write_text("Some markdown", encoding="utf-8")
            return md

        @staticmethod
        def chunk_text(text):
            return [text]

        @staticmethod
        def generate_tags_from_summary(summary, api_key=None, base_url=None, provider=None, model=None, max_tags=8):
            from summary_service.models import Tags
            return Tags(top=["cached"], tags=["cached"])

    # Mock the summary_service functions directly
    def mock_resolve_pdf_url(url, session):
        return "https://example.com/dummy.pdf"
    
    def mock_download_pdf(url, output_dir, session, **kwargs):
        p = tmp_path / "dummy.pdf"
        p.write_bytes(b"%PDF-1.4")
        return p
    
    def mock_extract_markdown(pdf_path, md_dir):
        p = tmp_path / "markdown"
        os.makedirs(p, exist_ok=True)
        md = p / "dummy.md"
        md.write_text("Some markdown", encoding="utf-8")
        return md
    
    def mock_generate_tags_from_summary(summary, **kwargs):
        from summary_service.models import Tags
        return Tags(top=["cached"], tags=["cached"])
    
    def mock_save_summary_with_service_record(arxiv_id, summary_content, tags, **kwargs):
        import json
        record = {
            "service_data": {
                "arxiv_id": arxiv_id,
                "source_type": "system",
                "created_at": "2025-08-30T15:01:22.214751",
                "original_url": kwargs.get("original_url"),
                "ai_judgment": kwargs.get("ai_judgment") or {}
            },
            "summary_data": {
                "content": summary_content,
                "tags": tags,
                "updated_at": "2025-08-30T15:01:22.214751"
            }
        }
        json_path = tmp_path / f"{arxiv_id}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Also create legacy files for backward compatibility
        md_path = tmp_path / f"{arxiv_id}.md"
        md_path.write_text(str(summary_content), encoding="utf-8")
        
        tags_path = tmp_path / f"{arxiv_id}.tags.json"
        tags_path.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")

    # Pre-create cached summary so the service takes the cached path branch
    (tmp_path / "dummy.md").write_text("CACHED SUMMARY TEXT", encoding="utf-8")
    # Don't create tags file so it will trigger backfilling

        # Mock the summarize_paper_url function for cached summary case
    def mock_summarize_paper_url_cached(url, api_key=None, base_url=None, provider="deepseek", model="deepseek-chat", 
                                       max_input_char=50000, extract_only=False, local=False, max_workers=1, session=None):
        # Create the expected output files
        summary_path = tmp_path / "dummy.md"
        summary_path.write_text("CACHED SUMMARY TEXT", encoding="utf-8")
        
        # Create tags file
        tags_path = tmp_path / "dummy.tags.json"
        import json
        tags_data = {"tags": ["cached"], "top": ["cached"]}
        tags_path.write_text(json.dumps(tags_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Create service record
        json_path = tmp_path / "dummy.json"
        record = {
            "service_data": {
                "arxiv_id": "dummy",
                "source_type": "system",
                "created_at": "2025-08-30T15:01:22.214751",
                "original_url": "https://example.com/dummy.pdf",
                "ai_judgment": {}
            },
            "summary_data": {
                "content": "CACHED SUMMARY TEXT",
                "tags": tags_data,
                "updated_at": "2025-08-30T15:01:22.214751"
            }
        }
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return summary_path, "https://example.com/dummy.pdf", "Cached Paper"

    # Mock the paper_summarizer module
    monkeypatch.setattr(svc.ps, "summarize_paper_url", mock_summarize_paper_url_cached)

    out_path, _, _ = svc._summarize_url("https://example.com/paper", api_key="key")  # type: ignore[attr-defined]

    assert out_path == tmp_path / "dummy.md"
    tags_path = tmp_path / "dummy.tags.json"
    assert tags_path.exists()
    import json as _json
    data = _json.loads(tags_path.read_text(encoding="utf-8"))
    # The tags should be backfilled correctly
    assert data.get("tags") == ["cached"]
    assert data.get("top") == ["cached"]


def test_summarize_url_failure(monkeypatch):
    """_summarize_url should swallow exceptions and return None."""

    def mock_summarize_paper_url_failure(url, api_key=None, base_url=None, provider="deepseek", model="deepseek-chat", 
                                       max_input_char=50000, extract_only=False, local=False, max_workers=1, session=None):
        raise RuntimeError("boom")

    # Mock the paper_summarizer module to raise an exception
    monkeypatch.setattr(svc.ps, "summarize_paper_url", mock_summarize_paper_url_failure)

    result, _, _ = svc._summarize_url("https://bad-url.com")  # type: ignore[attr-defined]
    assert result is None


def test_collect_local_links_prefers_markdown_over_pdfs(monkeypatch, tmp_path: Path):
    # Create dummy project structure for ps paths
    class DummyPS:
        MD_DIR = tmp_path / "markdown"
        PDF_DIR = tmp_path / "papers"

    md = DummyPS.MD_DIR
    pdf = DummyPS.PDF_DIR
    md.mkdir(parents=True, exist_ok=True)
    pdf.mkdir(parents=True, exist_ok=True)

    # Create stems in both places; markdown stems should be returned
    (md / "2506.10101.md").write_text("x", encoding="utf-8")
    (pdf / "2506.20202.pdf").write_bytes(b"%PDF")

    monkeypatch.setattr(svc, "ps", DummyPS)

    links = svc._collect_local_links()  # type: ignore[attr-defined]
    assert links == ["https://arxiv.org/pdf/2506.10101.pdf"]


def test_collect_local_links_falls_back_to_pdfs(monkeypatch, tmp_path: Path):
    class DummyPS:
        MD_DIR = tmp_path / "markdown"
        PDF_DIR = tmp_path / "papers"

    pdf = DummyPS.PDF_DIR
    pdf.mkdir(parents=True, exist_ok=True)
    (pdf / "2506.30303.pdf").write_bytes(b"%PDF")

    monkeypatch.setattr(svc, "ps", DummyPS)

    links = svc._collect_local_links()  # type: ignore[attr-defined]
    assert links == ["https://arxiv.org/pdf/2506.30303.pdf"]


def test_tags_only_run(monkeypatch, tmp_path: Path):
    class DummyPS:
        SUMMARY_DIR = tmp_path

        @staticmethod
        def generate_tags_from_summary(summary, api_key=None, base_url=None, provider=None, model=None, max_tags=8):
            from summary_service.models import Tags
            return Tags(top=["test"], tags=["t1", "t2"])

    monkeypatch.setattr(svc, "ps", DummyPS)
    monkeypatch.setattr(svc, "generate_tags_from_summary", DummyPS.generate_tags_from_summary)

    # Prepare summaries: one with tags, one without
    s1 = tmp_path / "2507.11111.md"
    s2 = tmp_path / "2507.22222.md"
    s1.write_text("S1", encoding="utf-8")
    s2.write_text("S2", encoding="utf-8")
    (tmp_path / "2507.11111.tags.json").write_text('{"tags":["exists"]}', encoding="utf-8")

    total, updated = svc._tags_only_run()  # type: ignore[attr-defined]
    assert total == 2 and updated == 1
    data = __import__('json').loads((tmp_path / "2507.22222.tags.json").read_text(encoding="utf-8"))
    # After our fix, tags are saved with the new structure
    assert data["tags"] == ["t1", "t2"]
    assert data["top"] == ["test"]


def test_tags_only_run_correct_structure(monkeypatch, tmp_path: Path):
    """Test that tags are saved with correct structure (not nested)."""
    class DummyPS:
        SUMMARY_DIR = tmp_path

        @staticmethod
        def generate_tags_from_summary(summary, api_key=None, base_url=None, provider=None, model=None, max_tags=8):
            from summary_service.models import Tags
            return Tags(top=["llm", "nlp"], tags=["machine learning", "natural language processing"])

    monkeypatch.setattr(svc, "ps", DummyPS)
    monkeypatch.setattr(svc, "generate_tags_from_summary", DummyPS.generate_tags_from_summary)

    # Prepare summary without tags
    s1 = tmp_path / "2507.11111.md"
    s1.write_text("S1", encoding="utf-8")

    total, updated = svc._tags_only_run()  # type: ignore[attr-defined]
    assert total == 1 and updated == 1

    # Check that tags are saved with correct structure (not nested)
    data = __import__('json').loads((tmp_path / "2507.11111.tags.json").read_text(encoding="utf-8"))

    # Should have the correct structure, not nested
    assert "top" in data
    assert "tags" in data
    assert data["top"] == ["llm", "nlp"]
    assert data["tags"] == ["machine learning", "natural language processing"]
    
    # Should NOT have the nested structure that was causing the bug
    assert "tags" not in data.get("tags", {})  # No nested "tags" field
