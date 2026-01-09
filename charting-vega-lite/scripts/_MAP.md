# scripts/
*Files: 2*

## Files

### analyze_data.py
> Imports: `json, sys, pathlib, datetime`
- **NumpyEncoder** (C) 
  - **default** (m) `(self, obj)`
- **infer_field_type** (f) `(series)`
- **analyze_field** (f) `(series)`
- **suggest_charts** (f) `(fields)`
- **main** (f) `()`

### prepare_data.py
> Imports: `json, sys, argparse, pathlib`
- **NumpyEncoder** (C) 
  - **default** (m) `(self, obj)`
- **optimize_dtypes** (f) `(df)`
- **prepare_data** (f) `(input_path, output_format='json', output_dir='/mnt/user-data/outputs')`
- **main** (f) `()`

