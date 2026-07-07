# Chart Customization Instructions

**When to use this reference:**
- User says "change colors", "different theme", "make it prettier"
- User requests specific formatting (currency, dates, percentages)
- User wants interactivity (hover, click, tooltips)
- After creating base chart and user wants refinements

**How to apply customizations:**
1. Locate the relevant section below
2. Copy the JSON modification
3. Apply to the `spec` object in your chart
4. Regenerate artifact with modified spec
5. Provide new link

## Color Schemes

**Execute when user requests color changes.**

Replace in spec:
```javascript
"encoding": {
  "color": {
    "field": "category",
    "type": "nominal",
    "scale": {"scheme": "tableau10"}  // Change scheme here
  }
}
```

**Sequential** (quantitative data):
- `viridis`, `plasma`, `inferno`, `magma`
- `blues`, `greens`, `oranges`, `purples`, `reds`

**Diverging** (data with meaningful center):
- `redblue`, `purplegreen`, `blueorange`

**Categorical** (nominal data):
- `tableau10` (recommended), `category20`

## Axis Formatting

### Numbers
```javascript
"encoding": {
  "y": {
    "field": "value",
    "type": "quantitative",
    "axis": {
      "format": "$,.2f"  // Currency with 2 decimals
    }
  }
}
```

Formats:
- `,.0f` - Thousands separator, no decimals
- `.2f` - 2 decimal places
- `.1%` - Percentage with 1 decimal
- `.2e` - Scientific notation

### Dates
```javascript
"encoding": {
  "x": {
    "field": "date",
    "type": "temporal",
    "axis": {
      "format": "%b %Y"  // Jan 2024
    }
  }
}
```

Formats:
- `%Y-%m-%d` - 2024-01-15
- `%b %Y` - Jan 2024
- `%B %d, %Y` - January 15, 2024

## Tooltips

### Multi-field
```javascript
"encoding": {
  "tooltip": [
    {"field": "category", "type": "nominal", "title": "Product"},
    {"field": "sales", "type": "quantitative", "title": "Sales", "format": "$,.0f"},
    {"field": "date", "type": "temporal", "format": "%B %Y"}
  ]
}
```

## Titles and Labels

```javascript
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "title": {
    "text": "Sales Performance",
    "subtitle": "Q1 2024",
    "fontSize": 18,
    "anchor": "start"
  },
  "data": {...},
  "encoding": {
    "x": {
      "field": "month",
      "type": "temporal",
      "axis": {"title": "Month"}
    },
    "y": {
      "field": "sales",
      "type": "quantitative",
      "axis": {"title": "Revenue (USD)"}
    }
  }
}
```

## Sizing

### Responsive
```javascript
{
  "width": "container",  // Fills parent
  "height": 400,
  "autosize": {"type": "fit", "contains": "padding"}
}
```

### Fixed
```javascript
{
  "width": 800,
  "height": 400
}
```

## Mark Styling

### Bars
```javascript
"mark": {
  "type": "bar",
  "cornerRadius": 5,
  "opacity": 0.8
}
```

### Lines
```javascript
"mark": {
  "type": "line",
  "strokeWidth": 3,
  "point": true  // Add points at data values
}
```

### Points
```javascript
"mark": {
  "type": "point",
  "size": 100,
  "filled": true,
  "opacity": 0.8
}
```

## Interactive Selections

### Highlight on hover
```javascript
{
  "params": [{
    "name": "hover",
    "select": {"type": "point", "on": "mouseover"}
  }],
  "mark": "bar",
  "encoding": {
    "opacity": {
      "condition": {"param": "hover", "value": 1},
      "value": 0.5
    }
  }
}
```

### Click to filter
```javascript
{
  "params": [{
    "name": "select",
    "select": {"type": "point"}
  }],
  "mark": "point",
  "encoding": {
    "color": {
      "condition": {"param": "select", "value": "steelblue"},
      "value": "lightgray"
    }
  }
}
```

## Legend Configuration

```javascript
"encoding": {
  "color": {
    "field": "category",
    "type": "nominal",
    "legend": {
      "title": "Product Type",
      "orient": "right",  // "left", "top", "bottom"
      "labelFontSize": 12
    }
  }
}
```

Hide legend:
```javascript
"legend": null
```

## Grid Lines

```javascript
"encoding": {
  "x": {
    "field": "date",
    "type": "temporal",
    "axis": {
      "grid": true,
      "gridColor": "#e0e0e0"
    }
  }
}
```

## Conditional Styling

Color based on value:
```javascript
"encoding": {
  "color": {
    "condition": {
      "test": "datum.value > 50",
      "value": "green"
    },
    "value": "red"
  }
}
```

## Quick Modifications

After creating base chart, most common customizations:
1. Color scheme (aesthetic preference)
2. Axis formatting (readability)
3. Tooltips (additional context)
4. Title/labels (clarity)
5. Sizing (layout fit)

Apply modifications to exported spec, test in artifact, finalize for Angular.
