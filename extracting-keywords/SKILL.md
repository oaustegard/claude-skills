---
name: extracting-keywords
description: Extract keywords from documents using YAKE algorithm. Use when users request keyword extraction, key terms, topic identification, or content summarization from text documents. Supports standard English and life sciences domain stopwords.
---

# Extracting Keywords

Extract keywords from text using YAKE (Yet Another Keyword Extractor), an unsupervised statistical keyword extraction algorithm.

## Installation

**First time only:** Install YAKE with optimized dependencies to avoid unnecessary downloads.

```bash
cd /home/claude
uv venv yake-venv --system-site-packages
uv pip install yake --python yake-venv/bin/python --no-deps
uv pip install jellyfish segtok regex --python yake-venv/bin/python
```

This reuses system packages (numpy, networkx) instead of downloading them (~0.08s vs ~5s).

## Stopwords Configuration

Two stopwords lists are bundled in `assets/`:

**English (default):** `stopwords_en.txt`
- Standard English stopwords (575 words)
- Use for general text, technical documentation, non-domain-specific content

**Life Sciences:** `stopwords_ls.txt`
- English stopwords + 102 domain-specific terms
- Filters research methodology noise (study, results, analysis, significant, observed)
- Filters academic boilerplate (paper, manuscript, publication, review, editing)
- Filters statistical terms (p-value, correlation, model, prediction)
- Use for biomedical papers, clinical studies, research articles, scientific literature

## Basic Usage

```python
import yake

# Read text
with open('document.txt', 'r') as f:
    text = f.read()

# Extract with English stopwords (default)
kw_extractor = yake.KeywordExtractor(
    lan="en",           # Language code
    n=3,                # Max n-gram size (1-3 word phrases)
    dedupLim=0.9,       # Deduplication threshold (0-1)
    top=20              # Number of keywords to return
)

keywords = kw_extractor.extract_keywords(text)

# Display results (lower score = more important)
for kw, score in keywords:
    print(f"{score:.4f}  {kw}")
```

## Domain-Specific Extraction

### Using Life Sciences Stopwords

**Option 1: Install custom stopwords file**

```bash
# Copy life sciences stopwords to YAKE package
cp assets/stopwords_ls.txt /home/claude/yake-venv/lib/python3.12/site-packages/yake/core/StopwordsList/stopwords_ls.txt

# Use with lan="ls"
kw_extractor = yake.KeywordExtractor(lan="ls", n=3, top=20)
```

**Option 2: Load custom stopwords directly**

```python
# Load stopwords from file
with open('assets/stopwords_ls.txt', 'r') as f:
    custom_stops = set(line.strip().lower() for line in f)

# Pass to extractor
kw_extractor = yake.KeywordExtractor(
    stopwords=custom_stops,
    n=3,
    top=20
)
```

## Parameters

**lan** (str): Language code for built-in stopwords
- `"en"` - English (default)
- `"ls"` - Life sciences (if stopwords_ls.txt installed)
- See YAKE docs for other language codes

**n** (int): Maximum n-gram size (default: 3)
- `1` - Single words only
- `2` - Up to 2-word phrases
- `3` - Up to 3-word phrases (recommended)
- `4-5` - May produce suboptimal results with YAKE's algorithm

**dedupLim** (float): Deduplication threshold (default: 0.9)
- Range: 0.0 to 1.0
- Higher values = more aggressive deduplication
- Controls handling of similar terms (e.g., "cancer cell" vs "cancer cells")

**top** (int): Number of keywords to return (default: 20)

**stopwords** (set): Custom stopwords set (overrides lan parameter)

## Workflow Patterns

### Single Document Analysis

```python
import yake

# Read document
with open('/mnt/user-data/uploads/article.txt', 'r') as f:
    text = f.read()

# Extract keywords
kw_extractor = yake.KeywordExtractor(lan="en", n=3, top=30)
keywords = kw_extractor.extract_keywords(text)

# Format results
results = []
for kw, score in keywords:
    results.append(f"{score:.4f}  {kw}")

print("\n".join(results))
```

### Comparing Stopwords Strategies

```python
import yake

# Load life sciences stopwords
with open('assets/stopwords_ls.txt', 'r') as f:
    ls_stops = set(line.strip().lower() for line in f)

# Extract with English stopwords
kw_en = yake.KeywordExtractor(lan="en", n=3, top=20)
keywords_en = kw_en.extract_keywords(text)

# Extract with life sciences stopwords
kw_ls = yake.KeywordExtractor(stopwords=ls_stops, n=3, top=20)
keywords_ls = kw_ls.extract_keywords(text)

# Compare results
print("English stopwords:")
for kw, score in keywords_en:
    print(f"  {score:.4f}  {kw}")

print("\nLife sciences stopwords:")
for kw, score in keywords_ls:
    print(f"  {score:.4f}  {kw}")
```

### Batch Processing

```python
import yake
import os

# Initialize extractor
kw_extractor = yake.KeywordExtractor(lan="en", n=3, top=15)

# Process multiple files
results = {}
for filename in os.listdir('/mnt/user-data/uploads'):
    if filename.endswith('.txt'):
        with open(f'/mnt/user-data/uploads/{filename}', 'r') as f:
            text = f.read()
        
        keywords = kw_extractor.extract_keywords(text)
        results[filename] = keywords

# Output results
for filename, keywords in results.items():
    print(f"\n{filename}:")
    for kw, score in keywords[:10]:  # Top 10
        print(f"  {score:.4f}  {kw}")
```

## Output Formats

### Plain Text
```python
for kw, score in keywords:
    print(f"{kw}: {score:.4f}")
```

### CSV
```python
import csv

with open('/mnt/user-data/outputs/keywords.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Keyword', 'Score'])
    writer.writerows(keywords)
```

### JSON
```python
import json

output = [{"keyword": kw, "score": score} for kw, score in keywords]
with open('/mnt/user-data/outputs/keywords.json', 'w') as f:
    json.dump(output, f, indent=2)
```

## Notes

- Lower scores indicate more important keywords
- YAKE is unsupervised - no training data required
- Works across 30+ languages
- Optimal n-gram size is 3 for most use cases
- For longer technical phrases (4+ words), consider post-processing or ontology matching
- Always specify full venv path: `/home/claude/yake-venv/bin/python`

## Troubleshooting

**Import errors:** Verify venv installation
```bash
/home/claude/yake-venv/bin/python -c "import yake; print(yake.__version__)"
```

**Empty results:** Check text length (YAKE needs sufficient content, typically 100+ words)

**Poor quality keywords:** Adjust parameters:
- Increase `dedupLim` for more aggressive deduplication
- Try domain-specific stopwords
- Increase `top` to see more candidates

**Generic terms appearing:** Add custom stopwords for your domain:
```python
with open('assets/stopwords_ls.txt', 'r') as f:
    stops = set(line.strip().lower() for line in f)

# Add domain-specific terms
stops.update(['term1', 'term2', 'term3'])

kw_extractor = yake.KeywordExtractor(stopwords=stops, n=3, top=20)
```
