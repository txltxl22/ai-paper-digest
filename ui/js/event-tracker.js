/**
 * Event Tracker - Frontend Module
 * 
 * Centralized event tracking system for the frontend.
 * Consolidates all event tracking logic from scattered JS files.
 */

class EventTracker {
  constructor() {
    this.endpoint = '/event';
    this.initialized = false;
  }

  /**
   * Initialize the event tracker
   */
  init() {
    if (this.initialized) return;
    
    // Set up global event listeners
    this.setupGlobalListeners();
    this.initialized = true;
  }

  /**
   * Set up global event listeners for automatic tracking
   */
  setupGlobalListeners() {
    // Track login form submissions
    document.getElementById('user-form')?.addEventListener('submit', () => {
      this.track('login');
    });

    // Track read list clicks
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('a[href*="/read"]');
      if (link) {
        this.track('read_list');
      }
    }, true);

    // Track favorites list clicks
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('a[href*="/favorites"]');
      if (link) {
        this.track('favorites_list');
      }
    }, true);

    // Track PDF opens
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('a.action-btn[href^="https://arxiv.org/pdf/"]');
      if (link) {
        const art = link.closest('article');
        const id = art ? art.getAttribute('data-id') : null;
        this.track('open_pdf', id, { href: link.getAttribute('href') });
      }
    }, true);
  }

  /**
   * Track an event
   * @param {string} type - Event type
   * @param {string} arxivId - Optional arXiv ID
   * @param {object} meta - Optional metadata
   */
  track(type, arxivId = null, meta = {}) {
    const payload = {
      type: type,
      arxiv_id: arxivId,
      meta: meta,
      ts: new Date().toISOString(),
      tz_offset_min: new Date().getTimezoneOffset()
    };

    try {
      navigator.sendBeacon(this.endpoint, JSON.stringify(payload));
    } catch(e) {
      console.warn('Failed to send event:', e);
    }
  }

  /**
   * Track article-related events
   */
  trackArticleEvent(type, articleElement, meta = {}) {
    const id = articleElement ? articleElement.getAttribute('data-id') : null;
    this.track(type, id, meta);
  }

  /**
   * Track user session events
   */
  trackSessionEvent(type) {
    this.track(type);
  }

  /**
   * Track mark as read
   */
  trackMarkRead(articleElement) {
    this.trackArticleEvent('mark_read', articleElement);
  }

  /**
   * Track unmark read
   */
  trackUnmarkRead(articleElement) {
    this.trackArticleEvent('unmark_read', articleElement);
  }

  /**
   * Track PDF open
   */
  trackPdfOpen(articleElement, href) {
    this.trackArticleEvent('open_pdf', articleElement, { href });
  }

  /**
   * Track login
   */
  trackLogin() {
    this.trackSessionEvent('login');
  }

  /**
   * Track logout
   */
  trackLogout() {
    this.trackSessionEvent('logout');
  }

  /**
   * Track read list view
   */
  trackReadList() {
    this.trackSessionEvent('read_list');
  }

  /**
   * Track reset
   */
  trackReset() {
    this.trackSessionEvent('reset');
  }

  /**
   * Track favorite/unfavorite
   */
  trackFavorite(articleElement, isFavorited) {
    const eventType = isFavorited ? 'mark_favorite' : 'unmark_favorite';
    this.trackArticleEvent(eventType, articleElement);
  }

  /**
   * Track unmark favorite from favorites page
   */
  trackUnmarkFavorite(articleElement) {
    this.trackArticleEvent('unmark_favorite', articleElement);
  }

  /**
   * Track favorites list view
   */
  trackFavoritesList() {
    this.trackSessionEvent('favorites_list');
  }

  /**
   * Track add to todo
   */
  trackAddToTodo(articleElement) {
    this.trackArticleEvent('mark_todo', articleElement);
  }

  /**
   * Track remove from todo
   */
  trackRemoveFromTodo(articleElement) {
    this.trackArticleEvent('unmark_todo', articleElement);
  }
}

// Create global event tracker instance
window.eventTracker = new EventTracker();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.eventTracker.init();
});
