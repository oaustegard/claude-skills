# Skills Environment Reference
**Version:** 1.0 | **Updated:** 2025-11-02 | **Python:** 3.12.3 | **Node:** 22.20.0

> **Purpose:** Cached environment knowledge for skills. Reference this document instead of running exploratory bash commands.

---

## Quick Capability Check

```bash
# Before implementing, check this file first
# If capability listed here → use directly
# If not listed → verify with bash, then update this file
```

**When to reference this file:**
- Planning computational workflows
- Checking package availability
- Verifying tool versions
- Understanding file system structure
- Determining resource limits

---

## Python Environment

### Core Data Science Stack
```python
# Numerical Computing
numpy==2.3.3              # Arrays, linear algebra, FFT, random
scipy==1.16.2             # Scientific computing, optimization, signal processing
pandas==2.3.3             # DataFrames, time series, data manipulation

# Machine Learning
scikit-learn==1.7.2       # Classification, regression, clustering, preprocessing
scikit-image==0.25.2      # Image processing algorithms
jax==0.7.2                # Auto-differentiation, GPU acceleration
jaxlib==0.7.2             # JAX runtime

# Visualization
matplotlib==3.10.7        # 2D plotting, charts, graphs
```

### Document Processing
```python
# Microsoft Office Formats
python-docx==1.2.0        # Word documents (.docx) - read/write/modify
python-pptx==1.0.2        # PowerPoint (.pptx) - create/modify slides
openpyxl==3.1.5          # Excel (.xlsx) - formulas, styles, charts

# PDF
pypdf==5.9.0             # PDF reading, merging, splitting
pypdfium2==4.30.0        # PDF rendering to images
img2pdf==0.6.1           # Image to PDF conversion

# Other Formats
odfpy==1.4.1             # OpenDocument formats
markitdown==0.1.3        # Markdown utilities
```

### Web & Network
```python
# HTTP & Web
httplib2==0.20.4         # HTTP client library
Flask==3.1.2             # Web framework (can run test servers)

# Parsing & Scraping
beautifulsoup4==4.14.2   # HTML/XML parsing
lxml==6.0.2              # Fast XML/HTML parser (C-based)
```

### Image & Media Processing
```python
# Image Processing
opencv-python==4.11.0.86         # Computer vision (full)
opencv-contrib-python==4.11.0.86 # OpenCV extra modules
opencv-python-headless==4.11.0.86 # No GUI (for scripts)
imageio==2.37.0                  # Read/write image formats
imageio-ffmpeg==0.6.0            # Video I/O via ffmpeg
Pillow (via PIL)                 # Image manipulation

# Media
mediapipe==0.10.14       # ML solutions for media processing
```

### Text Processing & NLP
```python
# Text Analysis
markdownify==1.2.0       # HTML to Markdown conversion
mistune==3.1.4           # Fast Markdown parser
Markdown==3.9            # Markdown to HTML

# Character Detection
chardet==5.2.0           # Character encoding detection
```

### Utilities
```python
# Data Structures & Algorithms
networkx==3.5            # Graph/network algorithms
graphviz==0.21           # Graph visualization (DOT language)

# File & System
click==8.3.0             # CLI creation framework
colorama==0.4.6          # Colored terminal text
Jinja2==3.1.6            # Template engine

# Cryptography & Security
cryptography==46.0.2     # Cryptographic recipes and primitives

# Math & Symbolic
mpmath==1.3.0            # Arbitrary-precision arithmetic
sympy (via mpmath)       # Symbolic mathematics
```

### ML & AI Infrastructure
```python
onnxruntime==1.23.1      # ONNX model inference
flatbuffers==25.9.23     # Serialization library (used by TensorFlow)
```

### Complete Package List
142 total packages installed. For full list:
```bash
pip list --format=freeze
```

---

## System Tools

### Document Conversion
```bash
pandoc 3.1.3             # Universal document converter
# Supports: markdown, docx, html, pdf, latex, epub, rst, org, mediawiki, etc.
# Usage: pandoc input.md -o output.docx
#        pandoc input.html -o output.pdf --pdf-engine=wkhtmltopdf
```

### Image Processing
```bash
ImageMagick 6.9.12-98    # Image manipulation suite
# Tools: convert, identify, mogrify, composite, montage
# Usage: convert input.jpg -resize 50% output.jpg
#        convert *.png -append vertical.png
#        identify -verbose image.jpg  # Get image info
```

