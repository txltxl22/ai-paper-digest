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
    const statusText = submissionStatus?.querySelector('.status-text');
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
          statusIcon.textContent = '⏳';
          statusText.textContent = '正在处理论文...';
          progressFill.style.width = '0%';
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
              statusIcon.textContent = '❌';
              statusText.textContent = result.message || '处理失败';
              progressFill.style.width = '0%';
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
            statusIcon.textContent = '❌';
            statusText.textContent = '网络错误，请重试';
            progressFill.style.width = '0%';
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
    console.log('Starting progress tracking for task:', taskId);
    
    // Get download progress elements
    const downloadProgressSection = document.getElementById('download-progress-section');
    const downloadProgressFill = downloadProgressSection?.querySelector('.download-progress-fill');
    const downloadProgressText = downloadProgressSection?.querySelector('.download-progress-text');
    const downloadSpeed = downloadProgressSection?.querySelector('#download-speed');
    const downloadSize = downloadProgressSection?.querySelector('#download-size');
    
    console.log('Download progress elements:', {
      section: !!downloadProgressSection,
      fill: !!downloadProgressFill,
      text: !!downloadProgressText,
      speed: !!downloadSpeed,
      size: !!downloadSize
    });
    
    let isDownloading = false;
    let pollInterval = 200; // Start with fast polling
    
    const pollProgress = async () => {
      try {
        const response = await fetch(`/download_progress/${taskId}`);
        if (response.ok) {
          const data = await response.json();
          const progress = data.progress;
          
          console.log('Progress update:', progress); // Debug log
          
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
          console.log('Checking download progress:', progress.step, progress.details);
          if (progress.step === 'downloading' && progress.details.includes('正在下载PDF')) {
            console.log('Showing download progress section');
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
            console.log('Entering download phase, slowing down polling to 3 seconds');
            clearInterval(this.progressInterval);
            this.progressInterval = setInterval(pollProgress, 3000);
          } else if (!isDownloading && wasDownloading) {
            // Just left download phase, speed up polling
            console.log('Leaving download phase, speeding up polling to 200ms');
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
            
            // Refresh page after delay
            setTimeout(() => {
              location.reload();
            }, 3000);
          } else if (progress.step === 'error') {
            if (statusIcon) statusIcon.textContent = '❌';
            if (statusText) statusText.textContent = '处理失败';
            // Hide download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
            this.stopProgressTracking();
            
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
      console.log('Progress tracking stopped');
    }
  }
}

// Initialize paper submission
new PaperSubmission();
