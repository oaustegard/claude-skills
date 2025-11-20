---
name: categorizing-bsky-accounts
description: Analyze and categorize Bluesky accounts by topic using keyword extraction. Use when users mention Bluesky account analysis, following/follower lists, topic discovery, account curation, or network analysis.
---

# Categorizing Bluesky Accounts

Analyze Bluesky accounts and categorize them by topic using keyword extraction from posts and bios. Supports multiple input modes: direct handle lists, following lists, and follower lists.

## Prerequisites

Install YAKE for keyword extraction:

```bash
pip install yake --break-system-packages
```

## Quick Start

The analyzer provides three input modes:

**Direct handle list:**
```bash
python bluesky_analyzer.py --handles "account1.bsky.social,account2.bsky.social,account3.bsky.social"
```

**Analyze following list:**
```bash
python bluesky_analyzer.py --following austegard.com --accounts 20
```

**Analyze followers:**
```bash
python bluesky_analyzer.py --followers austegard.com --accounts 20
```

**From file:**
```bash
python bluesky_analyzer.py --file accounts.txt
```

## Core Workflow

When users request Bluesky account analysis:

1. **Determine input mode** based on user's request:
   - List of handles → use `--handles`
   - "Following list" → use `--following`
   - "Followers" → use `--followers`
   - File provided → use `--file`

2. **Configure analysis parameters:**
   - `--accounts N` - Number to analyze (default: 10, max: 100)
   - `--posts N` - Posts per account (default: 20, max: 100)
   - `--filter "Category1,Category2"` - Only analyze matching categories
   - `--exclude "pattern1,pattern2"` - Skip accounts with matching keywords

3. **Run analysis:**
   ```bash
   python bluesky_analyzer.py [input-mode] [options]
   ```

4. **Choose output format:**
   - Grouped view (default): Accounts organized by topic
   - Detailed view (`--detailed`): Full keyword analysis per account
   - JSON export (`--format json`): Structured data
   - CSV export (`--format csv`): Spreadsheet-compatible
   - Markdown (`--format markdown`): Documentation-ready

## Parameters

### Input Modes (choose one)

**--handles "h1,h2,h3"**
Comma-separated list of Bluesky handles

**--following HANDLE**
Analyze accounts followed by HANDLE

**--followers HANDLE**
Analyze accounts following HANDLE

**--file PATH**
Read handles from file (one per line)

### Analysis Options

**--accounts N**
Number of accounts to analyze (1-100, default: 10)

**--posts N**
Posts to fetch per account (1-100, default: 20)

**--filter "Cat1,Cat2"**
Only analyze accounts matching these categories

**--exclude "word1,word2"**
Skip accounts with these keywords in bio/posts

**--categories PATH**
Custom category definitions (JSON file)

### Output Options

**--format [grouped|detailed|json|csv|markdown]**
Output format (default: grouped)

**--output PATH**
Output file path (default: /home/claude/bluesky_analysis.json)

**--confidence**
Show categorization confidence scores

## Category Customization

Create custom category definitions in JSON:

```json
{
  "AI/ML": {
    "keywords": ["ai", "llm", "machine learning", "model", "neural"],
    "weight": 1.0
  },
  "Web3": {
    "keywords": ["blockchain", "crypto", "web3", "defi", "dao"],
    "weight": 1.0
  },
  "Science": {
    "keywords": ["research", "paper", "phd", "university", "study"],
    "weight": 1.0
  }
}
```

Use custom categories:
```bash
python bluesky_analyzer.py --following handle --categories custom.json
```

### Default Categories

The analyzer includes these default categories:
- **AI/ML**: Artificial intelligence, machine learning, LLMs
- **Software Dev**: Programming, coding, development tools
- **Philosophy**: Philosophical discourse, consciousness, ethics
- **Music**: Music creation, streaming, artists
- **Law/Policy**: Legal, copyright, policy, regulation
- **Engineering**: Infrastructure, systems, architecture
- **Science**: Research, academia, scientific work
- **Other**: Accounts that don't fit defined categories

## Common Workflows

### Audit Your Following List

Discover topic distribution in accounts you follow:

```bash
python bluesky_analyzer.py --following your-handle.bsky.social --accounts 50
```

### Find Experts in a Topic

Filter by category to find ML researchers in someone's network:

```bash
python bluesky_analyzer.py --following handle --filter "AI/ML,Science" --accounts 100
```

### Categorize a List

Analyze a curated list of accounts:

```bash
cat > accounts.txt << 'EOF'
expert1.bsky.social
expert2.bsky.social
expert3.bsky.social
EOF

python bluesky_analyzer.py --file accounts.txt --format csv
```

### Export for Further Analysis

Generate structured data for processing:

```bash
python bluesky_analyzer.py --following handle --format json --output analysis.json
```

### Filter Out Bot Accounts

