// Paper Submission Module
class PaperSubmission {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('DOMContentLoaded', () => {
      const paperForm = document.getElementById('paper-submission-form');
      const submissionStatus = document.getElementById('submission-status');
      const statusIcon = submissionStatus?.querySelector('.status-icon');
      const statusText = submissionStatus?.querySelector('.status-text');
      const progressFill = submissionStatus?.querySelector('.progress-fill');
      
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
            
            if (response.ok && result.success) {
              // Success
              if (submissionStatus) {
                statusIcon.textContent = '✅';
                statusText.textContent = '论文处理成功！';
                progressFill.style.width = '100%';
              }
              
              showToast('✅ 论文处理成功！页面将在5秒后刷新...');
              
              // Clear input
              urlInput.value = '';
              
              // Refresh page after delay
              setTimeout(() => {
                location.reload();
              }, 5000);
              
            } else {
              // Error
              if (submissionStatus) {
                statusIcon.textContent = '❌';
                statusText.textContent = result.message || '处理失败';
                progressFill.style.width = '0%';
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
            
            if (submissionStatus) {
              statusIcon.textContent = '❌';
              statusText.textContent = '网络错误，请重试';
              progressFill.style.width = '0%';
            }
            
            showToast('❌ 网络错误，请重试');
          } finally {
            // Re-enable form
            submitBtn.disabled = false;
            submitBtn.textContent = '提交论文';
            
            // Hide status after delay
            if (submissionStatus) {
              setTimeout(() => {
                submissionStatus.style.display = 'none';
              }, 10000);
            }
          }
        });
      }
    });
  }
}

// Initialize paper submission
new PaperSubmission();
