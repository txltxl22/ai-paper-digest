import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*Swig.*")

import pytest
import json
from pathlib import Path

from inter.utils import get_debug_log_path
import paper_summarizer
from summary_service.pdf_processor import build_session, resolve_pdf_url, download_pdf
from summary_service.markdown_processor import extract_markdown
from summary_service.llm_utils import llm_invoke
from paper_summarizer import (
    progressive_summary,
    generate_tags_from_summary,
)
from summary_service.text_processor import chunk_text
from langchain_core.messages import HumanMessage, AIMessage
import pymupdf4llm


class FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self._content = content
        self.status_code = status
        self._headers = {"content-length": str(len(content))}

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP {self.status_code}")

    @property
    def headers(self):
        return self._headers

    def iter_content(self, chunk_size):
        yield self._content


class DummyBar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def update(self, n):
        pass


def test_build_session_no_proxy():
    session = build_session(None)
    assert session.proxies == {}


def test_build_session_with_proxy():
    session = build_session('http://proxy:1234')
    assert session.proxies['http'] == 'http://proxy:1234'
    assert session.proxies['https'] == 'http://proxy:1234'


def test_resolve_pdf_url_direct_pdf():
    url = 'http://example.com/doc.pdf'
    session = build_session()
    assert resolve_pdf_url(url, session) == url


def test_resolve_pdf_url_huggingface():
    hf = 'https://huggingface.co/papers/1234.5678'
    expected = 'https://arxiv.org/pdf/1234.5678.pdf'
    session = build_session()
    assert resolve_pdf_url(hf, session) == expected


def test_resolve_pdf_url_scrape(monkeypatch):
    html = '<html><body><a href="file.pdf">PDF</a></body></html>'
    class FakeSession:
        def get(self, url, timeout):
            class R:
                def raise_for_status(self): pass
                @property
                def text(self): return html
            return R()

    pdf = resolve_pdf_url('http://foo.com', session=FakeSession())
    assert pdf == 'http://foo.com/file.pdf'


def test_download_pdf(tmp_path, monkeypatch):
    # Create a larger fake PDF content that will pass integrity check
    content = b'%PDF-1.4\n' + b'x' * 1024  # PDF header + 1KB of content
    fake_session = type('S', (), {'get': lambda self, url, stream, timeout: FakeResponse(content)})()
    monkeypatch.setattr('summary_service.pdf_processor.tqdm', lambda *args, **kwargs: DummyBar())
    
    # Mock the PDF integrity check to always return True
    monkeypatch.setattr('summary_service.pdf_processor.verify_pdf_integrity', lambda x: True)

    out = download_pdf('http://example.com/x.pdf', output_dir=tmp_path, session=fake_session)
    assert out.exists()
    assert out.read_bytes() == content

    # Second call uses cache
    out2 = download_pdf('http://example.com/x.pdf', output_dir=tmp_path, session=fake_session)
    assert out2 == out


def test_extract_markdown(tmp_path, monkeypatch):
    pdf = tmp_path / 'a.pdf'
    pdf.write_bytes(b'%PDF')
    monkeypatch.setattr(pymupdf4llm, 'to_markdown', lambda p: '# Test')

    md = extract_markdown(pdf, md_dir=tmp_path)
    assert md.exists()
    assert md.read_text(encoding='utf-8') == '# Test'

    # cached
    md2 = extract_markdown(pdf, md_dir=tmp_path)
    assert md2 == md


def test_chunk_text():
    text = 'abcdefghij'
    chunks = chunk_text(text, max_chars=4, overlap_ratio=0.5)
    assert chunks == ['abcd', 'cdef', 'efgh', 'ghij']


def test_llm_invoke(monkeypatch):
    # Mock the LLM provider
    class DummyLLMProvider:
        def __init__(self, **kwargs): pass
        def invoke(self, messages): return AIMessage(content='resp')

    monkeypatch.setattr('summary_service.llm_utils.LLMProvider', DummyLLMProvider)
    msg = HumanMessage(content='hi')
    resp = llm_invoke([msg], api_key='key', base_url=None)
    assert isinstance(resp, AIMessage)
    assert resp.content == 'resp'


def test_progressive_summary(monkeypatch, tmp_path):
    calls = []
    def fake_llm(messages, api_key=None, **kwargs):
        calls.append(messages)

        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            # Return structured summary JSON
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    # ensure no existing cache
    debug_dir = Path(get_debug_log_path())
    if debug_dir.exists():
        for f in debug_dir.iterdir(): f.unlink()

    summary, chunks_summary = progressive_summary(['a', 'b'], summary_path=tmp_path/'summary.json', chunk_summary_path=tmp_path/'chunks.json', api_key='key', base_url=None, max_workers=1)
    
    # Check that we got structured objects
    assert summary is not None
    assert summary.one_sentence_summary == "FINAL"
    assert len(chunks_summary) == 2
    assert chunks_summary[0].main_content == "CHUNK"
    
    # two chunk calls + one final
    assert len(calls) == 3


