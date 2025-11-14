# Online Documentation Resources

**Progressive disclosure strategy:** Fetch these URLs only when user's request requires features beyond basic templates.

## When to Fetch Documentation

**DO NOT fetch preemptively.** Only fetch when:
- User requests feature not in skill templates (e.g., "add brush selection", "use conditional formatting")
- Error occurs that requires spec validation
- User asks "how do I..." for advanced feature
- Need to understand parameter syntax for complex interaction

**DO NOT fetch for:**
- Basic charts covered in templates (bar, line, scatter, pie, heatmap, area)
- Standard customizations in customization.md (colors, tooltips, axis formatting)
- Data structure questions (use analyze_data.py instead)

## Core Reference Pages

### Spec Structure
**URL:** https://vega.github.io/vega-lite/docs/spec.html
**When to fetch:**
- User asks about overall spec structure
- Need to understand top-level properties
- Validating spec completeness

**Contains:**
- Complete spec schema
- Required vs optional properties
- Top-level configuration options

### Mark Types
**URL:** https://vega.github.io/vega-lite/docs/mark.html
**When to fetch:**
- User requests mark type not in templates
- Need mark-specific properties (cornerRadius, interpolate, etc.)
- Understanding mark styling options

**Contains:**
- All mark types (bar, line, point, area, rect, text, tick, circle, square, rule, geoshape, boxplot, errorbar, errorband)
- Mark property reference
- Mark-specific configuration

### Encoding Channels
**URL:** https://vega.github.io/vega-lite/docs/encoding.html
**When to fetch:**
- User wants encoding channel not used in templates (angle, radius, shape, strokeWidth, etc.)
- Complex multi-field encoding needed
- Understanding encoding precedence

**Contains:**
- All encoding channels (x, y, color, size, shape, opacity, etc.)
- Channel-specific properties
- Type compatibility rules

## Interactive Features

### Selections (Parameters)
**URL:** https://vega.github.io/vega-lite/docs/selection.html
**When to fetch:**
- User says "interactive", "clickable", "filter by clicking"
- Need brush, interval, or point selection
- Linking multiple views with shared selection

**Contains:**
- Selection types (point, interval, brush)
- Selection configuration
- Cross-view selection binding
- Selection predicates

### Conditions
**URL:** https://vega.github.io/vega-lite/docs/condition.html
**When to fetch:**
- User wants conditional styling ("color positive values green")
- Selection-based styling needed
- Data-driven visual encoding

**Contains:**
- Conditional encoding syntax
- Test expressions
- Selection-based conditions
- Value-based conditions

### Tooltips
**URL:** https://vega.github.io/vega-lite/docs/tooltip.html
**When to fetch:**
- User wants custom tooltip formatting beyond examples in customization.md
- Need to disable/customize default tooltips
- Multi-field tooltip with complex formatting

**Contains:**
- Tooltip encoding options
- Formatting specifications
- Disabling tooltips
- Custom tooltip content

## Data Transformations

### Transform Overview
**URL:** https://vega.github.io/vega-lite/docs/transform.html
**When to fetch:**
- User needs data transformation not in basic templates
- Request for filtering, aggregation, calculation, binning
- Need to understand transform pipeline

**Contains:**
- Transform types overview
- Transform ordering
- Common patterns

### Aggregate
**URL:** https://vega.github.io/vega-lite/docs/aggregate.html
**When to fetch:**
- User wants "sum by category", "average per month", etc.
- Grouping and aggregation needed
- Statistical operations required

**Contains:**
- Aggregate operations (count, sum, mean, median, min, max, etc.)
- Grouping syntax
- Multiple aggregations

### Filter
**URL:** https://vega.github.io/vega-lite/docs/filter.html
**When to fetch:**
- User wants to "show only", "exclude", "filter data"
- Predicate expressions needed
- Time-based filtering

**Contains:**
- Filter predicate syntax
- Comparison operators
- Logical operators (and, or, not)
- Field predicates

### Calculate
**URL:** https://vega.github.io/vega-lite/docs/calculate.html
**When to fetch:**
- User needs computed fields
- Mathematical operations on existing fields
- Derived values

**Contains:**
- Expression syntax
- Available functions
- Field references

### Bin
**URL:** https://vega.github.io/vega-lite/docs/bin.html
**When to fetch:**
- User wants histogram
- Need to create value ranges
- Binning continuous data

**Contains:**
- Bin parameters (maxbins, step, extent)
- Binning strategies
- Custom bin specification

## Layout and Composition

### Faceting
**URL:** https://vega.github.io/vega-lite/docs/facet.html
**When to fetch:**
- User wants "small multiples", "one chart per category"
- Trellis plots needed
- Grid layouts of charts

