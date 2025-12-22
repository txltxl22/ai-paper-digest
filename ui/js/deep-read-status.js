// Deep Read Status Bar Manager
class DeepReadStatusBar {
  constructor() {
    this.statusBar = null;
    this.processingList = null;
    this.completedList = null;
    this.pollInterval = null;
    // Configure polling interval (in milliseconds)
    // Default: 3000ms (3 seconds)
    // Adjust this value to change how often the status bar checks for updates
    // Recommended range: 2000-5000ms (2-5 seconds)
    this.pollIntervalMs = 5000; // Poll every 5 seconds
    this.dismissedItems = new Set(); // Track dismissed items
    this.previousProcessing = new Set(); // Track previously processing items to detect completion
    this.notifiedCompletions = new Set(); // Track already notified completions
    this.init();
  }

  init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setup());
    } else {
      this.setup();
    }
  }

  setup() {
    this.statusBar = document.getElementById('deep-read-status-bar');
    if (!this.statusBar) {
      return; // Status bar not present (user not logged in)
    }

    this.processingList = document.getElementById('deep-read-processing-list');
    this.completedList = document.getElementById('deep-read-completed-list');

    if (!this.processingList || !this.completedList) {
      return;
    }

    // Check status once on page load, but don't start polling yet
    // Polling will only start when user triggers a deep read
    this.updateStatus().then(() => {
      // Only start polling if there are already active jobs (processing)
      const hasProcessing = this.processingList && this.processingList.children.length > 0;
      if (hasProcessing) {
        // There are jobs in progress, start polling
        this.startPolling();
      }
      // If only completed jobs exist, don't poll (user can dismiss them)
    });
  }

  startPolling() {
    // Don't start if already polling
    if (this.pollInterval) {
      return;
    }
    
    // Poll immediately
    this.updateStatus();

    // Then poll at intervals
    // Note: renderStatus() will automatically stop polling when there are no processing jobs
    this.pollInterval = setInterval(() => {
      this.updateStatus();
    }, this.pollIntervalMs);
  }

  // Register a new processing job to track for completion
  registerProcessingJob(arxivId) {
    this.previousProcessing.add(arxivId);
    // Clear from notified in case it was previously notified
    this.notifiedCompletions.delete(arxivId);
  }

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  async updateStatus() {
    try {
      const response = await fetch('/api/deep_read/status');
      if (!response.ok) {
        if (response.status === 401) {
          // User not logged in, hide status bar
          this.hideStatusBar();
          this.stopPolling();
          return Promise.resolve();
        }
        return Promise.resolve();
      }

      const data = await response.json();
      this.renderStatus(data);
      return Promise.resolve();
    } catch (error) {
      // Silently handle network errors
      return Promise.resolve();
    }
  }

  renderStatus(data) {
    if (!this.statusBar) {
      return;
    }

    const processing = (data.processing || []).filter(
      item => !this.dismissedItems.has(`processing-${item.arxiv_id}`)
    );
    const completed = (data.completed || []).filter(
      item => !this.dismissedItems.has(`completed-${item.arxiv_id}`)
    );

    // Detect newly completed items (were processing, now in completed)
    const currentProcessingIds = new Set(processing.map(p => p.arxiv_id));
    const currentCompletedIds = new Set(completed.map(c => c.arxiv_id));
    
    // Find items that were previously processing but are now completed
    for (const arxivId of this.previousProcessing) {
      if (currentCompletedIds.has(arxivId) && !this.notifiedCompletions.has(arxivId)) {
        // This item just completed! Find the completed item to get its title
        const completedItem = completed.find(c => c.arxiv_id === arxivId);
        const title = completedItem?.title || arxivId;
        this.notifiedCompletions.add(arxivId);
        this.onJobCompleted(arxivId, title);
      }
    }
    
    // Update previous processing set for next comparison
    this.previousProcessing = currentProcessingIds;

    // Show/hide processing section
    const processingSection = document.getElementById('deep-read-processing');
    if (processing.length > 0) {
      processingSection.style.display = 'block';
      this.renderProcessingList(processing);
    } else {
      processingSection.style.display = 'none';
    }

    // Show/hide completed section
    const completedSection = document.getElementById('deep-read-completed');
    if (completed.length > 0) {
      completedSection.style.display = 'block';
      this.renderCompletedList(completed);
    } else {
      completedSection.style.display = 'none';
    }

    // Show/hide entire status bar
    if (processing.length > 0 || completed.length > 0) {
      this.statusBar.style.display = 'block';
    } else {
      this.statusBar.style.display = 'none';
    }

    // Trigger header state update for modern layered design
    // This ensures the status bar positioning is recalculated
    if (window.updateHeaderState) {
      setTimeout(window.updateHeaderState, 0);
    }

    // Adjust layout for fixed header (legacy support)
    if (window.adjustLayout) {
      setTimeout(window.adjustLayout, 0);
    }

    // Stop polling if there are no processing jobs
    // (Completed jobs don't need polling, user can dismiss them)
    if (processing.length === 0) {
      this.stopPolling();
    }
  }

  // Called when a deep read job completes
  onJobCompleted(arxivId, title = null) {
    // Check if we're on the detail page for this paper
    const currentPath = window.location.pathname;
    const isOnDetailPage = currentPath === `/summary/${arxivId}`;
    
    // Use provided title or fallback to arxivId
    const displayTitle = title || arxivId;
    
    if (isOnDetailPage) {
      // We're on the detail page for this paper - auto refresh after showing notification
      this.showCompletionNotification(arxivId, displayTitle, true);
    } else {
      // We're on another page - show notification with link
      this.showCompletionNotification(arxivId, displayTitle, false);
    }
  }

  // Show a beautiful completion notification
  showCompletionNotification(arxivId, title = null, autoRefresh = false) {
    // Remove any existing notification
    const existingNotification = document.getElementById('deep-read-notification');
    if (existingNotification) {
      existingNotification.remove();
    }

    // Use provided title or fallback to arxivId
    const displayTitle = title || arxivId;
    const subtitleText = title ? `论文《${displayTitle}》的 AI 全文精读已完成` : `论文 ${arxivId} 的 AI 全文精读已完成`;

    // Create the notification element
    const notification = document.createElement('div');
    notification.id = 'deep-read-notification';
    notification.className = 'deep-read-notification';
    
    if (autoRefresh) {
      notification.innerHTML = `
        <div class="notification-content">
          <div class="notification-icon">🎉</div>
          <div class="notification-text">
            <div class="notification-title">AI 全文研读完成！</div>
            <div class="notification-subtitle">${subtitleText}</div>
            <div class="notification-action">页面将自动刷新...</div>
          </div>
        </div>
        <div class="notification-progress"></div>
      `;
    } else {
      notification.innerHTML = `
        <div class="notification-content">
          <div class="notification-icon">🎉</div>
          <div class="notification-text">
            <div class="notification-title">AI 全文研读完成！</div>
            <div class="notification-subtitle">${subtitleText}</div>
          </div>
          <a href="/summary/${arxivId}" class="notification-btn">
            <span>查看详情</span>
            <span>→</span>
          </a>
          <button class="notification-close" onclick="this.closest('.deep-read-notification').remove()">×</button>
        </div>
      `;
    }

    document.body.appendChild(notification);

    // Trigger animation
    requestAnimationFrame(() => {
      notification.classList.add('show');
    });

    if (autoRefresh) {
      // Auto refresh the page after 2 seconds
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } else {
      // Auto hide after 10 seconds if not clicked
      setTimeout(() => {
        if (notification.parentElement) {
          notification.classList.remove('show');
          setTimeout(() => notification.remove(), 300);
        }
      }, 10000);
    }
  }

  renderProcessingList(processing) {
    if (!this.processingList) return;

    this.processingList.innerHTML = processing
      .map(item => {
        const timeAgo = this.getTimeAgo(item.started_at);
        const displayText = item.title || item.arxiv_id;
        return `
          <span class="deep-read-status-item processing">
            <span class="spinner"></span>
            <a href="/summary/${item.arxiv_id}">${displayText}</a>
            <span class="time-ago">${timeAgo}</span>
          </span>
        `;
      })
      .join('');
  }

  renderCompletedList(completed) {
    if (!this.completedList) return;

    this.completedList.innerHTML = completed
      .map(item => {
        const timeAgo = this.getTimeAgo(item.completed_at);
        const displayText = item.title || item.arxiv_id;
        return `
          <span class="deep-read-status-item completed" data-arxiv-id="${item.arxiv_id}">
            <span>✓</span>
            <a href="/summary/${item.arxiv_id}">${displayText}</a>
            <span class="time-ago">${timeAgo}</span>
            <button onclick="window.deepReadStatusBar.dismissCompleted('${item.arxiv_id}'); event.stopPropagation();" title="关闭">×</button>
          </span>
        `;
      })
      .join('');

    // Add click handler to navigate (but allow dismiss button to work)
    this.completedList.querySelectorAll('.deep-read-status-item.completed').forEach(item => {
      item.addEventListener('click', (e) => {
        // If click was on dismiss button, don't navigate
        if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
          return;
        }
        const arxivId = item.getAttribute('data-arxiv-id');
        if (arxivId) {
          window.location.href = `/summary/${arxivId}`;
        }
      });
    });
  }

  async dismissCompleted(arxivId) {
    try {
      const response = await fetch(`/api/deep_read/${arxivId}/dismiss`, {
        method: 'POST'
      });

      if (response.ok) {
        // Mark as dismissed locally
        this.dismissedItems.add(`completed-${arxivId}`);
        // Update status to remove it from view
        // Note: renderStatus() will stop polling if no processing jobs remain
        this.updateStatus();
      }
    } catch (error) {
      // Silently handle errors
    }
  }

  getTimeAgo(isoString) {
    if (!isoString) return '';
    
    const now = new Date();
    const then = new Date(isoString);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    return `${diffDays}天前`;
  }

  hideStatusBar() {
    if (this.statusBar) {
      this.statusBar.style.display = 'none';
    }
  }
}

