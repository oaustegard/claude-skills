# UITree Format Specification

## Overview

UITree is a flat JSON structure representing a component hierarchy. It's designed for LLM generation—flat structure avoids deep nesting issues with streaming and parsing.

## Structure

```typescript
interface UITree {
  root: string;                    // Key of root element
  elements: Record<string, UIElement>;  // Flat map of all elements
  data?: Record<string, unknown>;  // Data model for bindings
}

interface UIElement {
  key: string;                     // Unique identifier
  type: string;                    // Component type from catalog
  props: Record<string, unknown>;  // Component props
  children?: string[];             // Keys of child elements
  visible?: VisibilityCondition;   // Optional visibility rule
}
```

## Key Generation

Keys must be unique within the tree. Conventions:
- Use descriptive names: `"revenueMetric"`, `"headerCard"`, `"userTable"`
- For repeated items, use suffixes: `"metric1"`, `"metric2"`
- Avoid generic names like `"div1"`, `"component3"`

## Parent-Child Relationships

Children are referenced by key, not embedded:

```json
{
  "root": "container",
  "elements": {
    "container": {
      "key": "container",
      "type": "Card",
      "props": { "title": "My Card" },
      "children": ["child1", "child2"]
    },
    "child1": {
      "key": "child1",
      "type": "Text",
      "props": { "content": "First child" }
    },
    "child2": {
      "key": "child2",
      "type": "Text",
      "props": { "content": "Second child" }
    }
  }
}
```

## Data Binding

### Value Paths

Props ending in `Path` reference the data model using JSON Pointer syntax:

| Path | Resolves to |
|------|-------------|
| `/revenue` | `data.revenue` |
| `/users/0/name` | `data.users[0].name` |
| `/settings/theme` | `data.settings.theme` |

### Read-Only Binding (valuePath, dataPath)

Used for display components. Data flows one way (data → UI):

```json
{
  "type": "Metric",
  "props": {
    "label": "Revenue",
    "valuePath": "/revenue"
  }
}
```

### Two-Way Binding (bindPath)

Used for input components. Data flows both ways:

```json
{
  "type": "Select",
  "props": {
    "label": "Status",
    "bindPath": "/filters/status",
    "options": [
      { "value": "active", "label": "Active" },
      { "value": "inactive", "label": "Inactive" }
    ]
  }
}
```

## Visibility Conditions

Control when elements render:

### Static

```json
{ "visible": true }   // Always visible (default)
{ "visible": false }  // Never visible
```

### Path-Based (Truthy Check)

```json
{ "visible": { "path": "/hasError" } }
```

### Boolean Logic

```json
// AND - all must be true
{ "visible": { "and": [{ "path": "/isAdmin" }, { "path": "/hasAccess" }] } }

// OR - any must be true
{ "visible": { "or": [{ "path": "/isOwner" }, { "path": "/isAdmin" }] } }

// NOT - negation
{ "visible": { "not": { "path": "/isHidden" } } }
```

### Comparisons

```json
// Equality
{ "visible": { "eq": [{ "path": "/status" }, "active"] } }

// Not equal
{ "visible": { "neq": [{ "path": "/count" }, 0] } }

// Numeric comparisons
{ "visible": { "gt": [{ "path": "/items" }, 5] } }
{ "visible": { "gte": [{ "path": "/items" }, 5] } }
{ "visible": { "lt": [{ "path": "/items" }, 10] } }
{ "visible": { "lte": [{ "path": "/items" }, 10] } }
```

### Complex Example

```json
{
  "visible": {
    "and": [
      { "path": "/user/isLoggedIn" },
      { "or": [
        { "eq": [{ "path": "/user/role" }, "admin"] },
        { "gt": [{ "path": "/user/level" }, 5] }
      ]}
    ]
  }
}
```

## Data Model

The `data` property provides values for bindings:

```json
{
  "root": "dashboard",
  "elements": { ... },
  "data": {
    "revenue": 125000,
    "growth": 0.15,
    "users": [
      { "name": "Alice", "status": "active" },
      { "name": "Bob", "status": "pending" }
    ],
    "filters": {
      "status": "all",
      "dateRange": "30d"
    }
  }
}
```

## Best Practices

### Keep Trees Flat

Avoid deep nesting. Prefer:
```
Grid → [Card, Card, Card]  (depth 2)
```

Over:
```
Grid → Card → Stack → Card → Text  (depth 5)
```

### Use Semantic Components

- **Metrics** for KPIs, not Text with styled numbers
- **Table** for tabular data, not nested Stacks
- **Chart** for visualizations, not custom SVG

### Provide Realistic Data

Always include sample data that matches the expected schema:

```json
{
  "type": "Chart",
  "props": {
    "type": "line",
    "dataPath": "/monthlyData"
  }
}
// data should include:
{
  "monthlyData": [
    { "month": "Jan", "value": 1000 },
    { "month": "Feb", "value": 1200 }
  ]
}
```

### Validate Keys

- Every `children` entry must exist in `elements`
- `root` must exist in `elements`
- No circular references
