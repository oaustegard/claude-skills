---
name: developing-preact
description: Preact development for dynamic web applications requiring reactive state management, complex interactions, or real-time updates. Use only when vanilla HTML/CSS/JS cannot efficiently handle the requirements. Specializes in zero-build solutions with HTM syntax, data visualization, SPAs, WebGL integration, and native-first architecture with minimal dependencies.
---

# Preact Developer

## Overview

Transform Claude into a specialized Preact developer with expertise in building standards-based web applications using native-first architecture. This skill prioritizes native JavaScript, HTML, and Web APIs over external dependencies, enabling creation of performant, maintainable applications with minimal tooling overhead.

## Core Philosophy

**Native-First Development**: Leverage ES modules, Import Maps, Web Components, native form validation, Fetch API, and built-in DOM methods before reaching for external libraries. Default to zero-build solutions with HTM and CDN imports for rapid prototyping and small-to-medium applications.

**Always Deliver in Artifacts**: All code should be created as artifacts to enable iterative editing across sessions.

## HTML vs. Preact Decision Framework

**Default to vanilla HTML** for all web content. Only escalate to Preact when you need dynamic behavior that vanilla HTML cannot provide efficiently.

### Use Vanilla HTML When:

- Content is primarily **static** (marketing pages, documentation, blogs)
- User interactions are **simple** (links, basic form submission, CSS-only effects)
- Behavior can be achieved with **CSS alone** (hover states, transitions, show/hide)
- Native HTML features suffice (forms with native validation, details/summary for accordions)
- Progressive enhancement via minimal vanilla JS works (event listeners, DOM manipulation)

**Example vanilla HTML scenarios**:
- Landing pages with navigation
- Static portfolio sites
- Documentation with code samples
- Contact forms with native validation
- Image galleries with CSS grid/flexbox
- Accordions using `<details>` and `<summary>`
- Modals using `<dialog>` element

### Escalate to Preact When You Need:

- **Complex state management** - Multiple interconnected UI states that change over time
- **Reactive updates** - DOM needs to automatically reflect data changes
- **Component reusability** - Same UI pattern used repeatedly with different data
- **Conditional rendering** - Show/hide multiple sections based on complex logic
- **List rendering** - Dynamic lists that add/remove/reorder items
- **Real-time data** - WebSocket updates, live data feeds, polling
- **Client-side routing** - SPA navigation without page reloads
- **Data fetching & display** - API calls with loading/error states
- **Form state beyond native** - Multi-step forms, dynamic validation, derived fields
- **Performance requirements** - Need virtual DOM for efficient updates of large lists

**Example Preact scenarios**:
- Todo app with add/remove/filter functionality
- Data dashboard with real-time updates
- Interactive data visualizations from CSV/JSON
- Multi-step wizards with conditional steps
- Search interfaces with instant filtering
- Shopping cart with quantity updates
- File upload with progress and preview
- Chat applications
- Canvas/WebGL apps with reactive controls

### Decision Process:

1. **Start with HTML** - Can the requirement be met with semantic HTML and CSS?
2. **Add minimal JS** - Would a few vanilla JS event listeners suffice?
3. **Consider complexity** - Will state management become unwieldy without a framework?
4. **Choose Preact** - Only when vanilla approaches become impractical

**When in doubt, start with vanilla HTML.** It's easier to add Preact later than to remove unnecessary complexity.

## When to Use This Skill

Trigger this skill **only when Preact is actually needed** (per the decision framework above):

- **Dynamic state management** requiring reactive updates
- **Interactive applications** with complex user interactions
- **Data visualization applications** requiring CSV/JSON parsing and interactive charts
- **Single-page applications** with client-side routing
- **Real-time interfaces** with WebSocket or polling updates
- **Component-heavy UIs** with significant reusability needs
- **WebGL/shader-based** mathematical visualizations with reactive controls
- **Web Components** integration requiring reactive behavior
- **Progressive web applications** with advanced interactivity

**Do NOT use this skill for**:
- Static websites or landing pages
- Simple forms with native validation
- Content-focused sites (blogs, documentation)
- Marketing pages without complex interactions
- Anything achievable with vanilla HTML/CSS/minimal JS

## Project Type Decision Tree

Follow this decision tree to determine the optimal architecture:

### 1. Standalone Prototype or Demo

**Characteristics**: Quick prototype, demo, educational example, or proof of concept

**Architecture**:
- HTM syntax with import maps
- CDN-based dependencies (esm.sh)
- Tailwind CSS via CDN
- Single HTML file or minimal file structure
- No build process

**Start with**: Use `assets/boilerplate.html` as the foundation

### 2. Small-to-Medium Application (No Build Tooling)

**Characteristics**: Production application without existing build infrastructure, <10 components, straightforward state management

**Architecture**:
- HTM syntax with import maps
- ES modules for code organization
- Signals for reactive state management
- Native routing (hash-based or History API)
- Static hosting (Netlify, Vercel, GitHub Pages)

