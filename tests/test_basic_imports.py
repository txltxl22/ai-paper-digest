"""
Basic import tests to verify the core functionality.
"""

import pytest


def test_paper_summarizer_imports():
    """Test that basic paper_summarizer functions can be imported."""
    from paper_summarizer import (
        build_session,
        resolve_pdf_url,
        download_pdf,
        extract_markdown,
    )

    # Test that functions are callable
    assert callable(build_session)
    assert callable(resolve_pdf_url)
    assert callable(download_pdf)
    assert callable(extract_markdown)


def test_summary_service_imports():
    """Test that summary_service modules can be imported."""
    from summary_service.text_processor import chunk_text
    from summary_service.models import StructuredSummary, PaperInfo, Tags
    from summary_service.record_manager import save_summary_with_service_record

    # Test that functions are callable
    assert callable(chunk_text)
    assert callable(save_summary_with_service_record)

    # Test that classes can be instantiated
    paper_info = PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract")
    assert paper_info.title_zh == "测试"
    assert paper_info.title_en == "Test"