### Media Processing
```bash
ffmpeg 6.1.1             # Video/audio processing
# Usage: ffmpeg -i input.mp4 -vf scale=1280:720 output.mp4
#        ffmpeg -i video.mp4 -vn audio.mp3  # Extract audio
#        ffmpeg -i input.mp4 -r 1 frames/frame_%04d.png  # Extract frames
```

### Version Control
```bash
git 2.43.0               # Distributed version control
# Full git functionality available
# Usage: git clone, commit, branch, merge, etc.
```

### Network Tools
```bash
curl 8.5.0               # HTTP client
wget 1.21.4              # File downloader

# Network access limited to approved domains:
# - api.anthropic.com, github.com, npmjs.com, pypi.org
# - archive.ubuntu.com, security.ubuntu.com
# See <network_configuration> for full list
```

### Graph Visualization
```bash
dot (graphviz)           # Graph rendering engine
# Usage: dot -Tpng graph.dot -o graph.png
#        neato -Tsvg network.dot -o network.svg
```

### Compression & Archiving
```bash
tar, gzip, bzip2         # Archive utilities
zip, unzip               # ZIP handling
```

### Text Processing
```bash
# Standard Unix tools
grep, sed, awk           # Text search and manipulation
jq                       # JSON processor
cut, sort, uniq          # Data processing
```

### Compilers & Interpreters
```bash
gcc, g++                 # C/C++ compilers
java                     # JVM available
python3 3.12.3          # Python interpreter
node 22.20.0            # JavaScript runtime
npm 10.9.3              # Node package manager
```

---

## Node.js / NPM Environment

### Global Packages Location
```bash
/home/claude/.npm-global/
```

### Installing Global Packages
```bash
npm install -g <package>
# Installs to /home/claude/.npm-global/bin
# Already in PATH
```

### Common Patterns
```javascript
// Node.js scripts can be executed
node script.js

// NPM packages can be installed on-demand
npm install lodash
// Then import in script

// TypeScript compilation (if needed)
npm install -g typescript
tsc script.ts
```

---

## File System Structure

### Read-Only Directories
```
/mnt/project/              # Project files from user's project
/mnt/skills/               # Skill libraries
  ├── public/              # Anthropic core skills (docx, pdf, pptx, xlsx, etc.)
  ├── user/                # User-created custom skills
  └── examples/            # Reference skill implementations
/mnt/user-data/uploads/    # Files uploaded by user in conversation
```

**Important:** Cannot write to these directories. Copy files to `/home/claude` to modify.

### Writable Directories
```
/home/claude/              # Main workspace (4.6GB available)
  ├── .cache/              # Python/npm caches
  ├── .npm-global/         # Global npm packages
  └── <work dirs>          # Create working directories here

/mnt/user-data/outputs/    # FINAL deliverables for user
```

**Critical:** User can only see files placed in `/mnt/user-data/outputs/`

### Workspace Pattern
```bash
# 1. Work in /home/claude
cd /home/claude
mkdir my-task
cd my-task
# ... do processing ...

# 2. Copy final results to outputs
cp final_report.pdf /mnt/user-data/outputs/
```

### Storage Limits
- **Available:** 4.6GB in `/home/claude`
- **Ephemeral:** Entire environment resets between sessions
- **No persistence:** Files don't survive session end

---

## Resource Constraints

### Computational Limits
```bash
# CPU: Shared container resources
# RAM: Limited (exact amount unspecified)
# Disk: 4.6GB available in /home/claude

# Best practices:
# - Stream large files instead of loading into memory
# - Use generators for big datasets
# - Clean up temporary files
# - Monitor disk usage: df -h /home/claude
```

### Network Restrictions
**Allowed domains:**
- api.anthropic.com
- archive.ubuntu.com, security.ubuntu.com
- github.com, npmjs.com, npmjs.org, registry.npmjs.org
- pypi.org, pythonhosted.org, files.pythonhosted.org
- yarnpkg.com, registry.yarnpkg.com

**Not accessible:**
- Most external APIs (unless in allowed list)
- Claude API requires explicit API key (not auto-authenticated)
- User's local files (must be uploaded first)

### Execution Timeouts
- Bash commands have timeout limits
- Long-running processes may be terminated
- Use efficient algorithms for large datasets

---

## Common Patterns & Recipes

