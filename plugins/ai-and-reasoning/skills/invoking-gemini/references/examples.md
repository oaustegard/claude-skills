# Examples

Comprehensive examples of Gemini usage patterns.

## Example 1: Document Data Extraction

Extract structured data from unstructured documents.

```python
from pydantic import BaseModel, Field
from gemini_client import invoke_with_structured_output
from pathlib import Path

class InvoiceData(BaseModel):
    invoice_number: str
    date: str
    vendor: str
    total_amount: float
    line_items: list[dict] = Field(description="List of items with description and price")

invoice_dir = Path("/mnt/user-data/uploads/invoices")
results = []

for invoice_file in invoice_dir.glob("*.txt"):
    with open(invoice_file) as f:
        invoice_text = f.read()

    data = invoke_with_structured_output(
        prompt=f"Extract invoice data:\n\n{invoice_text}",
        pydantic_model=InvoiceData
    )

    if data:
        results.append({
            'file': invoice_file.name,
            'invoice_number': data.invoice_number,
            'vendor': data.vendor,
            'total': data.total_amount
        })

# Save results
import pandas as pd
df = pd.DataFrame(results)
df.to_csv('/mnt/user-data/outputs/invoice_summary.csv', index=False)
```

## Example 2: Batch Classification

Classify large datasets efficiently.

```python
from pydantic import BaseModel
from enum import Enum
from gemini_client import invoke_parallel, invoke_with_structured_output

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class ReviewAnalysis(BaseModel):
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)
    key_topics: list[str] = Field(max_length=5)

# Load reviews
import pandas as pd
df = pd.read_csv('/mnt/user-data/uploads/reviews.csv')

results = []
for idx, row in df.iterrows():
    analysis = invoke_with_structured_output(
        prompt=f"Analyze this review: {row['review_text']}",
        pydantic_model=ReviewAnalysis,
        temperature=0.3  # Low temp for consistent classification
    )

    if analysis:
        results.append({
            'review_id': row['id'],
            'sentiment': analysis.sentiment.value,
            'confidence': analysis.confidence,
            'topics': ', '.join(analysis.key_topics)
        })

    # Progress
    if (idx + 1) % 10 == 0:
        print(f"Processed {idx + 1}/{len(df)} reviews")

# Save results
results_df = pd.DataFrame(results)
results_df.to_csv('/mnt/user-data/outputs/sentiment_analysis.csv', index=False)

# Summary statistics
print("\nSentiment Distribution:")
print(results_df['sentiment'].value_counts())
print(f"\nAverage Confidence: {results_df['confidence'].mean():.2f}")
```

## Example 3: Multi-Modal Product Catalog

Create structured product catalog from images.

```python
from pydantic import BaseModel, Field
from gemini_client import invoke_with_structured_output
from pathlib import Path

class Product(BaseModel):
    name: str
    category: str
    description: str = Field(max_length=200)
    primary_color: str
    additional_colors: list[str] = []
    estimated_price_tier: str = Field(description="budget, mid-range, or premium")
    key_features: list[str] = Field(max_length=5)

product_images = Path("/mnt/user-data/uploads/products")
catalog = []

for img_path in product_images.glob("*.jpg"):
    product = invoke_with_structured_output(
        prompt="""
        Analyze this product image and provide:
        - Product name and category
        - Brief description
        - Colors visible
        - Estimated price tier (budget/mid-range/premium)
        - Key features
        """,
        pydantic_model=Product,
        image_path=str(img_path)
    )

    if product:
        catalog.append({
            'image': img_path.name,
            **product.dict()
        })
        print(f"✓ {img_path.name}: {product.name}")

# Export catalog
import json
with open('/mnt/user-data/outputs/product_catalog.json', 'w') as f:
    json.dump(catalog, f, indent=2)

print(f"\nProcessed {len(catalog)} products")
```

## Example 4: Resume Parser

Extract structured data from resumes.

