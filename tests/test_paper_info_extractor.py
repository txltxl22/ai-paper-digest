"""
Tests for paper_info_extractor module.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from summary_service.paper_info_extractor import (
    PaperInfoExtractor,
    extract_title,
    extract_abstract,
    get_paper_info as get_paper_info_func,
    extract_arxiv_id
)


class TestPaperInfoExtractor:
    """Test PaperInfoExtractor functionality."""
    
    def test_get_paper_info_fetches_content_once(self):
        """Test that get_paper_info fetches HTML content only once and reuses it."""
        extractor = PaperInfoExtractor(timeout=10)
        
        # Mock HTML content for arXiv
        mock_content = """
        <html>
        <head>
            <title>Test Paper Title</title>
            <meta name="citation_title" content="Test Paper Title" />
        </head>
        <body>
            <blockquote class="abstract mathjax">
                This is a test abstract that should be extracted from the HTML content.
                It contains enough text to pass the minimum length requirement.
            </blockquote>
        </body>
        </html>
        """
        
        with patch.object(extractor.session, 'get') as mock_get:
            # Configure mock response
            mock_response = Mock()
            mock_response.text = mock_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            # Call get_paper_info
            result = extractor.get_paper_info("https://arxiv.org/abs/2508.15144")
            
            # Verify that session.get was called only once
            assert mock_get.call_count == 1, "Should fetch content only once"
            
            # Verify that both title and abstract were extracted
            assert result.title_en is not None, "Title should be extracted"
            assert result.abstract is not None, "Abstract should be extracted"
            assert "Test Paper" in result.title_en, "Title should contain expected text"
            assert "test abstract" in result.abstract.lower(), "Abstract should contain expected text"
            
        extractor.close()
    
    def test_private_methods_accept_content_parameter(self):
        """Test that private extraction methods accept and use content parameter."""
        extractor = PaperInfoExtractor(timeout=10)
        
        # Mock HTML content
        mock_content = """
        <html>
        <head>
            <title>Another Test Paper</title>
        </head>
        <body>
            <blockquote class="abstract mathjax">
                This is another test abstract with sufficient length to be extracted.
            </blockquote>
        </body>
        </html>
        """
        
        # Test that _extract_title_from_url accepts content parameter
        with patch.object(extractor, '_fetch_url_content') as mock_fetch:
            # Should not call _fetch_url_content when content is provided
            title = extractor._extract_title_from_url(
                "https://arxiv.org/abs/2508.15144",
                content=mock_content
            )
            
            # Verify _fetch_url_content was not called
            mock_fetch.assert_not_called()
            
            # Verify title was extracted from provided content
            assert title is not None
            assert "Another Test Paper" in title or "Test Paper" in title
        
        # Test that _extract_abstract_from_url accepts content parameter
        with patch.object(extractor, '_fetch_url_content') as mock_fetch:
            # Should not call _fetch_url_content when content is provided
            abstract = extractor._extract_abstract_from_url(
                "https://arxiv.org/abs/2508.15144",
                content=mock_content
            )
            
            # Verify _fetch_url_content was not called
            mock_fetch.assert_not_called()
            
            # Verify abstract was extracted from provided content
            assert abstract is not None
            assert len(abstract) > 50  # Should meet minimum length requirement
        
        extractor.close()
    
    def test_convenience_functions_use_get_paper_info(self):
        """Test that convenience functions extract_title and extract_abstract use get_paper_info."""
        mock_content = """
        <html>
        <head>
            <title>Convenience Test Paper</title>
        </head>
        <body>
            <blockquote class="abstract mathjax">
                This is a convenience test abstract with sufficient length to be extracted properly.
            </blockquote>
        </body>
        </html>
        """
        
        with patch('summary_service.paper_info_extractor.PaperInfoExtractor') as MockExtractor:
            from summary_service.models import PaperInfo
            mock_instance = Mock()
            mock_paper_info = PaperInfo(
                title_en="Convenience Test Paper",
                abstract="This is a convenience test abstract with sufficient length to be extracted properly.",
                arxiv_id="2508.15144",
                url="https://arxiv.org/abs/2508.15144",
                source="arxiv"
            )
            mock_instance.get_paper_info.return_value = mock_paper_info
            MockExtractor.return_value = mock_instance
            
            # Test extract_title
            title = extract_title("https://arxiv.org/abs/2508.15144")
            assert title == "Convenience Test Paper"
            mock_instance.get_paper_info.assert_called_once()
            
            # Reset mock
            mock_instance.reset_mock()
            
            # Test extract_abstract
            abstract = extract_abstract("https://arxiv.org/abs/2508.15144")
            assert abstract == "This is a convenience test abstract with sufficient length to be extracted properly."
            mock_instance.get_paper_info.assert_called_once()
    
    def test_get_paper_info_handles_fetch_failure(self):
        """Test that get_paper_info handles content fetch failures gracefully."""
        from summary_service.models import PaperInfo
        # Use a small retry delay for faster tests
        extractor = PaperInfoExtractor(timeout=10, retry_delay=0.01)
        
        with patch.object(extractor.session, 'get') as mock_get:
            # Simulate fetch failure
            mock_get.side_effect = Exception("Network error")
            
            result = extractor.get_paper_info("https://arxiv.org/abs/2508.15144")
            
            # Should return PaperInfo object with empty/default values but not crash
            assert result is not None
            assert isinstance(result, PaperInfo)
            assert result.title_en == "" or result.title_en is None
            assert result.abstract == "" or result.abstract is None
        
        extractor.close()
    
    def test_extract_arxiv_id_from_url(self):
        """Test arXiv ID extraction from various URL formats."""
        extractor = PaperInfoExtractor(timeout=10)
        
        # Test various URL formats
        test_cases = [
            ("https://arxiv.org/abs/2508.15144", "2508.15144"),
            ("https://arxiv.org/pdf/2508.15144.pdf", "2508.15144"),
            ("https://huggingface.co/papers/2508.15144", "2508.15144"),
            ("https://example.com/papers/2508.15144", "2508.15144"),
        ]
        
        for url, expected_id in test_cases:
            arxiv_id = extractor.extract_arxiv_id_from_url(url)
            assert arxiv_id == expected_id, f"Failed for URL: {url}"
        
        extractor.close()
    
    def test_private_methods_are_not_publicly_accessible(self):
        """Test that private methods cannot be accessed directly (they exist but are private)."""
        extractor = PaperInfoExtractor(timeout=10)
        
        # These methods should exist but be private (prefixed with _)
        assert hasattr(extractor, '_extract_title_from_url')
        assert hasattr(extractor, '_extract_abstract_from_url')
        assert hasattr(extractor, '_fetch_url_content')
        
        # Public methods should exist
        assert hasattr(extractor, 'get_paper_info')
        assert hasattr(extractor, 'extract_arxiv_id_from_url')
        
        # Old public methods should NOT exist
        assert not hasattr(extractor, 'extract_title_from_url')
        assert not hasattr(extractor, 'extract_abstract_from_url')
        
        extractor.close()
    
    def test_get_paper_info_returns_complete_structure(self):
        """Test that get_paper_info returns a complete info dictionary."""
        extractor = PaperInfoExtractor(timeout=10)
        
        mock_content = """
        <html>
        <head>
            <title>Complete Test Paper</title>
        </head>
        <body>
            <blockquote class="abstract mathjax">
                This is a complete test abstract with sufficient length to be extracted properly.
            </blockquote>
        </body>
        </html>
        """
        
        with patch.object(extractor.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.text = mock_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = extractor.get_paper_info("https://arxiv.org/abs/2508.15144")
            
            # Verify result is a PaperInfo object with expected attributes
            assert result is not None
            assert hasattr(result, "url")
            assert hasattr(result, "title_en")
            assert hasattr(result, "abstract")
            assert hasattr(result, "arxiv_id")
            assert hasattr(result, "source")
            
            # Verify source is correctly identified
            assert result.source == "arxiv"
            assert result.arxiv_id == "2508.15144"
            assert result.url == "https://arxiv.org/abs/2508.15144"
        
        extractor.close()

