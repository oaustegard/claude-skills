# Advanced Patterns

Advanced usage patterns for Gemini integration.

## Multi-Modal Processing

### Image Analysis with Structure

```python
from pydantic import BaseModel, Field
from gemini_client import invoke_with_structured_output

class ProductAnalysis(BaseModel):
    product_name: str
    category: str
    colors: list[str]
    estimated_price_range: str
    condition: str = Field(description="new, used, or refurbished")

result = invoke_with_structured_output(
    prompt="Analyze this product image. Identify the product, category, colors, and estimate price range.",
    pydantic_model=ProductAnalysis,
    image_path="/mnt/user-data/uploads/product.jpg"
)

print(f"Product: {result.product_name}")
print(f"Category: {result.category}")
print(f"Colors: {', '.join(result.colors)}")
```

### Batch Image Processing

```python
from pathlib import Path
from gemini_client import invoke_parallel

image_dir = Path("/mnt/user-data/uploads/photos")
image_files = list(image_dir.glob("*.jpg"))

prompts = [
    f"Describe this image in one sentence"
    for _ in image_files
]

# Note: parallel invocation doesn't support images directly
# Process sequentially with progress
for i, image_path in enumerate(image_files):
    result = invoke_gemini(
        prompt="Describe this image briefly",
        image_path=str(image_path)
    )
    print(f"[{i+1}/{len(image_files)}] {image_path.name}: {result}")
```

## Hybrid Workflows

### Claude Plans, Gemini Executes

Use Claude's reasoning for planning, Gemini for structured execution:

```python
# 1. Claude (you) analyzes requirements and creates extraction plan
# 2. Gemini executes structured extractions

from pydantic import BaseModel
from gemini_client import invoke_with_structured_output

class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str
    company: str

# Gemini extracts structured data
documents = [...]  # List of document paths
contacts = []

for doc_path in documents:
    with open(doc_path) as f:
        doc_text = f.read()

    result = invoke_with_structured_output(
        prompt=f"Extract contact information from:\n\n{doc_text}",
        pydantic_model=ContactInfo
    )
    contacts.append(result)

# 3. Claude synthesizes and analyzes results
# ... your analysis code here ...
```

### Parallel Processing with Different Models

```python
from concurrent.futures import ThreadPoolExecutor
from gemini_client import invoke_gemini

def process_with_model(text: str, model: str) -> str:
    return invoke_gemini(text, model=model)

# Compare outputs from different models
text = "Analyze the sentiment of this review: ..."

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(process_with_model, text, "gemini-2.0-flash-exp"): "flash-exp",
        executor.submit(process_with_model, text, "gemini-1.5-flash"): "flash",
        executor.submit(process_with_model, text, "gemini-1.5-pro"): "pro",
    }

    for future in as_completed(futures):
        model_name = futures[future]
        result = future.result()
        print(f"{model_name}: {result}")
```

## Complex Schema Patterns

### Nested Structures

```python
from pydantic import BaseModel
from typing import Optional

class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"

class Person(BaseModel):
    name: str
    age: Optional[int] = None
    email: str
    address: Address

result = invoke_with_structured_output(
    prompt="Extract person info: John Doe, 30, john@example.com, 123 Main St, Springfield, IL 62701",
    pydantic_model=Person
)
```

### Enums and Constraints

```python
from pydantic import BaseModel, Field, validator
from enum import Enum

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Task(BaseModel):
    title: str = Field(max_length=100)
    description: str
    priority: Priority
    estimated_hours: int = Field(ge=1, le=100)
    tags: list[str] = Field(max_length=10)

    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v

result = invoke_with_structured_output(
    prompt="Create a task: Fix login bug - Users can't login. This is urgent. Should take 4 hours. Tags: bug, auth, security",
    pydantic_model=Task
)
```

### Lists and Arrays

```python
from pydantic import BaseModel

class Ingredient(BaseModel):
    name: str
    quantity: str
    unit: str

class Recipe(BaseModel):
    title: str
    servings: int
    prep_time_minutes: int
    cook_time_minutes: int
    ingredients: list[Ingredient]
    instructions: list[str]

recipe_text = """
Make pasta carbonara.
Serves 4. Prep: 10 min. Cook: 20 min.
Ingredients: 400g spaghetti, 200g pancetta, 4 eggs, 100g parmesan, black pepper.
Instructions:
1. Boil pasta
2. Fry pancetta
3. Mix eggs and cheese
4. Combine all
"""

result = invoke_with_structured_output(
    prompt=f"Extract recipe from:\n{recipe_text}",
    pydantic_model=Recipe
)
```

## Error Recovery

### Retry with Schema Relaxation