```python
from pydantic import BaseModel, Field
from typing import Optional

class Education(BaseModel):
    degree: str
    institution: str
    year: Optional[str] = None

class Experience(BaseModel):
    title: str
    company: str
    duration: str
    responsibilities: list[str]

class Resume(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    summary: str = Field(max_length=300)
    skills: list[str]
    education: list[Education]
    experience: list[Experience]

resume_files = Path("/mnt/user-data/uploads/resumes")
parsed_resumes = []

for resume_file in resume_files.glob("*.txt"):
    with open(resume_file) as f:
        resume_text = f.read()

    parsed = invoke_with_structured_output(
        prompt=f"Parse this resume:\n\n{resume_text}",
        pydantic_model=Resume,
        temperature=0.2  # Low temp for accuracy
    )

    if parsed:
        parsed_resumes.append({
            'file': resume_file.name,
            'candidate': parsed.name,
            'email': parsed.email,
            'skills_count': len(parsed.skills),
            'years_experience': len(parsed.experience),
            'education_level': parsed.education[0].degree if parsed.education else 'None'
        })

# Create summary
import pandas as pd
df = pd.DataFrame(parsed_resumes)
df.to_csv('/mnt/user-data/outputs/resume_summary.csv', index=False)

# Skill frequency analysis
all_skills = []
for resume in parsed_resumes:
    all_skills.extend(resume.get('skills', []))

from collections import Counter
skill_counts = Counter(all_skills)
print("\nTop 10 Skills:")
for skill, count in skill_counts.most_common(10):
    print(f"  {skill}: {count}")
```

## Example 5: Meeting Notes Summarization

Batch process meeting notes into structured summaries.

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ActionItem(BaseModel):
    task: str
    assignee: str
    due_date: Optional[str] = None
    priority: str = Field(description="high, medium, or low")

class MeetingSummary(BaseModel):
    meeting_date: str
    attendees: list[str]
    key_topics: list[str] = Field(max_length=5)
    decisions: list[str]
    action_items: list[ActionItem]
    next_meeting: Optional[str] = None

notes_dir = Path("/mnt/user-data/uploads/meeting_notes")
summaries = []

for notes_file in sorted(notes_dir.glob("*.txt")):
    with open(notes_file) as f:
        notes = f.read()

    summary = invoke_with_structured_output(
        prompt=f"Summarize these meeting notes:\n\n{notes}",
        pydantic_model=MeetingSummary
    )

    if summary:
        summaries.append(summary)
        print(f"✓ {notes_file.name}: {len(summary.action_items)} action items")

# Generate action items report
all_action_items = []
for summary in summaries:
    for item in summary.action_items:
        all_action_items.append({
            'meeting_date': summary.meeting_date,
            'task': item.task,
            'assignee': item.assignee,
            'due_date': item.due_date,
            'priority': item.priority
        })

import pandas as pd
df = pd.DataFrame(all_action_items)
df.to_csv('/mnt/user-data/outputs/action_items.csv', index=False)

# Group by assignee
print("\nAction Items by Assignee:")
print(df.groupby('assignee').size().sort_values(ascending=False))
```

## Example 6: Parallel Translation

Translate content to multiple languages in parallel.

```python
from gemini_client import invoke_parallel

content = """
Welcome to our product! This innovative solution helps you
manage your tasks efficiently and collaborate with your team.
"""

languages = [
    "Spanish", "French", "German", "Italian", "Portuguese",
    "Japanese", "Korean", "Chinese", "Arabic", "Russian"
]

prompts = [
    f"Translate to {lang} (output only the translation):\n\n{content}"
    for lang in languages
]

translations = invoke_parallel(
    prompts=prompts,
    model="gemini-3-flash-preview",
    temperature=0.3,
    max_workers=10
)

# Create translation table
results = []
for lang, translation in zip(languages, translations):
    if translation:
        results.append({
            'language': lang,
            'translation': translation.strip()
        })

# Export
import pandas as pd
df = pd.DataFrame(results)
df.to_csv('/mnt/user-data/outputs/translations.csv', index=False)

print(f"Translated to {len(results)} languages")
```

## Example 7: Code Documentation Generator

Generate structured documentation from code.

```python
from pydantic import BaseModel, Field

class FunctionDoc(BaseModel):
    function_name: str
    description: str = Field(max_length=200)
    parameters: list[dict] = Field(description="List with name, type, description")
    return_type: str
    return_description: str
    example_usage: str
    complexity: str = Field(description="O(n), O(log n), etc.")

