/**
 * Abstract Viewer Module
 * 
 * Provides hover preview and click modal functionality for paper abstracts.
 * Handles on-demand fetching and caching of abstracts.
 */

class AbstractViewer {
    constructor() {
        this.hoverTimeout = null;
        this.currentPopover = null;
        this.currentModal = null;
        this.hoverDelay = 500; // ms
        this.cache = new Map(); // Cache for fetched abstracts
        
        this.init();
    }
    
    init() {
        // Bind event listeners
        document.addEventListener('mouseover', this.handleMouseOver.bind(this));
        document.addEventListener('mouseout', this.handleMouseOut.bind(this));
        document.addEventListener('click', this.handleClick.bind(this));
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }
    
    handleMouseOver(event) {
        const trigger = event.target.closest('.abstract-trigger');
        if (!trigger) return;
        
        // Clear any existing timeout
        if (this.hoverTimeout) {
            clearTimeout(this.hoverTimeout);
        }
        
        // Set timeout for hover preview
        this.hoverTimeout = setTimeout(() => {
            this.showPopover(trigger);
        }, this.hoverDelay);
    }
    
    handleMouseOut(event) {
        const trigger = event.target.closest('.abstract-trigger');
        if (!trigger) return;
        
        // Clear timeout if mouse leaves before delay
        if (this.hoverTimeout) {
            clearTimeout(this.hoverTimeout);
            this.hoverTimeout = null;
        }
        
        // Hide popover if mouse leaves the trigger area
        const relatedTarget = event.relatedTarget;
        if (!relatedTarget || !relatedTarget.closest('.abstract-popover')) {
            this.hidePopover();
        }
    }
    
    handleClick(event) {
        const trigger = event.target.closest('.abstract-trigger');
        if (!trigger) return;
        
        event.preventDefault();
        event.stopPropagation();
        
        // Clear hover timeout
        if (this.hoverTimeout) {
            clearTimeout(this.hoverTimeout);
            this.hoverTimeout = null;
        }
        
        // Hide popover and show modal
        this.hidePopover();
        this.showModal(trigger);
    }
    
    handleKeyDown(event) {
        // Close modal on Escape key
        if (event.key === 'Escape' && this.currentModal) {
            this.hideModal();
        }
    }
    
    async showPopover(trigger) {
        const arxivId = trigger.dataset.arxivId;
        const cachedAbstract = trigger.dataset.abstract;
        
        // Hide any existing popover
        this.hidePopover();
        
        // Create popover element
        const popover = this.createPopoverElement(arxivId, cachedAbstract);
        document.body.appendChild(popover);
        
        // Position popover
        this.positionPopover(popover, trigger);
        
        // Show popover
        requestAnimationFrame(() => {
            popover.classList.add('show');
        });
        
        this.currentPopover = popover;
        
        // Fetch abstract if not cached
        if (!cachedAbstract) {
            await this.fetchAbstractForPopover(arxivId, popover, trigger);
        }
    }
    
    hidePopover() {
        if (this.currentPopover) {
            this.currentPopover.classList.remove('show');
            setTimeout(() => {
                if (this.currentPopover && this.currentPopover.parentNode) {
                    this.currentPopover.parentNode.removeChild(this.currentPopover);
                }
                this.currentPopover = null;
            }, 200);
        }
    }
    
    createPopoverElement(arxivId, cachedAbstract) {
        const popover = document.createElement('div');
        popover.className = 'abstract-popover';
        
        if (cachedAbstract) {
            popover.innerHTML = `
                <div class="abstract-popover-arrow"></div>
                <div class="abstract-popover-header">
                    <span class="abstract-popover-icon">📄</span>
                    <span>摘要预览</span>
                </div>
                <div class="abstract-popover-text ${cachedAbstract.length > 300 ? 'truncated' : ''}">
                    ${cachedAbstract}
                </div>
                ${cachedAbstract.length > 300 ? `
                    <div class="abstract-popover-footer">
                        <button class="abstract-expand-btn" onclick="abstractViewer.showModal(document.querySelector('[data-arxiv-id=\\'${arxivId}\\']'))">
                            <span>📖</span>
                            <span>查看完整摘要</span>
                        </button>
                    </div>
                ` : ''}
            `;
        } else {
            popover.innerHTML = `
                <div class="abstract-popover-arrow"></div>
                <div class="abstract-popover-header">
                    <span class="abstract-popover-icon">⏳</span>
                    <span>正在获取摘要...</span>
                </div>
                <div class="abstract-popover-text">
                    正在从服务器获取摘要内容...
                </div>
            `;
        }
        
        return popover;
    }
    
