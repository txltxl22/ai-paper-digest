/**
 * Trending Section JavaScript
 * Handles tab switching and dynamic loading of trending data
 */
(function() {
  'use strict';

  const STORAGE_KEY = 'trending_period_preference';
  const DEFAULT_PERIOD = '30d';

  class TrendingManager {
    constructor() {
      this.section = document.getElementById('trending-section');
      if (!this.section) return;
      
      this.tabs = this.section.querySelectorAll('.trending-tab');
      this.containers = this.section.querySelectorAll('.trending-tags-container');
      
      this.init();
    }

    init() {
      // Bind tab click events
      this.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => this.handleTabClick(e));
      });
      
      // Restore saved preference or use default
      const savedPeriod = localStorage.getItem(STORAGE_KEY) || DEFAULT_PERIOD;
      this.selectPeriod(savedPeriod);
    }

    selectPeriod(period) {
      // Update tab states
      this.tabs.forEach(tab => {
        if (tab.dataset.period === period) {
          tab.classList.add('active');
          tab.setAttribute('aria-selected', 'true');
        } else {
          tab.classList.remove('active');
          tab.setAttribute('aria-selected', 'false');
        }
      });
      
      // Update container visibility
      this.containers.forEach(container => {
        if (container.dataset.period === period) {
          container.style.display = 'flex';
          container.classList.add('active');
        } else {
          container.style.display = 'none';
          container.classList.remove('active');
        }
      });
    }

    handleTabClick(e) {
      const clickedTab = e.currentTarget;
      const period = clickedTab.dataset.period;
      
      // Save preference to localStorage
      localStorage.setItem(STORAGE_KEY, period);
      
      // Update UI
      this.selectPeriod(period);
    }

    // Optional: Refresh trending data via API
    async refreshTrending(period = 7) {
      try {
        const response = await fetch(`/api/trending/?period=${period}&limit=15`);
        if (!response.ok) throw new Error('Failed to fetch trending data');
        
        const data = await response.json();
        this.updateContainer(period, data.tags);
      } catch (error) {
        console.error('Error refreshing trending:', error);
      }
    }

    updateContainer(period, tags) {
      const container = document.getElementById(`trending-tags-${period}`);
      if (!container) return;
      
      if (!tags || tags.length === 0) {
        container.innerHTML = `
          <div class="trending-empty">
            <span class="empty-icon">📊</span>
            <span class="empty-text">暂无趋势数据</span>
          </div>
        `;
        return;
      }
      
      const html = tags.map(tag => this.renderTag(tag)).join('');
      container.innerHTML = html;
    }

    renderTag(tag) {
      const isNewClass = tag.is_new ? 'is-new' : '';
      let growthHtml = '';
      
      if (tag.growth_direction === 'up') {
        const label = tag.is_new ? 'NEW' : (tag.growth_percent > 0 ? `+${tag.growth_percent}%` : '');
        growthHtml = `
          <span class="growth-indicator growth-up" title="+${tag.growth_diff} 较上期">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
              <path d="M5 2L9 7H1L5 2Z"/>
            </svg>
            ${label ? `<span class="growth-label">${label}</span>` : ''}
          </span>
        `;
      } else if (tag.growth_direction === 'down') {
        growthHtml = `
          <span class="growth-indicator growth-down" title="${tag.growth_diff} 较上期">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
              <path d="M5 8L1 3H9L5 8Z"/>
            </svg>
            <span class="growth-label">-${tag.growth_percent}%</span>
          </span>
        `;
      }
      
      return `
        <a href="/?tag=${encodeURIComponent(tag.name)}" class="trending-chip ${isNewClass}">
          <span class="chip-name">#${tag.name}</span>
          <span class="chip-count">${tag.count}</span>
          ${growthHtml}
        </a>
      `;
    }
  }

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    window.trendingManager = new TrendingManager();
  });
})();

