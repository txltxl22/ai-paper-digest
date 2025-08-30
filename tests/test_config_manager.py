"""
Test cases for the configuration management system.
Tests config loading, validation, and access functionality.
"""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from config_manager import (
    ConfigManager,
    LLMConfig,
    AppConfig,
    PaperProcessingConfig,
    PathsConfig,
    get_llm_config,
    get_app_config,
    get_paper_processing_config,
    get_paths_config,
    reload_config,
    save_config
)


class TestConfigManager:
    """Test the ConfigManager class functionality."""
    
    def test_init_with_default_config_file(self):
        """Test ConfigManager initialization with default config file."""
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            
            # Check that config is loaded
            assert manager._config is not None
            assert "llm" in manager._config
            assert "app" in manager._config
    
    def test_init_with_custom_config_file(self):
        """Test ConfigManager initialization with custom config file."""
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager("custom_config.json")
            
            # Check that config is loaded
            assert manager._config is not None
            assert "llm" in manager._config
            assert "app" in manager._config
    
    def test_load_config_from_file(self):
        """Test loading configuration from existing file."""
        test_config = {
            "llm": {
                "provider": "openai",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "max_tokens": 4000,
                "temperature": 0.1
            },
            "app": {
                "host": "localhost",
                "port": 8080,
                "debug": True,
                "admin_user_ids": ["admin1", "admin2"]
            },
            "paper_processing": {
                "max_workers": 2,
                "chunk_size": 1000,
                "max_tags": 5,
                "daily_submission_limit": 2
            },
            "paths": {
                "summary_dir": "test_summary",
                "user_data_dir": "test_user_data",
                "papers_dir": "test_papers",
                "markdown_dir": "test_markdown"
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
            with patch('config_manager.Path') as mock_path:
                mock_path.return_value.exists.return_value = True
                with patch.dict(os.environ, {}, clear=True):  # Clear environment variables
                    manager = ConfigManager()
                    
                    # Check that the loaded config matches (environment variables may override)
                    assert manager._config["llm"]["provider"] == test_config["llm"]["provider"]
                    assert manager._config["app"]["host"] == test_config["app"]["host"]
                    assert manager._config["paper_processing"]["max_workers"] == test_config["paper_processing"]["max_workers"]
    
    def test_load_config_with_missing_file(self):
        """Test loading configuration when file doesn't exist."""
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            
            # Should load default config
            assert manager._config is not None
            assert "llm" in manager._config
            assert "app" in manager._config
            assert "paper_processing" in manager._config
            assert "paths" in manager._config
    
    def test_override_with_env_variables(self):
        """Test that environment variables override config file values."""
        test_config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "max_tokens": 4000,
                "temperature": 0.1
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
                "daily_submission_limit": 3
            },
            "paths": {
                "summary_dir": "summary",
                "user_data_dir": "user_data",
                "papers_dir": "papers",
                "markdown_dir": "markdown"
            }
        }
        
        env_vars = {
            "LLM_PROVIDER": "openai",
            "DEEPSEEK_API_KEY": "env-api-key",
            "OPENAI_API_BASE": "https://api.openai.com/v1",
            "LLM_MODEL": "gpt-4",
            "APP_HOST": "localhost",
            "APP_PORT": "8080",
            "APP_DEBUG": "true",
            "ADMIN_USER_IDS": "admin1,admin2,admin3",
            "MAX_WORKERS": "2",
            "CHUNK_SIZE": "1000",
            "MAX_TAGS": "5",
            "DAILY_SUBMISSION_LIMIT": "2"
        }
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            with patch.dict(os.environ, env_vars, clear=True):
                manager = ConfigManager()
                
                # Check that environment variables override config
                assert manager._config["llm"]["provider"] == "openai"
                assert manager._config["llm"]["api_key"] == "env-api-key"
                assert manager._config["llm"]["base_url"] == "https://api.openai.com/v1"
                assert manager._config["llm"]["model"] == "gpt-4"
                assert manager._config["app"]["host"] == "localhost"
                assert manager._config["app"]["port"] == 8080
                assert manager._config["app"]["debug"] is True
                assert manager._config["app"]["admin_user_ids"] == ["admin1", "admin2", "admin3"]
                assert manager._config["paper_processing"]["max_workers"] == 2
                assert manager._config["paper_processing"]["chunk_size"] == 1000
                assert manager._config["paper_processing"]["max_tags"] == 5
                assert manager._config["paper_processing"]["daily_submission_limit"] == 2
    
    def test_get_llm_config(self):
        """Test getting LLM configuration."""
        test_config = {
            "llm": {
                "provider": "openai",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "max_tokens": 4000,
                "temperature": 0.1
            }
        }
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            llm_config = manager.get_llm_config()
            
            assert isinstance(llm_config, LLMConfig)
            assert llm_config.provider == "openai"
            assert llm_config.api_key == "test-key"
            assert llm_config.base_url == "https://api.openai.com/v1"
            assert llm_config.model == "gpt-4"
            assert llm_config.max_tokens == 4000
            assert llm_config.temperature == 0.1
    
    def test_get_app_config(self):
        """Test getting application configuration."""
        test_config = {
            "app": {
                "host": "localhost",
                "port": 8080,
                "debug": True,
                "admin_user_ids": ["admin1", "admin2"]
            }
        }
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            app_config = manager.get_app_config()
            
            assert isinstance(app_config, AppConfig)
            assert app_config.host == "localhost"
            assert app_config.port == 8080
            assert app_config.debug is True
            assert app_config.admin_user_ids == ["admin1", "admin2"]
    
    def test_get_paper_processing_config(self):
        """Test getting paper processing configuration."""
        test_config = {
            "paper_processing": {
                "max_workers": 2,
                "chunk_size": 1000,
                "max_tags": 5,
                "daily_submission_limit": 2
            }
        }
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            pp_config = manager.get_paper_processing_config()
            
            assert isinstance(pp_config, PaperProcessingConfig)
            assert pp_config.max_workers == 2
            assert pp_config.chunk_size == 1000
            assert pp_config.max_tags == 5
            assert pp_config.daily_submission_limit == 2
    
    def test_get_paths_config(self):
        """Test getting paths configuration."""
        test_config = {
            "paths": {
                "summary_dir": "test_summary",
                "user_data_dir": "test_user_data",
                "papers_dir": "test_papers",
                "markdown_dir": "test_markdown"
            }
        }
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            paths_config = manager.get_paths_config()
            
            assert isinstance(paths_config, PathsConfig)
            assert paths_config.summary_dir == "test_summary"
            assert paths_config.user_data_dir == "test_user_data"
            assert paths_config.papers_dir == "test_papers"
            assert paths_config.markdown_dir == "test_markdown"
    
    def test_get_config(self):
        """Test getting raw configuration dictionary."""
        test_config = {"test": "value"}
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            config = manager.get_config()
            
            assert config == test_config
            assert config is not manager._config  # Should be a copy
    
    def test_save_config(self):
        """Test saving configuration to file."""
        test_config = {"test": "value"}
        
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            manager._config = test_config
            
            with patch('builtins.open', mock_open()) as mock_file:
                manager.save_config()
                
                mock_file.assert_called_once()
                # Check that json.dump was called with the config
                mock_file().write.assert_called()
    
    def test_reload_config(self):
        """Test reloading configuration."""
        with patch('config_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            manager = ConfigManager()
            
            original_config = manager._config.copy()
            
            # Modify config
            manager._config["test"] = "modified"
            
            # Reload should restore original
            manager.reload()
            
            assert "test" not in manager._config
            assert manager._config == original_config


class TestConfigDataClasses:
    """Test the configuration data classes."""
    
    def test_llm_config(self):
        """Test LLMConfig data class."""
        config = LLMConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            max_tokens=4000,
            temperature=0.1
        )
        
        assert config.provider == "deepseek"
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.deepseek.com/v1"
        assert config.model == "deepseek-chat"
        assert config.max_tokens == 4000
        assert config.temperature == 0.1
    
    def test_app_config(self):
        """Test AppConfig data class."""
        config = AppConfig(
            host="localhost",
            port=8080,
            debug=True,
            admin_user_ids=["admin1", "admin2"]
        )
        
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.debug is True
        assert config.admin_user_ids == ["admin1", "admin2"]
    
    def test_paper_processing_config(self):
        """Test PaperProcessingConfig data class."""
        config = PaperProcessingConfig(
            max_workers=2,
            chunk_size=1000,
            max_tags=5,
            daily_submission_limit=2
        )
        
        assert config.max_workers == 2
        assert config.chunk_size == 1000
        assert config.max_tags == 5
        assert config.daily_submission_limit == 2
    
    def test_paths_config(self):
        """Test PathsConfig data class."""
        config = PathsConfig(
            summary_dir="summary",
            user_data_dir="user_data",
            papers_dir="papers",
            markdown_dir="markdown"
        )
        
        assert config.summary_dir == "summary"
        assert config.user_data_dir == "user_data"
        assert config.papers_dir == "papers"
        assert config.markdown_dir == "markdown"


