/**
 * Search functionality for paper search
 */
class SearchManager {
    constructor() {
        this.searchInput = document.getElementById('search-input');
        this.searchSuggestions = document.getElementById('search-suggestions');
        this.searchTypeSelect = document.getElementById('search-type-select');
        this.suggestionTimeout = null;
        this.currentSuggestions = [];
        
        this.init();
    }
    
    init() {
        if (!this.searchInput) return;
        
        // Add event listeners
        this.searchInput.addEventListener('input', this.handleInput.bind(this));
        this.searchInput.addEventListener('focus', this.handleFocus.bind(this));
        this.searchInput.addEventListener('blur', this.handleBlur.bind(this));
        this.searchInput.addEventListener('keydown', this.handleKeydown.bind(this));
        
        // Add select change event listener
        if (this.searchTypeSelect) {
            this.searchTypeSelect.addEventListener('change', this.handleSelectChange.bind(this));
        }
        
        // Hide suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && !this.searchSuggestions.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }
    
    handleInput(e) {
        const query = e.target.value.trim();
        
        // Clear previous timeout
        if (this.suggestionTimeout) {
            clearTimeout(this.suggestionTimeout);
        }
        
        if (query.length < 2) {
            this.hideSuggestions();
            return;
        }
        
        // Debounce the suggestion request
        this.suggestionTimeout = setTimeout(() => {
            this.fetchSuggestions(query);
        }, 300);
    }
    
    handleFocus(e) {
        const query = e.target.value.trim();
        if (query.length >= 2 && this.currentSuggestions.length > 0) {
            this.showSuggestions(this.currentSuggestions);
        }
    }
    
    handleBlur(e) {
        // Delay hiding to allow clicking on suggestions
        setTimeout(() => {
            this.hideSuggestions();
        }, 200);
    }
    
    handleKeydown(e) {
        if (e.key === 'Escape') {
            this.hideSuggestions();
            this.searchInput.blur();
        } else if (e.key === 'Enter') {
            // Let the form submit normally
            this.hideSuggestions();
        }
    }
    
    handleSelectChange(e) {
        // If there's a search query, trigger a new search
        const query = this.searchInput.value.trim();
        if (query.length >= 2) {
            this.fetchSuggestions(query);
        }
    }
    
    async fetchSuggestions(query) {
        try {
            const searchType = this.getSelectedSearchType();
            const response = await fetch(`/search/suggest?q=${encodeURIComponent(query)}&search_type=${searchType}`);
            if (!response.ok) return;
            
            const data = await response.json();
            this.currentSuggestions = data.suggestions || [];
            
            if (this.currentSuggestions.length > 0) {
                this.showSuggestions(this.currentSuggestions);
            } else {
                this.hideSuggestions();
            }
        } catch (error) {
            console.error('Error fetching search suggestions:', error);
            this.hideSuggestions();
        }
    }
    
    getSelectedSearchType() {
        return this.searchTypeSelect ? this.searchTypeSelect.value : 'all';
    }
    
    showSuggestions(suggestions) {
        if (!this.searchSuggestions) return;
        
        this.searchSuggestions.innerHTML = '';
        
        suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion;
            item.addEventListener('click', () => {
                this.selectSuggestion(suggestion);
            });
            
            // Add hover effect
            item.addEventListener('mouseenter', () => {
                item.classList.add('hover');
            });
            item.addEventListener('mouseleave', () => {
                item.classList.remove('hover');
            });
            
            this.searchSuggestions.appendChild(item);
        });
        
        this.searchSuggestions.style.display = 'block';
    }
    
    hideSuggestions() {
        if (this.searchSuggestions) {
            this.searchSuggestions.style.display = 'none';
        }
    }
    
    selectSuggestion(suggestion) {
        this.searchInput.value = suggestion;
        this.hideSuggestions();
        
        // Trigger form submission
        const form = this.searchInput.closest('form');
        if (form) {
            form.submit();
        }
    }
}

// Initialize search manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SearchManager();
});
