# Preact v10 - Comprehensive Reference Guide

## Import Map Configuration

### Standard Setup (Use for all standalone examples)

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

### With React Aliasing (for React ecosystem compatibility)

```html
<script type="importmap">
  {
    "imports": {
      "preact": "https://esm.sh/*preact@10.23.1",
      "preact/": "https://esm.sh/*preact@10.23.1/",
      "react": "https://esm.sh/*preact@10.23.1/compat",
      "react/": "https://esm.sh/*preact@10.23.1/compat/",
      "react-dom": "https://esm.sh/*preact@10.23.1/compat",
      "@preact/signals": "https://esm.sh/*@preact/signals@1.3.0",
      "htm/preact": "https://esm.sh/*htm@3.1.1/preact"
    }
  }
</script>
```

**Critical Note**: Always use the `*` prefix in esm.sh URLs to mark all dependencies as external, preventing duplicate Preact instances.

## HTM Syntax (Default Preference)

### Basic Usage

```javascript
import { render } from 'preact';
import { html } from 'htm/preact';

function App() {
  return html`
    <div class="container">
      <h1>Hello World</h1>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById('app'));
```

### Dynamic Values & Props

```javascript
const name = 'World';
const count = 42;

html`
  <div class=${className}>
    <h1>Hello ${name}!</h1>
    <button onClick=${handleClick}>Count: ${count}</button>
    <${CustomComponent} value=${count} />
  </div>
`;
```

### Conditional Rendering

```javascript
html`
  <div>
    ${isLoggedIn && html`<UserProfile />`}
    ${error ? html`<ErrorMessage />` : html`<Content />`}
  </div>
`;
```

### Lists & Keys

```javascript
html`
  <ul>
    ${items.map(item => html`
      <li key=${item.id}>${item.name}</li>
    `)}
  </ul>
`;
```

## Key Differences from React

### Event Handling

**Preact uses native DOM events** (not synthetic):

```javascript
// React - uses onChange
<input onChange={e => console.log(e.currentTarget.value)} />

// Preact core - use onInput for text inputs
<input onInput={e => console.log(e.currentTarget.value)} />

// Preact with preact/compat - onChange works like React
```

**Event names are case-sensitive** for custom events.

### Props vs Attributes

Preact **automatically detects** whether to use property or attribute:

```javascript
// Sets property (because setter exists)
<input value=${text} />

// Sets attribute (no corresponding property)
<div data-foo=${value} />

// SVG: use exact attribute names
<circle fill="none" stroke-width="2" />
```

### Children Handling

`props.children` is **not always an array**:

```javascript
import { toChildArray } from 'preact';

// WRONG - may break
function Bad(props) {
  const count = props.children.length; // Error if children isn't array
}

// CORRECT
function Good(props) {
  const count = toChildArray(props.children).length;
}
```

### State Updates are Asynchronous

**Never read state immediately after setState**:

```javascript
// WRONG
this.setState({ counter: this.state.counter + 1 });

// CORRECT
this.setState(prevState => ({
  counter: prevState.counter + 1
}));
```

### Class vs className

Both work, but `class` is preferred (smaller):

```javascript
<div class="foo" />     // Preferred
<div className="foo" /> // Also works
```

## Signals API

### Core Concepts

Signals are **reactive primitives** that auto-update components:

```javascript
import { signal, computed, effect } from '@preact/signals';

// Create signal
const count = signal(0);

// Read value
console.log(count.value); // 0

// Update value
count.value += 1;

// Use directly in JSX (auto-subscribes)
function Counter() {
  return html`<div>Count: ${count}</div>`;
}
```

### Computed Signals

**Derived values** that auto-update:

```javascript
const firstName = signal('John');
const lastName = signal('Doe');

const fullName = computed(() => 
  `${firstName.value} ${lastName.value}`
);

// Auto-updates when dependencies change
firstName.value = 'Jane';
console.log(fullName.value); // "Jane Doe"
```

### Effects

Run **side effects** when signals change:

```javascript
effect(() => {
  console.log(`Count is now: ${count.value}`);
  
  // Optional cleanup
  return () => {
    console.log('Cleaning up');
  };
});

count.value = 5; // Logs: "Count is now: 5"
```

### Batching Updates

```javascript
import { batch } from '@preact/signals';

batch(() => {
  count.value = 1;
  text.value = "updated";
  // Only triggers one re-render
});
```

### Hooks Integration

```javascript
import { useSignal, useComputed } from '@preact/signals';

function Counter() {
  const count = useSignal(0);
  const double = useComputed(() => count.value * 2);
  
  return html`
    <div>
      <p>${count} x 2 = ${double}</p>
      <button onClick=${() => count.value++}>Increment</button>
    </div>
  `;
}
```

## Web Components Integration

### Using Web Components

Preact **detects property setters** automatically:

```javascript
// Custom element with property setter
customElements.define('context-menu', class extends HTMLElement {
  set position({ x, y }) {
    this.style.cssText = `left:${x}px; top:${y}px;`;
  }
});

// Preact uses property (not attribute) because setter exists
<context-menu position=${{ x: 10, y: 20 }} />
```

### Accessing Methods via Refs

```javascript
import { useRef, useEffect } from 'preact/hooks';

function Foo() {
  const myRef = useRef(null);

  useEffect(() => {
    if (myRef.current) {
      myRef.current.doSomething(); // Call custom element method
    }
  }, []);

  return html`<x-foo ref=${myRef} />`;
}
```

## Performance Patterns

### Prevent Re-renders

```javascript
import { memo } from 'preact/compat';

// Only re-renders when props change
const Expensive = memo(({ value }) => html`
  <div>${value}</div>
`);
```

### Skip Virtual DOM with Signals

```javascript
// Re-renders component when count changes
function Unoptimized() {
  return html`<p>${count.value}</p>`;
}

// Updates text directly without component re-render
function Optimized() {
  return html`<p>${count}</p>`; // No .value access
}
```

## Context API

```javascript
import { createContext } from 'preact';
import { useContext } from 'preact/hooks';

const Theme = createContext('light');

function ThemedButton() {
  const theme = useContext(Theme);
  return html`<button class="btn-${theme}">Click</button>`;
}

function App() {
  return html`
    <${Theme.Provider} value="dark">
      <${ThemedButton} />
    </${Theme.Provider}>
  `;
}
```

## Error Boundaries

```javascript
class ErrorBoundary extends Component {
  constructor() {
    super();
    this.state = { errored: false };
  }

  static getDerivedStateFromError(error) {
    return { errored: true };
  }

  componentDidCatch(error, errorInfo) {
    logErrorToService(error, errorInfo);
  }

  render(props, state) {
    if (state.errored) {
      return html`<p>Something went wrong</p>`;
    }
    return props.children;
  }
}
```

## Common Gotchas

### 1. Keys Required in Loops
```javascript
// WRONG - no key
items.map(item => html`<li>${item}</li>`)

// CORRECT
items.map(item => html`<li key=${item.id}>${item}</li>`)
```

### 2. useEffect Cleanup Must Return Function
```javascript
// WRONG
useEffect(() => {
  subscription.subscribe();
  subscription.unsubscribe(); // Called immediately!
});

// CORRECT
useEffect(() => {
  subscription.subscribe();
  return () => subscription.unsubscribe();
});
```

### 3. Refs Need Null Checks
```javascript
const inputRef = useRef(null);

useEffect(() => {
  if (inputRef.current) {
    inputRef.current.focus();
  }
}, []);
```

## Version Info

- Core: Preact 10.x
- Signals: @preact/signals 1.3.x
- HTM: 3.1.x
- Target: Modern browsers with ES2015+ support
