# Architecture Patterns & Best Practices

## Native-First Development Philosophy

Prioritize native JavaScript, HTML, and Web APIs over external dependencies. This approach delivers:
- Smaller bundle sizes
- Better performance
- Reduced maintenance burden
- Future-proof code that doesn't depend on library churn

### Decision Framework for Dependencies

Before adding any external package, verify:

1. **Native APIs cannot accomplish this** - Check MDN and Can I Use
2. **Preact built-ins are insufficient** - signals, hooks, Context API
3. **Bundle size cost is justified** - Measure the actual benefit gained

## Zero-Build Architecture

For prototypes, demos, and small applications, use:
- ES modules via CDN (esm.sh)
- Import maps for dependency management
- HTM for zero-transpilation JSX-like syntax
- Inline or linked CSS (Tailwind via CDN)

### When to Introduce Build Tools

Consider build tooling when:
- TypeScript is required for team collaboration
- Code splitting across multiple entry points is needed
- CSS preprocessing (beyond Tailwind) is essential
- Bundle optimization for production is critical

## State Management Patterns

### Local Component State

Use for isolated component logic:

```javascript
import { useSignal } from '@preact/signals';

function Counter() {
  const count = useSignal(0);
  return html`
    <button onClick=${() => count.value++}>
      Count: ${count}
    </button>
  `;
}
```

### Global Signals

Use for shared state across components:

```javascript
// state.js
import { signal } from '@preact/signals';

export const currentUser = signal(null);
export const isAuthenticated = signal(false);

// Any component can import and use
import { currentUser } from './state.js';
```

### Context API

Use for dependency injection and theme/config:

```javascript
import { createContext } from 'preact';
import { useContext } from 'preact/hooks';

const ApiContext = createContext(null);

function App() {
  const api = createApiClient();
  return html`
    <${ApiContext.Provider} value=${api}>
      <${MainApp} />
    </${ApiContext.Provider}>
  `;
}
```

### External State Libraries

Consider Zustand or Jotai only when:
- Complex state derivations are needed
- Dev tools and time-travel debugging are required
- Team has existing patterns with these libraries

## Data Fetching Patterns

### Simple Fetch with Hooks

```javascript
import { useSignal, useSignalEffect } from '@preact/signals';

function UserProfile({ userId }) {
  const user = useSignal(null);
  const loading = useSignal(true);
  const error = useSignal(null);

  useSignalEffect(() => {
    loading.value = true;
    fetch(`/api/users/${userId}`)
      .then(r => r.json())
      .then(data => {
        user.value = data;
        loading.value = false;
      })
      .catch(err => {
        error.value = err;
        loading.value = false;
      });
  });

  if (loading.value) return html`<div>Loading...</div>`;
  if (error.value) return html`<div>Error: ${error.value.message}</div>`;
  return html`<div>${user.value.name}</div>`;
}
```

### Suspense for Async Data

```javascript
import { Suspense, lazy } from 'preact/compat';

// Resource pattern
function wrapPromise(promise) {
  let status = 'pending';
  let result;
  const suspender = promise.then(
    r => {
      status = 'success';
      result = r;
    },
    e => {
      status = 'error';
      result = e;
    }
  );
  return {
    read() {
      if (status === 'pending') throw suspender;
      if (status === 'error') throw result;
      return result;
    }
  };
}

const userResource = wrapPromise(fetch('/api/user').then(r => r.json()));

function UserData() {
  const user = userResource.read();
  return html`<div>${user.name}</div>`;
}

function App() {
  return html`
    <${Suspense} fallback=${html`<div>Loading...</div>`}>
      <${UserData} />
    </${Suspense}>
  `;
}
```

## Routing Strategies

### Hash-based Routing (Simplest)

```javascript
import { useSignal, useSignalEffect } from '@preact/signals';

const currentRoute = signal(window.location.hash.slice(1) || '/');

window.addEventListener('hashchange', () => {
  currentRoute.value = window.location.hash.slice(1) || '/';
});

function App() {
  return html`
    <nav>
      <a href="#/">Home</a>
      <a href="#/about">About</a>
    </nav>
    ${currentRoute.value === '/' && html`<${HomePage} />`}
    ${currentRoute.value === '/about' && html`<${AboutPage} />`}
  `;
}
```

### History API Routing (Production)

Consider preact-router or wouter for:
- Clean URLs without hashes
- Server-side rendering requirements
- Nested route patterns

## Form Handling

### Native Form Validation

Leverage HTML5 validation before JavaScript:

```javascript
function SignupForm() {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!e.target.checkValidity()) return;
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    // Submit data
  };

  return html`
    <form onSubmit=${handleSubmit}>
      <input 
        name="email" 
        type="email" 
        required 
        placeholder="Email"
      />
      <input 
        name="password" 
        type="password" 
        required 
        minlength="8"
        placeholder="Password"
      />
      <button type="submit">Sign Up</button>
    </form>
  `;
}
```

### Controlled Inputs with Signals

```javascript
function SearchBox() {
  const query = useSignal('');
  
  return html`
    <input
      value=${query}
      onInput=${e => query.value = e.target.value}
      placeholder="Search..."
    />
    <div>Results for: ${query}</div>
  `;
}
```

## Progressive Enhancement

### Core Principles

1. **HTML First** - Structure works without JavaScript
2. **CSS for Presentation** - Visual design doesn't require JS
3. **JavaScript for Enhancement** - Adds interactivity and polish

### Example: Accordion

