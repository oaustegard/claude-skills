# Vega-Lite Examples Inventory

This is a reference inventory of chart types from the official Vega-Lite examples gallery. Use this to identify appropriate chart patterns when analyze_data.py suggestions are insufficient or when user requests specific uncommon chart types.

## Bar Charts (16 examples)
- Simple Bar Chart
- Aggregate Bar Chart (Sorted)
- Grouped Bar Chart
- Stacked Bar Chart (standard, rounded corners, horizontal)
- Normalized (Percentage) Stacked Bar Chart
- Gantt Chart (Ranged Bar Marks)
- Layered Bar Chart
- Diverging Stacked Bar Chart (Population Pyramid, with Neutral Parts)
- Bar Chart with Labels/Overlays
- Bar Chart with Negative Values
- Heat Lane Chart

## Histograms & Distributions (11 examples)
- Histogram (standard, binned, log-scaled, non-linear)
- Relative Frequency Histogram
- Density Plot
- Stacked Density Estimates
- 2D Histogram Scatterplot/Heatmap
- Cumulative Frequency Distribution
- Wilkinson Dot Plot
- Isotype Dot Plot (standard, with Emoji)

## Scatter & Strip Plots (10 examples)
- Scatterplot (standard, colored, with null values, filled circles)
- 1D Strip Plot / Strip Plot
- Bubble Plot (standard, Gapminder, Natural Disasters)
- Scatter Plot with Text Marks
- Image-based Scatter Plot
- Strip plot with custom axis tick labels
- Dot Plot with Jittering

## Line Charts (15 examples)
- Line Chart (standard, with point markers, stroked markers)
- Multi Series Line Chart (standard, with repeat, with halo stroke)
- Slope Graph
- Step Chart
- Line Chart with Monotone Interpolation
- Connected Scatterplot (custom paths)
- Bump Chart
- Line Chart with Varying Size (trail mark)
- Comet Chart
- Line Chart with Markers and Invalid Values
- Line Charts Showing Ranks Over Time
- Sine/Cosine Curves (sequence generator)
- Line chart with varying stroke dash

## Area Charts & Streamgraphs (6 examples)
- Area Chart (standard, with gradient, with overlaying lines)
- Stacked Area Chart
- Normalized Stacked Area Chart
- Streamgraph
- Horizon Graph

## Table-based Plots (7 examples)
- Table Heatmap
- Annual Weather Heatmap
- 2D Histogram Heatmap
- Table Bubble Plot (Github Punch Card)
- Heatmap with Labels
- Lasagna Plot (Dense Time-Series Heatmap)
- Mosaic Chart with Labels
- Wind Vector Map

## Circular Plots (6 examples)
- Pie Chart (standard, with percentage tooltip, with labels)
- Donut Chart
- Radial Plot
- Pyramid Pie Chart

## Advanced Calculations (14 examples)
- Calculate Difference from Average/Annual Average
- Calculate Residuals
- Waterfall Chart
- Filtering Top-K Items / Top-K Plot with "Others"
- Lookup transform to combine data
- Parallel Coordinate Plot
- Bar Chart Showing Argmax Value
- Layering Averages over Raw Values
- Layering Rolling Averages over Raw Values
- Quantile-Quantile Plot (QQ Plot)
- Linear/Loess Regression
- Window transform for imputation

## Error Bars & Error Bands (4 examples)
- Error Bars (confidence interval, standard deviation)
- Line Chart with Confidence Interval Band
- Scatterplot with Mean and Standard Deviation Overlay

## Box Plots (3 examples)
- Box Plot with Min/Max Whiskers
- Tukey Box Plot (1.5 IQR)
- Box Plot with Pre-Calculated Summaries

## Labeling & Annotation (10 examples)
- Bar Chart with Labels (standard, with emojis)
- Layering text over heatmap
- Bar Chart Highlighting Values beyond Threshold
- Mean overlay over precipitation chart
- Histogram with Global Mean Overlay
- Line Chart with Highlighted Rectangles
- Distributions and Medians of Likert Scale Ratings
- Comparative Likert Scale Ratings

## Other Layered Plots (6 examples)
- Candlestick Chart
- Ranged Dot Plot
- Bullet Chart
- Layered Plot with Dual-Axis
- Weekly Weather Plot
- Wheat and Wages Example

## Faceting (9 examples)
- Trellis Bar/Stacked Bar Chart
- Trellis Scatter Plot (wrapped, Anscombe's Quartet)
- Trellis Histograms
- Becker's Barley Trellis Plot
- Trellis Area (standard, annual temperatures)
- Faceted Density Plot
- Compact Trellis Grid of Bar Charts

## Repeat & Concatenation (9 examples)
- Repeat and Layer for Different Measures
- Vertical/Horizontal Concatenation
- Interactive Scatterplot Matrix
- Marginal Histograms
- Discretizing scales
- Nested View Concatenation
- Population Pyramid

## Geographic/Maps (7 examples)
- Choropleth of Unemployment Rate
- One Dot per Zipcode/Airport in US
- Rules Connecting Airports
- Three Choropleths (disjoint data)
- US State Capitals on Map
- Line between Airports
- Income by State, Faceted
- London Tube Lines
- Projection explorer
- Earthquakes

## Interactive Charts (30+ examples)
- Bar Chart with Highlighting/Selection
- Histogram with Full-Height Hover Targets
- Interactive Legend
- Scatterplot with External Links and Tooltips
- Rectangular Brush / Area Chart with Brush
- Paintbrush Highlight
- Scatterplot Pan & Zoom
- Query Widgets
- Interactive Average
- Multi Series with Interactive Highlight (line, point, labels, tooltip)
- Isotype Grid
- Brushing Scatter to show table
- Selectable Heatmap
- Bar Chart with Minimap
- Interactive Index Chart
- Focus + Context (Smooth Histogram Zooming)
- Dynamic Color Legend
- Search Input
- Change zorder on hover
- Overview and Detail
- Crossfilter (Filter/Highlight)
- Interactive Scatterplot Matrix
- Interactive Dashboard with Cross Highlight
- Seattle Weather Exploration
- Connections among Airports
- Interactive scatter of global health statistics

## Usage Pattern

When user requests uncommon chart or analyze_data.py insufficient:

1. Search this inventory for relevant pattern
2. If found, construct spec using pattern from spec-builder-patterns.md or by fetching Vega-Lite example
3. If not found in inventory, fall back to programmatic builder

Priority order: spec-builder-patterns.md > this inventory > web_fetch Vega-Lite docs
