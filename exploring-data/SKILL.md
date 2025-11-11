---
name: exploring-data
description: Comprehensive exploratory data analysis (EDA) for uploaded datasets. Use when users upload .csv, .xlsx, .json, .parquet files or ask to explore, analyze, profile, or understand their data. Generates interactive HTML artifacts with visualizations and insights.
---

# Exploring Data - Comprehensive EDA Orchestration

## Core Philosophy

Provide thorough, automated exploratory data analysis that combines statistical profiling, visualization, and actionable insights. Generate a comprehensive HTML artifact that users can interact with and share.

## When to Use This Skill

Trigger when users:
- Upload data files (.csv, .xlsx, .json, .parquet, .tsv)
- Request "explore my data", "analyze this dataset", "profile this data"
- Ask "what's in this file?", "summarize this data", "show me insights"
- Need to understand data before modeling or analysis
- Want to identify data quality issues

## Workflow Overview

When user uploads data or requests EDA:

1. **Load and validate** data from `/mnt/user-data/uploads/`
2. **Profile** dataset systematically
3. **Generate visualizations** for distributions, correlations, relationships
4. **Identify issues** (missing data, outliers, skewness, duplicates)
5. **Create artifact** with all findings in interactive HTML

## EDA Analysis Steps

### Step 1: Data Loading & Initial Inspection

```python
import pandas as pd
import numpy as np
from pathlib import Path

# Detect and load file
uploads_dir = Path('/mnt/user-data/uploads')
files = list(uploads_dir.glob('*'))
data_file = files[0]  # Or ask user which file

# Load based on extension
if data_file.suffix == '.csv':
    df = pd.read_csv(data_file)
elif data_file.suffix == '.xlsx':
    df = pd.read_excel(data_file)
elif data_file.suffix == '.json':
    df = pd.read_json(data_file)
elif data_file.suffix == '.parquet':
    df = pd.read_parquet(data_file)
```

### Step 2: Dataset Profiling

Generate comprehensive profile including:

**Basic Statistics:**
```python
# Shape and structure
n_rows, n_cols = df.shape
memory_usage = df.memory_usage(deep=True).sum() / 1024**2  # MB

# Missing data
missing_counts = df.isnull().sum()
missing_pct = (missing_counts / len(df) * 100).round(2)

# Duplicates
n_duplicates = df.duplicated().sum()
duplicate_pct = (n_duplicates / len(df) * 100).round(2)

# Data types
dtypes_summary = df.dtypes.value_counts()
```

**Column Analysis:**
```python
# For each column, determine:
# - Data type (numeric, categorical, datetime, text)
# - Cardinality (unique values)
# - Missing values
# - Basic stats (min, max, mean, median for numeric)
# - Top values (for categorical)

column_profiles = {}
for col in df.columns:
    profile = {
        'dtype': str(df[col].dtype),
        'missing': df[col].isnull().sum(),
        'missing_pct': (df[col].isnull().sum() / len(df) * 100).round(2),
        'unique': df[col].nunique(),
        'cardinality': df[col].nunique() / len(df)
    }
    
    if pd.api.types.is_numeric_dtype(df[col]):
        profile.update({
            'mean': df[col].mean(),
            'median': df[col].median(),
            'std': df[col].std(),
            'min': df[col].min(),
            'max': df[col].max(),
            'q1': df[col].quantile(0.25),
            'q3': df[col].quantile(0.75),
            'skewness': df[col].skew(),
            'kurtosis': df[col].kurtosis()
        })
    elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_categorical_dtype(df[col]):
        top_values = df[col].value_counts().head(10)
        profile['top_values'] = top_values.to_dict()
    
    column_profiles[col] = profile
```

### Step 3: Data Quality Assessment

Identify issues:

```python
quality_issues = []

# Missing data issues
if missing_counts.sum() > 0:
    high_missing = missing_pct[missing_pct > 50]
    if len(high_missing) > 0:
        quality_issues.append({
            'type': 'high_missing',
            'severity': 'high',
            'columns': high_missing.index.tolist(),
            'description': f'{len(high_missing)} columns have >50% missing values'
        })

# High cardinality categoricals (potential IDs)
for col, profile in column_profiles.items():
    if profile['cardinality'] > 0.95 and not pd.api.types.is_numeric_dtype(df[col]):
        quality_issues.append({
            'type': 'high_cardinality',
            'severity': 'medium',
            'column': col,
            'description': f'{col} has {profile["unique"]} unique values - may be an ID'
        })

# Constant columns
constant_cols = [col for col in df.columns if df[col].nunique() == 1]
if constant_cols:
    quality_issues.append({
        'type': 'constant',
        'severity': 'medium',
        'columns': constant_cols,
        'description': f'{len(constant_cols)} columns have only one value'
    })

# Outliers (for numeric columns using IQR method)
outlier_summary = {}
for col in df.select_dtypes(include=[np.number]).columns:
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    outliers = ((df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))).sum()
    if outliers > 0:
        outlier_summary[col] = {
            'count': outliers,
            'percentage': (outliers / len(df) * 100).round(2)
        }
```

### Step 4: Visualization Generation

Create visualizations using matplotlib and seaborn:

**Numeric Distributions:**
```python
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64

def create_distribution_plot(df, col):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    
    # Histogram
    axes[0].hist(df[col].dropna(), bins=30, edgecolor='black', alpha=0.7)
    axes[0].set_title(f'{col} - Histogram')
    axes[0].set_xlabel(col)
    axes[0].set_ylabel('Frequency')
    
    # Boxplot
    axes[1].boxplot(df[col].dropna(), vert=True)
    axes[1].set_title(f'{col} - Boxplot')
    axes[1].set_ylabel(col)
    
    plt.tight_layout()
    
    # Convert to base64 for HTML embedding
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f'data:image/png;base64,{img_base64}'
```

