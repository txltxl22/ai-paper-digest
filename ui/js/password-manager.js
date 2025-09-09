/**
 * Password Management JavaScript
 * Handles password modal, form submissions, and user interactions
 */

class PasswordManager {
    constructor() {
        this.modal = null;
        this.currentForm = null;
        this.passwordStatus = null;
        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupEventListeners());
        } else {
            this.setupEventListeners();
        }
    }

    setupEventListeners() {
        // User name click handler
        const userName = document.getElementById('user-name');
        if (userName) {
            userName.addEventListener('click', () => this.openPasswordModal());
        }

        // Modal elements
        this.modal = document.getElementById('password-modal');
        const closeBtn = document.getElementById('close-password-modal');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }

        // Close modal when clicking outside
        if (this.modal) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.closeModal();
                }
            });
        }

        // Form submissions
        this.setupFormHandlers();
        
        // Toggle form button
        const toggleBtn = document.getElementById('toggle-password-form');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.togglePasswordForm());
        }

        // Load password status on modal open
        this.passwordStatus = document.getElementById('password-status');
    }

    setupFormHandlers() {
        // Set password form
        const setPasswordForm = document.getElementById('set-password-form-element');
        if (setPasswordForm) {
            setPasswordForm.addEventListener('submit', (e) => this.handleSetPassword(e));
        }

        // Change password form
        const changePasswordForm = document.getElementById('change-password-form-element');
        if (changePasswordForm) {
            changePasswordForm.addEventListener('submit', (e) => this.handleChangePassword(e));
        }

        // Remove password form
        const removePasswordForm = document.getElementById('remove-password-form-element');
        if (removePasswordForm) {
            removePasswordForm.addEventListener('submit', (e) => this.handleRemovePassword(e));
        }
    }

    async openPasswordModal() {
        if (!this.modal) return;

        this.modal.style.display = 'flex';
        await this.loadPasswordStatus();
    }

    closeModal() {
        if (this.modal) {
            this.modal.style.display = 'none';
            this.clearForms();
        }
    }

    async loadPasswordStatus() {
        try {
            const response = await fetch('/password_status');
            const data = await response.json();

            if (response.ok) {
                this.updatePasswordStatus(data);
            } else {
                console.error('Failed to load password status:', data.error);
            }
        } catch (error) {
            console.error('Error loading password status:', error);
        }
    }

    updatePasswordStatus(status) {
        if (!this.passwordStatus) return;

        const { has_password, is_admin, requires_password } = status;
        
        // Store the status data for use in showAppropriateForm
        this.currentPasswordStatus = status;
        
        let statusHtml = '<h4>密码状态</h4>';
        
        if (has_password) {
            statusHtml += '<p>✅ 已设置密码</p>';
        } else {
            statusHtml += '<p>❌ 未设置密码</p>';
        }
        
        if (is_admin) {
            statusHtml += '<p>👑 管理员用户</p>';
            if (requires_password) {
                statusHtml += '<p>⚠️ 管理员登录需要密码</p>';
            }
        } else {
            statusHtml += '<p>👤 普通用户</p>';
        }

        this.passwordStatus.innerHTML = statusHtml;
        
        // Immediately show appropriate form after updating status
        this.showAppropriateForm();
    }

    showAppropriateForm() {
        // Hide all forms first
        this.hideAllForms();

        // Show toggle button and modal actions only if user has a password
        const toggleBtn = document.getElementById('toggle-password-form');
        const modalActions = document.getElementById('modal-actions');
        
        if (this.currentPasswordStatus && this.currentPasswordStatus.has_password) {
            if (toggleBtn) {
                toggleBtn.style.display = 'inline-flex';
            }
            if (modalActions) {
                modalActions.style.display = 'flex';
            }
        } else {
            if (toggleBtn) {
                toggleBtn.style.display = 'none';
            }
            if (modalActions) {
                modalActions.style.display = 'none';
            }
        }

        // Show appropriate form based on password status
        if (this.currentPasswordStatus) {
            const { has_password } = this.currentPasswordStatus;
            
            if (!has_password) {
                // User doesn't have a password, show set password form
                this.showForm('set-password-form');
            } else {
                // User has a password, show change password form
                this.showForm('change-password-form');
            }
        } else {
            // Fallback: show set password form if status is not available
            this.showForm('set-password-form');
        }
    }

    hideAllForms() {
        const forms = ['set-password-form', 'change-password-form', 'remove-password-form'];
        forms.forEach(formId => {
            const form = document.getElementById(formId);
            if (form) {
                form.style.display = 'none';
            }
        });
    }

    showForm(formId) {
        this.hideAllForms();
        const form = document.getElementById(formId);
        if (form) {
            form.style.display = 'block';
            this.currentForm = formId;
        }
    }

    togglePasswordForm() {
        if (this.currentForm === 'change-password-form') {
            this.showForm('remove-password-form');
        } else if (this.currentForm === 'remove-password-form') {
            this.showForm('change-password-form');
        }
    }

    async handleSetPassword(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const password = formData.get('password');
        const confirmPassword = formData.get('confirm_password');

        // Validate passwords match
        if (password !== confirmPassword) {
            this.showError('密码不匹配');
            return;
        }

        try {
            const response = await fetch('/set_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess('密码设置成功');
                await this.loadPasswordStatus();
                this.showAppropriateForm();
            } else {
                this.showError(data.error || '设置密码失败');
            }
        } catch (error) {
            console.error('Error setting password:', error);
            this.showError('设置密码时发生错误');
        }
    }

    async handleChangePassword(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const oldPassword = formData.get('old_password');
        const newPassword = formData.get('new_password');
        const confirmPassword = formData.get('confirm_password');

        // Validate passwords match
        if (newPassword !== confirmPassword) {
            this.showError('新密码不匹配');
            return;
        }

        try {
            const response = await fetch('/change_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    old_password: oldPassword,
                    new_password: newPassword 
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess('密码修改成功');
                this.clearForm('change-password-form-element');
            } else {
                this.showError(data.error || '修改密码失败');
            }
        } catch (error) {
            console.error('Error changing password:', error);
            this.showError('修改密码时发生错误');
        }
    }

    async handleRemovePassword(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const password = formData.get('password');

        try {
            const response = await fetch('/remove_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess('密码移除成功');
                await this.loadPasswordStatus();
                this.showAppropriateForm();
            } else {
                this.showError(data.error || '移除密码失败');
            }
        } catch (error) {
            console.error('Error removing password:', error);
            this.showError('移除密码时发生错误');
        }
    }

    clearForm(formId) {
        const form = document.getElementById(formId);
        if (form) {
            form.reset();
        }
    }

    clearForms() {
        const forms = ['set-password-form-element', 'change-password-form-element', 'remove-password-form-element'];
        forms.forEach(formId => this.clearForm(formId));
    }

    showSuccess(message) {
        // You can integrate with your existing toast system here
        console.log('Success:', message);
        // For now, just show an alert
        alert('✅ ' + message);
    }

    showError(message) {
        // You can integrate with your existing toast system here
        console.error('Error:', message);
        // For now, just show an alert
        alert('❌ ' + message);
    }
}

// Initialize password manager when script loads
const passwordManager = new PasswordManager();
