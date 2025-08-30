// Theme Management Module
class ThemeManager {
  constructor() {
    this.init();
  }

  init() {
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const saved = localStorage.getItem('theme');
    const theme = saved === 'dark' || saved === 'light' ? saved : (prefersDark ? 'dark' : 'light');
    
    this.apply(theme);
    
    document.addEventListener('DOMContentLoaded', () => {
      this.apply(document.documentElement.getAttribute('data-theme') || theme);
    });
    
    document.addEventListener('click', (ev) => {
      if (ev.target && ev.target.id === 'theme-toggle') {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', next);
        this.apply(next);
      }
    });
  }

  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : 'light');
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
