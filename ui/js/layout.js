// Layout manager - Note: Header is position:sticky, so it naturally takes space
// This function is kept for legacy compatibility but does nothing
// The sticky header and fixed status bar handle their own positioning
function adjustMainPadding() {
  // No longer needed since:
  // 1. Header is sticky - naturally takes up space in document flow
  // 2. Status bar is fixed - overlays content intentionally
  // 3. Main content has its own padding in CSS
}

// Keep event listeners for compatibility
window.addEventListener('load', adjustMainPadding);
window.addEventListener('resize', adjustMainPadding);
document.addEventListener('DOMContentLoaded', adjustMainPadding);

// Export for other scripts to call (e.g. deep-read-status.js)
window.adjustLayout = adjustMainPadding;

