#!/usr/bin/env python3
"""
Extract key insights from ydata-profiling JSON for Claude to analyze.
Focuses on patterns, relationships, and quality issues rather than raw data.
"""
import json
import sys
from pathlib import Path

def extract_insights(profile_json_path):
    """Extract high-level insights optimized for LLM analysis."""
    with open(profile_json_path, 'r') as f:
        data = json.load(f)
    
    insights = {
        "dataset_overview": {},
        "variable_summary": {
            "numeric": [],
            "categorical": [],
            "temporal": [],
            "text": []
        },
        "data_quality": {
            "issues": [],
            "warnings": []
        },
        "patterns": {
            "correlations": [],
            "distributions": [],
            "relationships": []
        },
        "recommendations": []
    }
    
    # Dataset overview
    table = data.get('table', {})
    insights['dataset_overview'] = {
        "n_rows": table.get('n', 0),
        "n_cols": table.get('n_var', 0),
        "memory_size": table.get('memory_size', 0),
        "n_duplicates": table.get('n_duplicates', 0),
        "missing_cells": table.get('n_cells_missing', 0),
        "missing_pct": round(table.get('p_cells_missing', 0) * 100, 2)
    }
    
    variables = data.get('variables', {})
    correlations = data.get('correlations', {})
    
    # Analyze each variable
    for var_name, var in variables.items():
        vtype = var.get('type')
        n_missing = var.get('n_missing', 0)
        n_total = insights['dataset_overview']['n_rows']
        missing_pct = round((n_missing / n_total * 100), 2) if n_total > 0 else 0
        
        var_summary = {
            "name": var_name,
            "missing_pct": missing_pct,
            "n_unique": var.get('n_distinct', var.get('n_unique', 0))
        }
        
        if vtype == 'Numeric':
            # Skip if all missing
            if n_missing == n_total:
                continue
                
            var_summary.update({
                "mean": var.get('mean'),
                "std": var.get('std'),
                "min": var.get('min'),
                "max": var.get('max'),
                "skewness": var.get('skewness'),
                "n_zeros": var.get('n_zeros', 0),
                "n_infinite": var.get('n_infinite', 0)
            })
            
            # Detect patterns
            if var.get('n_zeros', 0) / n_total > 0.5:
                var_summary['note'] = "majority_zeros"
            elif var.get('skewness', 0) and abs(var.get('skewness', 0)) > 2:
                var_summary['note'] = "highly_skewed"
            elif var.get('std', 1) == 0:
                var_summary['note'] = "constant"
                
            insights['variable_summary']['numeric'].append(var_summary)
            
        elif vtype == 'Text':
            if n_missing == n_total:
                continue
                
            cardinality_ratio = var_summary['n_unique'] / n_total if n_total > 0 else 0
            var_summary['cardinality_ratio'] = round(cardinality_ratio, 3)
            
            # Classify
            if var_summary['n_unique'] == 1:
                var_summary['note'] = "constant"
            elif cardinality_ratio > 0.95:
                var_summary['note'] = "unique_identifier"
            elif cardinality_ratio < 0.5:
                var_summary['note'] = "categorical"
            else:
                var_summary['note'] = "high_cardinality"
                
            insights['variable_summary']['categorical'].append(var_summary)
            
        elif vtype == 'DateTime':
            var_summary.update({
                "min": var.get('min'),
                "max": var.get('max')
            })
            insights['variable_summary']['temporal'].append(var_summary)
    
    # Data quality issues
    if insights['dataset_overview']['missing_pct'] > 10:
        insights['data_quality']['issues'].append({
            "type": "high_missingness",
            "severity": "high" if insights['dataset_overview']['missing_pct'] > 30 else "medium",
            "description": f"{insights['dataset_overview']['missing_pct']}% of cells are missing"
        })
    
    if insights['dataset_overview']['n_duplicates'] > 0:
        dup_pct = round((insights['dataset_overview']['n_duplicates'] / insights['dataset_overview']['n_rows'] * 100), 2)
        insights['data_quality']['issues'].append({
            "type": "duplicates",
            "severity": "medium" if dup_pct > 1 else "low",
            "description": f"{insights['dataset_overview']['n_duplicates']} duplicate rows ({dup_pct}%)"
        })
    
    # Check for constant/useless columns
    constant_vars = [v['name'] for v in insights['variable_summary']['numeric'] if v.get('note') == 'constant']
    constant_vars += [v['name'] for v in insights['variable_summary']['categorical'] if v.get('note') == 'constant']
    if constant_vars:
        insights['data_quality']['warnings'].append({
            "type": "constant_columns",
            "count": len(constant_vars),
            "columns": constant_vars[:5]  # Show first 5
        })
    
    # Identify potential ID columns
    id_cols = [v['name'] for v in insights['variable_summary']['categorical'] if v.get('note') == 'unique_identifier']
    if id_cols:
        insights['data_quality']['warnings'].append({
            "type": "identifier_columns",
            "count": len(id_cols),
            "columns": id_cols[:5]
        })
    
    # Extract correlations (if available)
    if correlations and 'pearson' in correlations:
        pearson = correlations['pearson']
        # Find high correlations
        high_corrs = []
        processed_pairs = set()
        
        for var1, corr_dict in pearson.items():
            if isinstance(corr_dict, dict):
                for var2, corr_val in corr_dict.items():
                    if var1 != var2 and isinstance(corr_val, (int, float)):
                        pair = tuple(sorted([var1, var2]))
                        if pair not in processed_pairs and abs(corr_val) > 0.7:
                            high_corrs.append({
                                "var1": var1,
                                "var2": var2,
                                "correlation": round(corr_val, 3)
                            })
                            processed_pairs.add(pair)
        
        if high_corrs:
            insights['patterns']['correlations'] = sorted(high_corrs, key=lambda x: abs(x['correlation']), reverse=True)[:10]
    
    # Distribution patterns
    for var in insights['variable_summary']['numeric']:
        if var.get('note') == 'highly_skewed':
            insights['patterns']['distributions'].append({
                "variable": var['name'],
                "pattern": "skewed",
                "skewness": round(var.get('skewness', 0), 2)
            })
        elif var.get('note') == 'majority_zeros':
            insights['patterns']['distributions'].append({
                "variable": var['name'],
                "pattern": "zero-inflated",
                "zero_pct": round((var['n_zeros'] / insights['dataset_overview']['n_rows'] * 100), 1)
            })
    
    # Generate recommendations
    if insights['dataset_overview']['missing_pct'] > 20:
        insights['recommendations'].append("Consider imputation strategies or investigate the cause of missing data")
    
    if len(insights['patterns']['correlations']) > 5:
        insights['recommendations'].append("High correlations detected - consider dimensionality reduction or feature selection")
    
    if len([v for v in insights['variable_summary']['categorical'] if v.get('note') == 'high_cardinality']) > 0:
        insights['recommendations'].append("High-cardinality categorical variables may need encoding or grouping")
    
    numeric_count = len(insights['variable_summary']['numeric'])
    categorical_count = len([v for v in insights['variable_summary']['categorical'] if v.get('note') == 'categorical'])
    
    if numeric_count > 0 and categorical_count > 0:
        insights['recommendations'].append(f"Dataset has {numeric_count} numeric and {categorical_count} categorical variables suitable for analysis")
    
    return insights

