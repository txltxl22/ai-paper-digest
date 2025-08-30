"""
Fetch subsystem services for admin fetch operations.
"""
import subprocess
import shutil
import string
from pathlib import Path
from typing import Dict, List, Optional, Any, Generator
from .models import FetchCommand, FetchResult, StreamEvent


class FetchService:
    """Service for executing fetch operations."""
    
    def __init__(self, working_directory: Path):
        self.working_directory = working_directory
    
    def build_fetch_command(self, feed_url: str = "https://papers.takara.ai/api/feed") -> FetchCommand:
        """Build the command for fetching latest summaries."""
        # Check if uv is available, fallback to python if not
        uv_path = shutil.which("uv")
        python_path = shutil.which("python")
        
        if not python_path:
            python_path = shutil.which("python3")
        
        if not python_path:
            raise RuntimeError("Python not found in PATH")
        
        # Build command - prefer uv if available
        if uv_path:
            cmd = ["uv", "run", "python", "feed_paper_summarizer_service.py", feed_url]
        else:
            cmd = [python_path, "feed_paper_summarizer_service.py", feed_url]
        
        return FetchCommand(
            command=cmd,
            working_directory=str(self.working_directory),
            feed_url=feed_url
        )
    
    def execute_fetch(self, feed_url: str = "https://papers.takara.ai/api/feed") -> FetchResult:
        """Execute fetch operation synchronously."""
        fetch_cmd = self.build_fetch_command(feed_url)
        
        try:
            result = subprocess.run(
                fetch_cmd.command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=self.working_directory,
                timeout=fetch_cmd.timeout
            )
            
            # Extract summary statistics
            summary_stats = self._extract_summary_stats(result.stdout)
            
            return FetchResult(
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                summary_stats=summary_stats
            )
            
        except subprocess.TimeoutExpired:
            return FetchResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                summary_stats={},
                error_message="Feed service timed out after 5 minutes"
            )
        except Exception as exc:
            return FetchResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                summary_stats={},
                error_message=f"Failed to run feed service: {str(exc)}"
            )
    
    def execute_fetch_stream(self, feed_url: str = "https://papers.takara.ai/api/feed") -> Generator[StreamEvent, None, None]:
        """Execute fetch operation with streaming output."""
        fetch_cmd = self.build_fetch_command(feed_url)
        
        try:
            # Send initial status
            yield StreamEvent(
                event_type="status",
                message="正在启动服务...",
                icon="⏳"
            )
            
            yield StreamEvent(
                event_type="log",
                message=f"执行命令: {' '.join(fetch_cmd.command)}",
                level="info"
            )
            
            # Use Popen to get real-time output
            process = subprocess.Popen(
                fetch_cmd.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stdout and stderr
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                cwd=self.working_directory
            )
            
            # Send status update
            yield StreamEvent(
                event_type="status",
                message="正在连接RSS源...",
                icon="🔗"
            )
            
            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Clean and sanitize output
                    clean_output = output.rstrip()  # Remove trailing newline only
                    if clean_output:
                        # Remove all control characters that break JSON
                        clean_output = ''.join(char for char in clean_output if char in string.printable)
                        
                        # Escape only the essential characters for JSON
                        clean_output = clean_output.replace('\\', '\\\\').replace('"', '\\"')
                        
                        # Limit line length to prevent overwhelming the frontend
                        if len(clean_output) > 500:
                            clean_output = clean_output[:500] + "... [truncated]"
                        
                        yield StreamEvent(
                            event_type="log",
                            message=clean_output,
                            level="info"
                        )
            
            # Wait for process to complete and get return code
            return_code = process.poll()
            
            # Send completion status
            if return_code == 0:
                yield StreamEvent(
                    event_type="status",
                    message="获取成功！",
                    icon="✅"
                )
                yield StreamEvent(
                    event_type="complete",
                    message="最新论文摘要获取成功！",
                    status="success"
                )
            else:
                yield StreamEvent(
                    event_type="log",
                    message=f"进程返回码: {return_code}",
                    level="error"
                )
                yield StreamEvent(
                    event_type="status",
                    message="获取失败",
                    icon="❌"
                )
                yield StreamEvent(
                    event_type="complete",
                    message=f"Feed service failed with return code {return_code}",
                    status="error"
                )
                
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {str(e)}"
            yield StreamEvent(
                event_type="error",
                message=error_msg
            )
            yield StreamEvent(
                event_type="complete",
                message="文件路径错误",
                status="error"
            )
        except PermissionError as e:
            error_msg = f"权限错误: {str(e)}"
            yield StreamEvent(
                event_type="error",
                message=error_msg
            )
            yield StreamEvent(
                event_type="complete",
                message="权限不足",
                status="error"
            )
        except Exception as exc:
            error_msg = f"执行过程中发生错误: {str(exc)}"
            yield StreamEvent(
                event_type="error",
                message=error_msg
            )
            yield StreamEvent(
                event_type="complete",
                message="执行失败",
                status="error"
            )
    
    def _extract_summary_stats(self, stdout: str) -> Dict[str, str]:
        """Extract summary statistics from command output."""
        summary_stats = {}
        stdout_lines = stdout.strip().split('\n') if stdout else []
        
        for line in stdout_lines:
            if "Found" in line and "paper" in line.lower():
                summary_stats["papers_found"] = line.strip()
            elif "successfully" in line.lower():
                summary_stats["success_count"] = line.strip()
            elif "RSS feed updated" in line:
                summary_stats["rss_updated"] = line.strip()
            elif "All done" in line:
                summary_stats["completion"] = line.strip()
        
        return summary_stats
