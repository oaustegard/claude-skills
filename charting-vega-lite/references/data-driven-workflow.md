# Data-Driven Workflow: Edge Cases and Advanced Patterns

**IMPORTANT: Standard workflows are in SKILL.md. Only consult this file for edge cases.**

This reference covers scenarios NOT handled by Primary/Secondary workflows in SKILL.md:
- Multi-file datasets requiring joins
- Performance optimization for very large datasets (>100K rows)
- Complex validation scenarios
- Advanced error recovery patterns
- Custom aggregation before visualization

**For standard data upload → chart creation, use SKILL.md workflows directly.**

## Edge Case 1: Multi-File Datasets

When user uploads multiple related files needing joins:

### Identify Join Scenario
```python
# User uploads: sales.csv, products.csv, customers.csv
# Asks: "Show sales by product category and customer region"

import pandas as pd

# Load files
sales = pd.read_csv('/mnt/user-data/uploads/sales.csv')
products = pd.read_csv('/mnt/user-data/uploads/products.csv')
customers = pd.read_csv('/mnt/user-data/uploads/customers.csv')

# Identify join keys
print("Sales columns:", sales.columns.tolist())
print("Products columns:", products.columns.tolist())
print("Customers columns:", customers.columns.tolist())
# Look for: product_id, customer_id, etc.
```

### Execute Joins
```python
# Join datasets
merged = sales.merge(products, on='product_id', how='left')
merged = merged.merge(customers, on='customer_id', how='left')

# Save merged dataset
merged.to_csv('/mnt/user-data/uploads/merged_data.csv', index=False)

# NOW proceed with standard workflow:
# python prepare_data.py /mnt/user-data/uploads/merged_data.csv
```

### Edge Case: Missing Join Keys
If join keys don't match:
```python
# Fuzzy matching or manual mapping required
# Example: "product_name" vs "name"
merged = sales.merge(
    products, 
    left_on='product_name', 
    right_on='name',
    how='left'
)
```

## Edge Case 2: Performance Optimization (Large Datasets)

When dataset >100K rows or file size >100MB:

### Strategy 1: Sampling
```python
import pandas as pd

df = pd.read_csv('/mnt/user-data/uploads/large_file.csv')
print(f"Original: {len(df)} rows")

# Random sample (maintains distribution)
sampled = df.sample(n=10000, random_state=42)
sampled.to_csv('/mnt/user-data/uploads/sampled_data.csv', index=False)

# Proceed with sampled data
# python prepare_data.py /mnt/user-data/uploads/sampled_data.csv

# NOTE in chart title: "Based on 10K sample from 500K records"
```

### Strategy 2: Aggregation
```python
# If time series with high frequency
df['date'] = pd.to_datetime(df['timestamp'])

# Aggregate to hourly/daily instead of per-second
aggregated = df.groupby(df['date'].dt.floor('H')).agg({
    'value': 'mean',
    'count': 'sum'
}).reset_index()

aggregated.to_csv('/mnt/user-data/uploads/aggregated_data.csv', index=False)
```

### Strategy 3: Filtering
```python
# Focus on relevant subset
filtered = df[df['category'].isin(['A', 'B', 'C'])]  # Top 3 categories
filtered = filtered[filtered['date'] >= '2024-01-01']  # Recent data only

filtered.to_csv('/mnt/user-data/uploads/filtered_data.csv', index=False)
```

## Edge Case 3: Data Quality Issues

### Missing Values
```python
df = pd.read_csv('/mnt/user-data/uploads/file.csv')

# Check missing values
print(df.isnull().sum())

# Strategy: Drop rows with missing key fields
df_clean = df.dropna(subset=['key_field1', 'key_field2'])

# OR: Fill with meaningful defaults
df['numeric_col'].fillna(df['numeric_col'].median(), inplace=True)
df['category_col'].fillna('Unknown', inplace=True)

df_clean.to_csv('/mnt/user-data/uploads/cleaned_data.csv', index=False)
```

### Outliers
```python
# Remove outliers (>3 standard deviations)
from scipy import stats
z_scores = np.abs(stats.zscore(df['value']))
df_no_outliers = df[z_scores < 3]

df_no_outliers.to_csv('/mnt/user-data/uploads/no_outliers.csv', index=False)
```

### Duplicate Records
```python
# Check for duplicates
duplicates = df.duplicated(subset=['id']).sum()
print(f"Found {duplicates} duplicates")

# Remove duplicates (keep first occurrence)
df_dedup = df.drop_duplicates(subset=['id'], keep='first')

df_dedup.to_csv('/mnt/user-data/uploads/deduped_data.csv', index=False)
```

## Edge Case 4: Complex Validation