def format_for_claude(insights):
    """Format insights in a Claude-friendly markdown format."""
    lines = []
    
    lines.append("# EDA Insights Summary")
    lines.append("")
    
    # Dataset overview
    overview = insights['dataset_overview']
    lines.append("## Dataset Overview")
    lines.append(f"- **Shape**: {overview['n_rows']:,} rows × {overview['n_cols']} columns")
    lines.append(f"- **Memory**: {overview['memory_size']:,} bytes")
    lines.append(f"- **Missing data**: {overview['missing_pct']}% of cells")
    if overview['n_duplicates'] > 0:
        lines.append(f"- **Duplicates**: {overview['n_duplicates']:,} rows")
    lines.append("")
    
    # Variable summary
    lines.append("## Variable Summary")
    
    numeric_vars = insights['variable_summary']['numeric']
    if numeric_vars:
        lines.append(f"\n**Numeric Variables** ({len(numeric_vars)}):")
        for var in numeric_vars[:10]:  # Show top 10
            range_str = f"[{var['min']:.2f}, {var['max']:.2f}]" if var['min'] is not None else "N/A"
            note = f" ({var['note']})" if var.get('note') else ""
            lines.append(f"- **{var['name']}**: range {range_str}, μ={var.get('mean', 'N/A'):.2f}, σ={var.get('std', 'N/A'):.2f}{note}")
    
    categorical_vars = [v for v in insights['variable_summary']['categorical'] if v.get('note') == 'categorical']
    if categorical_vars:
        lines.append(f"\n**Categorical Variables** ({len(categorical_vars)}):")
        for var in categorical_vars[:10]:
            lines.append(f"- **{var['name']}**: {var['n_unique']} unique values")
    
    # Data quality
    if insights['data_quality']['issues']:
        lines.append("\n## Data Quality Issues")
        for issue in insights['data_quality']['issues']:
            severity = issue['severity'].upper()
            lines.append(f"- **[{severity}]** {issue['type']}: {issue['description']}")
    
    if insights['data_quality']['warnings']:
        lines.append("\n## Warnings")
        for warning in insights['data_quality']['warnings']:
            cols_display = ", ".join(warning['columns']) if len(warning['columns']) <= 5 else f"{', '.join(warning['columns'][:5])}... ({warning['count']} total)"
            lines.append(f"- **{warning['type']}**: {cols_display}")
    
    # Patterns
    if insights['patterns']['correlations']:
        lines.append("\n## Strong Correlations (|r| > 0.7)")
        for corr in insights['patterns']['correlations'][:5]:
            lines.append(f"- **{corr['var1']}** ↔ **{corr['var2']}**: r={corr['correlation']:.3f}")
    
    if insights['patterns']['distributions']:
        lines.append("\n## Distribution Patterns")
        for dist in insights['patterns']['distributions'][:5]:
            if dist['pattern'] == 'skewed':
                lines.append(f"- **{dist['variable']}**: Highly skewed (skewness={dist['skewness']})")
            elif dist['pattern'] == 'zero-inflated':
                lines.append(f"- **{dist['variable']}**: Zero-inflated ({dist['zero_pct']}% zeros)")
    
    # Recommendations
    if insights['recommendations']:
        lines.append("\n## Recommendations")
        for rec in insights['recommendations']:
            lines.append(f"- {rec}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python summarize_insights.py <eda_report.json>")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    # Extract insights
    insights = extract_insights(json_path)
    
    # Format for Claude
    markdown = format_for_claude(insights)
    
    # Save markdown summary
    summary_path = json_path.parent / "eda_insights_summary.md"
    with open(summary_path, 'w') as f:
        f.write(markdown)
    
    # Also save JSON for programmatic access
    json_summary_path = json_path.parent / "eda_insights_summary.json"
    with open(json_summary_path, 'w') as f:
        json.dump(insights, f, indent=2)
    
    # Print to stdout for immediate use
    print(markdown)
    print(f"\n---\n✓ Summary saved to: {summary_path}")
    print(f"✓ JSON saved to: {json_summary_path}")
