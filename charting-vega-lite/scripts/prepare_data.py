#!/usr/bin/env python3
"""
Prepares data for external reference by Vega-Lite specs.
Creates optimized data files and returns reference information.

Usage: python prepare_data.py <input_filepath> [--output-format json|csv]
Output: JSON with data file path, format, and reference metadata
"""

import json
import sys
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
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

def optimize_dtypes(df):
    """Optimize DataFrame dtypes for efficient serialization."""
    for col in df.columns:
        # Convert object columns with few unique values to category
        if df[col].dtype == 'object':
            unique_ratio = df[col].nunique() / len(df)
            if unique_ratio < 0.5:  # More than 50% repetition
                df[col] = df[col].astype('category')
        
        # Downcast numeric types
        elif pd.api.types.is_integer_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast='integer')
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast='float')
    
    return df

def prepare_data(input_path, output_format='json', output_dir='/mnt/user-data/outputs'):
    """
    Prepare data for external reference.
    
    Returns:
        dict with:
            - data_path: Path to prepared data file
            - format: 'json' or 'csv'
            - rows: Number of rows
            - columns: List of column names
            - size_bytes: File size
            - reference_pattern: How to reference in spec
    """
    # Load data
    if input_path.endswith('.csv'):
        df = pd.read_csv(input_path)
    elif input_path.endswith('.json'):
        df = pd.read_json(input_path)
    elif input_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(input_path)
    else:
        raise ValueError(f"Unsupported file type: {input_path}")
    
    # Optimize dtypes
    df = optimize_dtypes(df)
    
    # Determine output filename
    input_name = Path(input_path).stem
    output_path = Path(output_dir) / f"{input_name}_data.{output_format}"
    
    # Save optimized data
    if output_format == 'json':
        # Use records format for Vega-Lite compatibility
        data_records = df.to_dict(orient='records')
        with open(output_path, 'w') as f:
            json.dump(data_records, f, cls=NumpyEncoder)
    elif output_format == 'csv':
        df.to_csv(output_path, index=False)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    # Get file size
    size_bytes = output_path.stat().st_size
    
    # Prepare result
    result = {
        "data_path": str(output_path),
        "format": output_format,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "size_bytes": size_bytes,
        "size_human": f"{size_bytes / 1024:.1f} KB" if size_bytes > 1024 else f"{size_bytes} bytes",
        "reference_patterns": {
            "vega_lite_url": {
                "description": "Reference via URL (for web-hosted data)",
                "spec": {"data": {"url": f"computer://{output_path}"}}
            },
            "react_fetch": {
                "description": "Load in React component",
                "code": f"""
// Load data separately in React component
const [data, setData] = useState(null);

useEffect(() => {{
  fetch('computer://{output_path}')
    .then(r => r.json())
    .then(d => setData(d));
}}, []);

// Use in spec
const spec = {{
  ...
  data: {{values: data}},
  ...
}};
"""
            },
            "angular_http": {
                "description": "Load via Angular HttpClient",
                "code": f"""
// In component
this.http.get<any[]>('assets/{output_path.name}')
  .subscribe(data => {{
    this.spec.data.values = data;
    this.renderChart();
  }});
"""
            }
        }
    }
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Prepare data for Vega-Lite external reference')
    parser.add_argument('input_path', help='Path to input data file')
    parser.add_argument('--output-format', choices=['json', 'csv'], default='json',
                        help='Output format (default: json)')
    parser.add_argument('--output-dir', default='/mnt/user-data/outputs',
                        help='Output directory (default: /mnt/user-data/outputs)')
    
    args = parser.parse_args()
    
    try:
        result = prepare_data(args.input_path, args.output_format, args.output_dir)
        print(json.dumps(result, indent=2, cls=NumpyEncoder))
    except Exception as e:
        print(json.dumps({"error": str(e)}, cls=NumpyEncoder))
        sys.exit(1)

if __name__ == "__main__":
    main()
