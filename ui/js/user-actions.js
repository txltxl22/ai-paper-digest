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
    // Get all uid inputs (both desktop and mobile)
    const uidInputs = document.querySelectorAll('input[name="uid"]');
    const passwordInput = document.getElementById('password-input');
    const mobilePasswordInput = document.getElementById('mobile-password-input');
    const mobilePasswordItem = document.getElementById('mobile-password-item');
    const adminUsers = window.adminUsers || [];

    if (uidInputs.length === 0) return;

    const updatePasswordField = async (isAdmin, uid, passwordField, passwordContainer) => {
      // Handle container display (for mobile)
      if (passwordContainer) {
        if (isAdmin) {
          passwordContainer.style.display = 'flex';
        } else if (uid) {
          // Will be updated by checkUserPasswordStatus
        } else {
          passwordContainer.style.display = 'none';
        }
      }
      
      // Handle password field itself
      if (!passwordField) return;
      
      if (isAdmin) {
        // Admin users always need password field
        if (!passwordContainer) {
          passwordField.style.display = 'block';
        }
        passwordField.required = true;
        passwordField.placeholder = '密码（管理员必填）';
      } else {
        // For non-admin users, check if they have a password
        if (uid) {
          await this.checkUserPasswordStatus(uid, passwordField, passwordContainer);
        } else {
          if (!passwordContainer) {
            passwordField.style.display = 'none';
          }
          passwordField.required = false;
          passwordField.value = '';
        }
      }
    };

    const checkAndUpdate = async (inputElement) => {
      const uid = inputElement.value.trim();
      const isAdmin = adminUsers.includes(uid);
      
      // Update both desktop and mobile password fields to keep them in sync
      // This ensures the password field shows regardless of which input is being used
      updatePasswordField(isAdmin, uid, passwordInput, null);
      updatePasswordField(isAdmin, uid, mobilePasswordInput, mobilePasswordItem);
    };

    // Attach event listeners to all uid inputs
    uidInputs.forEach(uidInput => {
      uidInput.addEventListener('input', () => checkAndUpdate(uidInput));
      
      // Also check on initial load in case there's a pre-filled value
      if (uidInput.value.trim()) {
        checkAndUpdate(uidInput);
      }
    });
  }

  async checkUserPasswordStatus(uid, passwordInput, passwordContainer) {
    try {
      // Check if user has a password by calling the password status API
      const response = await fetch(`/password_status?uid=${encodeURIComponent(uid)}`);
      if (response.ok) {
        const data = await response.json();
        if (data.has_password) {
          // User has a password, show password field
          if (passwordContainer) {
            passwordContainer.style.display = 'flex';
          } else {
            passwordInput.style.display = 'block';
          }
          passwordInput.required = true;
          passwordInput.placeholder = '密码（必填）';
        } else {
          // User doesn't have password, hide password field
          if (passwordContainer) {
            passwordContainer.style.display = 'none';
          } else {
            passwordInput.style.display = 'none';
          }
          passwordInput.required = false;
          passwordInput.value = '';
          passwordInput.placeholder = '密码（如已设置）';
        }
      } else {
        // On error, assume user might have password
        if (passwordContainer) {
          passwordContainer.style.display = 'flex';
        } else {
          passwordInput.style.display = 'block';
        }
        passwordInput.required = false;
        passwordInput.placeholder = '密码（如已设置）';
      }
    } catch (error) {
      // On error, assume user might have password
      if (passwordContainer) {
        passwordContainer.style.display = 'flex';
      } else {
        passwordInput.style.display = 'block';
      }
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
      
      // Show password field for non-admin users (desktop)
      const passwordInput = document.getElementById('password-input');
      if (passwordInput) {
        passwordInput.style.display = 'block';
        passwordInput.required = true;
        passwordInput.focus();
      }
      
      // Show password field for non-admin users (mobile)
      const mobilePasswordInput = document.getElementById('mobile-password-input');
      const mobilePasswordItem = document.getElementById('mobile-password-item');
      if (mobilePasswordInput && mobilePasswordItem) {
        mobilePasswordItem.style.display = 'flex';
        mobilePasswordInput.required = true;
        mobilePasswordInput.focus();
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