### Data Analysis Pipeline
```python
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('/mnt/user-data/uploads/data.csv')

# Process
summary = df.groupby('category').agg({
    'value': ['mean', 'std', 'count']
})

# Visualize
plt.figure(figsize=(10, 6))
df.boxplot(column='value', by='category')
plt.savefig('/mnt/user-data/outputs/analysis.png')

# Export
summary.to_csv('/mnt/user-data/outputs/summary.csv')
```

### Document Generation
```bash
# Markdown to Word with template
pandoc report.md -o /mnt/user-data/outputs/report.docx \
  --reference-doc=template.docx \
  --toc --number-sections

# HTML to PDF
pandoc page.html -o /mnt/user-data/outputs/document.pdf

# Multiple formats at once
pandoc source.md \
  -o /mnt/user-data/outputs/report.docx \
  -o /mnt/user-data/outputs/report.pdf
```

### Image Processing Batch
```bash
# Resize all images
for img in *.jpg; do
    convert "$img" -resize 800x600 "processed/$img"
done

# Create thumbnail grid
montage *.jpg -geometry 200x200+2+2 /mnt/user-data/outputs/grid.jpg

# Convert format
mogrify -format png *.jpg  # Converts all jpg to png
```

### PDF Operations
```python
from pypdf import PdfReader, PdfWriter

# Merge PDFs
writer = PdfWriter()
for pdf in ['part1.pdf', 'part2.pdf', 'part3.pdf']:
    reader = PdfReader(pdf)
    for page in reader.pages:
        writer.add_page(page)

with open('/mnt/user-data/outputs/merged.pdf', 'wb') as f:
    writer.write(f)

# Extract text
reader = PdfReader('/mnt/user-data/uploads/document.pdf')
text = '\n'.join(page.extract_text() for page in reader.pages)
```

### Graph Generation
```python
import graphviz

# Create directed graph
dot = graphviz.Digraph(comment='System Architecture')
dot.attr(rankdir='LR')

dot.node('A', 'Frontend')
dot.node('B', 'API')
dot.node('C', 'Database')

dot.edge('A', 'B', 'HTTP')
dot.edge('B', 'C', 'SQL')

dot.render('/mnt/user-data/outputs/architecture', format='png')
```

### Web Scraping (Limited by Network)
```python
from bs4 import BeautifulSoup
import httplib2

# Only works for allowed domains
http = httplib2.Http()
response, content = http.request('https://github.com/anthropics/skills')
soup = BeautifulSoup(content, 'lxml')

# Extract data
titles = soup.find_all('h2')
```

### Template Composition (Token Efficient)
```bash
# Instead of generating content, fill templates
cat template.md | \
  sed "s/{{TITLE}}/$title/g" | \
  sed "s/{{DATE}}/$(date +%Y-%m-%d)/g" | \
  sed "s/{{AUTHOR}}/$author/g" > report.md

# Or use Python with Jinja2
python3 << 'EOF'
from jinja2 import Template
template = Template(open('template.html').read())
output = template.render(title="Report", data=results)
open('/mnt/user-data/outputs/report.html', 'w').write(output)
EOF
```

---

## Package Installation

### Python Packages
```bash
# ALWAYS use --break-system-packages flag
pip install pandas --break-system-packages

# For virtual environments (if needed)
python3 -m venv /home/claude/venv
source /home/claude/venv/bin/activate
pip install <package>
```

### NPM Packages
```bash
# Global installation
npm install -g <package>
# Installs to /home/claude/.npm-global/bin

# Local installation (in project)
cd /home/claude/my-project
npm install <package>
```

### Verifying Installation
```bash
# Python
python3 -c "import pandas; print(pandas.__version__)"

# System tool
which pandoc
pandoc --version

# NPM package
npm list -g <package>
```

---

## Environment Limitations

### Cannot Do
- ❌ Authenticate to Claude API automatically (artifacts can, bash/Python cannot)
- ❌ Access user's local filesystem directly (files must be uploaded)
- ❌ Make network requests to non-whitelisted domains
- ❌ Persist data across sessions (environment resets)
- ❌ Use GUI applications (headless environment)
- ❌ Access MCP servers (requires Claude Code CLI, not available here)
- ❌ Install system packages with apt (no sudo access)

### Can Do
- ✅ Process uploaded files from `/mnt/user-data/uploads/`
- ✅ Read project files from `/mnt/project/`
- ✅ Install Python packages with pip (using --break-system-packages)
- ✅ Install npm packages globally or locally
- ✅ Run computational analysis (pandas, numpy, scikit-learn)
- ✅ Generate documents (docx, pptx, xlsx, pdf)
- ✅ Process images and media (ImageMagick, ffmpeg, OpenCV)
- ✅ Convert between formats (pandoc)
- ✅ Execute arbitrary Python/Node.js scripts
- ✅ Run bash commands (within timeout limits)

