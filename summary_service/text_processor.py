"""
text_processor.py - Text processing utilities for summary generation

This module provides text chunking and processing functionality
for breaking down large documents into manageable chunks.
"""

from typing import List

# Default chunking configuration
CHUNK_LENGTH = 5000
CHUNK_OVERLAP_RATIO = 0.05


def chunk_text(
    text: str, max_chars: int = CHUNK_LENGTH, overlap_ratio: float = CHUNK_OVERLAP_RATIO
) -> List[str]:
    """Split text into overlapping chunks for processing.

    Args:
        text: The text to chunk
        max_chars: Maximum characters per chunk
        overlap_ratio: Ratio of overlap between chunks (0.0 to 1.0)

    Returns:
        List of text chunks

    Raises:
        ValueError: If max_chars <= 0 or overlap_ratio >= 1.0
    """
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


class TextProcessor:
    """Text processing utilities for summary generation."""

    def __init__(
        self,
        chunk_length: int = CHUNK_LENGTH,
        overlap_ratio: float = CHUNK_OVERLAP_RATIO,
    ):
        self.chunk_length = chunk_length
        self.overlap_ratio = overlap_ratio

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks using instance configuration."""
        return chunk_text(text, self.chunk_length, self.overlap_ratio)

    def process_text_for_summary(self, text: str) -> List[str]:
        """Process text and prepare it for summary generation.

        This method can be extended to include text cleaning, normalization,
        and other preprocessing steps before chunking.
        """
        # Basic text cleaning
        cleaned_text = text.strip()

        # Remove excessive whitespace
        cleaned_text = " ".join(cleaned_text.split())

        return self.chunk_text(cleaned_text)
