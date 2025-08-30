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

    // Login form submit
    document.getElementById('user-form')?.addEventListener('submit', () => {
      this.trackLogin();
    });

    // Read list click tracking
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('a[href*="/read"]');
      if (link) {
        this.trackReadList();
      }
    }, true);

    // PDF click tracking
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('a.action-btn[href^="https://arxiv.org/pdf/"]');
      if (link) {
        const art = link.closest('article');
        const id = art ? art.getAttribute('data-id') : null;
        this.trackPdfOpen(id, link.getAttribute('href'));
      }
    }, true);

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
    // Track logout event
    try {
      const payload = {
        type: 'logout',
        ts: new Date().toISOString(),
        tz_offset_min: new Date().getTimezoneOffset()
      };
      navigator.sendBeacon('/event', JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send logout event:', e);
    }
    
    document.cookie = 'uid=; Max-Age=0; path=/';
    location.reload();
  }

  resetAll() {
    fetch(window.appUrls.reset, { method: 'POST' }).then(r => {
      if (r.ok) location.reload();
    });
  }

  trackLogin() {
    try {
      const payload = {
        type: 'login',
        ts: new Date().toISOString(),
        tz_offset_min: new Date().getTimezoneOffset()
      };
      navigator.sendBeacon('/event', JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send login event:', e);
    }
  }

  trackReadList() {
    try {
      const payload = {
        type: 'read_list',
        ts: new Date().toISOString(),
        tz_offset_min: new Date().getTimezoneOffset()
      };
      navigator.sendBeacon('/event', JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send read_list event:', e);
    }
  }

  trackPdfOpen(arxivId, href) {
    const payload = {
      type: 'open_pdf',
      arxiv_id: arxivId,
      meta: { href },
      ts: new Date().toISOString(),
      tz_offset_min: new Date().getTimezoneOffset()
    };
    
    try {
      navigator.sendBeacon('/event', JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send open_pdf event:', e);
    }
  }

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
