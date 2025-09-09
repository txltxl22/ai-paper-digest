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

      // Handle admin password requirement
      this.initAdminPasswordCheck();
      
      // Handle login errors and notifications
      this.handleLoginErrors();
      this.showPasswordNotification();
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

  initAdminPasswordCheck() {
    const uidInput = document.querySelector('input[name="uid"]');
    const passwordInput = document.getElementById('password-input');
    const adminUsers = window.adminUsers || [];

    if (!uidInput || !passwordInput) return;

    uidInput.addEventListener('input', async () => {
      const uid = uidInput.value.trim();
      const isAdmin = adminUsers.includes(uid);
      
      if (isAdmin) {
        // Admin users always need password field
        passwordInput.style.display = 'block';
        passwordInput.required = true;
        passwordInput.placeholder = '密码（管理员必填）';
      } else {
        // For non-admin users, check if they have a password
        if (uid) {
          await this.checkUserPasswordStatus(uid, passwordInput);
        } else {
          passwordInput.style.display = 'none';
          passwordInput.required = false;
          passwordInput.value = '';
        }
      }
    });
  }

  async checkUserPasswordStatus(uid, passwordInput) {
    try {
      // Check if user has a password by calling the password status API
      const response = await fetch(`/password_status?uid=${encodeURIComponent(uid)}`);
      if (response.ok) {
        const data = await response.json();
        if (data.has_password) {
          // User has a password, show password field
          passwordInput.style.display = 'block';
          passwordInput.required = true;
          passwordInput.placeholder = '密码（必填）';
        } else {
          // User doesn't have password, hide password field
          passwordInput.style.display = 'none';
          passwordInput.required = false;
          passwordInput.value = '';
          passwordInput.placeholder = '密码（如已设置）';
        }
      } else {
        // On error, assume user might have password
        passwordInput.style.display = 'block';
        passwordInput.required = false;
        passwordInput.placeholder = '密码（如已设置）';
      }
    } catch (error) {
      // On error, assume user might have password
      passwordInput.style.display = 'block';
      passwordInput.required = false;
      passwordInput.placeholder = '密码（如已设置）';
    }
  }

  handleLoginErrors() {
    // Check URL parameters for login errors
    const urlParams = new URLSearchParams(window.location.search);
    const error = urlParams.get('error');
    
    if (error === 'invalid_password') {
      this.showError('密码错误，请重新输入');
      
      // Show password field for non-admin users
      const passwordInput = document.getElementById('password-input');
      if (passwordInput) {
        passwordInput.style.display = 'block';
        passwordInput.required = true;
        passwordInput.focus();
      }
      
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  showPasswordNotification() {
    // Show notification for new users about password setting
    const urlParams = new URLSearchParams(window.location.search);
    const showNotification = urlParams.get('show_password_notification');
    
    if (showNotification === 'true') {
      this.showInfo('💡 提示：您可以随时点击用户名来设置密码');
      
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  showError(message) {
    this.showNotification(message, 'error');
  }

  showInfo(message) {
    this.showNotification(message, 'info');
  }

  showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
      <div class="notification-content">
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
      </div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 5000);
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
