# HTML Template for EDA Reports

Complete HTML template with embedded styling and interactivity. Use this as the base structure, then inject generated data and visualizations.

## Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EDA Report: {dataset_name}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6; 
            color: #333; 
            background: #f5f5f5;
            padding: 20px;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        h1 { 
            color: #2c3e50; 
            border-bottom: 3px solid #3498db; 
            padding-bottom: 10px; 
            margin-bottom: 20px; 
        }
        h2 { 
            color: #34495e; 
            margin-top: 30px; 
            margin-bottom: 15px; 
            border-left: 4px solid #3498db; 
            padding-left: 15px; 
        }
        h3 { color: #555; margin-top: 20px; margin-bottom: 10px; }
        
        .summary-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin: 20px 0; 
        }
        .summary-card { 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 5px; 
            border-left: 4px solid #3498db; 
        }
        .summary-card .label { font-size: 0.9em; color: #666; }
        .summary-card .value { font-size: 1.8em; font-weight: bold; color: #2c3e50; }
        
        .issue { 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 5px; 
            border-left: 4px solid #e74c3c;
            background: #fee;
        }
        .issue.medium { border-left-color: #f39c12; background: #fef5e7; }
        .issue.low { border-left-color: #3498db; background: #e8f4f8; }
        .issue-title { font-weight: bold; margin-bottom: 5px; }
        
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td { 
            padding: 12px; 
            text-align: left; 
            border-bottom: 1px solid #ddd; 
        }
        th { 
            background: #3498db; 
            color: white; 
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        tr:hover { background: #f5f5f5; }
        
        .chart-container { 
            margin: 30px 0; 
            padding: 20px; 
            background: #fafafa; 
            border-radius: 8px; 
        }
        .chart-container img { 
            max-width: 100%; 
            height: auto; 
            display: block; 
            margin: 0 auto; 
        }
        
        .badge { 
            padding: 2px 8px; 
            border-radius: 3px; 
            font-size: 0.85em; 
            font-weight: 500;
        }
        .numeric-badge { background: #3498db; color: white; }
        .categorical-badge { background: #2ecc71; color: white; }
        .datetime-badge { background: #9b59b6; color: white; }
        .text-badge { background: #95a5a6; color: white; }
        
        .tabs { 
            display: flex; 
            gap: 10px; 
            margin: 20px 0; 
            border-bottom: 2px solid #ddd; 
            flex-wrap: wrap;
        }
        .tab { 
            padding: 10px 20px; 
            cursor: pointer; 
            background: #f8f9fa; 
            border-radius: 5px 5px 0 0; 
            transition: all 0.3s;
        }
        .tab:hover { background: #e9ecef; }
        .tab.active { 
            background: #3498db; 
            color: white; 
        }
        .tab-content { 
            display: none; 
            padding: 20px; 
            animation: fadeIn 0.3s;
        }
        .tab-content.active { display: block; }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .stat-box {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 5px 0;
        }
        .stat-label { 
            font-size: 0.85em; 
            color: #666; 
            font-weight: 500;
        }
        .stat-value { 
            font-size: 1.2em; 
            color: #2c3e50; 
            font-weight: bold;
        }
        
        .missing-bar {
            background: #ecf0f1;
            height: 30px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
        }
        .missing-fill {
            background: #e74c3c;
            height: 100%;
            transition: width 0.5s;
        }
        .missing-label {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.85em;
            font-weight: bold;
        }
        
        @media (max-width: 768px) {
            .summary-grid { grid-template-columns: 1fr; }
            .container { padding: 15px; }
            table { font-size: 0.9em; }
        }
    </style>
    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>📊 Exploratory Data Analysis Report</h1>
        <p style="color: #666; margin-bottom: 30px;">
            Dataset: <strong>{dataset_name}</strong> | 
            Generated: {timestamp}
        </p>
        
        <h2>📋 Dataset Overview</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">Rows</div>
                <div class="value">{n_rows:,}</div>
            </div>
            <div class="summary-card">
                <div class="label">Columns</div>
                <div class="value">{n_cols}</div>
            </div>
            <div class="summary-card">
                <div class="label">Missing Cells</div>
                <div class="value">{missing_cells:,}</div>
            </div>
            <div class="summary-card">
                <div class="label">Missing %</div>
                <div class="value">{missing_pct:.1f}%</div>
            </div>
            <div class="summary-card">
                <div class="label">Duplicate Rows</div>
                <div class="value">{n_duplicates:,}</div>
            </div>
            <div class="summary-card">
                <div class="label">Memory Usage</div>
                <div class="value">{memory_mb:.1f} MB</div>
            </div>
        </div>
        
        {quality_issues_section}
        
        <h2>📊 Column Profiles</h2>
        <div class="tabs">
            <div class="tab active" onclick="showTab('overview')">Overview</div>
            <div class="tab" onclick="showTab('statistics')">Statistics</div>
            <div class="tab" onclick="showTab('missing')">Missing Data</div>
        </div>
        
        <div id="overview" class="tab-content active">
            <table>
                <thead>
                    <tr>
                        <th>Column</th>
                        <th>Type</th>
                        <th>Unique</th>
                        <th>Missing</th>
                        <th>Sample Values</th>
                    </tr>
                </thead>
                <tbody>
                    {column_overview_rows}
                </tbody>
            </table>
        </div>
        
        <div id="statistics" class="tab-content">
            {numeric_stats_section}
        </div>
        
        <div id="missing" class="tab-content">
            {missing_data_section}
        </div>
        
        {visualizations_section}
        
        {correlation_section}
        
        <div style="margin-top: 50px; padding: 20px; background: #f8f9fa; border-radius: 5px; text-align: center; color: #666;">
            <p>Generated with Claude's exploring-data skill</p>
        </div>
    </div>
</body>
</html>
```

## Template Variables

Inject these variables into the template:

### Basic Info
- `{dataset_name}` - Name of the dataset file
- `{timestamp}` - Generation timestamp
- `{n_rows}` - Number of rows
- `{n_cols}` - Number of columns
- `{missing_cells}` - Total missing cells
- `{missing_pct}` - Percentage of missing data
- `{n_duplicates}` - Number of duplicate rows
- `{memory_mb}` - Memory usage in MB

### Sections
- `{quality_issues_section}` - HTML for data quality issues
- `{column_overview_rows}` - Table rows for column overview
- `{numeric_stats_section}` - Statistics table for numeric columns
- `{missing_data_section}` - Missing data visualizations
- `{visualizations_section}` - Distribution charts
- `{correlation_section}` - Correlation heatmap

## Building Sections

### Quality Issues Section

```python
def build_quality_issues_section(issues):
    if not issues:
        return '<p style="color: #27ae60; font-weight: 500;">✅ No significant data quality issues detected.</p>'
    
    html = '<h2>⚠️ Data Quality Issues</h2>'
    for issue in issues:
        severity_class = issue.get('severity', 'low')
        html += f'''
        <div class="issue {severity_class}">
            <div class="issue-title">{issue['type'].replace('_', ' ').title()}</div>
            <div>{issue['description']}</div>
        </div>
        '''
    return html
```

### Column Overview Rows

```python
def build_column_overview_rows(df, column_profiles):
    rows = []
    for col, profile in column_profiles.items():
        # Determine badge type
        dtype = str(profile['dtype'])
        if 'int' in dtype or 'float' in dtype:
            badge = '<span class="badge numeric-badge">Numeric</span>'
        elif 'object' in dtype or 'category' in dtype:
            badge = '<span class="badge categorical-badge">Categorical</span>'
        elif 'datetime' in dtype:
            badge = '<span class="badge datetime-badge">DateTime</span>'
        else:
            badge = '<span class="badge text-badge">Text</span>'
        
        # Sample values
        sample = df[col].dropna().head(3).tolist()
        sample_str = ', '.join(str(v) for v in sample)
        if len(sample_str) > 50:
            sample_str = sample_str[:50] + '...'
        
        rows.append(f'''
        <tr>
            <td><strong>{col}</strong></td>
            <td>{badge}</td>
            <td>{profile['unique']:,}</td>
            <td>{profile['missing']} ({profile['missing_pct']}%)</td>
            <td style="font-size: 0.9em; color: #666;">{sample_str}</td>
        </tr>
        ''')
    
    return '\n'.join(rows)
```

### Numeric Statistics Section

```python
def build_numeric_stats_section(column_profiles):
    numeric_profiles = {
        col: prof for col, prof in column_profiles.items() 
        if 'mean' in prof
    }
    
    if not numeric_profiles:
        return '<p>No numeric columns in dataset.</p>'
    
    html = '<table><thead><tr>'
    html += '<th>Column</th><th>Mean</th><th>Median</th><th>Std Dev</th>'
    html += '<th>Min</th><th>Max</th><th>Skewness</th></tr></thead><tbody>'
    
    for col, prof in numeric_profiles.items():
        html += f'''
        <tr>
            <td><strong>{col}</strong></td>
            <td>{prof['mean']:.2f}</td>
            <td>{prof['median']:.2f}</td>
            <td>{prof['std']:.2f}</td>
            <td>{prof['min']:.2f}</td>
            <td>{prof['max']:.2f}</td>
            <td>{prof['skewness']:.2f}</td>
        </tr>
        '''
    
    html += '</tbody></table>'
    return html
```

### Missing Data Section

```python
def build_missing_data_section(df):
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    
    if len(missing) == 0:
        return '<p style="color: #27ae60;">✅ No missing data detected.</p>'
    
    html = '<h3>Missing Values by Column</h3>'
    for col, count in missing.items():
        pct = (count / len(df) * 100)
        html += f'''
        <div style="margin: 15px 0;">
            <div style="margin-bottom: 5px;">
                <strong>{col}</strong>: {count:,} missing ({pct:.1f}%)
            </div>
            <div class="missing-bar">
                <div class="missing-fill" style="width: {pct}%"></div>
                <div class="missing-label">{pct:.1f}%</div>
            </div>
        </div>
        '''
    
    return html
```

### Visualizations Section

```python
def build_visualizations_section(df, column_profiles):
    html = '<h2>📈 Distributions</h2>'
    
    # Numeric columns (limit to first 10)
    numeric_cols = [
        col for col, prof in column_profiles.items() 
        if 'mean' in prof
    ][:10]
    
    for col in numeric_cols:
        img_data = create_distribution_plot(df, col)
        html += f'''
        <div class="chart-container">
            <h3>{col}</h3>
            <img src="{img_data}" alt="{col} distribution">
        </div>
        '''
    
    # Categorical columns (limit to first 5)
    categorical_cols = [
        col for col, prof in column_profiles.items()
        if 'top_values' in prof and prof['unique'] < 50
    ][:5]
    
    for col in categorical_cols:
        img_data = create_categorical_plot(df, col)
        html += f'''
        <div class="chart-container">
            <h3>{col}</h3>
            <img src="{img_data}" alt="{col} distribution">
        </div>
        '''
    
    return html
```

### Correlation Section

```python
def build_correlation_section(df):
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    if len(numeric_cols) < 2:
        return ''
    
    img_data = create_correlation_heatmap(df)
    
    html = '''
    <h2>🔗 Correlations</h2>
    <div class="chart-container">
        <img src="{}" alt="Correlation matrix">
    </div>
    '''.format(img_data)
    
    # Find strong correlations
    corr_matrix = df[numeric_cols].corr()
    high_corr = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            if abs(corr_matrix.iloc[i, j]) > 0.7:
                high_corr.append({
                    'col1': corr_matrix.columns[i],
                    'col2': corr_matrix.columns[j],
                    'corr': corr_matrix.iloc[i, j]
                })
    
    if high_corr:
        html += '<h3>Strong Correlations (|r| > 0.7)</h3><ul>'
        for item in high_corr:
            html += f'<li><strong>{item["col1"]}</strong> ↔ <strong>{item["col2"]}</strong>: {item["corr"]:.3f}</li>'
        html += '</ul>'
    
    return html
```

## Usage Example

```python
from datetime import datetime

# Generate all components
quality_issues_html = build_quality_issues_section(quality_issues)
column_overview_html = build_column_overview_rows(df, column_profiles)
numeric_stats_html = build_numeric_stats_section(column_profiles)
missing_data_html = build_missing_data_section(df)
visualizations_html = build_visualizations_section(df, column_profiles)
correlation_html = build_correlation_section(df)

# Inject into template
html_output = html_template.format(
    dataset_name='my_data.csv',
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    n_rows=len(df),
    n_cols=len(df.columns),
    missing_cells=df.isnull().sum().sum(),
    missing_pct=(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100),
    n_duplicates=df.duplicated().sum(),
    memory_mb=df.memory_usage(deep=True).sum() / 1024**2,
    quality_issues_section=quality_issues_html,
    column_overview_rows=column_overview_html,
    numeric_stats_section=numeric_stats_html,
    missing_data_section=missing_data_html,
    visualizations_section=visualizations_html,
    correlation_section=correlation_html
)

# Save
with open('/mnt/user-data/outputs/eda_report.html', 'w') as f:
    f.write(html_output)
```
