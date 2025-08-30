// User Actions Module
class UserActions {
  constructor() {
    this.init();
  }

  init() {
    // Logout functionality
    document.addEventListener('click', (ev) => {
      if (ev.target.id === 'logout-btn') {
        ev.preventDefault();
        this.logout();
      }
      
      if (ev.target.id === 'reset-btn') {
        ev.preventDefault();
        this.resetAll();
      }
    });

    // Note: Event tracking is now handled by the centralized EventTracker
    // Global listeners are set up in event-tracker.js

    // Tag filter auto-submit
    document.addEventListener('DOMContentLoaded', () => {
      const form = document.getElementById('tag-filter');
      if (form) {
        form.addEventListener('change', (ev) => {
          const t = ev.target;
          if (t && t.name === 'top') {
            form.submit();
          }
        });
      }
    });

    // Tag filter collapse/expand
    this.initTagFilter();
  }

  logout() {
    // Track logout event using centralized tracker
    window.eventTracker.trackLogout();
    
    document.cookie = 'uid=; Max-Age=0; path=/';
    location.reload();
  }

  resetAll() {
    fetch(window.appUrls.reset, { method: 'POST' }).then(r => {
      if (r.ok) location.reload();
    });
  }

  // Note: Event tracking methods are now handled by the centralized EventTracker
  // These methods are kept for backward compatibility but delegate to the tracker

  initTagFilter() {
    const container = document.getElementById('detail-chips');
    const toggleBtn = document.getElementById('toggle-detail-chips');
    if (!container || !toggleBtn) return;
    
    const chips = Array.from(container.querySelectorAll('.tag-chip'));
    const LIMIT = 24;
    
    if (chips.length > LIMIT) {
      for (let i = LIMIT; i < chips.length; i++) chips[i].style.display = 'none';
      toggleBtn.style.display = 'inline-block';
      
      let expanded = false;
      const updateLabel = () => {
        toggleBtn.textContent = expanded ? '收起标签' : `展开全部标签（+${chips.length - LIMIT}）`;
      };
      
      updateLabel();
      
      toggleBtn.addEventListener('click', () => {
        expanded = !expanded;
        for (let i = LIMIT; i < chips.length; i++) {
          chips[i].style.display = expanded ? '' : 'none';
        }
        updateLabel();
      });
    }
  }
}

// Initialize user actions
new UserActions();
