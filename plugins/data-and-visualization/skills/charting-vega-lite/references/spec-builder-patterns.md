# Spec Builder Patterns: Build Charts Programmatically

**PURPOSE:** Build Vega-Lite specs from scratch without templates. Use when analyze_data.py suggests chart types beyond the 6 basic templates.

**PRINCIPLE:** Vega-Lite specs are just JSON. Build them programmatically based on data patterns.

## Core Spec Structure

Every Vega-Lite spec follows this pattern:
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "width": "container",
  "height": 400,
  "data": {},
  "mark": "MARK_TYPE",
  "encoding": {
    "CHANNEL": {"field": "FIELD_NAME", "type": "FIELD_TYPE"}
  }
}
```

## Building Specs by Pattern

### Pattern: Simple Bar Chart
```python
def build_bar_chart(x_field, x_type, y_field, y_type):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "bar",
        "encoding": {
            "x": {"field": x_field, "type": x_type},
            "y": {"field": y_field, "type": y_type}
        }
    }
```

### Pattern: Grouped Bar Chart
```python
def build_grouped_bar(x_field, y_field, color_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "bar",
        "encoding": {
            "x": {"field": x_field, "type": "nominal"},
            "y": {"field": y_field, "type": "quantitative"},
            "color": {"field": color_field, "type": "nominal"},
            "xOffset": {"field": color_field}
        }
    }
```

### Pattern: Stacked Bar Chart
```python
def build_stacked_bar(x_field, y_field, color_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "bar",
        "encoding": {
            "x": {"field": x_field, "type": "nominal"},
            "y": {"field": y_field, "type": "quantitative", "stack": True},
            "color": {"field": color_field, "type": "nominal"}
        }
    }
```

### Pattern: Histogram
```python
def build_histogram(field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "bar",
        "encoding": {
            "x": {"field": field, "type": "quantitative", "bin": True},
            "y": {"aggregate": "count", "type": "quantitative"}
        }
    }
```

### Pattern: Box Plot
```python
def build_box_plot(x_field, y_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": {"type": "boxplot", "extent": "min-max"},
        "encoding": {
            "x": {"field": x_field, "type": "nominal"},
            "y": {"field": y_field, "type": "quantitative"}
        }
    }
```

### Pattern: Multi-Series Line Chart
```python
def build_multi_line(x_field, y_field, color_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "line",
        "encoding": {
            "x": {"field": x_field, "type": "temporal"},
            "y": {"field": y_field, "type": "quantitative"},
            "color": {"field": color_field, "type": "nominal"}
        }
    }
```

### Pattern: Stacked Area Chart
```python
def build_stacked_area(x_field, y_field, color_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "area",
        "encoding": {
            "x": {"field": x_field, "type": "temporal"},
            "y": {"field": y_field, "type": "quantitative", "stack": True},
            "color": {"field": color_field, "type": "nominal"}
        }
    }
```

### Pattern: Strip Plot (1D Scatter)
```python
def build_strip_plot(x_field, y_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": {"type": "tick", "thickness": 2},
        "encoding": {
            "x": {"field": x_field, "type": "nominal"},
            "y": {"field": y_field, "type": "quantitative"}
        }
    }
```

### Pattern: Bubble Chart
```python
def build_bubble_chart(x_field, y_field, size_field, color_field=None):
    encoding = {
        "x": {"field": x_field, "type": "quantitative"},
        "y": {"field": y_field, "type": "quantitative"},
        "size": {"field": size_field, "type": "quantitative"}
    }
    if color_field:
        encoding["color"] = {"field": color_field, "type": "nominal"}
    
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "circle",
        "encoding": encoding
    }
```

### Pattern: Error Bars
```python
def build_error_bars(x_field, y_field, y_error_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "layer": [
            {
                "mark": {"type": "errorbar", "extent": "stdev"},
                "encoding": {
                    "x": {"field": x_field, "type": "nominal"},
                    "y": {"field": y_field, "type": "quantitative"}
                }
            },
            {
                "mark": {"type": "point", "filled": True},
                "encoding": {
                    "x": {"field": x_field, "type": "nominal"},
                    "y": {"field": y_field, "type": "quantitative", "aggregate": "mean"}
                }
            }
        ]
    }
```

### Pattern: Normalized Stacked Bar
```python
def build_normalized_bar(x_field, y_field, color_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "mark": "bar",
        "encoding": {
            "x": {"field": x_field, "type": "nominal"},
            "y": {
                "field": y_field,
                "type": "quantitative",
                "stack": "normalize",
                "axis": {"format": ".0%"}
            },
            "color": {"field": color_field, "type": "nominal"}
        }
    }