class TestGlobalFunctions:
    """Test the global configuration functions."""
    
    def test_get_llm_config_global(self):
        """Test global get_llm_config function."""
        config = get_llm_config()
        
        assert isinstance(config, LLMConfig)
        assert hasattr(config, 'provider')
        assert hasattr(config, 'api_key')
        assert hasattr(config, 'base_url')
        assert hasattr(config, 'model')
        assert hasattr(config, 'max_tokens')
        assert hasattr(config, 'temperature')
    
    def test_get_app_config_global(self):
        """Test global get_app_config function."""
        config = get_app_config()
        
        assert isinstance(config, AppConfig)
        assert hasattr(config, 'host')
        assert hasattr(config, 'port')
        assert hasattr(config, 'debug')
        assert hasattr(config, 'admin_user_ids')
    
    def test_get_paper_processing_config_global(self):
        """Test global get_paper_processing_config function."""
        config = get_paper_processing_config()
        
        assert isinstance(config, PaperProcessingConfig)
        assert hasattr(config, 'max_workers')
        assert hasattr(config, 'chunk_size')
        assert hasattr(config, 'max_tags')
        assert hasattr(config, 'daily_submission_limit')
    
    def test_get_paths_config_global(self):
        """Test global get_paths_config function."""
        config = get_paths_config()
        
        assert isinstance(config, PathsConfig)
        assert hasattr(config, 'summary_dir')
        assert hasattr(config, 'user_data_dir')
        assert hasattr(config, 'papers_dir')
        assert hasattr(config, 'markdown_dir')
    
    def test_reload_config_global(self):
        """Test global reload_config function."""
        # Should not raise any exceptions
        reload_config()
    
    def test_save_config_global(self):
        """Test global save_config function."""
        # Should not raise any exceptions
        save_config()


