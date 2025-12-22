/**
 * Mobile Navigation Handler
 * Handles mobile menu toggle, overlay interactions, and mobile-specific functionality
 */

class MobileNavigation {
    constructor() {
        this.mobileMenuToggle = document.getElementById('mobile-menu-toggle');
        this.miniHeaderMenuBtn = document.getElementById('mini-header-menu-btn');
        this.mobileNavOverlay = document.getElementById('mobile-nav-overlay');
        this.mobileNavClose = document.getElementById('mobile-nav-close');
        this.mobileNavContent = document.querySelector('.mobile-nav-content');
        
        // Mobile-specific buttons
        this.mobileLogoutBtn = document.getElementById('mobile-logout-btn');
        this.mobileAdminFetchBtn = document.getElementById('mobile-admin-fetch-btn');
        this.mobileThemeToggle = document.getElementById('mobile-theme-toggle');
        this.mobileUserForm = document.getElementById('mobile-user-form');
        
        // Desktop buttons (for delegation)
        this.desktopLogoutBtn = document.getElementById('logout-btn');
        this.desktopAdminFetchBtn = document.getElementById('admin-fetch-btn');
        this.desktopThemeToggle = document.getElementById('theme-toggle');
        this.desktopUserForm = document.getElementById('user-form');
        
        this.isMenuOpen = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.setupMobileDelegation();
    }
    
    bindEvents() {
        // Menu toggle events
        if (this.mobileMenuToggle) {
            this.mobileMenuToggle.addEventListener('click', () => this.toggleMenu());
        }
        
        // Mini-header menu button (appears when main header scrolls away)
        if (this.miniHeaderMenuBtn) {
            this.miniHeaderMenuBtn.addEventListener('click', () => this.toggleMenu());
        }
        
        if (this.mobileNavClose) {
            this.mobileNavClose.addEventListener('click', () => this.closeMenu());
        }
        
        // Overlay click to close
        if (this.mobileNavOverlay) {
            this.mobileNavOverlay.addEventListener('click', (e) => {
                if (e.target === this.mobileNavOverlay) {
                    this.closeMenu();
                }
            });
        }
        
        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isMenuOpen) {
                this.closeMenu();
            }
        });
        
        // Prevent body scroll when menu is open
        this.mobileNavOverlay.addEventListener('transitionstart', () => {
            if (this.isMenuOpen) {
                document.body.style.overflow = 'hidden';
            }
        });
        
        this.mobileNavOverlay.addEventListener('transitionend', () => {
            if (!this.isMenuOpen) {
                document.body.style.overflow = '';
            }
        });
    }
    
    setupMobileDelegation() {
        // Mobile logout button delegates to desktop logout
        if (this.mobileLogoutBtn && this.desktopLogoutBtn) {
            this.mobileLogoutBtn.addEventListener('click', () => {
                this.desktopLogoutBtn.click();
                this.closeMenu();
            });
        }
        
        // Mobile admin fetch button delegates to desktop admin fetch
        if (this.mobileAdminFetchBtn && this.desktopAdminFetchBtn) {
            this.mobileAdminFetchBtn.addEventListener('click', () => {
                this.desktopAdminFetchBtn.click();
                this.closeMenu();
            });
        }
        
        // Mobile theme toggle delegates to desktop theme toggle
        if (this.mobileThemeToggle && this.desktopThemeToggle) {
            this.mobileThemeToggle.addEventListener('click', () => {
                this.desktopThemeToggle.click();
                this.closeMenu();
            });
        }
        
        // Mobile login form delegates to desktop login form
        if (this.mobileUserForm && this.desktopUserForm) {
            this.mobileUserForm.addEventListener('submit', (e) => {
                // Copy the input value to desktop form
                const mobileInput = this.mobileUserForm.querySelector('input[name="uid"]');
                const desktopInput = this.desktopUserForm.querySelector('input[name="uid"]');
                
                if (mobileInput && desktopInput) {
                    desktopInput.value = mobileInput.value;
                }
                
                // Submit the desktop form
                this.desktopUserForm.submit();
                this.closeMenu();
            });
        }
    }
    
    toggleMenu() {
        if (this.isMenuOpen) {
            this.closeMenu();
        } else {
            this.openMenu();
        }
    }
    
    openMenu() {
        this.isMenuOpen = true;
        if (this.mobileMenuToggle) {
            this.mobileMenuToggle.classList.add('active');
        }
        if (this.miniHeaderMenuBtn) {
            this.miniHeaderMenuBtn.classList.add('active');
        }
        this.mobileNavOverlay.classList.add('active');
        
        // Update theme button icon in mobile menu
        this.updateMobileThemeIcon();
    }
    
    closeMenu() {
        this.isMenuOpen = false;
        if (this.mobileMenuToggle) {
            this.mobileMenuToggle.classList.remove('active');
        }
        if (this.miniHeaderMenuBtn) {
            this.miniHeaderMenuBtn.classList.remove('active');
        }
        this.mobileNavOverlay.classList.remove('active');
    }
    
    updateMobileThemeIcon() {
        if (this.mobileThemeToggle && this.desktopThemeToggle) {
            const desktopIcon = this.desktopThemeToggle.textContent;
            const mobileIcon = this.mobileThemeToggle.querySelector('.nav-icon');
            if (mobileIcon) {
                mobileIcon.textContent = desktopIcon;
            }
        }
    }
    
    // Handle window resize
    handleResize() {
        if (window.innerWidth > 768 && this.isMenuOpen) {
            this.closeMenu();
        }
    }
    
    // Handle mobile login focus
    focusMobileLogin() {
        if (window.innerWidth <= 768) {
            // Open mobile menu if not already open
            if (!this.isMenuOpen) {
                this.openMenu();
            }
            
            // Focus on mobile login input after menu animation
            setTimeout(() => {
                const mobileLoginInput = document.querySelector('.mobile-login-input');
                if (mobileLoginInput) {
                    mobileLoginInput.focus();
                    mobileLoginInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }, 350); // Wait for slide animation to complete
        } else {
            // Desktop: focus on desktop login input
            const desktopLoginInput = document.querySelector('#user-form input[name="uid"]');
            if (desktopLoginInput) {
                desktopLoginInput.focus();
            }
        }
    }
}

// Initialize mobile navigation when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if mobile elements exist
    if (document.getElementById('mobile-menu-toggle')) {
        window.mobileNav = new MobileNavigation();
        
        // Handle window resize
        window.addEventListener('resize', () => {
            window.mobileNav.handleResize();
        });
    }
});

// Global function for handling mobile login
function handleMobileLogin() {
    if (window.mobileNav) {
        window.mobileNav.focusMobileLogin();
    } else {
        // Fallback for desktop or if mobile nav not initialized
        const desktopLoginInput = document.querySelector('#user-form input[name="uid"]');
        if (desktopLoginInput) {
            desktopLoginInput.focus();
        }
    }
}

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MobileNavigation;
}