**Contains:**
- Facet encoding
- Row and column facets
- Facet configuration

### Layer
**URL:** https://vega.github.io/vega-lite/docs/layer.html
**When to fetch:**
- User wants multiple marks on same chart (e.g., line + points)
- Overlay visualizations needed
- Combining different mark types

**Contains:**
- Layer specification
- Shared encodings
- Layer-specific encodings

### Concat
**URL:** https://vega.github.io/vega-lite/docs/concat.html
**When to fetch:**
- User wants multiple independent charts side-by-side
- Dashboard-style layouts
- Horizontal/vertical concatenation

**Contains:**
- Concat specification
- Horizontal and vertical concat
- Flexible composition

### Repeat
**URL:** https://vega.github.io/vega-lite/docs/repeat.html
**When to fetch:**
- User wants same chart template for multiple fields
- Scatterplot matrix (SPLOM)
- Repeated specifications

**Contains:**
- Repeat specification
- Row and column repeat
- Field substitution

## Styling and Configuration

### Scale
**URL:** https://vega.github.io/vega-lite/docs/scale.html
**When to fetch:**
- User needs custom scale configuration beyond color schemes
- Domain/range customization
- Scale type questions (linear, log, sqrt, etc.)

**Contains:**
- Scale types
- Domain and range
- Scale properties (clamp, padding, nice, etc.)
- Color schemes

### Axis
**URL:** https://vega.github.io/vega-lite/docs/axis.html
**When to fetch:**
- User needs axis customization beyond format strings
- Custom tick placement
- Axis styling details

**Contains:**
- Axis properties
- Tick configuration
- Grid lines
- Axis orientation

### Legend
**URL:** https://vega.github.io/vega-lite/docs/legend.html
**When to fetch:**
- User needs legend customization beyond position
- Custom legend formatting
- Legend styling

**Contains:**
- Legend properties
- Symbol configuration
- Label formatting
- Legend layout

### Title
**URL:** https://vega.github.io/vega-lite/docs/title.html
**When to fetch:**
- User needs complex title configuration
- Subtitle, anchor positioning
- Title styling details

**Contains:**
- Title properties
- Subtitle support
- Positioning options
- Text styling

## Time Series Specific

### Time Unit
**URL:** https://vega.github.io/vega-lite/docs/timeunit.html
**When to fetch:**
- User has temporal data needing aggregation by time unit
- "Group by month", "show by year" requests
- Time-based binning

**Contains:**
- Time unit types (year, quarter, month, week, day, hour, etc.)
- Time unit transformations
- Temporal binning

## Examples Gallery

### Example Gallery
**URL:** https://vega.github.io/vega-lite/examples/
**When to fetch:**
- User's request matches complex pattern not in templates
- Need inspiration for advanced visualization
- Looking for specific example type

**Contains:**
- Categorized examples
- Interactive specs
- Copy-paste ready code

**Browse by category:**
- Single view: https://vega.github.io/vega-lite/examples/#single-view-plots
- Composite views: https://vega.github.io/vega-lite/examples/#composite-marks
- Interactive: https://vega.github.io/vega-lite/examples/#interactive
- Geo: https://vega.github.io/vega-lite/examples/#geographic

## Fetching Strategy

**Step 1: Identify need**
```
IF user_request requires [feature]:
  IDENTIFY most specific documentation page for [feature]
ELSE:
  USE templates and existing references
```

**Step 2: Fetch documentation**
```bash
# Use web_search tool to fetch specific URL
# Extract relevant section from page
# Apply pattern to user's data
```

**Step 3: Synthesize and apply**
```
EXTRACT relevant syntax from fetched docs
MODIFY user's spec with new feature
TEST in artifact
PROVIDE updated link
```

## URL Structure Pattern

All Vega-Lite docs follow this pattern:
```
https://vega.github.io/vega-lite/docs/[TOPIC].html
```

**Common topics:**
- mark.html, encoding.html, transform.html
- [specific-transform].html (aggregate.html, filter.html, etc.)
- [specific-encoding].html (color.html, size.html, etc.)
- config.html (global configuration)
- data.html (data loading options)

**To find specific feature documentation:**
1. Check if topic exists in inventory above
2. If not, construct URL: `https://vega.github.io/vega-lite/docs/[topic-name].html`
3. Fetch and validate URL works
4. Extract relevant information

## Critical Rules

1. **Only fetch when necessary** - Don't preload documentation
2. **Be specific** - Fetch exact page needed, not entire doc site
3. **Extract and apply** - Don't just link to docs, implement the solution
4. **Cache knowledge** - If fetched once in conversation, reuse that knowledge
5. **Verify applicability** - Ensure fetched pattern works with user's data structure
