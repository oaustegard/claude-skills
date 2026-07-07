# Chart Type Selection Reference

Comprehensive catalog of chart types with data requirements and use cases.

## Standard Chart Types

### Categorical Comparison (Nominal + Quantitative)
**Bar Chart** - Compare values across categories
- Data: One categorical field, one numeric field
- Use: Rankings, comparisons, distributions
- Template: `assets/templates/bar.json`

**Grouped Bar** - Compare multiple series across categories
- Data: Two categorical fields, one numeric field
- Use: Multi-series comparisons, subcategory analysis
- Build: Use color encoding for second categorical field

**Stacked Bar** - Show part-to-whole with categories
- Data: Two categorical fields, one numeric field
- Use: Composition within categories
- Build: Add `"stack": true` to y encoding

### Time Series (Temporal + Quantitative)
**Line Chart** - Show trends over time
- Data: Date/time field, one or more numeric fields
- Use: Trends, patterns, temporal relationships
- Template: `assets/templates/line.json`

**Area Chart** - Emphasize magnitude over time
- Data: Date/time field, one numeric field
- Use: Volume visualization, cumulative values
- Template: `assets/templates/area.json`

**Stacked Area** - Multiple series composition over time
- Data: Date/time field, category field, numeric field
- Use: Part-to-whole temporal analysis
- Build: Add color encoding by category, stack areas

### Correlation (Two Quantitative)
**Scatter Plot** - Reveal relationships between variables
- Data: Two numeric fields, optional category for color
- Use: Correlation analysis, outlier detection, clustering
- Template: `assets/templates/scatter.json`

**Bubble Chart** - Three-dimensional quantitative relationships
- Data: Three numeric fields (x, y, size), optional category
- Use: Multi-variable comparison
- Build: Add size encoding to scatter plot

### Part-to-Whole (Nominal + Quantitative)
**Pie Chart** - Show proportions of a whole
- Data: One categorical field, one numeric field
- Use: Simple proportions, limited categories (<7)
- Template: `assets/templates/pie.json`

**Donut Chart** - Pie with center emphasis
- Data: Same as pie chart
- Use: Same as pie, with focus metric in center
- Build: Set `innerRadius` in arc mark

### Two-Dimensional Categorical (Two Nominal + Quantitative)
**Heatmap** - Intensity across two dimensions
- Data: Two categorical fields, one numeric field
- Use: Patterns in matrix data, correlation matrices
- Template: `assets/templates/heatmap.json`

### Distribution (Quantitative)
**Histogram** - Frequency distribution
- Data: One numeric field
- Use: Distribution shape, outlier detection
- Build: Use bin transform with bar mark

**Box Plot** - Statistical distribution summary
- Data: Categorical field (groups), numeric field (values)
- Use: Compare distributions, identify outliers
- Build: Use boxplot mark type

## Advanced Patterns

### Multi-View Compositions

**Layered** - Overlay multiple marks
```javascript
"layer": [
  {"mark": "line", "encoding": {...}},
  {"mark": "point", "encoding": {...}}
]
```
Use: Combined chart types (line + points, area + line)

**Faceted** - Small multiples
```javascript
"facet": {"field": "category", "type": "nominal"},
"spec": {"mark": "bar", "encoding": {...}}
```
Use: Compare patterns across categories

**Concatenated** - Side-by-side views
```javascript
"hconcat": [
  {"mark": "bar", ...},
  {"mark": "line", ...}
]
```
Use: Different aspects of same dataset

### Interactive Patterns

**Brush and Link** - Cross-filtering across views
- Use: Explore data across multiple dimensions
- Pattern: Selection parameter shared between views

**Zoom and Filter** - Detail on demand
- Use: Large datasets with focus + context
- Pattern: Dual-view with interval selection

**Tooltips** - Contextual information
- Use: Additional details on hover
- Pattern: Multi-field tooltip encoding

## Selection Guide

### By Data Structure

| X Field | Y Field | Color | Chart Type |
|---------|---------|-------|------------|
| Nominal | Quantitative | - | Bar |
| Temporal | Quantitative | Nominal | Line (colored) |
| Quantitative | Quantitative | Nominal | Scatter |
| Nominal | Nominal | Quantitative | Heatmap |
| - | - | Nominal/Theta | Pie |

### By Question

| Question | Chart Type | Why |
|----------|------------|-----|
| How do categories compare? | Bar | Direct magnitude comparison |
| What's the trend over time? | Line | Temporal continuity |
| Are these variables related? | Scatter | Correlation visibility |
| What's the distribution? | Histogram | Frequency patterns |
| How do parts make up the whole? | Pie/Stacked Bar | Proportional relationships |
| What patterns exist in 2D categories? | Heatmap | Density/intensity visualization |

### By Data Volume

| Rows | Suggested Types | Avoid |
|------|-----------------|-------|
| <50 | Bar, Pie, Scatter | Aggregated views |
| 50-500 | Line, Scatter, Bar | Pie (too many slices) |
| 500-5000 | Line, Heatmap, Aggregated bar | Individual point scatter |
| 5000+ | Binned/aggregated, Heatmap | Raw scatter, detailed bar |

## Template Usage

All templates use placeholder syntax:
- `__DATA__`: Will be replaced with actual data array
- `__X_FIELD__`, `__Y_FIELD__`, etc.: Field names from data
- `__X_TYPE__`, `__Y_TYPE__`, etc.: Vega-Lite type (nominal/quantitative/temporal/ordinal)

Load template, replace placeholders, use resulting spec.
