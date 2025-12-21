// Paper Submission Module
class PaperSubmission {
  constructor() {
    this.progressInterval = null;
    this.lastSubmissionResult = null;
    this.currentTaskId = null; // Track current task being processed
    this.currentSubmissionState = null; // Store current submission state
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
    
    // Desktop quota
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
    
    // Mobile quota sync
    const mobileRemaining = document.getElementById('mobile-remaining');
    const mobileResetTime = document.getElementById('mobile-reset-time');
    if (mobileRemaining) {
      mobileRemaining.textContent = `${quota.remaining}/${quota.daily_limit}`;
    }
    if (mobileResetTime) {
      mobileResetTime.textContent = quota.next_reset_formatted;
    }
    
    // Sidebar quota sync
    const sidebarRemaining = document.getElementById('sidebar-remaining');
    if (sidebarRemaining) {
      sidebarRemaining.textContent = `${quota.remaining}/${quota.daily_limit}`;
    }
  }

  initFormHandling() {
    // Desktop form
    const paperForm = document.getElementById('paper-submission-form');
    if (paperForm) {
      this.setupFormHandler(paperForm, {
        urlInput: document.getElementById('paper-url-input'),
        submitBtn: paperForm.querySelector('.submit-btn'),
        statusEl: document.getElementById('submission-status'),
        statusIcon: () => document.getElementById('submission-status')?.querySelector('.status-icon'),
        statusText: () => document.getElementById('submission-status')?.querySelector('.status-title'),
        progressFill: () => document.getElementById('submission-status')?.querySelector('.progress-fill'),
        progressText: () => document.getElementById('submission-status')?.querySelector('.progress-text'),
        currentStep: () => document.getElementById('submission-status')?.querySelector('#current-step'),
        fileSizeInfo: () => document.getElementById('submission-status')?.querySelector('#file-size-info'),
      });
    }
    
    // Mobile form
    const mobileForm = document.getElementById('mobile-paper-form');
    if (mobileForm) {
      this.setupFormHandler(mobileForm, {
        urlInput: document.getElementById('mobile-paper-url'),
        submitBtn: mobileForm.querySelector('.mobile-submit-btn'),
        statusEl: document.getElementById('mobile-status'),
        statusIcon: () => document.getElementById('mobile-status')?.querySelector('.status-icon'),
        statusText: () => document.getElementById('mobile-step'), // Mobile uses same element for status and step
        progressFill: () => document.getElementById('mobile-progress'),
        progressText: () => document.getElementById('mobile-progress-text'),
        currentStep: () => document.getElementById('mobile-step'), // Same as statusText for mobile
        fileSizeInfo: null,
      });
    }
    
    // Sidebar form
    const sidebarForm = document.getElementById('sidebar-paper-form');
    if (sidebarForm) {
      this.setupFormHandler(sidebarForm, {
        urlInput: document.getElementById('sidebar-paper-url'),
        submitBtn: sidebarForm.querySelector('.sidebar-submit-btn'),
        statusEl: document.getElementById('sidebar-status'),
        statusIcon: () => document.getElementById('sidebar-status')?.querySelector('.status-spinner'),
        statusText: () => document.getElementById('sidebar-step'),
        progressFill: () => document.getElementById('sidebar-progress'),
        progressText: null,
        currentStep: () => document.getElementById('sidebar-step'),
        fileSizeInfo: null,
      });
    }
  }

  setupFormHandler(form, elements) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      // If there's already a task in progress, don't submit again
      if (this.currentTaskId && this.progressInterval) {
        showToast('⚠️ 已有论文正在处理中，请等待完成');
        // Show the existing progress instead
        if (elements.statusEl) {
          elements.statusEl.style.display = 'block';
          elements.statusEl.classList.add('active');
        }
        return;
      }
      
      const paperUrl = elements.urlInput.value.trim();
      
      if (!paperUrl) {
        showToast('请输入论文URL');
        return;
      }
      
      // Get all status elements
      const statusIcon = elements.statusIcon?.();
      const statusText = elements.statusText?.();
      const progressFill = elements.progressFill?.();
      const progressText = elements.progressText?.();
      const currentStep = elements.currentStep?.();
      const fileSizeInfo = elements.fileSizeInfo?.();
      
