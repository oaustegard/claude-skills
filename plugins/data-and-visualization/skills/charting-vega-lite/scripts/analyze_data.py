#!/usr/bin/env python3
"""
Analyzes tabular data and suggests appropriate Vega-Lite chart types.
Usage: python analyze_data.py <filepath>
Output: JSON with data summary and chart recommendations
"""

import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types and NaN values."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif pd.isna(obj):
            return None
        return super().default(obj)

def infer_field_type(series):
    """Infer Vega-Lite field type from pandas series."""
    if pd.api.types.is_numeric_dtype(series):
        # Check if it's actually ordinal (few unique integer values)
        if pd.api.types.is_integer_dtype(series) and series.nunique() < 10:
            return "ordinal"
        return "quantitative"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "temporal"
    else:
        # Nominal vs ordinal heuristic
        unique_count = series.nunique()
        if unique_count < 20 and unique_count < len(series) / 2:
            return "nominal"
        return "nominal"  # Default to nominal for text

def analyze_field(series):
    """Analyze a single field and return its characteristics."""
    field_info = {
        "name": series.name,
        "type": infer_field_type(series),
        "unique_count": series.nunique(),
        "null_count": series.isnull().sum(),
        "sample_values": series.dropna().head(5).tolist()
    }
    
    if pd.api.types.is_numeric_dtype(series):
        field_info["stats"] = {
            "min": float(series.min()),
            "max": float(series.max()),
            "mean": float(series.mean()),
            "median": float(series.median())
        }
    
    return field_info