# Read source files
code_dir = Path("/mnt/user-data/uploads/source_code")
documentation = []

for code_file in code_dir.glob("*.py"):
    with open(code_file) as f:
        code = f.read()

    # Extract functions (simplified)
    import re
    functions = re.findall(r'def\s+(\w+)\s*\([^)]*\):[^}]*?(?=\ndef|\Z)', code, re.DOTALL)

    for func_code in functions[:5]:  # Limit to first 5 functions
        doc = invoke_with_structured_output(
            prompt=f"Generate documentation for this Python function:\n\n{func_code}",
            pydantic_model=FunctionDoc
        )

        if doc:
            documentation.append(doc.dict())

# Export as JSON
import json
with open('/mnt/user-data/outputs/api_documentation.json', 'w') as f:
    json.dump(documentation, f, indent=2)

# Generate markdown
with open('/mnt/user-data/outputs/API_DOCS.md', 'w') as f:
    f.write("# API Documentation\n\n")
    for doc in documentation:
        f.write(f"## {doc['function_name']}\n\n")
        f.write(f"{doc['description']}\n\n")
        f.write(f"**Returns:** `{doc['return_type']}` - {doc['return_description']}\n\n")
        f.write(f"**Complexity:** {doc['complexity']}\n\n")
        f.write(f"**Example:**\n```python\n{doc['example_usage']}\n```\n\n")
```

## Example 8: Financial Report Analysis

Extract key metrics from financial reports.

```python
from pydantic import BaseModel, Field

class FinancialMetrics(BaseModel):
    company_name: str
    reporting_period: str
    revenue: float = Field(description="In millions")
    net_income: float = Field(description="In millions")
    profit_margin: float = Field(ge=0, le=100, description="Percentage")
    key_highlights: list[str] = Field(max_length=5)
    risks: list[str] = Field(max_length=3)

reports_dir = Path("/mnt/user-data/uploads/financial_reports")
metrics = []

for report_file in reports_dir.glob("*.txt"):
    with open(report_file) as f:
        report_text = f.read()

    data = invoke_with_structured_output(
        prompt=f"""
        Extract financial metrics from this quarterly report.
        All monetary values should be in millions.

        {report_text}
        """,
        pydantic_model=FinancialMetrics,
        temperature=0.1  # Very low for numerical accuracy
    )

    if data:
        metrics.append(data.dict())

# Analysis
import pandas as pd
df = pd.DataFrame(metrics)

print("\nFinancial Summary:")
print(f"Average Revenue: ${df['revenue'].mean():.2f}M")
print(f"Average Net Income: ${df['net_income'].mean():.2f}M")
print(f"Average Profit Margin: {df['profit_margin'].mean():.2f}%")

df.to_csv('/mnt/user-data/outputs/financial_metrics.csv', index=False)
```

## Example 9: Survey Response Analysis

Analyze open-ended survey responses.

```python
from pydantic import BaseModel
from enum import Enum

class Satisfaction(str, Enum):
    VERY_SATISFIED = "very_satisfied"
    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    DISSATISFIED = "dissatisfied"
    VERY_DISSATISFIED = "very_dissatisfied"

class SurveyAnalysis(BaseModel):
    satisfaction: Satisfaction
    main_sentiment: str = Field(max_length=100)
    mentioned_features: list[str] = Field(description="Features mentioned positively or negatively")
    pain_points: list[str] = Field(description="Problems or complaints")
    suggestions: list[str] = Field(description="Improvement suggestions")

# Load survey data
import pandas as pd
df = pd.read_csv('/mnt/user-data/uploads/survey_responses.csv')

analyses = []
for idx, row in df.iterrows():
    analysis = invoke_with_structured_output(
        prompt=f"Analyze this survey response:\n\nQuestion: {row['question']}\nAnswer: {row['response']}",
        pydantic_model=SurveyAnalysis
    )

    if analysis:
        analyses.append({
            'response_id': row['id'],
            'satisfaction': analysis.satisfaction.value,
            'sentiment': analysis.main_sentiment,
            'features': ', '.join(analysis.mentioned_features),
            'pain_points': ', '.join(analysis.pain_points),
            'suggestions': ', '.join(analysis.suggestions)
        })