      // Store current submission state for reopening sidebar
      this.currentSubmissionState = {
        elements: elements,
        statusIcon: statusIcon,
        statusText: statusText,
        progressFill: progressFill,
        progressText: progressText,
        currentStep: currentStep,
        fileSizeInfo: fileSizeInfo
      };
      
      // Show submission status with initial state
      if (elements.statusEl) {
        elements.statusEl.style.display = 'block';
        elements.statusEl.classList.add('active');
        if (statusIcon) statusIcon.textContent = '⏳';
        if (statusText) statusText.textContent = '正在提交论文...';
        if (progressFill) {
          progressFill.style.width = '0%';
          progressFill.classList.add('animating');
        }
        if (progressText) progressText.textContent = '0%';
        if (currentStep) currentStep.textContent = '正在连接服务器...';
        if (fileSizeInfo) fileSizeInfo.textContent = '';
        
        // Hide download progress section initially (desktop only)
        const downloadProgressSection = document.getElementById('download-progress-section');
        if (downloadProgressSection) {
          downloadProgressSection.style.display = 'none';
        }
      }
      
      // Disable form
      if (elements.submitBtn) {
        elements.submitBtn.disabled = true;
        const btnText = elements.submitBtn.querySelector('.btn-text');
        if (btnText) {
          btnText.textContent = '提交中...';
        } else {
          elements.submitBtn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">提交中...</span>';
        }
      }
      
