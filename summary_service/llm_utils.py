"""
llm_utils.py - LLM utilities and provider management

This module provides LLM invocation functionality with support for
DeepSeek, Ollama, and OpenAI-compatible providers.
"""

import logging
import os
import re
from typing import List, Optional

from langchain_deepseek.chat_models import DEFAULT_API_BASE as DEEPSEEK_DEFAULT_API_BASE
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI

_LOG = logging.getLogger("llm_utils")

# Default configuration
DEFAULT_LLM_PROVIDER = "deepseek"  # "deepseek", "ollama", or "openai"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
MODEL_NAME = "deepseek-chat"


class LLMProvider:
    """LLM provider configuration and management."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: str = DEFAULT_LLM_PROVIDER,
        model: str = None,
        timeout: int = 120,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.provider = provider.lower()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        # Set defaults based on provider
        self._configure_provider()

    def _configure_provider(self):
        """Configure provider-specific settings."""
        if self.provider == "ollama":
            if not self.base_url:
                self.base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
            if not self.model:
                self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        elif self.provider == "openai":
            if not self.api_key:
                self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.base_url:
                self.base_url = os.getenv(
                    "OPENAI_API_BASE", "https://api.openai.com/v1"
                )
            if not self.model:
                self.model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        else:  # deepseek
            if not self.api_key:
                self.api_key = os.getenv("DEEPSEEK_API_KEY")
            if not self.model:
                self.model = MODEL_NAME

    def get_llm(self):
        """Get the configured LLM instance."""
        if self.provider == "ollama":
            _LOG.debug("Using Ollama provider: %s at %s", self.model, self.base_url)
            return OllamaLLM(
                model=self.model,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        elif self.provider == "openai":
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable or pass api_key"
                )
            _LOG.debug(
                "Using OpenAI-compatible provider: %s at %s", self.model, self.base_url
            )
            return ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                max_tokens=None,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        else:  # deepseek
            if not self.api_key:
                raise ValueError(
                    "DeepSeek API key required. Set DEEPSEEK_API_KEY environment variable or pass api_key"
                )
            _LOG.debug("Using DeepSeek provider: %s", self.model)
            return ChatDeepSeek(
                model=self.model,
                max_tokens=None,
                timeout=None,
                max_retries=self.max_retries,
                api_key=self.api_key,
                api_base=self.base_url if self.base_url else DEEPSEEK_DEFAULT_API_BASE,
            )

    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Invoke LLM with the configured provider."""
        llm = self.get_llm()

        if self.provider == "ollama":
            # Convert messages to text for Ollama (simpler interface)
            if len(messages) == 1:
                prompt = messages[0].content
            else:
                # Handle conversation format
                prompt = "\n\n".join(
                    [
                        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
                        for m in messages
                    ]
                )

            response = llm.invoke(prompt)

            # Clean up Ollama response to extract only the actual output
            # Ollama may include <think> tags mixed with output, unlike DeepSeek Chat
            cleaned_content = response
            if isinstance(cleaned_content, str):
                # Remove <think>...</think> blocks
                cleaned_content = re.sub(
                    r"<think>.*?</think>", "", cleaned_content, flags=re.DOTALL
                )

            return AIMessage(content=cleaned_content)
        else:
            return llm.invoke(messages)


def llm_invoke(
    messages: List[BaseMessage],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    model: str = None,
    **kwargs,
) -> AIMessage:
    """Invoke LLM with support for DeepSeek, Ollama, and OpenAI-compatible providers."""
    llm_provider = LLMProvider(
        api_key=api_key, base_url=base_url, provider=provider, model=model, **kwargs
    )
    return llm_provider.invoke(messages)


def clean_ollama_response(content: str) -> str:
    """Clean Ollama response by removing <think> tags."""
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)


def extract_json_from_response(content: str, provider: str = "deepseek") -> str:
    """Extract JSON content from LLM response, handling different provider formats."""
    raw = content.strip()

    # Clean up any <think> tags that might appear in Ollama output
    if provider.lower() == "ollama":
        raw = clean_ollama_response(raw)

    # Strip fenced code blocks if present, e.g., ```json ... ``` or ``` ... ```
    fenced_match = re.search(r"```(?:json|\w+)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fenced_match:
        raw = fenced_match.group(1).strip()

    return raw