**Correlation Matrix:**
```python
def create_correlation_heatmap(df):
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) < 2:
        return None
    
    corr_matrix = df[numeric_cols].corr()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', 
                center=0, square=True, ax=ax, cbar_kws={'shrink': 0.8})
    ax.set_title('Correlation Matrix')
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f'data:image/png;base64,{img_base64}'
```

**Categorical Distributions:**
```python
def create_categorical_plot(df, col, top_n=10):
    value_counts = df[col].value_counts().head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    value_counts.plot(kind='barh', ax=ax)
    ax.set_title(f'{col} - Top {top_n} Values')
    ax.set_xlabel('Count')
    ax.invert_yaxis()
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return f'data:image/png;base64,{img_base64}'
```

### Step 5: Generate HTML Artifact

Create interactive HTML report. See [references/html-template.md](references/html-template.md) for complete template structure.

The HTML artifact includes:
- Dataset overview with key metrics
- Data quality issues flagged by severity
- Column profiles with statistics
- Interactive tabs for different views
- Embedded visualizations (base64 encoded)
- Correlation matrix
- Missing data visualization

## Complete Workflow Implementation

Orchestrate all steps:

```python
def generate_eda_report(filepath):
    """Generate comprehensive EDA report from data file."""
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from datetime import datetime
    from io import BytesIO
    import base64
    
    # Set visualization style
    sns.set_style('whitegrid')
    plt.rcParams['figure.facecolor'] = 'white'
    
    # Load data
    if filepath.suffix == '.csv':
        df = pd.read_csv(filepath)
    elif filepath.suffix == '.xlsx':
        df = pd.read_excel(filepath)
    elif filepath.suffix == '.json':
        df = pd.read_json(filepath)
    elif filepath.suffix == '.parquet':
        df = pd.read_parquet(filepath)
    
    # Profile dataset (Steps 2-3)
    # Generate visualizations (Step 4)
    # Build HTML report (Step 5)
    
    # Save to outputs
    output_path = '/mnt/user-data/outputs/eda_report.html'
    with open(output_path, 'w') as f:
        f.write(html_output)
    
    return output_path
```

## Usage Pattern

When user uploads data:

1. **Detect file**: Check `/mnt/user-data/uploads/` for data files
2. **Confirm**: "I found {filename}. Generating comprehensive EDA report..."
3. **Execute**: Run complete analysis workflow
4. **Present**: Link to HTML artifact
5. **Summarize**: Extract 3-5 key insights

## Key Insights to Highlight

After generating report, summarize:

- **Data shape and quality**: "1000 rows, 15 columns, 2% missing data"
- **Column types**: "8 numeric, 5 categorical, 2 datetime"
- **Key issues**: "High correlation between X and Y (0.95), Z has 30% outliers"
- **Distributions**: "Revenue is right-skewed, Age is normally distributed"
- **Recommendations**: "Consider removing constant columns, investigate missing data in Column X"

## Advanced Features

### Time Series Analysis

If datetime columns detected:

```python
if datetime_cols:
    for col in datetime_cols:
        df[col] = pd.to_datetime(df[col])
        # Analyze trends, seasonality
        # Add time-based visualizations
```

### Multivariate Analysis

For relationship exploration:

```python
# Pairplot for numeric columns (limit to 6 for performance)
numeric_cols = df.select_dtypes(include=[np.number]).columns[:6]
if len(numeric_cols) > 1:
    pairplot = sns.pairplot(df[numeric_cols], diag_kind='kde')
    # Convert to base64 for HTML embedding
```

### Statistical Tests

Add hypothesis testing where relevant:

```python
from scipy.stats import normaltest

# Normality tests for numeric columns
for col in numeric_cols:
    stat, p = normaltest(df[col].dropna())
    # Flag if non-normal (p < 0.05)
```

## Performance Considerations

- **Large datasets** (>100k rows): Sample for visualizations
- **Many columns** (>50): Prioritize key columns
- **Memory**: Monitor usage, suggest chunking if needed
- **Visualization limit**: Max 20 plots for responsiveness

## Package Requirements

Uses pre-installed packages:
- **pandas 2.3.3** - Data manipulation
- **numpy 2.3.3** - Numerical operations
- **matplotlib 3.10.7** - Visualization
- **seaborn 0.13.2** - Statistical visualizations
- **scipy 1.16.2** - Statistical tests
- **scikit-learn 1.7.2** - ML preprocessing

## Constraints

**DO:**
- Always generate interactive HTML artifact
- Provide concise textual summary alongside artifact
- Handle common file formats (.csv, .xlsx, .json, .parquet)
- Identify and flag data quality issues
- Create visualizations for distributions and relationships
- Save outputs to `/mnt/user-data/outputs/`

**DON'T:**
- Use external profiling libraries (not pre-installed)
- Generate excessive plots (>20) for large datasets
- Assume column meanings without user context
- Make ML recommendations without being asked
- Skip quality checks

## Example Interaction

**User:** "Can you explore my sales data?"

**Assistant:** "I found `sales_2024.csv` (2.3 MB). Generating comprehensive EDA report...

[Creates report with visualizations, statistics, quality checks]

[View EDA Report](computer:///mnt/user-data/outputs/eda_report.html)

**Key Findings:**
- 12,450 transactions across 8 columns
- Revenue shows right skew: median $127, outliers up to $15k
- 3.2% missing values in 'customer_id' column
- Strong correlation (0.82) between quantity and total_amount
- Seasonal pattern detected: Q4 peaks

Would you like me to investigate any specific aspect further?"
