// Header Scroll Behavior - Modern Design
// Manages sticky header, deep read status bar positioning, and mobile mini-header
// 
// Design Rules:
// 1. Desktop & Mobile: When header is in screen (even partially covered), status bar is below it
// 2. Desktop & Mobile: When header is out of screen, status bar moves to top (if it has items)
// 3. Mobile only: When header is out of screen, show compact mini-header at top
// 4. Mobile: Paper submission FAB remains at bottom-right (no conflict)
(function() {
  let lastScrollY = window.scrollY;
  let headerHeight = 0;
  let ticking = false;
  
  function updateHeaderState() {
    const header = document.querySelector('header');
    const deepReadBar = document.querySelector('.deep-read-status-bar-fixed');
    
    if (!header) return;
    
    // Get header height
    headerHeight = header.offsetHeight;
    
    // Update CSS variable for header height
    document.documentElement.style.setProperty('--header-height', `${headerHeight}px`);
    
    // Check if header is in viewport
    // Modern design: header is "visible" if any part of it is in the viewport
    const headerRect = header.getBoundingClientRect();
    const isHeaderInScreen = headerRect.bottom > 0;
    
    // Update body classes for styling
    if (isHeaderInScreen) {
      document.body.classList.add('header-visible');
      document.body.classList.remove('header-hidden');
    } else {
      document.body.classList.remove('header-visible');
      document.body.classList.add('header-hidden');
    }
    
    // Update deep read status bar position if it exists and is visible
    if (deepReadBar && deepReadBar.style.display !== 'none') {
      const hasItems = deepReadBar.querySelector('.status-items')?.children.length > 0;
      
      if (isHeaderInScreen) {
        // Header is in screen - status bar below it (modern layered design)
        deepReadBar.style.top = `${headerHeight}px`;
        deepReadBar.style.zIndex = '999'; // Below header
      } else if (hasItems) {
        // Header is out of screen and status bar has items
        // On mobile: position below mini-header (48px), on desktop: at top
        const isMobile = window.innerWidth <= 768;
        if (isMobile) {
          deepReadBar.style.top = '48px'; // Below mini-header
          deepReadBar.style.zIndex = '1001'; // Below mini-header
        } else {
          deepReadBar.style.top = '0px'; // At top
          deepReadBar.style.zIndex = '1001'; // Above everything
        }
      }
    }
  }
  
  function onScroll() {
    lastScrollY = window.scrollY;
    requestTick();
  }
  
  function requestTick() {
    if (!ticking) {
      window.requestAnimationFrame(update);
      ticking = true;
    }
  }
  
  function update() {
    updateHeaderState();
    ticking = false;
  }
  
  // Initialize on DOM ready
  function init() {
    // Initial update
    updateHeaderState();
    
    // Listen to scroll events
    window.addEventListener('scroll', onScroll, { passive: true });
    
    // Listen to resize events
    window.addEventListener('resize', () => {
      updateHeaderState();
    }, { passive: true });
    
    // Update when deep read status bar changes
    const observer = new MutationObserver(() => {
      updateHeaderState();
    });
    
    const deepReadBar = document.querySelector('.deep-read-status-bar-fixed');
    if (deepReadBar) {
      observer.observe(deepReadBar, {
        attributes: true,
        attributeFilter: ['style'],
        childList: true,
        subtree: true
      });
    }
    
    // Export updateHeaderState for other scripts to call
    window.updateHeaderState = updateHeaderState;
  }
  
  // Initialize on different page load events
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  // Also initialize on page show (for back/forward navigation)
  window.addEventListener('pageshow', (event) => {
    // Update state on page show, especially for cached pages
    setTimeout(init, 0);
  });
})();

