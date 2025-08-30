// Toast Notification Module
class ToastManager {
  constructor() {
    this.timer = null;
  }

  show(message, duration = 3000) {
    let toast = document.getElementById('toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'toast';
      document.body.appendChild(toast);
    }
    
    toast.textContent = message;
    toast.classList.add('show');

    clearTimeout(this.timer);
    this.timer = setTimeout(() => toast.classList.remove('show'), duration);
  }
}

// Global toast instance
window.showToast = (msg, duration = 3000) => {
  if (!window.toastManager) {
    window.toastManager = new ToastManager();
  }
  window.toastManager.show(msg, duration);
};
