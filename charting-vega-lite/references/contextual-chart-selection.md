# Contextual Chart Selection

## Principle

**Generic chart suggestions based solely on data types are insufficient.**

Chart selection must consider:
1. What the data represents (domain/context)
2. What questions the user likely wants answered
3. Which visualizations will reveal meaningful patterns
4. Practical readability constraints

## Decision Framework

### Step 1: Understand Data Context

**Read sample data and column names to infer domain:**

```python
# Example: Assay data
columns = ['Plate', 'Sample ID', 'Assay', 'Well', 'Signal', 'CV']
sample = df.head(10)
# → This is multi-analyte immunoassay data
```

**Common data domains:**
- **Biomedical:** Assays, patient records, clinical trials, imaging
- **Financial:** Transactions, time series, performance metrics, portfolios
- **IoT/Sensor:** Time series, spatial data, environmental monitoring
- **E-commerce:** Sales, user behavior, inventory, conversions
- **Scientific:** Experiments, measurements, observations, simulations

### Step 2: Map Domain to Analysis Questions

**For each domain, anticipate user's analytical goals:**

**Biomedical assay data:**
- Which biomarkers have strongest signals?
- Are there patterns across samples?
- What's the variability per assay?
- Any outliers or quality issues?
- Do sample groups differ?

**Financial time series:**
- What are the trends over time?
- How volatile is performance?
- Are there seasonal patterns?
- How do different assets compare?
- Where are inflection points?

**IoT sensor data:**
- What are temporal patterns?
- Are there anomalies?
- How do sensors correlate?
- What's the distribution of readings?
- Are there spatial patterns?

### Step 3: Select Charts That Answer Questions

**Match questions to chart types:**

| Question | Chart Type | Why |
|----------|-----------|-----|
| Compare categories | Bar, Box plot | Clear magnitude comparison |
| Show distribution | Histogram, Box plot | Reveals shape, outliers |
| Reveal patterns in matrix | Heatmap | Shows 2D relationships |
| Track changes over time | Line, Area | Temporal continuity |
| Find correlations | Scatter, Bubble | Shows relationships |
| Show composition | Stacked bar, Pie (if <7 categories) | Part-to-whole |
| Compare groups | Grouped bar, Faceted plots | Multi-series comparison |

### Step 4: Apply Readability Filters

**Eliminate impractical suggestions:**

```python
# Too many categories for pie chart
if chart_type == 'pie' and n_categories > 7:
    skip  # Unreadable

# Too many series for multi-line
if chart_type == 'multi-line' and n_series > 10:
    consider_faceting_or_filtering

# Heatmap with high cardinality
if chart_type == 'heatmap' and (x_unique > 50 or y_unique > 50):
    consider_aggregation_or_sampling
```

## Domain-Specific Examples

### Multi-Analyte Assay Data

**Context indicators:**
- Columns: Plate, Sample ID, Assay, Well, Signal, CV
- 51 unique assays
- 74 samples
- Numeric signal values

**Meaningful charts:**
1. **Bar: Mean Signal by Assay** → Which biomarkers are strongest?
2. **Heatmap: Sample × Assay** → Pattern recognition across plate
3. **Box plot: Signal by Assay** → Variability and quality metrics
4. **Histogram: Signal Distribution** → Overall data quality
5. **Scatter: Sample Index vs Signal** → Positional effects?
6. **Bar: Top 20 Assays** → Focus on most responsive markers

**Avoid:**
- Pie chart with 51 categories (unreadable)
- Line chart without temporal axis (inappropriate)
- Stacked bar (no meaningful composition question)

### Financial Time Series

**Context indicators:**
- Columns: Date, Ticker, Price, Volume
- Temporal data
- Multiple securities

**Meaningful charts:**
1. **Line: Price over Time** → Trend analysis
2. **Multi-line: Multiple Securities** → Comparative performance
3. **Stacked area: Volume by Ticker** → Market composition
4. **Scatter: Volume vs Price Change** → Liquidity patterns
5. **Box plot: Returns by Ticker** → Volatility comparison

**Avoid:**
- Bar chart of daily prices (loses continuity)
- Heatmap without meaningful 2D structure
- Pie chart of volumes (temporal aspect lost)

### E-commerce Sales

**Context indicators:**
- Columns: Date, Product, Category, Revenue, Units
- Transactional data
- Multiple products/categories

**Meaningful charts:**
1. **Line: Revenue over Time** → Growth trends
2. **Bar: Revenue by Category** → Category comparison
3. **Stacked bar: Revenue by Category over Time** → Composition changes
4. **Scatter: Units vs Revenue** → Pricing patterns
5. **Heatmap: Product × Month** → Seasonal patterns

## Anti-Patterns

**DON'T suggest charts just because data types match:**

❌ "You have nominal and quantitative fields, so here's a bar chart"
✅ "Your assay data has 51 biomarkers - bar chart shows which have strongest signals"

❌ "Here are 10 chart types that technically work with your data"
✅ "Here are 7 charts that answer key questions about your assay results"

❌ "Pie chart available because you have categories"
✅ "Skipping pie chart - 51 categories would be unreadable. Bar chart better for comparison."

## Implementation Pattern

```python
# 1. Infer domain
domain = infer_domain_from_columns_and_samples(df)

# 2. Get analysis questions for domain
questions = get_domain_questions(domain)

# 3. Map questions to chart types
candidates = map_questions_to_charts(questions, df)

# 4. Filter by readability
viable_charts = [c for c in candidates if is_readable(c, df)]

# 5. Prioritize by insight value
charts = sorted(viable_charts, key=lambda c: c.insight_score, reverse=True)[:8]
```

## Key Takeaway

**Chart selection is an analytical decision, not a template-matching exercise.**

Consider:
1. What does this data represent?
2. What will the user want to learn?
3. Which charts will reveal those insights?
4. Which charts are practically readable?

This produces focused, meaningful visualizations rather than exhaustive but generic options.
