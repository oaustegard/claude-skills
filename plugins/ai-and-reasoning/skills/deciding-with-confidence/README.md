# deciding-with-confidence

Answers yes/no, multiple-choice and rubric-score questions about a piece of text
with a probability for every option and a calibrated confidence, in the request
and response shapes of OpenAI's Decisions API. Claude Haiku 5.5 does the
judging; the skill estimates the probabilities that a purpose-built decision
model would read off its logits.

```bash
echo '{"input": "I was charged twice.", "questions": [{"type": "choice", "name": "dept",
  "instructions": "Which department?", "choices": [{"value": "billing"}, {"value": "shipping"}]}]}' \
  | python3 scripts/decide.py run -
```

It runs through the Anthropic API (`pip install anthropic` and a key), the
`claude` CLI, Amazon Bedrock, or parallel subagents inside Claude Code: the
`deciding-with-confidence` plugin installs a `decider` agent pinned to Haiku
5.5 alongside the skill.
On a 104-item eval it reached 0.846 accuracy against 0.894 for a purpose-built
decision model, with matching calibration error. Its wrong answers come at low
confidence, so thresholding on confidence and on agreement between samples
catches most of them. See `SKILL.md` for the procedure and
`references/method.md` for the measurements.

`assets/eval.jsonl` includes 64 items from the banking77 test split (PolyAI,
CC-BY-4.0); each item names its source.