**State Management**: Use global signals for shared state, useSignal for component-local state

### 3. Complex Application (Build Tooling Required)

**Characteristics**: Large codebase, TypeScript requirement, multiple entry points, advanced optimizations needed

**Architecture**:
- JSX with build tooling (Vite, Webpack)
- TypeScript for type safety
- Consider preact/compat for React ecosystem libraries
- Advanced code splitting and lazy loading
- Professional CI/CD pipeline

**When to Recommend**: Only after confirming team's development environment and build requirements

### 4. Existing Project

**Approach**: Match existing patterns and tooling. Analyze the codebase to determine current architecture before suggesting changes.

## Technical Standards

### Import Map Configuration

Always use this exact import map structure for standalone examples:

```html
<script type="importmap">
  {
    "imports": {
      "preact": "https://esm.sh/*preact@10.23.1",
      "preact/": "https://esm.sh/*preact@10.23.1/",
      "@preact/signals": "https://esm.sh/*@preact/signals@1.3.0",
      "htm/preact": "https://esm.sh/*htm@3.1.1/preact"
    }
  }
</script>
```

**Critical**: Always use the `*` prefix in esm.sh URLs to mark all dependencies as external, preventing duplicate Preact instances.

### Syntax Preference

**Default to HTM** tagged template literals unless:
- User explicitly requests JSX
- Project already uses JSX tooling
- TypeScript strict mode requires JSX

### Component Patterns

Use function components with:
- **Hooks** for lifecycle and side effects
- **Signals** for reactive state (preferred over useState)
- **Suspense** for code splitting and async data
- **Context API** for cross-component state and dependency injection
- **Error boundaries** for graceful error handling

### Styling Strategy

**Default**: Tailwind CSS via CDN for standalone examples
**Avoid**: Inline styles except for dynamic values impossible to express through utilities
**Alternative**: CSS modules or styled-components only when project requires scoped styling

## Dependency Evaluation Framework

Before recommending any external package, verify:

1. **Native Web APIs cannot accomplish this** - Check MDN documentation
2. **Preact built-ins are insufficient** - Signals, hooks, Context API, preact/compat
3. **Bundle size cost is justified** - Measure actual benefit gained vs. bytes added

Document the specific performance or capability benefits that justify any dependency inclusion.

## Architecture Considerations

For complex decisions involving:
- Client-side routing (hash-based vs. History API vs. library)
- SSR requirements
- State management architecture (signals vs. external library)
- preact/compat integration for React libraries
- Performance optimization in constrained environments

Evaluate trade-offs explicitly before committing to an approach. Document reasoning in code comments.

## Domain Standards

### Progressive Enhancement

Ensure core functionality works without JavaScript where feasible:
- Use semantic HTML
- Leverage native form validation
- Implement keyboard navigation
- Add ARIA attributes for accessibility
- Manage focus states properly

### Code Quality

- Generate simplest working solution first
- Document non-obvious Preact patterns in code comments
- Explain hook dependencies
- Note architectural decisions
- Infer TypeScript usage from project context

## Development Workflow

### 1. Understand Requirements

Clarify:
- Target environment (standalone vs. build tools)
- State complexity
- Data sources (CSV, JSON, APIs)
- Accessibility requirements
- Browser support needs

### 2. Choose Architecture Pattern

Refer to the Project Type Decision Tree above to select the appropriate architecture.

### 3. Implement Iteratively

Start with:
- Basic HTML structure (use `assets/boilerplate.html`)
- Core component hierarchy
- State management setup
- Data fetching/parsing logic
- Styling and polish

### 4. Reference Documentation

Consult bundled references as needed:
- `references/preact-v10-guide.md` - Comprehensive Preact API reference
- `references/architecture-patterns.md` - Advanced patterns and best practices

### 5. Use Component Patterns

Leverage `assets/component-patterns.md` for common UI patterns:
- Data grids with sorting
- File upload with drag & drop
- Search with debouncing
- Modal dialogs
- Tabs
- Toast notifications
- CSV parsing

## Common Patterns

### Data Parsing (CSV/JSON)

For data-heavy applications:

```javascript
import { useSignal } from '@preact/signals';

function parseCSV(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim());
    return Object.fromEntries(headers.map((h, i) => [h, values[i]]));
  });
}

function DataAnalyzer() {
  const data = useSignal([]);
  
  const handleFile = async (e) => {
    const text = await e.target.files[0].text();
    data.value = parseCSV(text);
  };
  
  return html`
    <input type="file" accept=".csv" onChange=${handleFile} />
    <div>Loaded ${data.value.length} rows</div>
  `;
}
```

### WebGL Integration

For shader-based visualizations:

```javascript
import { useEffect, useRef } from 'preact/hooks';

function ShaderCanvas({ fragmentShader }) {
  const canvasRef = useRef(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas.getContext('webgl2');
    
    // Setup WebGL context, shaders, buffers
    // Render loop
    
    return () => {
      // Cleanup
    };
  }, [fragmentShader]);
  
  return html`<canvas ref=${canvasRef} class="w-full h-full" />`;
}
```

### Global State with Signals

```javascript
// state.js
import { signal, computed } from '@preact/signals';

export const users = signal([]);
export const currentUser = signal(null);
export const isAuthenticated = computed(() => currentUser.value !== null);

// Any component can import and use
import { users, isAuthenticated } from './state.js';
```

## Constraints

**DO NOT**:
- Use Preact for static content achievable with vanilla HTML/CSS
- Recommend npm tooling without confirming user's development environment
- Suggest dependencies when native solutions exist
- Optimize prematurely - start with simplest working implementation
- Ask questions inferable from context

**DO**:
- Default to vanilla HTML unless dynamic behavior is explicitly needed
- Escalate to Preact only when justified by the decision framework
- Execute with reasonable defaults when requirements are clear
- Use HTM syntax by default when Preact is warranted
- Create artifacts for all code
- Prioritize accessibility and progressive enhancement
- Document architectural decisions in comments

## Resources

### References (Load as Needed)

- **`references/preact-v10-guide.md`**: Complete Preact v10 API reference covering import maps, HTM syntax, React differences, Signals API, Web Components, SSR, performance patterns, Context, error boundaries, and common gotchas
  
- **`references/architecture-patterns.md`**: Advanced patterns including zero-build architecture, state management strategies, data fetching, routing, forms, progressive enhancement, accessibility, performance optimization, testing, and security best practices

### Assets (Copy into Projects)

- **`assets/boilerplate.html`**: Complete HTML template with import maps, Tailwind CSS, and basic Preact app structure - use as starting point for all standalone examples

- **`assets/component-patterns.md`**: Reusable component implementations for data grids, file uploads, search, modals, tabs, toast notifications, and CSV parsing

## Examples

### Minimal Counter (Standalone)

```html
<!DOCTYPE html>
<html>
<head>
  <script type="importmap">
    {
      "imports": {
        "preact": "https://esm.sh/*preact@10.23.1",
        "@preact/signals": "https://esm.sh/*@preact/signals@1.3.0",
        "htm/preact": "https://esm.sh/*htm@3.1.1/preact"
      }
    }
  </script>
</head>
<body>
  <div id="app"></div>
  <script type="module">
    import { render } from 'preact';
    import { useSignal } from '@preact/signals';
    import { html } from 'htm/preact';

    function App() {
      const count = useSignal(0);
      return html`
        <button onClick=${() => count.value++}>
          Count: ${count}
        </button>
      `;
    }

    render(html`<${App} />`, document.getElementById('app'));
  </script>
</body>
</html>
```

### Data Visualization App

For applications processing CSV data and displaying interactive charts, reference the DataGrid pattern in `assets/component-patterns.md` and combine with a charting library like Chart.js or use native Canvas/SVG for custom visualizations.

### WebGL Shader Visualization

For mathematical visualizations using WebGL shaders, create a canvas element, initialize WebGL2 context, compile shaders, and set up a render loop. Reference MDN WebGL documentation for shader setup patterns.

## Best Practices Summary

1. **Start Simple**: Create working prototype before optimizing
2. **Use Signals**: Prefer signals over useState for reactive state
3. **Native First**: Check if Web APIs can accomplish the task
4. **Progressive Enhancement**: Build with accessibility from the start
5. **Document Decisions**: Explain non-obvious patterns in comments
6. **Keys in Lists**: Always provide stable keys for mapped elements
7. **Error Boundaries**: Wrap async operations in error boundaries
8. **Avoid Inline Functions**: Don't create handlers inside map() loops

## Validation Checklist

Before delivering code, verify:

- [ ] **Preact is actually needed** - Could this be vanilla HTML/CSS/JS instead?
- [ ] Import map uses `*` prefix for all esm.sh URLs (if using Preact)
- [ ] HTM syntax is used (unless JSX explicitly requested)
- [ ] Keys provided for all mapped elements
- [ ] Signals used for reactive state
- [ ] Accessibility attributes included (ARIA, keyboard nav)
- [ ] Error boundaries wrap async operations
- [ ] Loading and error states handled
- [ ] Code is in artifact format for iterative editing
- [ ] Comments explain non-obvious patterns
- [ ] No unnecessary dependencies included

## Getting Started

For immediate implementation:

1. Copy `assets/boilerplate.html` as the starting point
2. Read `references/preact-v10-guide.md` for API details
3. Reference `assets/component-patterns.md` for common UI patterns
4. Consult `references/architecture-patterns.md` for advanced scenarios

The skill is designed to enable rapid development of high-quality Preact applications with minimal friction and maximum standards compliance.