      try {
        // Submit paper URL - this now returns immediately with task_id
        const response = await fetch('/submit_paper', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ url: paperUrl }),
        });
        
        const result = await response.json();
        
        if (response.ok && result.success && result.task_id) {
          // Success - start progress tracking immediately
          showToast('✅ 论文提交成功！正在处理中...');
          
          // Store task ID
          this.currentTaskId = result.task_id;
          
          // Clear input
          elements.urlInput.value = '';
          
          // Keep mobile modal open during processing
          const mobileOverlay = document.getElementById('mobile-submission-overlay');
          if (mobileOverlay && mobileOverlay.classList.contains('active')) {
            // Don't close the modal - let user see progress
            // The modal will close when they manually close it or when redirect happens
          }
          
          // Start progress tracking
          this.startProgressTracking(
            result.task_id,
            statusIcon,
            statusText,
            progressFill,
            progressText,
            currentStep,
            fileSizeInfo,
            elements.submitBtn,
            elements.statusEl
          );
          
        } else {
          // Error - quota exceeded or validation error
          this.currentTaskId = null;
          this.currentSubmissionState = null;
          this.handleSubmissionError(result, statusIcon, statusText, progressFill, progressText, currentStep, elements.submitBtn, elements.statusEl);
        }
        
      } catch (error) {
        console.error('Paper submission error:', error);
        
        this.currentTaskId = null;
        this.currentSubmissionState = null;
        
        if (statusIcon) statusIcon.textContent = '❌';
        if (statusText) statusText.textContent = '网络错误，请重试';
        if (progressFill) {
          progressFill.style.width = '0%';
          progressFill.classList.remove('animating');
        }
        if (progressText) progressText.textContent = '0%';
        if (currentStep) currentStep.textContent = '网络错误';
        
        showToast('❌ 网络错误，请重试');
        this.resetSubmitButton(elements.submitBtn);
        
        // Hide status after delay
        setTimeout(() => {
          if (elements.statusEl) {
            elements.statusEl.style.display = 'none';
            elements.statusEl.classList.remove('active');
          }
        }, 8000);
      }
    });
  }

  handleSubmissionError(result, statusIcon, statusText, progressFill, progressText, currentStep, submitBtn, statusEl) {
    if (statusIcon) statusIcon.textContent = '❌';
    if (statusText) statusText.textContent = result.message || '提交失败';
    if (progressFill) {
      progressFill.style.width = '0%';
      progressFill.classList.remove('animating');
      progressFill.classList.add('error');
    }
    if (progressText) progressText.textContent = '0%';
    if (currentStep) currentStep.textContent = result.message || '处理失败';
    
    showToast(`❌ ${result.message || '处理失败'}`);
    this.resetSubmitButton(submitBtn);
    
    // Hide status after delay
    setTimeout(() => {
      if (statusEl) {
        statusEl.style.display = 'none';
        statusEl.classList.remove('active');
      }
      if (progressFill) progressFill.classList.remove('error');
    }, 8000);
  }

  resetSubmitButton(submitBtn) {
    if (submitBtn) {
      submitBtn.disabled = false;
      // Check if it's a mobile or sidebar button (different structure)
      const btnText = submitBtn.querySelector('.btn-text');
      if (btnText) {
        // Desktop button - update text only
        const btnIcon = submitBtn.querySelector('.btn-icon');
        if (btnIcon) btnIcon.textContent = '🚀';
        btnText.textContent = '提交处理';
      } else {
        // Mobile/sidebar button - replace innerHTML
        submitBtn.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-text">提交处理</span>';
      }
    }
  }

  startProgressTracking(taskId, statusIcon, statusText, progressFill, progressText, currentStep, fileSizeInfo, submitBtn, statusEl) {
    // Get download progress elements
    const downloadProgressSection = document.getElementById('download-progress-section');
    const downloadProgressFill = downloadProgressSection?.querySelector('.download-progress-fill');
    const downloadProgressText = downloadProgressSection?.querySelector('.download-progress-text');
    const downloadSpeed = downloadProgressSection?.querySelector('#download-speed');
    const downloadSize = downloadProgressSection?.querySelector('#download-size');
    
    let isDownloading = false;
    let pollCount = 0;
    const maxPolls = 600; // 5 minutes max with 500ms interval
    
    const pollProgress = async () => {
      pollCount++;
      if (pollCount > maxPolls) {
        this.stopProgressTracking();
        if (statusIcon) statusIcon.textContent = '⚠️';
        if (statusText) statusText.textContent = '处理超时，请刷新页面查看结果';
        showToast('⚠️ 处理时间较长，请刷新页面查看结果');
        this.resetSubmitButton(submitBtn);
        return;
      }
      
      try {
        const response = await fetch(`/download_progress/${taskId}`);
        if (response.ok) {
          const data = await response.json();
          const progress = data.progress;
          
          // Update main progress UI
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
            
            // Update download speed
            if (downloadSpeed) {
              downloadSpeed.textContent = '下载中...';
            }
          } else if (progress.step !== 'downloading') {
            // Hide download progress section for non-download steps
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
            this.progressInterval = setInterval(pollProgress, 2000);
          } else if (!isDownloading && wasDownloading) {
            // Just left download phase, speed up polling
            clearInterval(this.progressInterval);
            this.progressInterval = setInterval(pollProgress, 500);
          }
          
          // Update status based on step
          if (progress.step === 'completed') {
            // Success!
            if (statusIcon) statusIcon.textContent = '✅';
            if (statusText) statusText.textContent = '论文处理成功！';
            if (progressFill) {
              progressFill.style.width = '100%';
              progressFill.classList.remove('animating');
              progressFill.classList.add('success');
            }
            if (progressText) progressText.textContent = '100%';
            
            // Hide download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
            
            this.stopProgressTracking();
            this.resetSubmitButton(submitBtn);
            
            // Show completion toast with guide to deep read status
            if (progress.details.includes('论文已存在')) {
              showToast('✅ 论文已存在，处理完成！', 5000);
            } else {
              showToast('✅ 论文处理成功！可在顶部查看深度阅读状态', 5000);
            }
            
            // Show guide notification pointing to deep read status bar
            this.showDeepReadStatusGuide();
            
            // Get summary URL from result if available
            const summaryUrl = progress.result?.summary_url;
            
            // Redirect to paper detail page after delay (longer delay to let user see the guide)
            setTimeout(() => {
              if (summaryUrl) {
                window.location.href = summaryUrl;
              } else {
                // Fallback: refresh the page
                const url = new URL(window.location);
                url.searchParams.set('_t', Date.now());
                window.location.href = url.toString();
              }
            }, 3000);
            
          } else if (progress.step === 'error') {
            // Error occurred
            if (statusIcon) statusIcon.textContent = '❌';
            if (statusText) statusText.textContent = '处理失败';
            if (progressFill) {
              progressFill.classList.remove('animating');
              progressFill.classList.add('error');
            }
            if (currentStep) currentStep.textContent = progress.details;
            
            // Hide download progress section
            if (downloadProgressSection) {
              downloadProgressSection.style.display = 'none';
            }
            
            this.stopProgressTracking();
            this.resetSubmitButton(submitBtn);
            
            // Show error toast with details
            showToast(`❌ ${progress.details}`, 5000);
            
            // Keep status visible longer so user can see the error
            // Don't auto-hide - let user manually dismiss or see it
            // Status will be hidden when user submits again or closes modal
            
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
    
    // Start polling with initial fast interval
    pollProgress(); // Poll immediately
    this.progressInterval = setInterval(pollProgress, 500);
  }

  stopProgressTracking() {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
    // Clear task tracking when completed or errored
    this.currentTaskId = null;
    this.currentSubmissionState = null;
  }

  showDeepReadStatusGuide() {
    // Check if deep read status bar exists
    const deepReadStatusBar = document.getElementById('deep-read-status-bar');
    if (!deepReadStatusBar) {
      return; // No deep read status bar, skip guide
    }

    // Create a modern guide notification
    let guideNotification = document.getElementById('deep-read-guide-notification');
    if (!guideNotification) {
      guideNotification = document.createElement('div');
      guideNotification.id = 'deep-read-guide-notification';
      guideNotification.className = 'deep-read-guide-notification';
      document.body.appendChild(guideNotification);
    }

    // Set content
    guideNotification.innerHTML = `
      <div class="guide-content">
        <div class="guide-icon">👆</div>
        <div class="guide-text">
          <div class="guide-title">论文提交成功！</div>
          <div class="guide-subtitle">可在页面顶部查看深度阅读处理状态</div>
        </div>
        <button class="guide-close" onclick="this.parentElement.parentElement.classList.remove('show'); setTimeout(() => this.parentElement.parentElement.remove(), 300);">✕</button>
      </div>
      <div class="guide-arrow"></div>
    `;

    // Position arrow to point at deep read status bar
    const updateArrowPosition = () => {
      const arrow = guideNotification.querySelector('.guide-arrow');
      if (arrow && deepReadStatusBar) {
        const barRect = deepReadStatusBar.getBoundingClientRect();
        const guideRect = guideNotification.getBoundingClientRect();
        const arrowLeft = barRect.left + (barRect.width / 2) - guideRect.left;
        arrow.style.left = `${Math.max(20, Math.min(arrowLeft, guideRect.width - 20))}px`;
      }
    };

    // Show notification with animation
    setTimeout(() => {
      guideNotification.classList.add('show');
      updateArrowPosition();
      window.addEventListener('scroll', updateArrowPosition);
      window.addEventListener('resize', updateArrowPosition);
    }, 100);

    // Auto-hide after 10 seconds (longer to give user time to read)
    setTimeout(() => {
      guideNotification.classList.remove('show');
      window.removeEventListener('scroll', updateArrowPosition);
      window.removeEventListener('resize', updateArrowPosition);
      setTimeout(() => {
        if (guideNotification.parentElement) {
          guideNotification.remove();
        }
      }, 300);
    }, 10000);

    // Ensure deep read status bar is visible
    if (deepReadStatusBar && window.deepReadStatusBar) {
      // Trigger status bar update
      if (window.deepReadStatusBar.updateStatus) {
        window.deepReadStatusBar.updateStatus();
      }
    }
  }
}

// Initialize paper submission
const paperSubmissionHandler = new PaperSubmission();
// Make it globally accessible for sidebar reopening
window.paperSubmissionHandler = paperSubmissionHandler;

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
    
    // If there's an ongoing submission, make sure status is visible
    if (window.paperSubmissionHandler && window.paperSubmissionHandler.currentTaskId) {
      const submissionStatus = document.getElementById('submission-status');
      if (submissionStatus) {
        submissionStatus.style.display = 'block';
        submissionStatus.classList.add('active');
      }
    }
  }
}