// Add spinner animation CSS if not already present
if (!document.getElementById('deep-read-status-styles')) {
  const style = document.createElement('style');
  style.id = 'deep-read-status-styles';
  style.textContent = `
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}

// Initialize status bar - ensure it runs on every page load
function initializeDeepReadStatusBar() {
  // Clean up existing instance if any
  if (window.deepReadStatusBar) {
    if (window.deepReadStatusBar.stopPolling) {
      window.deepReadStatusBar.stopPolling();
    }
    window.deepReadStatusBar = null;
  }
  
  // Initialize new instance
  try {
    window.deepReadStatusBar = new DeepReadStatusBar();
  } catch (error) {
    console.error('Error initializing deep read status bar:', error);
  }
}

// Initialize on multiple events to ensure it runs on every page load
(function() {
  // Function to try initialization
  function tryInitialize() {
    initializeDeepReadStatusBar();
  }
  
  // Initialize immediately if DOM is ready
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    // Use setTimeout to ensure DOM is fully ready
    setTimeout(tryInitialize, 0);
  } else {
    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', tryInitialize, { once: true });
  }
  
  // Also initialize on window load (fallback)
  window.addEventListener('load', function() {
    if (!window.deepReadStatusBar) {
      tryInitialize();
    }
  }, { once: true });
  
  // Re-initialize on pageshow event (handles back/forward navigation and cached pages)
  window.addEventListener('pageshow', function(event) {
    // Always re-initialize on pageshow to handle cached pages
    setTimeout(tryInitialize, 0);
  });
  
  // Also listen for popstate (back/forward navigation)
  window.addEventListener('popstate', function() {
    setTimeout(tryInitialize, 100);
  });
})();

