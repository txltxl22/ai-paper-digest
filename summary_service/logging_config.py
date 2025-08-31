"""
Logging Configuration Module

This module provides thread-safe logging configuration for the summary service,
including setup for queue-based logging and silencing of noisy third-party libraries.
"""

import logging
import logging.handlers
import sys
from queue import Queue
from typing import Optional


class ThreadSafeLoggingConfig:
    """Thread-safe logging configuration with queue-based logging."""
    
    def __init__(self):
        self._log_listener: Optional[logging.handlers.QueueListener] = None
        self._log_queue: Optional[Queue] = None
    
    def setup_logging(self, debug: bool = False) -> None:
        """
        Configure thread-safe logging for the service and silence chatty libraries.
        
        This uses a QueueHandler + QueueListener pattern to prevent log line mixing
        when multiple threads log simultaneously. All worker threads write to a queue,
        and the main thread processes the queue sequentially, ensuring clean output.
        
        Args:
            debug: Whether to enable debug logging
        """
        # Create a queue for thread-safe logging
        self._log_queue = Queue()
        
        # Create a queue handler that workers will use
        queue_handler = logging.handlers.QueueHandler(self._log_queue)
        
        # Create a console handler for the main thread
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s")
        )
        
        # Create a queue listener that runs in the main thread
        self._log_listener = logging.handlers.QueueListener(
            self._log_queue, console_handler, respect_handler_level=True
        )
        
        # Start the listener
        self._log_listener.start()
        
        # Configure the root logger to use the queue handler
        root_logger = logging.getLogger()
        root_logger.handlers.clear()  # Remove any existing handlers
        root_logger.addHandler(queue_handler)
        root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Silence noisy libraries if not in debug mode
        if not debug:
            self._silence_noisy_libraries()
    
    def _silence_noisy_libraries(self) -> None:
        """Silence noisy third-party libraries."""
        # Add HTTP filter to remove HTTP request/response logs
        class _MuteHttpXFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
                name = record.name or ""
                if name.startswith("httpx") or name.startswith("httpcore"):
                    return False
                msg = record.getMessage()
                if isinstance(msg, str) and (
                    msg.startswith("HTTP Request:") or msg.startswith("HTTP Response:")
                ):
                    return False
                return True

        for handler in logging.getLogger().handlers:
            handler.addFilter(_MuteHttpXFilter())

        # Configure noisy loggers
        noisy_loggers = [
            "httpx",
            "httpcore",
            "urllib3",
            "openai",
            "langchain_core",
            "langchain_community",
            "langchain_deepseek",
            "langchain_ollama",
            "tenacity",
            "asyncio",
        ]
        
        for name in noisy_loggers:
            logger = logging.getLogger(name)
            # Be strict with network stacks
            if name in ("httpx", "httpcore"):
                logger.setLevel(logging.CRITICAL)
                logger.disabled = True
            else:
                logger.setLevel(logging.WARNING)
            logger.handlers.clear()
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
    
    def stop(self) -> None:
        """Stop the logging listener and cleanup."""
        if self._log_listener:
            self._log_listener.stop()
            self._log_listener = None
        if self._log_queue:
            self._log_queue = None


# Global logging configuration instance
logging_config = ThreadSafeLoggingConfig()


def setup_logging(debug: bool = False) -> None:
    """
    Setup thread-safe logging configuration.
    
    Args:
        debug: Whether to enable debug logging
    """
    logging_config.setup_logging(debug)


def stop_logging() -> None:
    """Stop the logging listener and cleanup."""
    logging_config.stop()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