def test_progressive_summary_cache_logic(monkeypatch, tmp_path):
    """Test cache logic for both summary and chunk summary caches."""
    calls = []
    
    def fake_llm(messages, api_key=None, **kwargs):
        calls.append(messages)
        
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            # Return structured summary JSON
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # Test 1: No cache exists, should generate everything
    calls.clear()
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=True
    )
    
    assert summary is not None
    assert summary.one_sentence_summary == "FINAL"
    assert len(chunks_summary) == 2
    assert summary_path.exists()
    assert chunk_summary_path.exists()
    # 2 chunk calls + 1 final summary call
    assert len(calls) == 3
    
    # Test 2: Both caches exist, should use cache (no LLM calls)
    calls.clear()
    summary2, chunks_summary2 = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=True
    )
    
    assert summary2 is not None
    assert summary2.one_sentence_summary == "FINAL"
    assert len(chunks_summary2) == 2
    # No LLM calls should be made (summary cache returns early)
    assert len(calls) == 0
    
    # Test 3: Summary cache disabled, should regenerate summary but use chunk cache
    calls.clear()
    summary3, chunks_summary3 = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=False,
        use_chunk_summary_cache=True
    )
    
    assert summary3 is not None
    assert summary3.one_sentence_summary == "FINAL"
    assert len(chunks_summary3) == 2
    # Only final summary call should be made (chunks use cache)
    assert len(calls) == 1
    
    # Test 4: Summary cache enabled but chunk cache disabled
    # Note: This is a limitation of the current implementation - if summary cache exists,
    # it returns early regardless of chunk cache setting
    calls.clear()
    summary4, chunks_summary4 = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=False
    )
    
    assert summary4 is not None
    assert summary4.one_sentence_summary == "FINAL"
    assert len(chunks_summary4) == 2
    # No LLM calls should be made (summary cache returns early)
    assert len(calls) == 0
    
    # Test 5: Both caches disabled, should regenerate everything
    calls.clear()
    summary5, chunks_summary5 = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=False,
        use_chunk_summary_cache=False
    )
    
    assert summary5 is not None
    assert summary5.one_sentence_summary == "FINAL"
    assert len(chunks_summary5) == 2
    # 2 chunk calls + 1 final summary call
    assert len(calls) == 3


def test_progressive_summary_cache_file_creation(monkeypatch, tmp_path):
    """Test that cache files are created correctly."""
    def fake_llm(messages, api_key=None, **kwargs):
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # Generate summaries and caches
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1
    )
    
    # Verify cache files exist and contain valid JSON
    assert summary_path.exists()
    assert chunk_summary_path.exists()
    
    # Check summary cache content
    summary_data = json.loads(summary_path.read_text(encoding='utf-8'))
    assert 'paper_info' in summary_data
    assert 'one_sentence_summary' in summary_data
    assert 'innovations' in summary_data
    assert 'results' in summary_data
    assert 'terminology' in summary_data
    
    # Check chunk summary cache content
    chunk_data = json.loads(chunk_summary_path.read_text(encoding='utf-8'))
    assert isinstance(chunk_data, list)
    assert len(chunk_data) == 2
    assert 'main_content' in chunk_data[0]
    assert 'innovations' in chunk_data[0]
    assert 'key_terms' in chunk_data[0]


def test_progressive_summary_cache_corruption_handling(monkeypatch, tmp_path):
    """Test handling of corrupted cache files."""
    def fake_llm(messages, api_key=None, **kwargs):
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # Create corrupted cache files
    summary_path.write_text("invalid json", encoding='utf-8')
    chunk_summary_path.write_text("invalid json", encoding='utf-8')
    
    # Should handle corruption gracefully and regenerate
    calls = []
    def counting_llm(messages, api_key=None, **kwargs):
        calls.append(messages)
        return fake_llm(messages, api_key, **kwargs)
    
    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', counting_llm)
    
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=True
    )
    
    # Should handle corruption gracefully - summary cache fails, chunk cache fails, returns None
    assert summary is None
    assert len(chunks_summary) == 0
    # No LLM calls should be made due to early return on corruption
    assert len(calls) == 0


