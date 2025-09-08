// Paper Submission Module
class PaperSubmission {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('DOMContentLoaded', () => {
      this.loadQuotaInfo();
      this.initFormHandling();
    });
  }

  async loadQuotaInfo() {
    try {
      const response = await fetch('/quota');
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          this.updateQuotaDisplay(result.quota);
        }
      }
    } catch (error) {
      console.error('Failed to load quota info:', error);
    }
  }

  updateQuotaDisplay(quota) {
    const remainingElement = document.getElementById('remaining-uploads');
    const resetTimeElement = document.getElementById('reset-time');
    const dailyLimitElement = document.getElementById('daily-limit');
    
    if (remainingElement) {
      remainingElement.textContent = `${quota.remaining}/${quota.daily_limit}`;
      remainingElement.className = `quota-value ${quota.remaining === 0 ? 'quota-exhausted' : ''}`;
    }
    
    if (resetTimeElement) {
      resetTimeElement.textContent = quota.next_reset_formatted;
    }
    
    if (dailyLimitElement) {
      dailyLimitElement.textContent = quota.daily_limit;
    }
  }

  initFormHandling() {
    const paperForm = document.getElementById('paper-submission-form');
    const submissionStatus = document.getElementById('submission-status');
    const statusIcon = submissionStatus?.querySelector('.status-icon');
    const statusText = submissionStatus?.querySelector('.status-title');
    const progressFill = submissionStatus?.querySelector('.progress-fill');
    const progressText = submissionStatus?.querySelector('.progress-text');
    const currentStep = submissionStatus?.querySelector('#current-step');
    const fileSizeInfo = submissionStatus?.querySelector('#file-size-info');
    
    // Download progress elements
    const downloadProgressSection = document.getElementById('download-progress-section');
    const downloadProgressFill = downloadProgressSection?.querySelector('.download-progress-fill');
    const downloadProgressText = downloadProgressSection?.querySelector('.download-progress-text');
    const downloadSpeed = downloadProgressSection?.querySelector('#download-speed');
    const downloadSize = downloadProgressSection?.querySelector('#download-size');
    
    let progressInterval = null;
    
    if (paperForm) {
      paperForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const urlInput = document.getElementById('paper-url-input');
        const paperUrl = urlInput.value.trim();
        
        if (!paperUrl) {
          showToast('请输入论文URL');
          return;
        }
        
        // Show submission status
        if (submissionStatus) {
          submissionStatus.style.display = 'block';
          if (statusIcon) statusIcon.textContent = '⏳';
          if (statusText) statusText.textContent = '正在处理论文...';
          if (progressFill) progressFill.style.width = '0%';
          if (progressText) progressText.textContent = '0%';
          if (currentStep) currentStep.textContent = '论文下载中...';
          if (fileSizeInfo) fileSizeInfo.textContent = '';
          
          // Hide download progress section initially
          const downloadProgressSection = document.getElementById('download-progress-section');
          if (downloadProgressSection) {
            downloadProgressSection.style.display = 'none';
          }
        }
        
        // Disable form
        const submitBtn = paperForm.querySelector('.submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = '处理中...';
        
        let result = null;
        try {
          // Submit paper URL
          const response = await fetch('/submit_paper', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: paperUrl }),
          });
          
          const result = await response.json();
          
          // Store the result for later use in redirect
          this.lastSubmissionResult = result;
          
          // Start progress tracking if we have a task_id
          if (result.task_id) {
            this.startProgressTracking(result.task_id, statusIcon, statusText, progressFill, progressText, currentStep, fileSizeInfo);
          }
          
          if (response.ok && result.success) {
            // Success - progress tracking will handle the UI updates
            showToast('✅ 论文提交成功！正在处理中...');
            
            // Clear input
            urlInput.value = '';
            
            // Don't refresh page immediately - let progress tracking handle it
            
          } else {
            // Error - stop progress tracking
            this.stopProgressTracking();
            
            if (submissionStatus) {
              if (statusIcon) statusIcon.textContent = '❌';
              if (statusText) statusText.textContent = result.message || '处理失败';
              if (progressFill) progressFill.style.width = '0%';
              if (progressText) progressText.textContent = '0%';
              if (currentStep) currentStep.textContent = '处理失败';
            }
            
            showToast(`❌ ${result.message || '处理失败'}`);
            
            // Handle specific errors
            if (result.error === 'Login required') {
              // Focus on login form
              const loginInput = document.getElementById('user-form')?.querySelector('input[name=uid]');
              if (loginInput) {
                loginInput.focus();
              }
            }
          }
          
        } catch (error) {
          console.error('Paper submission error:', error);
          this.stopProgressTracking();
          
          if (submissionStatus) {
            if (statusIcon) statusIcon.textContent = '❌';
            if (statusText) statusText.textContent = '网络错误，请重试';
            if (progressFill) progressFill.style.width = '0%';
            if (progressText) progressText.textContent = '0%';
            if (currentStep) currentStep.textContent = '网络错误';
          }
          
          showToast('❌ 网络错误，请重试');
        } finally {
          // Re-enable form
          submitBtn.disabled = false;
          submitBtn.textContent = '提交论文';
          
          // Hide status after delay (if not tracking progress)
          if (!result?.task_id) {
            setTimeout(() => {
              submissionStatus.style.display = 'none';
            }, 10000);
          }
        }
      });
    }
  }

  startProgressTracking(taskId, statusIcon, statusText, progressFill, progressText, currentStep, fileSizeInfo) {
    
    // Get download progress elements
    const downloadProgressSection = document.getElementById('download-progress-section');
    const downloadProgressFill = downloadProgressSection?.querySelector('.download-progress-fill');
    const downloadProgressText = downloadProgressSection?.querySelector('.download-progress-text');
    const downloadSpeed = downloadProgressSection?.querySelector('#download-speed');
    const downloadSize = downloadProgressSection?.querySelector('#download-size');
    
    
    let isDownloading = false;
    let pollInterval = 200; // Start with fast polling
    
    const pollProgress = async () => {
      try {
        const response = await fetch(`/download_progress/${taskId}`);
        if (response.ok) {
          const data = await response.json();
          const progress = data.progress;
          
          // Update UI elements
          if (progressFill) {
            progressFill.style.width = `${progress.progress}%`;
          }
          if (progressText) {
            progressText.textContent = `${progress.progress}%`;
          }
          if (currentStep) {
            currentStep.textContent = progress.details;
          }
          
          // Handle download progress separately
          if (progress.step === 'downloading' && progress.details.includes('正在下载PDF')) {
            // Show download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'block';
            }
            
            // Extract download percentage from details
            const downloadMatch = progress.details.match(/(\d+)%/);
            if (downloadMatch && downloadProgressFill && downloadProgressText) {
              const downloadPercent = parseInt(downloadMatch[1]);
              downloadProgressFill.style.width = `${downloadPercent}%`;
              downloadProgressText.textContent = `${downloadPercent}%`;
            }
            
            // Extract file size info from details
            const sizeMatch = progress.details.match(/\(([\d.]+)MB \/ ([\d.]+)MB\)/);
            if (sizeMatch && downloadSize) {
              downloadSize.textContent = `${sizeMatch[1]} MB / ${sizeMatch[2]} MB`;
            }
            
            // Update download speed (simplified)
            if (downloadSpeed) {
              downloadSpeed.textContent = '下载中...';
            }
          } else if (progress.step !== 'downloading') {
            // Only hide download progress section for non-download steps
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
          }
          
          // Check if we're in download phase
          const wasDownloading = isDownloading;
          isDownloading = progress.step === 'downloading' && progress.details.includes('正在下载PDF');
          
          // Adjust polling interval based on phase
          if (isDownloading && !wasDownloading) {
            // Just entered download phase, slow down polling
            clearInterval(this.progressInterval);
            this.progressInterval = setInterval(pollProgress, 3000);
          } else if (!isDownloading && wasDownloading) {
            // Just left download phase, speed up polling
            clearInterval(this.progressInterval);
            this.progressInterval = setInterval(pollProgress, 200);
          }
          
          // Update status based on step
          if (progress.step === 'completed') {
            if (statusIcon) statusIcon.textContent = '✅';
            if (statusText) statusText.textContent = '论文处理成功！';
            // Hide download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
            this.stopProgressTracking();
            
            // Show completion toast with details
            if (progress.details.includes('论文已存在') || progress.details.includes('已经被处理过了')) {
              showToast('✅ 论文已存在，处理完成！');
            } else {
              showToast('✅ 论文处理成功！');
            }
            
            // Redirect to paper detail page after delay
            setTimeout(() => {
              // Use summary_url from the API response if available
              if (this.lastSubmissionResult && this.lastSubmissionResult.summary_url) {
                window.location.href = this.lastSubmissionResult.summary_url;
              } else {
                // Fallback: refresh the page if no summary_url available
                const url = new URL(window.location);
                url.searchParams.set('_t', Date.now());
                window.location.href = url.toString();
              }
            }, 1500);
          } else if (progress.step === 'error') {
            if (statusIcon) statusIcon.textContent = '❌';
            if (statusText) statusText.textContent = '处理失败';
            // Hide download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
            this.stopProgressTracking();
            
            // Show error toast with details
            showToast(`❌ 处理失败: ${progress.details}`);
            
            // Hide status after delay
            setTimeout(() => {
              const submissionStatus = document.getElementById('submission-status');
              if (submissionStatus) {
                submissionStatus.style.display = 'none';
              }
            }, 10000);
          } else {
            // Update status text based on current step
            const stepMessages = {
              'starting': '正在初始化...',
              'resolving': '正在解析PDF链接...',
              'downloading': '正在下载PDF...',
              'extracting': '正在提取文本...',
              'checking': '正在检查AI相关性...',
              'summarizing': '正在生成摘要...'
            };
            
            if (statusText) {
              statusText.textContent = stepMessages[progress.step] || '正在处理...';
            }
            
            // Show toast for key processing steps
            if (progress.step === 'checking' && progress.details.includes('AI检查完成')) {
              const confidence = progress.details.match(/置信度: ([\d.]+)/);
              if (confidence) {
                showToast(`🔍 AI检查完成 (置信度: ${confidence[1]})`);
              }
            } else if (progress.step === 'summarizing' && progress.details.includes('摘要生成完成')) {
              showToast('📝 摘要生成完成！');
            }
          }
        }
      } catch (error) {
        console.error('Progress tracking error:', error);
      }
    };
    
    // Start polling
    this.progressInterval = setInterval(pollProgress, pollInterval);
  }

  stopProgressTracking() {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
  }
}

// Initialize paper submission
new PaperSubmission();

// Global function for toggling paper submission panel
function togglePaperSubmission() {
  const content = document.getElementById('submission-content');
  const toggleIcon = document.querySelector('.toggle-icon');
  const toggleBtn = document.getElementById('submission-toggle-btn');
  
  if (!content || !toggleIcon || !toggleBtn) return;
  
  const isExpanded = content.classList.contains('expanded');
  
  if (isExpanded) {
    // Collapse
    content.classList.remove('expanded');
    toggleIcon.classList.remove('expanded');
    toggleBtn.setAttribute('aria-label', '展开提交表单');
  } else {
    // Expand
    content.classList.add('expanded');
    toggleIcon.classList.add('expanded');
    toggleBtn.setAttribute('aria-label', '收起提交表单');
  }
}
