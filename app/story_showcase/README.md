# Story Showcase Module

## Design Decision: Static Files Location

This module follows a **self-contained design** where:
- **Static files** (HTML, CSS, JS) are in `/story_showcase/` at the project root
- **Flask routes** are in `/app/story_showcase/` following the application's module pattern

### Why This Design?

1. **Self-Contained Module**: The story showcase is a standalone feature that can be easily moved, shared, or removed without affecting the main application.

2. **Separation of Concerns**: 
   - Static assets are separate from the main `/ui/` directory (which serves the core application)
   - Flask application code follows the established pattern in `/app/`

3. **Flask Best Practices**: 
   - Uses Blueprint for route organization
   - Explicit static file serving for better control
   - Follows the same factory pattern as other modules

### Alternative Considered

**Option: Move to `/ui/story_showcase/`**
- Would match the main UI pattern
- But would mix story showcase with core application UI
- Less self-contained

### Current Structure

```
story_showcase/          # Static files (root level)
├── index.html
├── css/
│   └── style.css
├── js/
│   ├── data.js
│   └── script.js
└── *.md                 # Documentation

app/story_showcase/       # Flask application code
├── __init__.py
├── factory.py
└── routes.py
```

This design is **appropriate** because:
- The story showcase is a standalone feature
- It's easier to maintain and potentially extract
- It doesn't pollute the main `/ui/` directory
- The Flask routes properly abstract the file serving

