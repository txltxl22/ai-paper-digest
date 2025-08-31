"""
Configuration management for the AI Paper Digest System.
Handles loading, validating, and providing access to application settings.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM configuration settings."""
    provider: str
    api_key: str
    base_url: str
    model: str
    max_tokens: int
    temperature: float
    max_input_char: int


@dataclass
class AppConfig:
    """Application configuration settings."""
    host: str
    port: int
    debug: bool
    admin_user_ids: list[str]


@dataclass
class PaperProcessingConfig:
    """Paper processing configuration settings."""
    max_workers: int
    chunk_size: int
    max_tags: int
    daily_submission_limit: int
    max_pdf_size_mb: int


@dataclass
class PathsConfig:
    """Path configuration settings."""
    summary_dir: str
    user_data_dir: str
    papers_dir: str
    markdown_dir: str


class ConfigManager:
    """Manages application configuration loading and access."""
    
    def __init__(self, config_file: str = "web_app_config.json"):
        self.config_file = Path(config_file)
        self._config: Optional[Dict[str, Any]] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file and environment variables."""
        # Start with default config
        self._config = self._get_default_config()
        
        # Load base config from file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Merge file config with defaults
                    self._merge_config(file_config)
            except (json.JSONDecodeError, FileNotFoundError):
                # Keep default config if file is invalid or not found
                pass
        
        # Override with environment variables
        self._override_with_env()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "llm": {
                "provider": "deepseek",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "max_tokens": 4000,
                "temperature": 0.1,
                "max_input_char": 100000
            },
            "app": {
                "host": "0.0.0.0",
                "port": 22581,
                "debug": False,
                "admin_user_ids": []
            },
            "paper_processing": {
                "max_workers": 4,
                "chunk_size": 2000,
                "max_tags": 8,
                "daily_submission_limit": 3,
                "max_pdf_size_mb": 20
            },
            "paths": {
                "summary_dir": "summary",
                "user_data_dir": "user_data",
                "papers_dir": "papers",
                "markdown_dir": "markdown"
            }
        }
    
    def _merge_config(self, file_config: Dict[str, Any]) -> None:
        """Merge file configuration with current config."""
        for section, values in file_config.items():
            if section in self._config:
                if isinstance(values, dict):
                    self._config[section].update(values)
                else:
                    self._config[section] = values
            else:
                self._config[section] = values
    
    def _override_with_env(self) -> None:
        """Override configuration with environment variables."""
        # LLM settings
        if os.getenv("LLM_PROVIDER"):
            self._config["llm"]["provider"] = os.getenv("LLM_PROVIDER")
        
        if os.getenv("DEEPSEEK_API_KEY"):
            self._config["llm"]["api_key"] = os.getenv("DEEPSEEK_API_KEY")
        
        if os.getenv("OPENAI_API_BASE"):
            self._config["llm"]["base_url"] = os.getenv("OPENAI_API_BASE")
        
        if os.getenv("LLM_MODEL"):
            self._config["llm"]["model"] = os.getenv("LLM_MODEL")
        
        if os.getenv("LLM_MAX_INPUT_CHAR"):
            self._config["llm"]["max_input_char"] = int(os.getenv("LLM_MAX_INPUT_CHAR"))
        
        # App settings
        if os.getenv("APP_HOST"):
            self._config["app"]["host"] = os.getenv("APP_HOST")
        
        if os.getenv("APP_PORT"):
            self._config["app"]["port"] = int(os.getenv("APP_PORT"))
        
        if os.getenv("APP_DEBUG"):
            self._config["app"]["debug"] = os.getenv("APP_DEBUG").lower() == "true"
        
        if os.getenv("ADMIN_USER_IDS"):
            self._config["app"]["admin_user_ids"] = [
                uid.strip() for uid in os.getenv("ADMIN_USER_IDS").split(",") if uid.strip()
            ]
        
        # Paper processing settings
        if os.getenv("MAX_WORKERS"):
            self._config["paper_processing"]["max_workers"] = int(os.getenv("MAX_WORKERS"))
        
        if os.getenv("CHUNK_SIZE"):
            self._config["paper_processing"]["chunk_size"] = int(os.getenv("CHUNK_SIZE"))
        
        if os.getenv("MAX_TAGS"):
            self._config["paper_processing"]["max_tags"] = int(os.getenv("MAX_TAGS"))
        
        if os.getenv("DAILY_SUBMISSION_LIMIT"):
            self._config["paper_processing"]["daily_submission_limit"] = int(os.getenv("DAILY_SUBMISSION_LIMIT"))
        
        if os.getenv("MAX_PDF_SIZE_MB"):
            self._config["paper_processing"]["max_pdf_size_mb"] = int(os.getenv("MAX_PDF_SIZE_MB"))
    
    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration."""
        llm_config = self._config["llm"]
        return LLMConfig(
            provider=llm_config["provider"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            model=llm_config["model"],
            max_tokens=llm_config["max_tokens"],
            temperature=llm_config["temperature"],
            max_input_char=llm_config["max_input_char"]
        )
    
    def get_app_config(self) -> AppConfig:
        """Get application configuration."""
        app_config = self._config["app"]
        return AppConfig(
            host=app_config["host"],
            port=app_config["port"],
            debug=app_config["debug"],
            admin_user_ids=app_config["admin_user_ids"]
        )
    
    def get_paper_processing_config(self) -> PaperProcessingConfig:
        """Get paper processing configuration."""
        pp_config = self._config["paper_processing"]
        return PaperProcessingConfig(
            max_workers=pp_config["max_workers"],
            chunk_size=pp_config["chunk_size"],
            max_tags=pp_config["max_tags"],
            daily_submission_limit=pp_config["daily_submission_limit"],
            max_pdf_size_mb=pp_config["max_pdf_size_mb"]
        )
    
    def get_paths_config(self) -> PathsConfig:
        """Get paths configuration."""
        paths_config = self._config["paths"]
        return PathsConfig(
            summary_dir=paths_config["summary_dir"],
            user_data_dir=paths_config["user_data_dir"],
            papers_dir=paths_config["papers_dir"],
            markdown_dir=paths_config["markdown_dir"]
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config.copy()
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)


# Global configuration instance
config_manager = ConfigManager()


def get_llm_config() -> LLMConfig:
    """Get LLM configuration."""
    return config_manager.get_llm_config()


def get_app_config() -> AppConfig:
    """Get application configuration."""
    return config_manager.get_app_config()


def get_paper_processing_config() -> PaperProcessingConfig:
    """Get paper processing configuration."""
    return config_manager.get_paper_processing_config()


def get_paths_config() -> PathsConfig:
    """Get paths configuration."""
    return config_manager.get_paths_config()


def reload_config() -> None:
    """Reload configuration."""
    config_manager.reload()


def save_config() -> None:
    """Save configuration to file."""
    config_manager.save_config()


def get_provider_defaults(provider: str) -> tuple[str, str]:
    """
    Get default base URL and model for the specified provider.
    
    Args:
        provider: The LLM provider name
        
    Returns:
        Tuple of (base_url, model) defaults for the provider
    """
    defaults = {
        "deepseek": (None, None),  # using langchain_deepseek
        "openai": ("https://api.openai.com/v1", "gpt-3.5-turbo"),
        "ollama": ("http://localhost:11434", "qwen3:8b"),
    }
    return defaults.get(provider.lower(), defaults["deepseek"])


def get_provider_config(provider: str, base_url: str = None, model: str = None, api_key: str = None) -> dict:
    """
    Get provider-specific configuration based on provider choice.
    
    Args:
        provider: The LLM provider name
        base_url: Optional base URL override
        model: Optional model override
        api_key: Optional API key
        
    Returns:
        Dictionary with provider configuration
    """
    default_base_url, default_model = get_provider_defaults(provider)
    
    # Use provided values or defaults
    final_base_url = base_url if base_url else default_base_url
    final_model = model if model else default_model
    
    config = {
        "provider": provider,
        "base_url": final_base_url,
        "model": final_model,
        "api_key": api_key,
    }
    
    return config