```python
from pydantic import BaseModel

class StrictData(BaseModel):
    field1: str
    field2: int
    field3: list[str]

# Try strict schema first
result = invoke_with_structured_output(prompt, StrictData)

if not result:
    # Retry with relaxed schema
    class RelaxedData(BaseModel):
        field1: str
        field2: Optional[int] = None
        field3: Optional[list[str]] = []

    result = invoke_with_structured_output(prompt, RelaxedData)
```

### Validation and Correction

```python
from pydantic import BaseModel, ValidationError

result = invoke_with_structured_output(prompt, MyModel)

if result:
    try:
        # Additional validation
        assert len(result.items) > 0, "Must have at least one item"
        assert result.total > 0, "Total must be positive"
    except AssertionError as e:
        print(f"Validation failed: {e}")
        # Retry with corrected prompt
        corrected_prompt = f"{prompt}\n\nIMPORTANT: {e}"
        result = invoke_with_structured_output(corrected_prompt, MyModel)
```

## Performance Optimization

### Prompt Caching

For repeated prompts with same prefix:

```python
# Share common context across requests
base_context = """
You are analyzing customer reviews for sentiment.
Categories: positive, neutral, negative
Format: JSON with 'sentiment' and 'confidence' fields
"""

reviews = ["Review 1...", "Review 2...", "Review 3..."]

for review in reviews:
    full_prompt = f"{base_context}\n\nReview: {review}"
    result = invoke_gemini(full_prompt)
```

### Batch Size Tuning

```python
from gemini_client import invoke_parallel

# Process in optimal batches
all_prompts = [...]  # 1000 prompts
batch_size = 50  # Tune based on rate limits

results = []
for i in range(0, len(all_prompts), batch_size):
    batch = all_prompts[i:i+batch_size]
    batch_results = invoke_parallel(batch, max_workers=10)
    results.extend(batch_results)

    # Rate limit breathing room
    if i + batch_size < len(all_prompts):
        time.sleep(2)
```

### Temperature Tuning

```python
# Factual extraction: low temperature
factual = invoke_gemini(
    "Extract the date from: Meeting scheduled for March 15th",
    temperature=0.1
)

# Creative generation: high temperature
creative = invoke_gemini(
    "Write a creative tagline for a coffee shop",
    temperature=0.9
)

# Balanced: medium temperature
balanced = invoke_gemini(
    "Summarize this article",
    temperature=0.7
)
```

## Cost Optimization

### Token Counting

```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Count tokens before sending
token_count = model.count_tokens("Your prompt here")
print(f"Input tokens: {token_count.total_tokens}")

# Estimate cost
input_cost = (token_count.total_tokens / 1_000_000) * 0.15
print(f"Estimated input cost: ${input_cost:.4f}")
```

### Prompt Compression

```python
# Verbose (wasteful)
verbose_prompt = """
Please analyze the following text and extract the following information:
- The name of the person
- Their email address
- Their phone number
- Their company name

Text:
John Doe works at Acme Corp. Email: john@acme.com, Phone: 555-0100
"""

# Concise (efficient)
concise_prompt = """
Extract: name, email, phone, company

John Doe works at Acme Corp. Email: john@acme.com, Phone: 555-0100
"""

# With structured output, schema provides the context
result = invoke_with_structured_output(
    prompt="John Doe works at Acme Corp. Email: john@acme.com, Phone: 555-0100",
    pydantic_model=ContactInfo  # Schema explains structure
)
```

## Integration with Other Tools

### Save Results to Database

```python
import sqlite3
from gemini_client import invoke_with_structured_output

conn = sqlite3.connect('/home/claude/results.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        name TEXT, email TEXT, phone TEXT, company TEXT
    )
''')

documents = [...]
for doc in documents:
    result = invoke_with_structured_output(doc, ContactInfo)
    if result:
        cursor.execute(
            'INSERT INTO contacts VALUES (?, ?, ?, ?)',
            (result.name, result.email, result.phone, result.company)
        )

conn.commit()
```

### Export to CSV

```python
import csv
from gemini_client import invoke_with_structured_output

results = []
for item in items:
    result = invoke_with_structured_output(item, DataModel)
    if result:
        results.append(result.dict())

# Write to CSV
with open('/mnt/user-data/outputs/results.csv', 'w', newline='') as f:
    if results:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
```

### Combine with Pandas

```python
import pandas as pd
from gemini_client import invoke_with_structured_output

# Process data with Gemini, analyze with pandas
data = []
for text in texts:
    result = invoke_with_structured_output(text, StructuredData)
    if result:
        data.append(result.dict())

df = pd.DataFrame(data)
print(df.describe())
print(df.groupby('category').size())
```
