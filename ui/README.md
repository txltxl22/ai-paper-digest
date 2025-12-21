# UI Frontend Documentation

Clean, modular frontend architecture with reusable components, organized CSS, and maintainable JavaScript.

## Directory Structure

```
ui/
├── components/      # Reusable HTML components (Jinja2 templates)
├── css/            # Modular stylesheets
├── js/             # JavaScript modules
├── *.html          # Main page templates
└── base.css        # Core styles + CSS variables
```

## Quick Start

### Adding a New Page

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Theme script MUST be first to prevent flash -->
  <script>
    (function() {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const saved = localStorage.getItem('theme');
      const theme = saved === 'dark' || saved === 'light' ? saved : (prefersDark ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', theme);
    })();
  </script>
  
  <!-- CSS in order: base → badges → components → modal -->
  <link rel="stylesheet" href="{{ base_css_versioned() }}">
  <link rel="stylesheet" href="{{ static_css_versioned('badges.css') }}">
  <link rel="stylesheet" href="{{ static_css_versioned('components.css') }}">
  <link rel="stylesheet" href="{{ static_css_versioned('modal.css') }}">
</head>
<body>
  {% include 'components/header.html' %}
  <main><!-- content --></main>
  
  <!-- JS: core first, then features -->
  <script src="{{ url_for('static_js', filename='event-tracker.js') }}"></script>
  <script src="{{ url_for('static_js', filename='theme.js') }}"></script>
  <script src="{{ url_for('static_js', filename='toast.js') }}"></script>
</body>
</html>
```

### Using Components

```jinja2
{% include 'components/header.html' %}
{% include 'components/tag-filter.html' %}
{% include 'components/trending-section.html' %}

{% for e in entries %}
  {% include 'components/article-card.html' %}
{% endfor %}

{% include 'components/pagination.html' %}
```

## Components Reference

| Component | Purpose |
|-----------|---------|
| `header.html` | Site header, nav, login |
| `article-card.html` | Paper display card |
| `tag-filter.html` | Search and filter UI |
| `trending-section.html` | Trending tags with tabs |
| `pagination.html` | Page navigation |
| `paper-submission.html` | Paper URL form |
| `sidebar-submission.html` | Desktop sidebar + mobile FAB |
| `admin-modal.html` | Admin operations modal |
| `deep-read-status.html` | Processing status bar |

## CSS Guidelines

### Always Use CSS Variables

```css
/* ✅ Good - Theme-aware */
.element {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--divider);
  padding: var(--spacing-lg);
}

/* ❌ Bad - Hard-coded */
.element {
  background: #ffffff;
  color: #000000;
}
```

### Common CSS Variables

```css
/* Colors */
--text              /* Primary text */
--muted-text        /* Secondary text */
--card-bg           /* Card background */
--primary           /* Brand color */
--divider           /* Borders */

/* Spacing */
--spacing-sm        /* 0.5rem */
--spacing-md        /* 0.75rem */
--spacing-lg        /* 1rem */
--spacing-xl        /* 1.5rem */

/* Border Radius */
--radius-sm         /* 4px */
--radius-md         /* 8px */
--radius-lg         /* 12px */
```

### Responsive Breakpoints

```css
/* Mobile first */
.element { flex-direction: column; }

@media (min-width: 768px) {  /* Tablet */
  .element { flex-direction: row; }
}

@media (min-width: 1200px) {  /* Desktop */
  .element { max-width: 1200px; }
}
```

## JavaScript Patterns

### Module Template

```javascript
/**
 * MyModule - Description
 * @class MyModule
 */
class MyModule {
  constructor() {
    this.init();
  }

  init() {
    // Use event delegation
    document.addEventListener('click', (ev) => {
      if (ev.target.matches('.my-selector')) {
        this.handleClick(ev);
      }
    });
  }

  handleClick(event) {
    event.preventDefault();
    // Handle click
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  new MyModule();
});
```

### Common Operations

```javascript
// Show toast notification
window.showToast('Message', 3000);

// Track event
window.eventTracker.track('event_name', 'id', { data: 'value' });