```

## Data Pattern → Chart Builder Decision Tree

```python
def select_chart_builder(fields):
    """Select appropriate chart builders based on data structure."""
    
    quant = [f for f in fields if f["type"] == "quantitative"]
    temp = [f for f in fields if f["type"] == "temporal"]
    nom = [f for f in fields if f["type"] == "nominal"]
    
    builders = []
    
    # Distribution patterns
    if len(quant) == 1 and len(nom) == 0:
        builders.append(("Histogram", build_histogram, [quant[0]["name"]]))
    
    # Comparison patterns
    if len(nom) >= 1 and len(quant) >= 1:
        builders.append(("Bar Chart", build_bar_chart, 
                        [nom[0]["name"], "nominal", quant[0]["name"], "quantitative"]))
        
        if len(nom) >= 2:
            builders.append(("Grouped Bar", build_grouped_bar,
                           [nom[0]["name"], quant[0]["name"], nom[1]["name"]]))
            builders.append(("Stacked Bar", build_stacked_bar,
                           [nom[0]["name"], quant[0]["name"], nom[1]["name"]]))
    
    # Distribution comparison
    if len(nom) >= 1 and len(quant) >= 1:
        builders.append(("Box Plot", build_box_plot,
                        [nom[0]["name"], quant[0]["name"]]))
        builders.append(("Strip Plot", build_strip_plot,
                        [nom[0]["name"], quant[0]["name"]]))
    
    # Time series patterns
    if len(temp) >= 1 and len(quant) >= 1:
        if len(nom) >= 1:
            builders.append(("Multi-Line", build_multi_line,
                           [temp[0]["name"], quant[0]["name"], nom[0]["name"]]))
            builders.append(("Stacked Area", build_stacked_area,
                           [temp[0]["name"], quant[0]["name"], nom[0]["name"]]))
    
    # Correlation patterns
    if len(quant) >= 2:
        if len(quant) >= 3:
            builders.append(("Bubble Chart", build_bubble_chart,
                           [quant[0]["name"], quant[1]["name"], quant[2]["name"]]))
        
        if len(nom) >= 1:
            builders.append(("Colored Scatter", build_bubble_chart,
                           [quant[0]["name"], quant[1]["name"], None, nom[0]["name"]]))
    
    # Proportion patterns
    if len(nom) >= 2 and len(quant) >= 1:
        builders.append(("Normalized Bar", build_normalized_bar,
                        [nom[0]["name"], quant[0]["name"], nom[1]["name"]]))
    
    return builders
```

## Usage in Workflow

**Instead of loading templates:**
```python
# Old way (template-constrained)
with open('templates/bar.json') as f:
    spec = json.load(f)

# New way (pattern-driven)
spec = build_bar_chart(
    x_field="category",
    x_type="nominal",
    y_field="value",
    y_type="quantitative"
)
```

**Build multiple chart variations:**
```python
import json

# Get data analysis
fields = analyze_result["fields"]

# Select chart builders
builders = select_chart_builder(fields)

# Generate specs
chart_objects = []
for name, builder_func, args in builders:
    spec = builder_func(*args)
    chart_objects.append({
        "type": name,
        "reason": f"Generated from pattern: {name.lower()}",
        "spec": spec
    })

# Now have 8-12 chart options instead of just 3-5
```

## Advanced Patterns

### Layered Charts (Multiple Marks)
```python
def build_line_with_points(x_field, y_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": "container",
        "layer": [
            {
                "mark": "line",
                "encoding": {
                    "x": {"field": x_field, "type": "temporal"},
                    "y": {"field": y_field, "type": "quantitative"}
                }
            },
            {
                "mark": {"type": "point", "filled": True, "size": 50},
                "encoding": {
                    "x": {"field": x_field, "type": "temporal"},
                    "y": {"field": y_field, "type": "quantitative"}
                }
            }
        ]
    }
```

### Faceted Charts (Small Multiples)
```python
def build_faceted_bar(x_field, y_field, facet_field):
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "facet": {"field": facet_field, "type": "nominal"},
        "spec": {
            "width": 200,
            "mark": "bar",
            "encoding": {
                "x": {"field": x_field, "type": "nominal"},
                "y": {"field": y_field, "type": "quantitative"}
            }
        }
    }
```

## Exploring Vega-Lite Examples Gallery

**When user requests uncommon chart type:**

1. Search examples gallery: https://vega.github.io/vega-lite/examples/
2. Find relevant example
3. Fetch the spec JSON
4. Adapt to user's data structure

**Example process:**
```python
# User requests: "violin plot"
# 1. Not in basic templates
# 2. Check if in spec-builder-patterns.md → No
# 3. Fetch from examples gallery:

# Use web_search to find:
# https://vega.github.io/vega-lite/examples/[violin-plot-example].html

# Extract spec structure
# Adapt field names to user's data
# Generate spec
```

## Chart Type Categories from Vega-Lite

**Bar Charts (10+ variations):**
- Simple, grouped, stacked, normalized, horizontal, ranged

**Line Charts (8+ variations):**
- Simple, multi-series, stepped, monotone, area, trail

**Scatter & Strip (6+ variations):**
- Scatter, bubble, strip, jitter, connected scatter

**Distribution (6+ variations):**
- Histogram, box plot, violin plot, density plot, QQ plot

**Part-to-Whole (5+ variations):**
- Pie, donut, stacked bar, normalized bar, treemap

**Two-Dimensional (4+ variations):**
- Heatmap, density heatmap, hexbin, rect

**Advanced (10+ variations):**
- Error bars/bands, box plots, waterfall, parallel coordinates, sankey

## Critical Rules

1. **Don't be template-constrained** - Build specs programmatically
2. **Suggest 8-12 chart options** - Not just 3-5
3. **Use builders for variations** - Grouped, stacked, normalized
4. **Reference examples gallery** - For uncommon chart types
5. **Explain pattern reasoning** - Why this chart fits the data

## Integration with analyze_data.py

**Enhance suggestions beyond basic templates:**
```python
# In analyze_data.py, expand suggestions:
suggestions = []

# Always check for:
- Histograms (1 quantitative)
- Box plots (1 nominal + 1 quantitative)
- Grouped/stacked variations (2+ nominal + 1 quantitative)
- Multi-series (1 temporal + 1 quantitative + 1 nominal)
- Bubble charts (3+ quantitative)
- Strip plots (1 nominal + 1 quantitative)
- Normalized bars (2+ nominal + 1 quantitative)
```
