// Admin Modal Module
class AdminModal {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('click', (ev) => {
      if (ev.target.id === 'admin-fetch-btn') {
        ev.preventDefault();
        this.showModal();
      }
      
      if (ev.target.id === 'close-modal-btn') {
        document.getElementById('admin-progress-modal').style.display = 'none';
      }
      
      if (ev.target.id === 'cancel-fetch-btn') {
        document.getElementById('admin-progress-modal').style.display = 'none';
        showToast('已取消获取操作');
      }
      
      if (ev.target.id === 'clear-logs-btn') {
        document.getElementById('log-output').innerHTML = '';
      }
      
      if (ev.target.id === 'fallback-fetch-btn') {
        ev.preventDefault();
      }
    });

    // Close modal when clicking outside
    document.getElementById('admin-progress-modal')?.addEventListener('click', (ev) => {
      if (ev.target.id === 'admin-progress-modal') {
        ev.target.style.display = 'none';
      }
    });
  }

  showModal() {
    const modal = document.getElementById('admin-progress-modal');
    const statusText = modal.querySelector('.status-text');
    const statusIcon = modal.querySelector('.status-icon');
    const logOutput = document.getElementById('log-output');
    const summaryStats = document.getElementById('summary-stats');
    const statsContent = document.getElementById('stats-content');
    
    // Reset modal state
    modal.style.display = 'block';
    statusText.textContent = '正在启动服务...';
    statusIcon.textContent = '⏳';
    logOutput.innerHTML = '';
    summaryStats.style.display = 'none';
    statsContent.innerHTML = '';
    
    // Hide fallback button initially
    const fallbackBtn = document.getElementById('fallback-fetch-btn');
    if (fallbackBtn) {
      fallbackBtn.style.display = 'none';
    }
    
    // Add initial log entry
    this.addLogEntry('开始获取最新论文摘要...', 'info');
    
    // Start the fetch process
    this.startFetchProcess(statusText, statusIcon, logOutput, summaryStats, statsContent);
  }

  startFetchProcess(statusText, statusIcon, logOutput, summaryStats, statsContent) {
    fetch(window.appUrls.admin_stream, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      this.addLogEntry('🔗 已连接到服务器，开始获取最新摘要...', 'info');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      const readStream = () => {
        return reader.read().then(({ done, value }) => {
          if (done) {
            return;
          }
          
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          lines.forEach(line => {
            if (line.startsWith('data: ')) {
              try {
                const jsonData = line.slice(6).trim();
                if (!jsonData || jsonData === '') {
                  return;
                }
                
                const data = JSON.parse(jsonData);
                
                if (!data.type) {
                  console.warn('Received data without type:', data);
                  return;
                }
                
                switch (data.type) {
                  case 'status':
                    statusText.textContent = data.message;
                    statusIcon.textContent = data.icon;
                    this.addLogEntry(data.message, 'info');
                    break;
                    
                  case 'log':
                    this.addLogEntry(data.message, 'info');
                    break;
                    
                  case 'complete':
                    if (data.status === 'success') {
                      statusText.textContent = '获取成功！';
                      statusIcon.textContent = '✅';
                      this.addLogEntry('✅ ' + data.message, 'success');
                      
                      setTimeout(() => {
                        showToast('✅ 最新论文摘要获取成功！页面将在3秒后刷新...');
                        setTimeout(() => {
                          location.reload();
                        }, 3000);
                      }, 1000);
                    } else {
                      statusText.textContent = '获取失败';
                      statusIcon.textContent = '❌';
                      this.addLogEntry('❌ ' + data.message, 'error');
                    }
                    break;
                    
                  case 'error':
                    this.addLogEntry('❌ ' + data.message, 'error');
                    break;
                }
              } catch (error) {
                console.error('Error parsing SSE data:', error);
                const errorMsg = error.message || '未知错误';
                this.addLogEntry(`❌ 解析数据时发生错误: ${errorMsg}`, 'error');
                
                console.log('Raw data that failed to parse:', line);
                
                try {
                  const rawData = line.slice(6);
                  if (rawData && rawData.trim()) {
                    this.addLogEntry(`📄 原始数据: ${rawData}`, 'info');
                  }
                } catch (e) {
                  console.log('Could not display raw data:', e);
                }
              }
            }
          });
          
          return readStream();
        });
      };
      
      return readStream();
    })
    .catch(error => {
      console.error('Fetch error:', error);
      
      let errorMessage = '❌ 连接错误，请检查网络连接';
      let errorType = 'error';
      
      if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
        errorMessage = '❌ 无法连接到服务器，请检查服务是否正在运行';
        errorType = 'error';
      } else if (error.name === 'AbortError') {
        errorMessage = '⏹️ 请求被取消';
        errorType = 'warning';
      } else if (error.message.includes('timeout')) {
        errorMessage = '⏰ 连接超时，请检查网络速度';
        errorType = 'warning';
      } else if (error.message.includes('NetworkError')) {
        errorMessage = '🌐 网络错误，请检查网络连接';
        errorType = 'error';
      }
      
      this.addLogEntry(errorMessage, errorType);
      this.addLogEntry(`🔍 错误详情: ${error.name}: ${error.message}`, 'info');

      statusText.textContent = '连接失败';
      statusIcon.textContent = '❌';
      
      this.addLogEntry('💡 Windows用户提示: 请检查防火墙设置和网络连接', 'info');
      this.addLogEntry('💡 如果问题持续，请尝试刷新页面或重启服务', 'info');
      
      const fallbackBtn = document.getElementById('fallback-fetch-btn');
      if (fallbackBtn) {
        fallbackBtn.style.display = 'inline-block';
        fallbackBtn.onclick = () => {
          this.addLogEntry('🔄 尝试使用备用方式获取...', 'info');
          statusText.textContent = '使用备用方式...';
          statusIcon.textContent = '🔄';
          
          fetch(window.appUrls.admin_fetch, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          })
          .then(response => response.json())
          .then(data => {
            if (data.status === 'success') {
              statusText.textContent = '获取成功！';
              statusIcon.textContent = '✅';
              this.addLogEntry('✅ 备用方式获取成功！', 'success');
              showToast('✅ 最新论文摘要获取成功！页面将在3秒后刷新...');
              setTimeout(() => location.reload(), 3000);
            } else {
              statusText.textContent = '获取失败';
              statusIcon.textContent = '❌';
              this.addLogEntry('❌ 备用方式也失败了: ' + data.message, 'error');
            }
          })
          .catch(fallbackError => {
            statusText.textContent = '获取失败';
            statusIcon.textContent = '❌';
            this.addLogEntry('❌ 备用方式出错: ' + fallbackError.message, 'error');
          });
        };
      }
    });
  }

  addLogEntry(message, type = 'info') {
    const logOutput = document.getElementById('log-output');
    const timestamp = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.className = `log-line log-${type}`;
    logLine.innerHTML = `<span class="log-timestamp">[${timestamp}]</span>${message}`;
    logOutput.appendChild(logLine);
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  displaySummaryStats(stats, container) {
    container.innerHTML = '';
    
    const statLabels = {
      'papers_found': '发现的论文',
      'success_count': '成功处理',
      'rss_updated': 'RSS更新',
      'completion': '完成状态'
    };
    
    Object.entries(stats).forEach(([key, value]) => {
      if (value) {
        const statItem = document.createElement('div');
        statItem.className = 'stat-item';
        statItem.innerHTML = `
          <span class="stat-label">${statLabels[key] || key}:</span>
          <span class="stat-value">${value}</span>
        `;
        container.appendChild(statItem);
      }
    });
  }
}

// Initialize admin modal
new AdminModal();
