import json
import os
import re
from pathlib import Path
from typing import Tuple, List

from .ai_cache import AICacheManager
from .utils import create_content_hash


class AIContentChecker:
    """Checks if paper content is AI-related using LLM with caching."""
    
    def __init__(self, ai_cache_manager: AICacheManager, llm_config, prompts_dir: Path):
        self.ai_cache_manager = ai_cache_manager
        self.llm_config = llm_config
        self.prompts_dir = prompts_dir
    
    def check_paper_ai_relevance(self, text_content: str, url: str = None) -> Tuple[bool, float, List[str]]:
        """Check if paper content is AI-related using LLM with caching."""
        
        # Create cache key from URL or content hash
        if url:
            cache_key = url
        else:
            # Use content hash as cache key if no URL
            cache_key = create_content_hash(text_content)
        
        # Check cache first
        cached_result = self.ai_cache_manager.get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Import paper_summarizer module
            import paper_summarizer as ps
            
            # Get the first 1000 tokens (approximate)
            first_1000 = text_content[:1000]
            
            # Read prompt from the prompts/ai_check.md file
            from langchain_core.prompts import PromptTemplate
            
            prompt_template = PromptTemplate.from_file(
                self.prompts_dir / "ai_check.md", 
                encoding="utf-8"
            )
            
            prompt_content = prompt_template.format(first_1000=first_1000)

            # Use the same LLM client as in paper_summarizer
            from langchain_core.messages import HumanMessage
            
            # Get LLM configuration
            api_key = self.llm_config.api_key
            base_url = self.llm_config.base_url
            provider = self.llm_config.provider
            model = self.llm_config.model
            
            # Use the same LLM invocation method
            response = ps.llm_invoke(
                [HumanMessage(content=prompt_content)],
                api_key=api_key,
                base_url=base_url,
                provider=provider,
                model=model
            )
            
            # Parse response
            response_text = response.content.strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            # Parse JSON
            print(f"Response text: {response_text}")
            result = json.loads(response_text)
            is_ai = result.get('is_ai', False)
            confidence = result.get('confidence', 0.0)
            tags = result.get('tags', [])
            
            # Cache the result
            self.ai_cache_manager.cache_result(cache_key, is_ai, confidence, tags)
            
            return is_ai, confidence, tags
            
        except Exception as e:
            print(f"Error checking AI relevance: {e}")
            # Default to True if there's an error, to be safe
            return True, 0.5, []