def suggest_charts(fields):
    """Suggest chart types based on field characteristics - EXPANDED."""
    suggestions = []
    
    # Count field types
    quantitative = [f for f in fields if f["type"] == "quantitative"]
    temporal = [f for f in fields if f["type"] == "temporal"]
    nominal = [f for f in fields if f["type"] == "nominal"]
    
    # DISTRIBUTION PATTERNS
    # Pattern: Single quantitative = histogram
    if len(quantitative) >= 1:
        suggestions.append({
            "type": "histogram",
            "reason": "Distribution of values",
            "encoding": {
                "x": quantitative[0]["name"],
                "bin": True,
                "y": "count"
            },
            "priority": "medium"
        })
    
    # COMPARISON PATTERNS
    # Pattern: Nominal + Quantitative = bar chart + variations
    if len(quantitative) >= 1 and len(nominal) >= 1:
        suggestions.append({
            "type": "bar",
            "reason": "Categorical comparison",
            "encoding": {
                "x": nominal[0]["name"],
                "y": quantitative[0]["name"]
            },
            "priority": "high"
        })
        
        # Box plot for distribution comparison
        suggestions.append({
            "type": "boxplot",
            "reason": "Distribution comparison across categories",
            "encoding": {
                "x": nominal[0]["name"],
                "y": quantitative[0]["name"]
            },
            "priority": "medium"
        })
        
        # Strip plot alternative
        suggestions.append({
            "type": "stripplot",
            "reason": "Individual data points by category",
            "encoding": {
                "x": nominal[0]["name"],
                "y": quantitative[0]["name"]
            },
            "priority": "low"
        })
        
        # Grouped bar if 2+ nominal
        if len(nominal) >= 2:
            suggestions.append({
                "type": "grouped-bar",
                "reason": "Multi-series comparison",
                "encoding": {
                    "x": nominal[0]["name"],
                    "y": quantitative[0]["name"],
                    "color": nominal[1]["name"]
                },
                "priority": "high"
            })
            
            suggestions.append({
                "type": "stacked-bar",
                "reason": "Part-to-whole by category",
                "encoding": {
                    "x": nominal[0]["name"],
                    "y": quantitative[0]["name"],
                    "color": nominal[1]["name"]
                },
                "priority": "medium"
            })
            
            suggestions.append({
                "type": "normalized-bar",
                "reason": "Percentage composition by category",
                "encoding": {
                    "x": nominal[0]["name"],
                    "y": quantitative[0]["name"],
                    "color": nominal[1]["name"]
                },
                "priority": "medium"
            })
    
    # TIME SERIES PATTERNS
    if len(temporal) >= 1 and len(quantitative) >= 1:
        suggestions.append({
            "type": "line",
            "reason": "Time series visualization",
            "encoding": {
                "x": temporal[0]["name"],
                "y": quantitative[0]["name"]
            },
            "priority": "high"
        })
        
        suggestions.append({
            "type": "area",
            "reason": "Time series with magnitude emphasis",
            "encoding": {
                "x": temporal[0]["name"],
                "y": quantitative[0]["name"]
            },
            "priority": "medium"
        })
        
        # Multi-series if nominal available
        if len(nominal) >= 1:
            suggestions.append({
                "type": "multi-line",
                "reason": "Multiple time series comparison",
                "encoding": {
                    "x": temporal[0]["name"],
                    "y": quantitative[0]["name"],
                    "color": nominal[0]["name"]
                },
                "priority": "high"
            })
            
            suggestions.append({
                "type": "stacked-area",
                "reason": "Cumulative time series",
                "encoding": {
                    "x": temporal[0]["name"],
                    "y": quantitative[0]["name"],
                    "color": nominal[0]["name"]
                },
                "priority": "medium"
            })
    
    # CORRELATION PATTERNS
    if len(quantitative) >= 2:
        suggestions.append({
            "type": "scatter",
            "reason": "Correlation analysis",
            "encoding": {
                "x": quantitative[0]["name"],
                "y": quantitative[1]["name"],
                "color": nominal[0]["name"] if nominal else None
            },
            "priority": "high"
        })
        
        # Bubble chart if 3+ quantitative
        if len(quantitative) >= 3:
            suggestions.append({
                "type": "bubble",
                "reason": "Three-variable correlation",
                "encoding": {
                    "x": quantitative[0]["name"],
                    "y": quantitative[1]["name"],
                    "size": quantitative[2]["name"],
                    "color": nominal[0]["name"] if nominal else None
                },
                "priority": "medium"
            })
    
    # PART-TO-WHOLE PATTERNS
    if len(nominal) >= 1 and len(quantitative) >= 1:
        # Only suggest pie if reasonable category count
        if nominal[0].get("unique_count", 999) < 7:
            suggestions.append({
                "type": "pie",
                "reason": "Part-to-whole relationship",
                "encoding": {
                    "theta": quantitative[0]["name"],
                    "color": nominal[0]["name"]
                },
                "priority": "low"
            })
    
    # TWO-DIMENSIONAL CATEGORICAL
    if len(nominal) >= 2 and len(quantitative) >= 1:
        suggestions.append({
            "type": "heatmap",
            "reason": "Two-dimensional categorical comparison",
            "encoding": {
                "x": nominal[0]["name"],
                "y": nominal[1]["name"],
                "color": quantitative[0]["name"]
            },
            "priority": "medium"
        })
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: priority_order.get(x["priority"], 3))
    
    return suggestions

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python analyze_data.py <filepath>"}, cls=NumpyEncoder))
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    try:
        # Load data
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.endswith('.json'):
            df = pd.read_json(filepath)
        elif filepath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            print(json.dumps({"error": f"Unsupported file type: {filepath}"}, cls=NumpyEncoder))
            sys.exit(1)
        
        # Analyze fields
        fields = [analyze_field(df[col]) for col in df.columns]
        
        # Get chart suggestions
        suggestions = suggest_charts(fields)
        
        # Prepare output
        result = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "fields": fields,
            "suggested_charts": suggestions,
            "sample_data": df.head(10).to_dict(orient='records')
        }
        
        print(json.dumps(result, indent=2, cls=NumpyEncoder))
    
    except Exception as e:
        print(json.dumps({"error": str(e)}, cls=NumpyEncoder))
        sys.exit(1)
        sys.exit(1)

if __name__ == "__main__":
    main()
