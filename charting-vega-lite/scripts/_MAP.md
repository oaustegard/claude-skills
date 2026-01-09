# scripts/
*Files: 2*

## Files

### analyze_data.py
> Imports: `json, sys, pathlib, datetime`
- **NumpyEncoder** (C) :15
  - **default** (m) `(self, obj)` :17
- **infer_field_type** (f) `(series)` :32
- **analyze_field** (f) `(series)` :48
- **suggest_charts** (f) `(fields)` :68
- **main** (f) `()` :267

### prepare_data.py
> Imports: `json, sys, argparse, pathlib`
- **NumpyEncoder** (C) :17
  - **default** (m) `(self, obj)` :19
- **optimize_dtypes** (f) `(df)` :34
- **prepare_data** (f) `(input_path, output_format='json', output_dir='/mnt/user-data/outputs')` :51
- **main** (f) `()` :144