    positionPopover(popover, trigger) {
        const triggerRect = trigger.getBoundingClientRect();
        const popoverRect = popover.getBoundingClientRect();
        
        // Position above the trigger
        let top = triggerRect.top - popoverRect.height - 10;
        let left = triggerRect.left + (triggerRect.width / 2) - (popoverRect.width / 2);
        
        // Adjust if popover goes off screen
        if (left < 10) left = 10;
        if (left + popoverRect.width > window.innerWidth - 10) {
            left = window.innerWidth - popoverRect.width - 10;
        }
        
        if (top < 10) {
            // Position below if no space above
            top = triggerRect.bottom + 10;
            popover.querySelector('.abstract-popover-arrow').style.transform = 'translateX(-50%) rotate(180deg)';
            popover.querySelector('.abstract-popover-arrow').style.top = 'auto';
            popover.querySelector('.abstract-popover-arrow').style.bottom = '-6px';
        }
        
        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
    }
    
    async fetchAbstractForPopover(arxivId, popover, trigger) {
        try {
            const response = await fetch(`/api/abstract/${arxivId}`);
            const data = await response.json();
            
            if (response.ok && data.abstract) {
                // Update popover content
                const header = popover.querySelector('.abstract-popover-header');
                const text = popover.querySelector('.abstract-popover-text');
                
                header.innerHTML = `
                    <span class="abstract-popover-icon">📄</span>
                    <span>摘要预览</span>
                `;
                
                text.className = `abstract-popover-text ${data.abstract.length > 300 ? 'truncated' : ''}`;
                text.textContent = data.abstract;
                
                // Add expand button if text is long
                if (data.abstract.length > 300) {
                    const footer = document.createElement('div');
                    footer.className = 'abstract-popover-footer';
                    footer.innerHTML = `
                        <button class="abstract-expand-btn" onclick="abstractViewer.showModal(document.querySelector('[data-arxiv-id=\\'${arxivId}\\']'))">
                            <span>📖</span>
                            <span>查看完整摘要</span>
                        </button>
                    `;
                    popover.appendChild(footer);
                }
                
                // Cache the abstract
                trigger.dataset.abstract = data.abstract;
                this.cache.set(arxivId, data.abstract);
            } else {
                // Show error
                const header = popover.querySelector('.abstract-popover-header');
                const text = popover.querySelector('.abstract-popover-text');
                
                header.innerHTML = `
                    <span class="abstract-popover-icon">❌</span>
                    <span>获取失败</span>
                `;
                text.textContent = data.message || '无法获取摘要';
            }
        } catch (error) {
            console.error('Error fetching abstract:', error);
            
            const header = popover.querySelector('.abstract-popover-header');
            const text = popover.querySelector('.abstract-popover-text');
            
            header.innerHTML = `
                <span class="abstract-popover-icon">❌</span>
                <span>网络错误</span>
            `;
            text.textContent = '网络连接失败，请稍后重试';
        }
    }
    
    async showModal(trigger) {
        const arxivId = trigger.dataset.arxivId;
        const cachedAbstract = trigger.dataset.abstract;
        const englishTitle = trigger.dataset.englishTitle;
        
        // Hide any existing modal
        this.hideModal();
        
        // Create modal element
        const modal = this.createModalElement(arxivId, cachedAbstract, englishTitle);
        document.body.appendChild(modal);
        
        // Show modal
        requestAnimationFrame(() => {
            modal.style.display = 'flex';
        });
        
        this.currentModal = modal;
        
        // Fetch abstract if not cached
        if (!cachedAbstract) {
            await this.fetchAbstractForModal(arxivId, modal, trigger, englishTitle);
        }
    }
    