def test_progressive_summary_cache_missing_chunk_file(monkeypatch, tmp_path):
    """Test behavior when chunk summary file is missing but summary file exists."""
    def fake_llm(messages, api_key=None, **kwargs):
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # Create valid summary cache but no chunk cache
    summary_path.write_text(json.dumps({
        "paper_info": {
            "title_zh": "测试论文",
            "title_en": "Test Paper"
        },
        "one_sentence_summary": "CACHED",
        "innovations": [
            {
                "title": "Test Innovation",
                "description": "A test innovation",
                "improvement": "Improves upon existing methods",
                "significance": "Has important implications"
            }
        ],
        "results": {
            "experimental_highlights": ["Test result"],
            "practical_value": ["Test value"]
        },
        "terminology": [
            {
                "term": "Test Term",
                "definition": "A test term"
            }
        ]
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    # chunk_summary_path should not exist
    
    calls = []
    def counting_llm(messages, api_key=None, **kwargs):
        calls.append(messages)
        return fake_llm(messages, api_key, **kwargs)
    
    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', counting_llm)
    
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=True
    )
    
    # Should use summary cache but return empty chunk summaries since chunk file doesn't exist
    assert summary is not None
    assert summary.one_sentence_summary == "CACHED"  # From cache
    assert len(chunks_summary) == 0  # Empty because chunk file doesn't exist
    # No LLM calls should be made (summary cache returns early)
    assert len(calls) == 0


def test_progressive_summary_cache_default_values(monkeypatch, tmp_path):
    """Test that cache parameters default to True."""
    def fake_llm(messages, api_key=None, **kwargs):
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # First call - generate everything
    calls = []
    def counting_llm(messages, api_key=None, **kwargs):
        calls.append(messages)
        return fake_llm(messages, api_key, **kwargs)
    
    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', counting_llm)
    
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1
        # use_summary_cache and use_chunk_summary_cache should default to True
    )
    
    assert summary is not None
    assert len(chunks_summary) == 2
    # 2 chunk calls + 1 final summary call
    assert len(calls) == 3
    
    # Second call - should use cache (default values)
    calls.clear()
    summary2, chunks_summary2 = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1
        # use_summary_cache and use_chunk_summary_cache should default to True
    )
    
    assert summary2 is not None
    assert len(chunks_summary2) == 2
    # No LLM calls should be made (using cache)
    assert len(calls) == 0


def test_progressive_summary_cache_only_chunk_exists(monkeypatch, tmp_path):
    """Test behavior when only chunk summary cache exists but not summary cache."""
    def fake_llm(messages, api_key=None, **kwargs):
        # Check if this is the final summary call by looking for "AI助手论文总结" in the content
        message_content = messages[0].content if messages else ""
        if "AI助手论文总结" in message_content:
            return AIMessage(content=json.dumps({
                "paper_info": {
                    "title_zh": "测试论文",
                    "title_en": "Test Paper"
                },
                "one_sentence_summary": "FINAL",
                "innovations": [
                    {
                        "title": "Test Innovation",
                        "description": "A test innovation",
                        "improvement": "Improves upon existing methods",
                        "significance": "Has important implications"
                    }
                ],
                "results": {
                    "experimental_highlights": ["Test result"],
                    "practical_value": ["Test value"]
                },
                "terminology": [
                    {
                        "term": "Test Term",
                        "definition": "A test term"
                    }
                ]
            }))
        # Return chunk summary JSON
        return AIMessage(content=json.dumps({
            "main_content": "CHUNK",
            "innovations": [{"title": "Test Innovation", "description": "A test innovation", "improvement": "Improves upon existing methods", "significance": "Has important implications"}],
            "key_terms": [
                {
                    "term": "Test Term",
                    "definition": "A test term"
                }
            ]
        }))

    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', fake_llm)
    
    summary_path = tmp_path / 'summary.json'
    chunk_summary_path = tmp_path / 'chunks.json'
    chunks = ['chunk1', 'chunk2']
    
    # Create only chunk summary cache (no summary cache)
    chunk_summary_path.write_text(json.dumps([
        {
            "main_content": "CACHED_CHUNK",
            "innovations": [
                {
                    "title": "Cached Innovation",
                    "description": "A cached innovation",
                    "improvement": "Improves upon existing methods",
                    "significance": "Has important implications"
                }
            ],
            "key_terms": [
                {
                    "term": "Cached Term",
                    "definition": "A cached term"
                }
            ]
        },
        {
            "main_content": "CACHED_CHUNK_2",
            "innovations": [
                {
                    "title": "Cached Innovation 2",
                    "description": "A cached innovation 2",
                    "improvement": "Improves upon existing methods",
                    "significance": "Has important implications"
                }
            ],
            "key_terms": [
                {
                    "term": "Cached Term 2",
                    "definition": "A cached term 2"
                }
            ]
        }
    ], ensure_ascii=False, indent=2), encoding='utf-8')
    
    # summary_path should not exist
    
    calls = []
    def counting_llm(messages, api_key=None, **kwargs):
        calls.append(messages)
        return fake_llm(messages, api_key, **kwargs)
    
    monkeypatch.setattr('summary_service.summary_generator.llm_invoke', counting_llm)
    
    summary, chunks_summary = progressive_summary(
        chunks, 
        summary_path=summary_path, 
        chunk_summary_path=chunk_summary_path, 
        api_key='key', 
        base_url=None, 
        max_workers=1,
        use_summary_cache=True,
        use_chunk_summary_cache=True
    )
    
    # Should use chunk cache but generate summary
    assert summary is not None
    assert summary.one_sentence_summary == "FINAL"
    assert len(chunks_summary) == 2
    assert chunks_summary[0].main_content == "CACHED_CHUNK"
    assert chunks_summary[1].main_content == "CACHED_CHUNK_2"
    # Only final summary call should be made (chunks use cache)
    assert len(calls) == 1
    
    # Summary cache should be created
    assert summary_path.exists()