When data structure is ambiguous:

### Validate Chart Requirements
```python
def validate_bar_chart(df, x_field, y_field):
    """Validate data fits bar chart requirements."""
    
    # Check x is categorical
    if df[x_field].nunique() > 50:
        return False, f"{x_field} has too many categories (>50)"
    
    # Check y is numeric
    if not pd.api.types.is_numeric_dtype(df[y_field]):
        return False, f"{y_field} is not numeric"
    
    # Check for nulls
    null_count = df[[x_field, y_field]].isnull().sum().sum()
    if null_count > 0:
        return False, f"Found {null_count} null values"
    
    return True, "Valid for bar chart"

# Use validation
valid, message = validate_bar_chart(df, 'category', 'value')
if not valid:
    # Inform user: message
    # Suggest alternatives or data cleaning
```

### Suggest Data Transformations
```python
# Too many categories? Suggest grouping
if df['category'].nunique() > 20:
    # Group by top N
    top_categories = df['category'].value_counts().head(10).index
    df['category_grouped'] = df['category'].apply(
        lambda x: x if x in top_categories else 'Other'
    )
    # Use 'category_grouped' for charting
```

## Edge Case 5: Advanced Error Recovery

### analyze_data.py Fails on Specific Data Types
```python
# Example: Mixed type columns causing issues

df = pd.read_csv('/mnt/user-data/uploads/problematic.csv')

# Fix mixed types
for col in df.columns:
    # Try numeric conversion
    try:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    except:
        pass
    
    # Try datetime conversion
    try:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    except:
        pass

# Save fixed version
df.to_csv('/mnt/user-data/uploads/fixed_data.csv', index=False)

# Retry analyze_data.py
```

### prepare_data.py Memory Issues
```python
# For very large files, process in chunks

chunk_size = 10000
chunks = []

for chunk in pd.read_csv('/mnt/user-data/uploads/huge_file.csv', 
                         chunksize=chunk_size):
    # Process chunk (filter, transform)
    processed = chunk[chunk['value'] > 0]
    chunks.append(processed)

# Combine processed chunks
result = pd.concat(chunks, ignore_index=True)
result.to_csv('/mnt/user-data/uploads/processed_data.csv', index=False)
```

## Edge Case 6: Custom Pre-Aggregation

When visualization requires pre-computed metrics:

### Example: Category Totals for Bar Chart
```python
# Raw data: transaction-level
# Needed: category totals

df = pd.read_csv('/mnt/user-data/uploads/transactions.csv')

# Aggregate by category
category_totals = df.groupby('category').agg({
    'amount': 'sum',
    'count': 'count'
}).reset_index()

category_totals.columns = ['category', 'total_amount', 'transaction_count']

# Save aggregated data
category_totals.to_csv('/mnt/user-data/uploads/category_summary.csv', index=False)

# Now use standard workflow
# python prepare_data.py /mnt/user-data/uploads/category_summary.csv
```

### Example: Time Series Resampling
```python
df = pd.read_csv('/mnt/user-data/uploads/timeseries.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

# Resample to daily (from minutely data)
daily = df.resample('D').agg({
    'value': 'mean',
    'count': 'sum'
}).reset_index()

daily.to_csv('/mnt/user-data/uploads/daily_data.csv', index=False)
```

## Performance Guidelines

**When to optimize:**
- File size >50MB → Consider sampling or aggregation
- Row count >100K → Sample or aggregate before visualization
- Column count >50 → Select relevant columns only
- Categories >50 → Group into top N + "Other"

**Optimization decision tree:**
```
IF rows > 100K AND user wants overview:
  → Sample to 10K-20K rows
ELSE IF rows > 100K AND user wants time trend:
  → Aggregate to lower frequency (hourly→daily, daily→weekly)
ELSE IF categories > 50:
  → Keep top 20, group rest as "Other"
ELSE IF file_size > 100MB:
  → Select relevant columns only
ELSE:
  → Use full dataset
```

## Critical Reminders

1. **These are EDGE CASES** - Standard workflows handle 95% of requests
2. **Simplify first** - Always try standard workflow before complex transformations
3. **Document transformations** - Tell user what was changed (sampled, aggregated, etc.)
4. **Preserve original data** - Save transformed data as new file
5. **Test standard workflow first** - Only use edge case patterns when standard fails

## When NOT to Use This Reference

**DO NOT consult this file for:**
- Standard data upload → chart creation (use SKILL.md Primary Workflow)
- Single file, reasonable size (<50MB, <100K rows)
- Clean data with clear types
- User requests standard chart types (bar, line, scatter, pie)
- Data already in good structure

**These scenarios use SKILL.md workflows without reading this reference.**
