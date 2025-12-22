/**
 * Theme Management Module
 * 
 * Handles dark/light theme switching with localStorage persistence.
 * 
 * Architecture:
 * - Initial theme is applied inline in HTML <head> to prevent flash
 * - This module only handles theme toggle button updates and user interactions
 * - Theme state is stored in localStorage as 'theme' key ('dark' or 'light')
 * - Falls back to system preference if no saved theme exists
 * 
 * Usage:
 * - Automatically initializes on script load
 * - Desktop: Click #theme-toggle button
 * - Mobile: Mobile nav delegates to desktop button
 * 
 * @class ThemeManager
 */
class ThemeManager {
  constructor() {
    this.init();
  }

  /**
   * Initialize theme manager
   * Sets up event listeners for theme toggle
   */
  init() {
    // Theme is already applied inline in HTML <head> to prevent flash
    // Just update the toggle button when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
      const theme = document.documentElement.getAttribute('data-theme') || 'light';
      this.updateButton(theme);
    });
    
    // Handle theme toggle clicks
    document.addEventListener('click', (ev) => {
      if (ev.target && ev.target.id === 'theme-toggle') {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', next);
        this.apply(next);
      }
    });
  }

  /**
   * Apply theme to document and update button
   * @param {string} theme - Theme name ('dark' or 'light')
   */
  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : 'light');
    this.updateButton(theme);
  }

  /**
   * Update theme toggle button icon and accessibility attributes
   * @param {string} theme - Current theme name ('dark' or 'light')
   */
  updateButton(theme) {
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      const icon = theme === 'dark' ? btn.getAttribute('data-icon-dark') : btn.getAttribute('data-icon-light');
      btn.textContent = icon || (theme === 'dark' ? '☀️' : '🌙');
      btn.setAttribute('title', theme === 'dark' ? '切换到日间模式' : '切换到夜间模式');
      btn.setAttribute('aria-label', theme === 'dark' ? '切换到日间模式' : '切换到夜间模式');
    }
  }
}

// Initialize theme manager
new ThemeManager();