results_df = pd.DataFrame(analyses)
results_df.to_csv('/mnt/user-data/outputs/survey_analysis.csv', index=False)

# Aggregate insights
print("\nSatisfaction Distribution:")
print(results_df['satisfaction'].value_counts())

all_pain_points = [p for points in analyses for p in points.get('pain_points', [])]
from collections import Counter
print("\nTop Pain Points:")
for pain, count in Counter(all_pain_points).most_common(5):
    print(f"  {pain}: {count}")
```

## Example 10: Hybrid Claude + Gemini Workflow

Claude does complex reasoning, Gemini does structured extraction.

```python
from pydantic import BaseModel
from gemini_client import invoke_with_structured_output, invoke_parallel

# Step 1: Claude (you) analyzes the dataset and determines categories
# Assume you've identified key categories for classification

class DataPoint(BaseModel):
    text: str
    category: str
    confidence: float
    key_terms: list[str]

# Step 2: Gemini extracts structured data at scale
raw_data = pd.read_csv('/mnt/user-data/uploads/raw_data.csv')

structured_data = []
batch_size = 50

for i in range(0, len(raw_data), batch_size):
    batch = raw_data.iloc[i:i+batch_size]

    for idx, row in batch.iterrows():
        result = invoke_with_structured_output(
            prompt=f"Classify and extract from: {row['text']}",
            pydantic_model=DataPoint,
            temperature=0.3
        )

        if result:
            structured_data.append(result.dict())

    print(f"Processed {min(i+batch_size, len(raw_data))}/{len(raw_data)}")

# Step 3: Claude analyzes the structured results
df = pd.DataFrame(structured_data)

# Your analysis here:
# - Identify patterns
# - Generate insights
# - Create visualizations
# - Produce final report

print(f"\nProcessed {len(structured_data)} items")
print(f"Average confidence: {df['confidence'].mean():.2f}")
print("\nCategory distribution:")
print(df['category'].value_counts())
```

## Example 11: Blog Header Image Generation

Generate a styled blog header image with a single call.

```python
import sys
sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import generate_image

# Style prefix — prepend to any subject for consistent visual identity
RISO_ILLUSTRATION = (
    "Style: Risograph-inspired editorial illustration. "
    "Visible halftone dot texture and slight color misregistration between layers. "
    "Limited ink palette: deep indigo, warm coral, and sage green on off-white paper. "
    "Layered transparency where colors overlap creates rich secondary tones. "
    "Modern and professional — the aesthetic of an indie design studio, not a fantasy novel. "
    "Generous whitespace. No photorealism, no glow effects, no cyberpunk. No text or labels."
)

RISO_DIAGRAM = (
    "Style: Risograph-inspired technical diagram. "
    "Visible halftone dot texture and slight color misregistration. "
    "Limited ink palette: deep indigo for primary shapes and text, "
    "warm coral for highlights and active elements, "
    "sage green for secondary elements and connections. "
    "Off-white paper background. Clean layout with generous spacing. "
    "Professional and readable."
)

# Generate illustration header
subject = "A raven perched on a network graph, watching data flow between nodes"
result = generate_image(
    f"{RISO_ILLUSTRATION}\n\nSubject: {subject}. Wide landscape format, suitable as a blog header.",
    model="image-pro",       # Use image-pro for published content
    temperature=0.75,
    output_path="/mnt/user-data/outputs/blog_header.png"
)

if result:
    print(f"Header saved: {result['path']}")
else:
    print("Generation failed — retry or check credentials")
```

Key patterns:
- **Style prefix + subject composition**: The prefix sets visual rules, the subject describes content
- **`image-pro` for published content**: Better quality and text rendering than default
- **Temperature 0.7-0.8 for illustrations**: Allows creative variation while staying on-style
- **Explicit output path**: Control where the file lands for downstream use

## Example 12: Technical Diagram Generation

Generate a styled technical diagram with text labels.

```python
from gemini_client import generate_image