class TestConfigIntegration:
    """Test configuration integration with the application."""
    
    def test_config_with_real_file(self, tmp_path):
        """Test configuration with a real temporary file."""
        config_file = tmp_path / "test_config.json"
        test_config = {
            "llm": {
                "provider": "test-provider",
                "api_key": "test-key",
                "base_url": "https://test.api.com/v1",
                "model": "test-model",
                "max_tokens": 1000,
                "temperature": 0.5
            },
            "app": {
                "host": "test-host",
                "port": 9999,
                "debug": True,
                "admin_user_ids": ["test-admin"]
            },
            "paper_processing": {
                "max_workers": 1,
                "chunk_size": 500,
                "max_tags": 3,
                "daily_submission_limit": 1
            },
            "paths": {
                "summary_dir": "test_summary",
                "user_data_dir": "test_user_data",
                "papers_dir": "test_papers",
                "markdown_dir": "test_markdown"
            }
        }
        
        # Write test config to file
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f)
        
        # Test ConfigManager with real file and cleared environment
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager(str(config_file))
            
            # Verify config was loaded correctly
            llm_config = manager.get_llm_config()
            assert llm_config.provider == "test-provider"
            assert llm_config.api_key == "test-key"
            
            app_config = manager.get_app_config()
            assert app_config.host == "test-host"
            assert app_config.port == 9999
            
            pp_config = manager.get_paper_processing_config()
            assert pp_config.max_workers == 1
            assert pp_config.daily_submission_limit == 1
    
    def test_config_environment_override(self, tmp_path):
        """Test that environment variables properly override config file."""
        config_file = tmp_path / "test_config.json"
        test_config = {
            "llm": {
                "provider": "file-provider",
                "api_key": "file-key",
                "base_url": "https://file.api.com/v1",
                "model": "file-model",
                "max_tokens": 1000,
                "temperature": 0.5
            },
            "app": {
                "host": "file-host",
                "port": 9999,
                "debug": False,
                "admin_user_ids": []
            },
            "paper_processing": {
                "max_workers": 1,
                "chunk_size": 500,
                "max_tags": 3,
                "daily_submission_limit": 1
            },
            "paths": {
                "summary_dir": "summary",
                "user_data_dir": "user_data",
                "papers_dir": "papers",
                "markdown_dir": "markdown"
            }
        }
        
        # Write test config to file
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f)
        
        # Set environment variables
        env_vars = {
            "LLM_PROVIDER": "env-provider",
            "DEEPSEEK_API_KEY": "env-key",
            "OPENAI_API_BASE": "https://env.api.com/v1",
            "LLM_MODEL": "env-model",
            "APP_HOST": "env-host",
            "APP_PORT": "8888",
            "APP_DEBUG": "true",
            "ADMIN_USER_IDS": "env-admin1,env-admin2",
            "MAX_WORKERS": "2",
            "CHUNK_SIZE": "1000",
            "MAX_TAGS": "5",
            "DAILY_SUBMISSION_LIMIT": "2"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = ConfigManager(str(config_file))
            
            # Environment variables should override file values
            llm_config = manager.get_llm_config()
            assert llm_config.provider == "env-provider"
            assert llm_config.api_key == "env-key"
            assert llm_config.base_url == "https://env.api.com/v1"
            assert llm_config.model == "env-model"
            
            app_config = manager.get_app_config()
            assert app_config.host == "env-host"
            assert app_config.port == 8888
            assert app_config.debug is True
            assert app_config.admin_user_ids == ["env-admin1", "env-admin2"]
            
            pp_config = manager.get_paper_processing_config()
            assert pp_config.max_workers == 2
            assert pp_config.chunk_size == 1000
            assert pp_config.max_tags == 5
            assert pp_config.daily_submission_limit == 2


class TestConfigErrorHandling:
    """Test error handling in configuration system."""
    
    def test_invalid_json_file(self, tmp_path):
        """Test handling of invalid JSON in config file."""
        config_file = tmp_path / "invalid_config.json"
        
        # Write invalid JSON
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json}')
        
        # Should fall back to default config
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager(str(config_file))
            
            # Should have default config loaded
            assert manager._config is not None
            assert "llm" in manager._config
            assert "app" in manager._config
    
    def test_missing_config_sections(self, tmp_path):
        """Test handling of config file with missing sections."""
        config_file = tmp_path / "partial_config.json"
        partial_config = {
            "llm": {
                "provider": "test-provider"
            }
            # Missing other sections
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(partial_config, f)
        
        # Should merge with defaults
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager(str(config_file))
            
            # Should have all sections
            assert "llm" in manager._config
            assert "app" in manager._config
            assert "paper_processing" in manager._config
            assert "paths" in manager._config
            
            # Should have default values for missing sections
            assert manager._config["app"]["port"] == 22581
            assert manager._config["paper_processing"]["max_workers"] == 4
