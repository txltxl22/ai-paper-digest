// Article Actions Module
class ArticleActions {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('click', this.handleClick.bind(this));
  }

  handleClick(ev) {
    if (ev.target.matches('.toggle-link')) {
      ev.preventDefault();
      this.togglePreview(ev.target);
    }
    
    // Handle mark-read-link clicks
    let markReadElement = ev.target.closest('.mark-read-link');
    if (markReadElement) {
      ev.preventDefault();
      
      if (markReadElement.classList.contains('disabled')) {
        showToast('需要登录，\n登录只需输入任意用户名😄');
      } else {
        this.markRead(markReadElement);
      }
      return;
    }
      
    if (ev.target.matches('.remove-read-link')) {
      ev.preventDefault();
      this.removeFromRead(ev.target);
    }
  }

  togglePreview(link) {
    const art = link.closest('article');
    const prev = art.querySelector('.preview-html');
    prev.classList.toggle('collapsed');
    link.textContent = prev.classList.contains('collapsed') ? '展开' : '收起';
    
    // Track event
    const id = art.getAttribute('data-id');
    const payload = {
      type: 'read_more',
      arxiv_id: id,
      meta: { collapsed: prev.classList.contains('collapsed') },
      ts: new Date().toISOString(),
      tz_offset_min: new Date().getTimezoneOffset()
    };
    
    try {
      navigator.sendBeacon('/event', JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send event:', e);
    }
  }

  markRead(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    
    fetch(window.appUrls.mark_read + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        art.remove();
        this.updateInfoBarCounts(-1, 1);
        
        // Track event
        const payload = {
          type: 'mark_read',
          arxiv_id: id,
          ts: new Date().toISOString(),
          tz_offset_min: new Date().getTimezoneOffset()
        };
        
        try {
          navigator.sendBeacon('/event', JSON.stringify(payload));
        } catch(e) {
          console.warn('Failed to send event:', e);
        }
      }
    });
  }

  removeFromRead(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    
    fetch(window.appUrls.unmark_read + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        art.remove();
        
        // Track event
        const payload = {
          type: 'unmark_read',
          arxiv_id: id,
          ts: new Date().toISOString(),
          tz_offset_min: new Date().getTimezoneOffset()
        };
        
        try {
          navigator.sendBeacon('/event', JSON.stringify(payload));
        } catch(e) {
          console.warn('Failed to send event:', e);
        }
      }
    });
  }

  updateInfoBarCounts(unreadDelta, readDelta) {
    const infoBar = document.getElementById('info-bar');
    if (infoBar) {
      const spans = infoBar.querySelectorAll('span');
      if (spans.length >= 3) {
        let readSpan = spans[0].querySelector('strong');
        let todaySpan = spans[1].querySelector('strong');
        let unreadSpan = spans[2].querySelector('strong');
        
        if (readSpan && unreadSpan) {
          let read = parseInt(readSpan.textContent, 10);
          let unread = parseInt(unreadSpan.textContent, 10);
          if (!isNaN(read) && !isNaN(unread)) {
            readSpan.textContent = read + readDelta;
            unreadSpan.textContent = Math.max(0, unread + unreadDelta);
          }
        }
        
        if (todaySpan) {
          let today = parseInt(todaySpan.textContent, 10);
          if (!isNaN(today)) {
            todaySpan.textContent = today + readDelta;
          }
        }
      }
    }
  }
}

// Initialize article actions
new ArticleActions();
