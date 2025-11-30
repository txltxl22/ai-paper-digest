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
      console.log('Deep read status bar not found - user may not be logged in');
      return; // Status bar not present (user not logged in)
    }

    this.processingList = document.getElementById('deep-read-processing-list');
    this.completedList = document.getElementById('deep-read-completed-list');

    if (!this.processingList || !this.completedList) {
      console.error('Deep read status bar elements not found');
      return;
    }

    console.log('Deep read status bar initialized');
    // Start polling
    this.startPolling();
  }

  startPolling() {
    // Poll immediately
    this.updateStatus();

    // Then poll at intervals
    this.pollInterval = setInterval(() => {
      this.updateStatus();
    }, this.pollIntervalMs);
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
          return;
        }
        console.warn('Failed to fetch deep read status:', response.status, response.statusText);
        return;
      }

      const data = await response.json();
      this.renderStatus(data);
    } catch (error) {
      console.error('Error fetching deep read status:', error);
      // Don't hide on error, just log it - might be network issue
    }
  }

  renderStatus(data) {
    if (!this.statusBar) {
      console.warn('Status bar element not found in renderStatus');
      return;
    }

    const processing = (data.processing || []).filter(
      item => !this.dismissedItems.has(`processing-${item.arxiv_id}`)
    );
    const completed = (data.completed || []).filter(
      item => !this.dismissedItems.has(`completed-${item.arxiv_id}`)
    );

    console.log('Deep read status update:', { processing: processing.length, completed: completed.length });

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
  }

  renderProcessingList(processing) {
    if (!this.processingList) return;

    this.processingList.innerHTML = processing
      .map(item => {
        const timeAgo = this.getTimeAgo(item.started_at);
        return `
          <span class="deep-read-status-item processing">
            <span class="spinner"></span>
            <a href="/summary/${item.arxiv_id}">${item.arxiv_id}</a>
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
        return `
          <span class="deep-read-status-item completed" data-arxiv-id="${item.arxiv_id}">
            <span>✓</span>
            <a href="/summary/${item.arxiv_id}">${item.arxiv_id}</a>
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
        this.updateStatus();
      }
    } catch (error) {
      console.error('Error dismissing completed job:', error);
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

// Initialize status bar
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.deepReadStatusBar = new DeepReadStatusBar();
  });
} else {
  window.deepReadStatusBar = new DeepReadStatusBar();
}