RISO_DIAGRAM = (
    "Style: Risograph-inspired technical diagram. "
    "Visible halftone dot texture and slight color misregistration. "
    "Limited ink palette: deep indigo for primary shapes and text, "
    "warm coral for highlights and active elements, "
    "sage green for secondary elements and connections. "
    "Off-white paper background. Clean layout with generous spacing. "
    "Professional and readable."
)

result = generate_image(
    f"{RISO_DIAGRAM}\n\n"
    "A flowchart showing: User Request → Claude Planning → Gemini Extraction → "
    "Claude Synthesis → Final Report. Highlight the Gemini step in coral. "
    "Wide landscape format.",
    model="image-pro",
    temperature=0.6,  # Lower temp for diagrams — more precise
)
```

## Example 13: Batch Image Generation with Variants

Generate multiple variants of the same concept for selection.

```python
from gemini_client import generate_image

subjects = [
    "A raven carrying a scroll through a library of glowing books",
    "A raven assembling puzzle pieces that form a constellation",
    "A raven observing its reflection in a pool of data streams",
]

results = []
for i, subject in enumerate(subjects):
    result = generate_image(
        f"Style: Risograph-inspired editorial illustration with deep indigo, "
        f"warm coral, sage green on off-white. No text.\n\n"
        f"Subject: {subject}. Wide landscape format.",
        model="nano-banana-2",   # Use fast model for drafts
        temperature=0.8,
        output_path=f"/mnt/user-data/outputs/variant_{i+1}.png"
    )
    if result:
        results.append(result["path"])
        print(f"Variant {i+1}: {result['path']}")

# Present all variants for user to pick
# present_files(results)
```

## Example 14: Image Generation with Structured Feedback Loop

Generate an image, analyze it with Gemini vision, regenerate if needed.

```python
from gemini_client import generate_image, invoke_with_structured_output
from pydantic import BaseModel, Field

class ImageQuality(BaseModel):
    has_text_artifacts: bool = Field(description="Unwanted text in the image")
    style_match: int = Field(ge=1, le=5, description="How well it matches risograph style")
    composition_score: int = Field(ge=1, le=5)
    issues: list[str] = Field(description="Problems to fix in re-generation")

# Generate
result = generate_image(
    "Style: Risograph editorial. Deep indigo, coral, sage green.\n\n"
    "Subject: A raven on a circuit board. Wide landscape.",
    model="image-pro",
    temperature=0.75,
)

if result:
    # Analyze with vision
    quality = invoke_with_structured_output(
        prompt="Evaluate this image for: unwanted text artifacts, "
               "risograph style fidelity (halftone dots, misregistration, limited palette), "
               "and composition quality.",
        pydantic_model=ImageQuality,
        image_path=result["path"]
    )
    print(f"Style match: {quality.style_match}/5")
    print(f"Issues: {quality.issues}")

    # Re-generate with fixes if needed
    if quality.style_match < 3 or quality.has_text_artifacts:
        fix_prompt = f"Fix: {', '.join(quality.issues)}. "
        # Regenerate with adjusted prompt...
```

## Best Practices from Examples

**1. Temperature tuning:**
- Factual extraction: 0.1-0.3
- Classification: 0.3-0.5
- Diagrams / technical images: 0.5-0.7
- Creative tasks / illustrations: 0.7-0.9

**2. Batch processing:**
- Process in batches of 50-100
- Add delays between batches for rate limits
- Show progress to user

**3. Error handling:**
- Always check if result is None
- Log failures for debugging
- Consider retry logic for critical tasks

**4. Schema design:**
- Use Field descriptions for clarity
- Add constraints (ge, le, max_length)
- Use Enums for fixed categories

**5. Output formats:**
- CSV for tabular data
- JSON for hierarchical data
- Markdown for documentation
- Database for large datasets

**6. Image generation:**
- Compose prompts as: style prefix + subject + format ("Wide landscape")
- Use `image-pro` / `nano-banana-pro` for published content, `nano-banana-2` for drafts
- Temperature 0.5-0.7 for diagrams, 0.7-0.8 for illustrations
- Add negative constraints ("No photorealism, no glow effects") to avoid model defaults
- Always check result is not None before using the path
