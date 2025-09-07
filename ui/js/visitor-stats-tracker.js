/**
 * Visitor Stats Tracker
 * 
 * Automatically tracks page views and user actions for analytics.
 */

class VisitorStatsTracker {
    constructor() {
        this.userId = this.getUserId();
        this.sessionId = this.getOrCreateSessionId();
        this.currentPage = window.location.pathname;
        this.referrer = document.referrer;
        this.userAgent = navigator.userAgent;
        
        // Track page view on page load
        this.trackPageView();
        
        // Track actions
        this.setupActionTracking();
    }
    
    getUserId() {
        // Try to get user ID from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'uid') {
                return value;
            }
        }
        return 'anonymous';
    }
    
    getOrCreateSessionId() {
        // Try to get session ID from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'session_id') {
                return value;
            }
        }
        
        // Create new session ID
        const sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
        
        // Set cookie for 30 days
        const expires = new Date();
        expires.setDate(expires.getDate() + 30);
        document.cookie = `session_id=${sessionId}; expires=${expires.toUTCString()}; path=/`;
        
        return sessionId;
    }
    
    async trackPageView() {
        try {
            const response = await fetch('/stats/track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    page: this.currentPage,
                    referrer: this.referrer,
                    user_agent: this.userAgent,
                    session_id: this.sessionId
                })
            });
            
            if (!response.ok) {
                console.warn('Failed to track page view:', response.status);
            }
        } catch (error) {
            console.warn('Error tracking page view:', error);
        }
    }
    
    async trackAction(actionType, page = null, arxivId = null, metadata = {}) {
        try {
            const response = await fetch('/stats/track/action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    action_type: actionType,
                    page: page || this.currentPage,
                    arxiv_id: arxivId,
                    metadata: metadata,
                    session_id: this.sessionId
                })
            });
            
            if (!response.ok) {
                console.warn('Failed to track action:', response.status);
            }
        } catch (error) {
            console.warn('Error tracking action:', error);
        }
    }
    
    setupActionTracking() {
        // Track mark read actions
        document.addEventListener('click', (event) => {
            const target = event.target;
            
            // Mark read button
            if (target.classList.contains('mark-read-btn') || 
                target.closest('.mark-read-btn')) {
                const arxivId = target.dataset.arxivId || 
                              target.closest('[data-arxiv-id]')?.dataset.arxivId;
                this.trackAction('mark_read', this.currentPage, arxivId);
            }
            
            // Unmark read button
            if (target.classList.contains('unmark-read-btn') || 
                target.closest('.unmark-read-btn')) {
                const arxivId = target.dataset.arxivId || 
                              target.closest('[data-arxiv-id]')?.dataset.arxivId;
                this.trackAction('unmark_read', this.currentPage, arxivId);
            }
            
            // Read more button
            if (target.classList.contains('read-more-btn') || 
                target.closest('.read-more-btn')) {
                const arxivId = target.dataset.arxivId || 
                              target.closest('[data-arxiv-id]')?.dataset.arxivId;
                this.trackAction('read_more', this.currentPage, arxivId);
            }
            
            // Open PDF button
            if (target.classList.contains('open-pdf-btn') || 
                target.closest('.open-pdf-btn')) {
                const arxivId = target.dataset.arxivId || 
                              target.closest('[data-arxiv-id]')?.dataset.arxivId;
                this.trackAction('open_pdf', this.currentPage, arxivId);
            }
            
            // Login button
            if (target.classList.contains('login-btn') || 
                target.closest('.login-btn')) {
                this.trackAction('login', this.currentPage);
            }
            
            // Logout button
            if (target.classList.contains('logout-btn') || 
                target.closest('.logout-btn')) {
                this.trackAction('logout', this.currentPage);
            }
            
            // Reset button
            if (target.classList.contains('reset-btn') || 
                target.closest('.reset-btn')) {
                this.trackAction('reset', this.currentPage);
            }
            
            // Paper submission
            if (target.classList.contains('submit-paper-btn') || 
                target.closest('.submit-paper-btn')) {
                this.trackAction('submit_paper', this.currentPage);
            }
            
            // Tag filter
            if (target.classList.contains('tag-filter-btn') || 
                target.closest('.tag-filter-btn')) {
                const tag = target.dataset.tag || 
                           target.closest('[data-tag]')?.dataset.tag;
                this.trackAction('filter_by_tag', this.currentPage, null, { tag });
            }
        });
        
        // Track form submissions
        document.addEventListener('submit', (event) => {
            const form = event.target;
            
            if (form.classList.contains('paper-submission-form')) {
                this.trackAction('submit_paper_form', this.currentPage);
            }
            
            if (form.classList.contains('login-form')) {
                this.trackAction('login_form', this.currentPage);
            }
        });
        
        // Track navigation
        document.addEventListener('click', (event) => {
            const link = event.target.closest('a');
            if (link && link.href && !link.href.startsWith('javascript:')) {
                const href = link.href;
                if (href.includes('/detail/')) {
                    const arxivId = href.split('/detail/')[1];
                    this.trackAction('navigate_to_detail', this.currentPage, arxivId);
                } else if (href.includes('arxiv.org')) {
                    this.trackAction('navigate_to_arxiv', this.currentPage);
                }
            }
        });
    }
}

// Initialize visitor stats tracker when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.visitorStatsTracker = new VisitorStatsTracker();
});

// Export for use in other modules
window.VisitorStatsTracker = VisitorStatsTracker;
