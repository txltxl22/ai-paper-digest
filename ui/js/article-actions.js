// Article Actions Module
class ArticleActions {
  constructor() {
    this.init();
  }

  init() {
    document.addEventListener('click', this.handleClick.bind(this));
  }

  // Save current scroll position relative to the target element
  saveScrollPosition(element) {
    const rect = element.getBoundingClientRect();
    this.savedScrollPosition = {
      top: window.pageYOffset + rect.top,
      elementTop: rect.top,
      elementHeight: rect.height
    };
  }

  // Restore scroll position after action
  restoreScrollPosition() {
    if (this.savedScrollPosition) {
      window.scrollTo({
        top: this.savedScrollPosition.top,
        behavior: 'instant' // Use instant to avoid animation
      });
      this.savedScrollPosition = null;
    }
  }

  // Scroll to target card or find alternative
  scrollToNextCard(targetCard) {
    if (targetCard && targetCard.tagName === 'ARTICLE') {
      // Scroll to the target card
      const rect = targetCard.getBoundingClientRect();
      const scrollTop = window.pageYOffset + rect.top - 20; // 20px offset for better visibility
      window.scrollTo({
        top: scrollTop,
        behavior: 'instant'
      });
    } else {
      // If no target card, try to find any remaining article
      const articles = document.querySelectorAll('article');
      if (articles.length > 0) {
        const rect = articles[0].getBoundingClientRect();
        const scrollTop = window.pageYOffset + rect.top - 20;
        window.scrollTo({
          top: scrollTop,
          behavior: 'instant'
        });
      } else {
        // No cards left, scroll to top
        window.scrollTo({
          top: 0,
          behavior: 'instant'
        });
      }
    }
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
    
    // Save scroll position before toggle
    this.saveScrollPosition(art);
    
    const prev = art.querySelector('.preview-html');
    prev.classList.toggle('collapsed');
    link.textContent = prev.classList.contains('collapsed') ? '展开' : '收起';
    
    // Restore scroll position after toggle
    setTimeout(() => {
      this.restoreScrollPosition();
    }, 0);
    
    // Track event using centralized tracker
    window.eventTracker.trackReadMore(art, prev.classList.contains('collapsed'));
  }

  markRead(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    
    // Save scroll position before removal
    this.saveScrollPosition(art);
    
    // Capture next card reference before removal
    const nextCard = art.nextElementSibling;
    
    fetch(window.appUrls.mark_read + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        art.remove();
        this.updateInfoBarCounts(-1, 1);
        
        // Scroll to next card after removal
        setTimeout(() => {
          this.scrollToNextCard(nextCard);
        }, 0);
        
        // Track event using centralized tracker
        window.eventTracker.trackMarkRead(art);
      }
    });
  }

  removeFromRead(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    
    // Save scroll position before removal
    this.saveScrollPosition(art);
    
    // Capture next card reference before removal
    const nextCard = art.nextElementSibling;
    
    fetch(window.appUrls.unmark_read + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        art.remove();
        
        // Scroll to next card after removal
        setTimeout(() => {
          this.scrollToNextCard(nextCard);
        }, 0);
        
        // Track event using centralized tracker
        window.eventTracker.trackUnmarkRead(art);
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