    hideModal() {
        if (this.currentModal) {
            this.currentModal.style.display = 'none';
            setTimeout(() => {
                if (this.currentModal && this.currentModal.parentNode) {
                    this.currentModal.parentNode.removeChild(this.currentModal);
                }
                this.currentModal = null;
            }, 200);
        }
    }
    
    createModalElement(arxivId, cachedAbstract, englishTitle) {
        const modal = document.createElement('div');
        modal.className = 'abstract-modal';
        
        // Use English title if available, otherwise fall back to arxiv ID
        const titleText = englishTitle ? `Abstract - ${englishTitle}` : `Abstract - ${arxivId}`;
        
        if (cachedAbstract) {
            modal.innerHTML = `
                <div class="abstract-modal-content">
                    <div class="abstract-modal-header">
                        <div class="abstract-modal-title">
                            <span class="abstract-modal-icon">📄</span>
                            <span>${titleText}</span>
                        </div>
                        <button class="close-btn" onclick="abstractViewer.hideModal()">
                            <span class="close-icon">×</span>
                        </button>
                    </div>
                    <div class="abstract-modal-body">
                        <p class="abstract-modal-text">${cachedAbstract}</p>
                    </div>
                    <div class="abstract-modal-footer">
                        <button class="abstract-modal-close-btn" onclick="abstractViewer.hideModal()">
                            <span>关闭</span>
                        </button>
                    </div>
                </div>
            `;
        } else {
            modal.innerHTML = `
                <div class="abstract-modal-content">
                    <div class="abstract-modal-header">
                        <div class="abstract-modal-title">
                            <span class="abstract-modal-icon">📄</span>
                            <span>${titleText}</span>
                        </div>
                        <button class="close-btn" onclick="abstractViewer.hideModal()">
                            <span class="close-icon">×</span>
                        </button>
                    </div>
                    <div class="abstract-modal-body">
                        <div class="abstract-modal-loading">
                            <span class="abstract-modal-loading-icon">⏳</span>
                            <span>正在获取摘要...</span>
                        </div>
                    </div>
                    <div class="abstract-modal-footer">
                        <button class="abstract-modal-close-btn" onclick="abstractViewer.hideModal()">
                            <span>关闭</span>
                        </button>
                    </div>
                </div>
            `;
        }
        
        // Close modal when clicking outside
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.hideModal();
            }
        });
        
        return modal;
    }
    
    async fetchAbstractForModal(arxivId, modal, trigger, englishTitle) {
        try {
            const response = await fetch(`/api/abstract/${arxivId}`);
            const data = await response.json();
            
            if (response.ok && data.abstract) {
                // Update modal content
                const body = modal.querySelector('.abstract-modal-body');
                body.innerHTML = `
                    <p class="abstract-modal-text">${data.abstract}</p>
                `;
                
                // Cache the abstract
                trigger.dataset.abstract = data.abstract;
                this.cache.set(arxivId, data.abstract);
            } else {
                // Show error
                const body = modal.querySelector('.abstract-modal-body');
                body.innerHTML = `
                    <div class="abstract-modal-error">
                        <div class="abstract-modal-error-icon">❌</div>
                        <div class="abstract-modal-error-message">无法获取摘要</div>
                        <div class="abstract-modal-error-details">${data.message || '未知错误'}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error fetching abstract:', error);
            
            const body = modal.querySelector('.abstract-modal-body');
            body.innerHTML = `
                <div class="abstract-modal-error">
                    <div class="abstract-modal-error-icon">❌</div>
                    <div class="abstract-modal-error-message">网络错误</div>
                    <div class="abstract-modal-error-details">网络连接失败，请稍后重试</div>
                </div>
            `;
        }
    }
}

// Initialize the abstract viewer when DOM is loaded
let abstractViewer;
document.addEventListener('DOMContentLoaded', () => {
    abstractViewer = new AbstractViewer();
});

// Export for global access
window.abstractViewer = abstractViewer;