```javascript
// Works without JS (details/summary), enhanced with JS
function Accordion({ items }) {
  const openItems = useSignal(new Set());

  return html`
    <div>
      ${items.map((item, i) => html`
        <details
          key=${item.id}
          open=${openItems.value.has(i)}
          onToggle=${e => {
            const newSet = new Set(openItems.value);
            if (e.target.open) {
              newSet.add(i);
            } else {
              newSet.delete(i);
            }
            openItems.value = newSet;
          }}
        >
          <summary>${item.title}</summary>
          <div>${item.content}</div>
        </details>
      `)}
    </div>
  `;
}
```

## Accessibility Patterns

### Keyboard Navigation

```javascript
function Modal({ isOpen, onClose, children }) {
  const modalRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    
    document.addEventListener('keydown', handleKeyDown);
    modalRef.current?.focus();
    
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return html`
    <div
      role="dialog"
      aria-modal="true"
      ref=${modalRef}
      tabindex="-1"
    >
      ${children}
    </div>
  `;
}
```

### ARIA Labels and Live Regions

```javascript
function SearchResults({ results, loading }) {
  return html`
    <div>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        ${loading ? 'Loading results...' : `${results.length} results found`}
      </div>
      <ul role="list">
        ${results.map(r => html`
          <li key=${r.id}>${r.title}</li>
        `)}
      </ul>
    </div>
  `;
}
```

## Performance Optimization

### Code Splitting

```javascript
import { Suspense, lazy } from 'preact/compat';

const HeavyComponent = lazy(() => import('./HeavyComponent.js'));

function App() {
  return html`
    <${Suspense} fallback=${html`<div>Loading...</div>`}>
      <${HeavyComponent} />
    </${Suspense}>
  `;
}
```

### Memoization

```javascript
import { useMemo } from 'preact/hooks';
import { memo } from 'preact/compat';

// Memoize expensive computations
function DataGrid({ rows }) {
  const sortedRows = useMemo(
    () => rows.sort((a, b) => a.name.localeCompare(b.name)),
    [rows]
  );
  
  return html`<table>...</table>`;
}

// Memoize components
const ExpensiveRow = memo(({ data }) => html`
  <tr>
    <td>${data.name}</td>
    <td>${data.value}</td>
  </tr>
`);
```

### Virtual Scrolling

For large lists (1000+ items), consider:
- react-window (via preact/compat)
- Manual implementation with Intersection Observer

## Testing Strategies

### Unit Testing Components

```javascript
import { render } from '@testing-library/preact';
import { html } from 'htm/preact';

test('Counter increments', async () => {
  const { getByText } = render(html`<${Counter} />`);
  const button = getByText(/count:/i);
  
  fireEvent.click(button);
  expect(button.textContent).toBe('Count: 1');
});
```

### E2E Testing

Use Playwright or Cypress for:
- Critical user flows
- Cross-browser testing
- Visual regression testing

## Common Pitfalls

### 1. Overusing Signals for Local State

```javascript
// BAD - Signal not needed for local state
function Toggle() {
  const isOpen = signal(false); // Global signal!
  // ...
}

// GOOD - Use useSignal for component-local state
function Toggle() {
  const isOpen = useSignal(false);
  // ...
}
```

### 2. Forgetting Keys in Lists

```javascript
// BAD - No keys
items.map(item => html`<li>${item.name}</li>`)

// GOOD - Stable keys
items.map(item => html`<li key=${item.id}>${item.name}</li>`)
```

### 3. Missing Error Boundaries

Always wrap async operations in error boundaries:

```javascript
function App() {
  return html`
    <${ErrorBoundary}>
      <${Suspense} fallback=${html`<Loading />`}>
        <${AsyncComponent} />
      </${Suspense}>
    </${ErrorBoundary}>
  `;
}
```

### 4. Inline Function Creation in Loops

```javascript
// BAD - Creates new function every render
items.map(item => html`
  <button onClick=${() => handleClick(item.id)}>
    ${item.name}
  </button>
`)

// GOOD - Create handler outside loop or use data attributes
const handleItemClick = (e) => {
  const id = e.target.dataset.id;
  handleClick(id);
};

items.map(item => html`
  <button onClick=${handleItemClick} data-id=${item.id}>
    ${item.name}
  </button>
`)
```

## CSS Architecture

### Utility-First with Tailwind

Prefer Tailwind utilities for rapid development:

```javascript
html`
  <div class="flex items-center gap-4 p-4 bg-white rounded-lg shadow">
    <img class="w-12 h-12 rounded-full" src=${avatar} />
    <div>
      <h3 class="text-lg font-semibold">${name}</h3>
      <p class="text-gray-600">${email}</p>
    </div>
  </div>
`
```

### Custom CSS When Needed

For complex layouts or animations:

```html
<style>
  @keyframes slideIn {
    from { transform: translateX(-100%); }
    to { transform: translateX(0); }
  }
  
  .sidebar {
    animation: slideIn 0.3s ease-out;
  }
</style>
```

### CSS Modules (with Build Tools)

For component-scoped styles in larger apps:

```javascript
import styles from './Button.module.css';

function Button({ children }) {
  return html`
    <button class=${styles.button}>
      ${children}
    </button>
  `;
}
```

## Security Best Practices

### XSS Prevention

Never use `dangerouslySetInnerHTML` with user content:

```javascript
// BAD - XSS vulnerability
<div dangerouslySetInnerHTML=${{ __html: userInput }} />

// GOOD - Preact escapes by default
<div>${userInput}</div>
```

### CSRF Protection

For forms that mutate state:

```javascript
function DeleteForm({ itemId, csrfToken }) {
  const handleDelete = async () => {
    await fetch(`/api/items/${itemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRF-Token': csrfToken
      }
    });
  };
  
  return html`
    <button onClick=${handleDelete}>Delete</button>
  `;
}
```
