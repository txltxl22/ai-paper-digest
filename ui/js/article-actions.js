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
      ev.stopPropagation();
      
      if (markReadElement.classList.contains('disabled')) {
        this.guideToLogin('标记为已读');
      } else {
        this.markRead(markReadElement);
      }
      return;
    }
      
    if (ev.target.matches('.remove-read-link')) {
      ev.preventDefault();
      this.removeFromRead(ev.target);
    }
    
    // Handle favorite-link clicks
    let favoriteElement = ev.target.closest('.favorite-link');
    if (favoriteElement) {
      console.log('Favorite clicked, preventing default');
      ev.preventDefault();
      ev.stopPropagation();
      
      if (favoriteElement.classList.contains('disabled')) {
        this.guideToLogin('收藏');
      } else {
        this.toggleFavorite(favoriteElement);
      }
      return;
    }
    
    // Handle favorite star button clicks
    let starButton = ev.target.closest('.favorite-star-btn');
    if (starButton) {
      ev.preventDefault();
      this.toggleFavoriteStar(starButton);
      return;
    }
    
    if (ev.target.matches('.remove-favorite-link')) {
      ev.preventDefault();
      this.removeFromFavorites(ev.target);
    }
  }

  guideToLogin(action) {
    // Show informative toast message
    showToast(`需要登录才能${action}，\n请在页面顶部输入任意用户名登陆`);
    
    // Just show toast, no focus behavior to avoid scrolling
    // User can manually click the login form if they want
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

  toggleFavorite(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    const isFavorited = link.getAttribute('data-favorited') === 'true';
    
    // Add loading state
    const originalText = link.textContent;
    link.textContent = isFavorited ? '取消中...' : '收藏中...';
    link.style.opacity = '0.6';
    link.style.pointerEvents = 'none';
    
    const url = isFavorited ? window.appUrls.unmark_favorite : window.appUrls.mark_favorite;
    
    fetch(url + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        const newFavorited = !isFavorited;
        
        // Update button state (no removal from page)
        link.setAttribute('data-favorited', newFavorited);
        link.textContent = newFavorited ? '取消收藏' : '收藏';
        link.style.opacity = '';
        link.style.pointerEvents = '';
        
        // Show success toast
        showToast(newFavorited ? '已添加到收藏 ⭐' : '已从收藏移除');
        
        // Track event
        window.eventTracker.trackFavorite(art, newFavorited);
      } else {
        // Restore original state on error
        link.textContent = originalText;
        link.style.opacity = '';
        link.style.pointerEvents = '';
        showToast('操作失败，请重试');
      }
    }).catch(() => {
      // Restore original state on error
      link.textContent = originalText;
      link.style.opacity = '';
      link.style.pointerEvents = '';
      showToast('网络错误，请重试');
    });
  }

  toggleFavoriteStar(button) {
    const art = button.closest('article');
    const id = button.getAttribute('data-id') || art.getAttribute('data-id');
    const isFavorited = button.getAttribute('data-favorited') === 'true';
    
    // Add loading state with animation
    button.style.opacity = '0.5';
    button.style.pointerEvents = 'none';
    button.style.transform = 'scale(0.9)';
    
    const url = isFavorited ? window.appUrls.unmark_favorite : window.appUrls.mark_favorite;
    
    fetch(url + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        const newFavorited = !isFavorited;
        
        // Update button state (no removal from page)
        button.setAttribute('data-favorited', newFavorited);
        const svg = button.querySelector('svg');
        if (svg) {
          svg.style.fill = newFavorited ? '#fbbf24' : 'none';
        }
        button.style.opacity = newFavorited ? '1' : '0.6';
        button.style.pointerEvents = '';
        button.style.transform = '';
        
        // Show success toast
        showToast(newFavorited ? '已添加到收藏 ⭐' : '已从收藏移除');
        
        // Track event
        window.eventTracker.trackFavorite(art, newFavorited);
      } else {
        // Restore original state on error
        button.style.opacity = '';
        button.style.pointerEvents = '';
        button.style.transform = '';
        showToast('操作失败，请重试');
      }
    }).catch(() => {
      // Restore original state on error
      button.style.opacity = '';
      button.style.pointerEvents = '';
      button.style.transform = '';
      showToast('网络错误，请重试');
    });
  }

  removeFromFavorites(link) {
    const art = link.closest('article');
    const id = art.getAttribute('data-id');
    
    // Save scroll position before removal
    this.saveScrollPosition(art);
    
    // Capture next card reference before removal
    const nextCard = art.nextElementSibling;
    
    fetch(window.appUrls.unmark_favorite + id, { method: 'POST' }).then(r => {
      if (r.ok) {
        art.remove();
        
        // Scroll to next card after removal
        setTimeout(() => {
          this.scrollToNextCard(nextCard);
        }, 0);
        
        // Track event using centralized tracker
        window.eventTracker.trackUnmarkFavorite(art);
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