---

## Skill Development Tips

### Reference This File
```markdown
<!-- In SKILL.md -->
Before implementing, reference:
/mnt/skills/resources/ENVIRONMENT_REFERENCE.md

Check for:
- Package availability
- Tool versions
- File system structure
- Common patterns
```

### Token Efficiency
```markdown
# Instead of:
"Let me check if pandas is installed..."
[runs bash: pip list | grep pandas]
"Yes, pandas 2.3.3 is available"

# Do this:
"According to ENVIRONMENT_REFERENCE.md, pandas 2.3.3 is available"
[proceed directly to implementation]
```

### Code Choice Rubric

**Simple bash? Use it.**
```bash
# File operations, text processing, simple workflows
cp file.txt /mnt/user-data/outputs/
cat data.csv | grep "2025" | wc -l
for f in *.txt; do echo "$f"; done
```

**More complex? Aim for inline Python.**
```bash
# Single-purpose data processing, calculations
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('data.csv')
print(df.groupby('category')['value'].mean())
EOF

# Or single-line when possible
python3 -c "import json; print(json.dumps({'key': 'value'}, indent=2))"
```

**Reusable/complex? Python script with minimal extras.**
```python
#!/usr/bin/env python3
# scripts/process.py - Validates data schema
import sys, json

def validate(data):
    # Core logic only - no verbose comments, no unnecessary imports
    return all(k in data for k in ['id', 'name'])

if __name__ == "__main__":
    data = json.loads(sys.argv[1])
    exit(0 if validate(data) else 1)
```

**Decision tree:**
- File/text manipulation → bash
- Data processing (one-off) → inline Python
- Repeated operations → Python script
- Complex validation/transformation → Python script

### Pattern Reuse
Copy patterns from "Common Patterns & Recipes" section rather than implementing from scratch.

### Update Protocol
If you discover:
- New installed package
- Updated tool version
- New capability
- Useful pattern

→ Document the finding and note it should be added to this reference

---

## Debugging & Diagnostics

### Directory Structure Viewing
```bash
# tree command is NOT available
# Use ls -lhR instead for recursive listings
ls -lhR /path/to/directory

# For specific depth control
ls -lh /path/to/directory
ls -lh /path/to/directory/*/
```

### Check Package Availability
```bash
# Python package
python3 -c "import <package>" && echo "Available" || echo "Not installed"

# System tool
which <tool> || echo "Not found"

# Get version
<tool> --version
```

### Disk Space
```bash
df -h /home/claude
du -sh /home/claude/*  # Check directory sizes
```

### Environment Variables
```bash
env | grep -i python
env | grep -i node
```

### Network Connectivity Test
```bash
curl -I https://api.anthropic.com  # Should work
curl -I https://example.com         # May fail (not whitelisted)
```

### Python Environment Info
```python
import sys
print(f"Python: {sys.version}")
print(f"Executable: {sys.executable}")
print(f"Path: {sys.path}")
```

---

## Version History

**v1.0** (2025-11-02)
- Initial environment reference
- Python 3.12.3, Node 22.20.0
- 142 Python packages documented
- Core tools and patterns catalogued

**Update Schedule:**
- Monthly refresh recommended
- After major environment changes
- When new capabilities discovered

---

## Quick Reference Card

```bash
# Most Used Tools
python3          # Python 3.12.3
node/npm         # Node 22.20.0 / npm 10.9.3
pandas           # Data analysis
numpy            # Numerical computing
matplotlib       # Plotting
python-docx      # Word documents
python-pptx      # PowerPoint
openpyxl         # Excel
pypdf            # PDF processing
pandoc           # Document conversion
convert          # Image processing (ImageMagick)
ffmpeg           # Video/audio processing
git              # Version control

# File Structure
/home/claude/                    → Work here
/mnt/user-data/uploads/          → Read user files
/mnt/user-data/outputs/          → Put final outputs HERE
/mnt/project/                    → Read project files
/mnt/skills/                     → Read skill resources

# Common Operations
pip install <pkg> --break-system-packages
npm install -g <pkg>
pandoc input.md -o output.docx
convert image.jpg -resize 50% small.jpg
df -h /home/claude
```

---

**For skills:** Import knowledge from this file rather than running exploratory commands. Saves tokens and time.
