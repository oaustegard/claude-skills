# Drift report — example

What a review produces. This is the report for a small parser package whose
`README.md` claims `parse(text)` turns text into records and `Reader(path).read()`
streams them, checked against the source and tests via `gather_context.py`.

---

**Document:** `README.md`  ·  **Sources:** `pkg/parser.py`  ·  **Tests:** `tests/`

| Verdict | Claim (prose) | Reality |
|---|---|---|
| PASS | `parse(text)` turns text into records | `parse(text, strict=False)` exists; `test_parse_empty` exercises it |
| UNSUPPORTED | `Reader(path).read()` streams records | `Reader.read(self, n=10)` exists and matches, but `test_reader_reads` asserts `True` — it never calls `read()`. No test protects this claim. |

**Summary:** 1 PASS, 1 UNSUPPORTED, 0 FAIL, 0 STALE.

**Recommended actions:**
- The `read()` claim is accurate today but unprotected. Add a test that calls
  `Reader(path).read()` and asserts on its output, so a future change to `read`
  fails loudly instead of silently invalidating the README.

---

Notes on reading this report:

- **UNSUPPORTED is the interesting verdict.** A dumb signature check would have
  marked `read()` green — the signature matches. Reading the *test* shows the
  claim rests on nothing. That gap is what an agent review adds over a
  declarative check, and it points at a missing test rather than a doc edit.
- **FAIL would mean the doc is wrong now** (e.g., README says `parse` returns a
  dict but the code returns a list). Those get a prose fix.
- **STALE would mean the doc references something gone** (e.g., a removed
  `parse_strict` function). Those get a prose fix or removal.
- The report never claims the *tests* are correct — only that the prose agrees
  with code+tests as they stand. Bad tests upstream still produce a confident
  PASS.
