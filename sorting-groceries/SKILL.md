---
name: sorting-groceries
description: Sort grocery lists by aisle order using store aisle sign photos. Build aisle maps from uploaded images, match items to aisles, and output optimized shopping routes. Use when users upload aisle sign photos, request grocery list sorting, want shopping trip optimization, need store layout mapping, or mention grocery list organization.
metadata:
  version: 0.2.0
---

# Sorting Groceries by Aisle

Sort a user's grocery list by aisle order so they can walk the store in one efficient pass, no backtracking.

## When Triggered

Activate when user:
- Uploads photos of grocery store aisle signs or markers
- Provides a grocery/shopping list alongside store layout info
- Asks to sort, organize, or optimize a shopping list by aisle
- Mentions aisle numbers, store maps, or shopping routes

## Inputs

Two inputs are needed. Prompt for whichever is missing:

1. **Aisle sign images** — Photos of aisle markers, hanging signs, or endcap labels. Each typically shows an aisle number and category keywords (e.g., "Aisle 5: Coffee, Tea, Cocoa").
2. **Grocery list** — Text, pasted note, or photo of a handwritten list. Any format.

## Building the Aisle Map

Read each uploaded aisle sign image for its aisle number (or label, e.g. "A5")
and category text exactly as printed (e.g., "Pasta, Sauces, Canned
Vegetables"). Compile into a structured map:

```
Aisle 1: Bread, Bakery Items, Tortillas
Aisle 2: Cereal, Breakfast, Granola Bars
Aisle 3: Pasta, Sauces, Canned Goods
...
```

If an image is blurry or partially unreadable, note what was legible and flag
uncertainty rather than guessing.

## Perimeter Zones

Grocery stores also have unnumbered perimeter sections. Use the user's own
signage wherever their photos cover it; otherwise fall back to this typical
layout, run counterclockwise from the entrance:

| Zone | Typical items |
|------|---------------|
| **Produce** | Fresh fruits, vegetables, herbs, salad mixes |
| **Deli** | Sliced meats, prepared foods, rotisserie chicken |
| **Bakery** | Fresh bread, cakes, pastries (distinct from packaged bread aisle) |
| **Dairy** | Milk, cheese, yogurt, butter, eggs |
| **Meat & Seafood** | Fresh/frozen meat, poultry, fish |
| **Frozen** | Frozen meals, ice cream, frozen vegetables |

Typical flow: **Produce → Deli/Bakery → Meat/Seafood → Dairy → Frozen**.

## Matching Items to Aisles

Parse every item from the user's list, preserving their original wording
alongside any normalized form (e.g. "parm" → parmesan cheese; "2 lbs chicken
breast" → chicken breast, 2 lbs). Match each item to the aisle or perimeter
zone its category text best fits. When an item could plausibly sit in more
than one place (honey: baking vs. condiments), assign the most likely one and
add a note rather than guessing silently — see Multi-Aisle Items below. An
item that matches nothing goes to "couldn't place" rather than being forced
into a guessed aisle.

## Output

Present the final list grouped by aisle in store-walk order:

```
🛒 Sorted Shopping List — [Store Name if known]

PRODUCE
  □ bananas
  □ baby spinach
  □ 3 avocados

AISLE 1 — Bread, Bakery Items, Tortillas
  □ whole wheat bread
  □ flour tortillas

AISLE 2 — Cereal, Breakfast, Granola Bars
  □ oatmeal
  □ granola bars

AISLE 3 — Pasta, Sauces, Canned Goods
  □ spaghetti
  □ marinara sauce
  □ canned black beans

...

DAIRY
  □ 2% milk
  □ shredded mozzarella
  □ eggs (1 dozen)

⚠️ COULDN'T PLACE
  □ birthday candles — not enough aisle info to determine location
```

## Output Formatting Rules

- Use checkbox format (`□`) so the list is easy to use on a phone
- Include the aisle's category description next to the aisle number for quick reference
- Keep the user's quantities and notes attached to each item
- Perimeter zones go in logical store-walk order (Produce first, Frozen/Dairy last)
- Numbered aisles go in ascending order between the perimeter zones
- Unmatched items go at the end under a clear "couldn't place" heading

## Multi-Aisle Items

Some items legitimately live in multiple locations. When this occurs:
- Place the item in the **most common** aisle for that store's layout
- Add a parenthetical note: "(also check Aisle 7)"
- Common examples: honey (baking vs condiments), tortilla chips (snacks vs Hispanic foods), butter (dairy vs baking)

## Handling Ambiguity

- **Blurry/unreadable signs**: Note which aisles had unclear text. Ask user to confirm if critical items might be affected.
- **Store-brand categories**: Some stores use unusual groupings ("International Foods" might contain pasta in one store). Trust the sign text over assumptions.
- **Missing aisles**: If user uploaded signs for aisles 1-5 and 8-12 but not 6-7, note the gap. Items that don't match any uploaded aisle go to "couldn't place" rather than being guessed into missing aisles.

## Store Layout Reuse

If the user mentions they shop at this store regularly:
- Present the aisle map as a clean reference they can save
- Suggest they can reuse it in future conversations by pasting just the map text instead of re-uploading photos
- Format the reusable map clearly:

```
📍 [Store Name] Aisle Map
Aisle 1: Bread, Bakery Items, Tortillas
Aisle 2: Cereal, Breakfast, Granola Bars
...
Produce | Deli/Bakery | Meat & Seafood | Dairy | Frozen
```