// Safe element access
const element = document.getElementById('my-id');
if (element) {
  element.classList.add('active');
}
```

## JavaScript Modules

| Module | Purpose | Global Export |
|--------|---------|--------------|
| `event-tracker.js` | Analytics tracking | `window.eventTracker` |
| `theme.js` | Dark/light theme toggle | - |
| `toast.js` | Notifications | `window.showToast()` |
| `user-actions.js` | Login/logout | - |
| `article-actions.js` | Article interactions | - |
| `admin-modal.js` | Admin operations | - |
| `paper-submission.js` | Paper submission | - |
| `mobile-nav.js` | Mobile menu | `window.mobileNav` |
| `search.js` | Search functionality | - |
| `password-manager.js` | Password management | - |
| `abstract-viewer.js` | Abstract display | - |
| `deep-read-status.js` | Status bar | `window.deepReadStatusBar` |
| `trending.js` | Trending tabs | - |

## Theme System (Important!)

### Why the Inline Script?

**Problem**: Without inline script, page flashes light mode before JS loads dark theme.

**Solution**: Inline script in `<head>` applies theme **before** page renders.

```html
<head>
  <!-- This MUST be before stylesheets -->
  <script>
    (function() {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const saved = localStorage.getItem('theme');
      const theme = saved === 'dark' || saved === 'light' ? saved : (prefersDark ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', theme);
    })();
  </script>
  
  <link rel="stylesheet" href="...">
</head>
```

**Result**: No flash, smooth experience in dark mode! 🎉

## Development Workflow

### 1. Adding a Component

```bash
# Create files
touch ui/components/my-component.html
# Add styles to ui/css/components.css
# Add JS if needed: touch ui/js/my-component.js
```

```html
<!-- Include in page -->
{% include 'components/my-component.html' %}
```

### 2. Testing Checklist

- [ ] Light mode works
- [ ] Dark mode works  
- [ ] Theme toggle (no flash)
- [ ] Desktop (>1200px)
- [ ] Tablet (768-1200px)
- [ ] Mobile (<768px)
- [ ] No console errors

### 3. Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Theme flash | Add inline script to `<head>` |
| Styles not working | Check CSS load order (base.css first) |
| JS not running | Use `DOMContentLoaded` or event delegation |
| Dark mode wrong colors | Use CSS variables, not hard-coded colors |

## File Loading Order

### CSS (Critical!)
1. `base.css` - Core + variables
2. `badges.css` - Badges
3. `components.css` - Components
4. `modal.css` - Modals

### JavaScript
1. `event-tracker.js` - Analytics (first!)
2. `theme.js` - Theme toggle
3. `toast.js` - Notifications
4. Other modules (order doesn't matter)

## Architecture Principles

### Separation of Concerns
- **HTML**: Structure only
- **CSS**: Styling only  
- **JavaScript**: Behavior only

### Modularity
- Components are self-contained
- Styles organized by feature
- JS classes encapsulate functionality

### Progressive Enhancement
- Core works without JS
- JS enhances experience
- Styles degrade gracefully

## Responsive Design

| Breakpoint | Layout |
|------------|--------|
| < 768px | Mobile: stacked, hamburger menu, FAB |
| 768-1200px | Tablet: no sidebar, FAB |
| > 1200px | Desktop: sidebar, full nav |

## Best Practices

### Do ✅
- Use CSS variables for colors
- Use event delegation
- Add JSDoc comments
- Test both themes
- Test all breakpoints
- Use semantic HTML

### Don't ❌
- Hard-code colors
- Bind events directly to elements
- Forget inline theme script
- Skip mobile testing
- Use inline styles
- Mix concerns (HTML/CSS/JS)

## Quick Commands

```bash
# Find hard-coded colors (should be empty!)
grep -r "color: #" ui/css/

# Find missing CSS variables
grep -r "#[0-9a-f]\{6\}" ui/css/
```

## Resources

- **CSS Variables**: See `ui/base.css` lines 1-100
- **Component Examples**: Check existing components in `ui/components/`
- **JS Patterns**: Look at `ui/js/theme.js` for well-documented example

---

**Remember**: When in doubt, check existing code for patterns! Keep it simple, keep it modular.
