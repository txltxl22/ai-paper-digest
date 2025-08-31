# Title Extractor Module

This module provides functionality for extracting paper titles from arXiv and Hugging Face URLs.

## Features

- **arXiv Support**: Extract titles from arXiv paper pages
- **Hugging Face Support**: Extract titles from Hugging Face paper pages
- **Robust Error Handling**: Graceful handling of network errors and parsing failures
- **Title Cleaning**: Automatic removal of arXiv IDs and other prefixes
- **Batch Processing**: Process multiple URLs efficiently

## Usage

### Basic Usage

```python
from summary_service.title_extractor import extract_title, get_paper_info

# Extract just the title
title = extract_title("https://arxiv.org/abs/2508.18966")
print(title)  # "USO: Unified Style and Subject-Driven Generation via Disentangled and Reward Learning"

# Get comprehensive information
info = get_paper_info("https://arxiv.org/abs/2508.18966")
print(info)
# {
#     "url": "https://arxiv.org/abs/2508.18966",
#     "title": "USO: Unified Style and Subject-Driven Generation via Disentangled and Reward Learning",
#     "arxiv_id": "2508.18966",
#     "source": "arxiv",
#     "success": True,
#     "error": None
# }
```

### Advanced Usage

```python
from summary_service.title_extractor import TitleExtractor

# Create an extractor with custom timeout
extractor = TitleExtractor(timeout=15)

# Extract title
title = extractor.extract_title_from_url("https://arxiv.org/abs/2508.18966")

# Extract arXiv ID
arxiv_id = extractor.extract_arxiv_id_from_url("https://arxiv.org/abs/2508.18966")

# Get comprehensive info
info = extractor.get_paper_info("https://arxiv.org/abs/2508.18966")

# Don't forget to close the session
extractor.close()
```

### Integration with Summary Service

```python
from summary_service.integration_example import create_enhanced_service_record

# Create enhanced service record with title
record = create_enhanced_service_record(
    arxiv_id="2508.18966",
    original_url="https://arxiv.org/abs/2508.18966",
    source_type="system"
)
```

## Supported URL Formats

### arXiv
- `https://arxiv.org/abs/2508.18966`
- `https://arxiv.org/pdf/2508.18966.pdf`

### Hugging Face
- `https://huggingface.co/papers/2508.20453`

## Error Handling

The module handles various error scenarios:

- **Network Timeouts**: Configurable timeout with retry logic
- **Invalid URLs**: Graceful handling of malformed URLs
- **Missing Content**: Fallback patterns for different page structures
- **Rate Limiting**: User agent headers to avoid blocking

## Dependencies

- `requests`: For HTTP requests
- `re`: For regex pattern matching
- `urllib.parse`: For URL parsing

## Configuration

- **Timeout**: Default 10 seconds, configurable per request
- **User Agent**: Set to avoid being blocked by websites
- **Retry Logic**: Built-in error handling for network issues

## Examples

See `integration_example.py` for complete integration examples with the existing summary service.