Skip accounts matching spam patterns:

```bash
python bluesky_analyzer.py --following handle --exclude "bot,spam,promo"
```

## Output Formats

### Grouped View (Default)

Accounts organized by detected category:

```
## AI/ML (5 accounts)

**John Smith** (@john.bsky.social)
  AI researcher focusing on LLM alignment
  Topics: alignment, safety, ai research, interpretability

**Jane Doe** (@jane.bsky.social)
  Building ML infrastructure at Scale Co
  Topics: mlops, kubernetes, infrastructure, deployment
```

### Detailed View

Full keyword analysis for each account:

```
John Smith (@john.bsky.social)
Posts analyzed: 20
Bio: AI researcher focusing on LLM alignment
Top Keywords:
  • alignment                      (0.0234)
  • safety research                (0.0287)
  • interpretability               (0.0312)
```

### JSON Format

Structured data for programmatic use:

```json
{
  "accounts": [
    {
      "handle": "john.bsky.social",
      "display_name": "John Smith",
      "category": "AI/ML",
      "confidence": 0.85,
      "keywords": [
        {"keyword": "alignment", "score": 0.0234},
        {"keyword": "safety research", "score": 0.0287}
      ]
    }
  ]
}
```

### CSV Format

Spreadsheet-compatible output:

```csv
handle,display_name,category,confidence,top_keywords
john.bsky.social,John Smith,AI/ML,0.85,"alignment, safety research, interpretability"
```

## Advanced Usage

### Pagination for Large Lists

For following lists >100 accounts:

```bash
# First batch
python bluesky_analyzer.py --following handle --accounts 100 --output batch1.json

# Use cursor from batch1 for next batch (automatically handled internally)
```

### Confidence Scoring

Show how strongly accounts match categories:

```bash
python bluesky_analyzer.py --following handle --confidence
```

Output includes confidence scores:
- 0.9-1.0: Very strong match
- 0.7-0.9: Strong match
- 0.5-0.7: Moderate match
- <0.5: Weak match (may be miscategorized)

### Combining Filters

Analyze specific subset with multiple criteria:

```bash
python bluesky_analyzer.py --following handle \
  --filter "AI/ML,Science" \
  --exclude "crypto,nft" \
  --accounts 50 \
  --posts 30
```

## Technical Details

### Keyword Extraction

Uses YAKE (Yet Another Keyword Extractor):
- Language: English
- N-grams: 1-3 words
- Deduplication: 0.9 threshold
- Top keywords: 15 per account

### API Rate Limits

Bluesky API limits:
- 3000 requests per 5 minutes
- 5000 requests per hour

The analyzer respects these limits with built-in delays.

### Categorization Algorithm

1. Extract keywords from recent posts (default: 20)
2. Combine with bio/description text
3. Match against category patterns
4. Score each category by keyword overlap
5. Assign highest-scoring category
6. Calculate confidence based on score distribution

### Data Privacy

The analyzer:
- Only accesses public profile data
- Does not store credentials
- Operates read-only
- Respects Bluesky's terms of service

## Troubleshooting

**"No accounts to analyze"**
- Verify handle format (include domain: handle.bsky.social)
- Check if account exists and has public following/followers

**"Insufficient content for keyword extraction"**
- Account has few posts (<5)
- Posts are very short
- Try increasing `--posts` parameter

**Rate limit errors**
- Reduce `--accounts` parameter
- Add delays between batches
- Check Bluesky API status

**Import errors**
- Install YAKE: `pip install yake --break-system-packages`
- Verify Python 3.8+: `python3 --version`

## Integration with Other Skills

Combine with:
- **exploring-data**: Analyze exported JSON/CSV
- **charting-vega-lite**: Visualize category distributions
- **extracting-keywords**: Fine-tune keyword extraction parameters

## Example Sessions

**User:** "Can you analyze the accounts I follow on Bluesky and tell me what topics they focus on?"

**Claude:**
```python
# Run analyzer on user's following list
python bluesky_analyzer.py --following user-handle.bsky.social --accounts 50
```

**User:** "Find ML researchers in @alice's network and export to CSV"

**Claude:**
```python
python bluesky_analyzer.py --following alice.bsky.social \
  --filter "AI/ML,Science" \
  --format csv \
  --output ml_researchers.csv
```

**User:** "Here's a list of 30 accounts, categorize them with custom topics"

**Claude:**
```python
# First, save custom categories
cat > my_categories.json << 'EOF'
{
  "Climate Tech": {
    "keywords": ["climate", "sustainability", "clean energy", "carbon"],
    "weight": 1.0
  },
  "Biotech": {
    "keywords": ["biotech", "crispr", "genomics", "protein"],
    "weight": 1.0
  }
}
EOF

# Then analyze with custom categories
python bluesky_analyzer.py --file accounts.txt --categories my_categories.json
```
