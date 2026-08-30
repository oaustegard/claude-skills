#!/usr/bin/env python3
"""Rank a draft's sentences by how staged they look. Optional stage 1.5.

The regex scan reaches lexical tells. The structural third — a sentence built to
make a finding arrive rather than to state it — has no surface form to match, so
`declaude_lint.py` cannot see it and the skill hands that third to a reader. This
script narrows what the reader has to look at.

    python3 declaude_rank.py DRAFT.md               # top 15 candidates
    python3 declaude_rank.py DRAFT.html --top 25
    python3 declaude_rank.py DRAFT.md --json
    python3 declaude_rank.py --fit                  # refit the axis from register.md

It is a fitted direction in sentence-embedding space, not a model with a prompt.
The axis is the mean of `embed(was) - embed(now)` over the matched before/after
pairs in `references/register.md`: same content on both sides, staging the only
variable. Fixed weights, no sampling, no question to phrase three ways — which is
the point, given that two defensible phrasings of one judging question rank the
same texts at -0.50 to each other.

WHAT IT DOES AND DOES NOT DO. It shortlists; it does not decide, and nothing
should be gated on it. Measured in `references/preservation.md`: 76% leave-one-out
on the pairs it is fitted from, and on one real editing pass it put all nine
edited sentences at a median rank of 13 of 53 against a chance median of 26
(permutation p=0.031). One draft is one draft. It also cannot rank documents —
against ten human-graded samples the correlation is -0.26, p=0.46 — so a
document-level number is not offered here.

Needs torch and transformers, which the rest of the skill does not. Everything
in `declaude_lint.py` and `declaude_diff.py` stays standard-library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AXIS_PATH = HERE.parent / "assets" / "staging-axis.json"
REGISTER = HERE.parent / "references" / "register.md"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

sys.path.insert(0, str(HERE))
try:
    from declaude_lint import html_to_lines, looks_like_html
except ImportError:
    def looks_like_html(t: str) -> bool:
        return "<html" in t[:4000].lower() or "<p>" in t[:4000].lower()

    def html_to_lines(t: str) -> str:
        return re.sub(r"<[^>]+>", " ", t)

PAIR_RE = re.compile(r"> was:\s*(.+?)\n> now:\s*(.+?)(?=\n\n|\n> was:|\Z)", re.S)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace(">", " ").replace("*", "")).strip()


def register_pairs(text: str) -> list[tuple[str, str]]:
    out = []
    for was, now in PAIR_RE.findall(text):
        w, n = _clean(was), _clean(now)
        if len(w.split()) >= 4 and len(n.split()) >= 4:
            out.append((w, n))
    return out


def sentences(text: str) -> list[str]:
    if looks_like_html(text):
        text = html_to_lines(text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^#{1,6}\s.*$", " ", text, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
            if 4 <= len(s.split()) <= 60]


def _embedder():
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError:
        sys.exit("declaude_rank needs torch and transformers:  pip install torch transformers\n"
                 "The lint and diff stages do not — this stage is optional.")
    tok = AutoTokenizer.from_pretrained(MODEL)
    mod = AutoModel.from_pretrained(MODEL).eval()

    @torch.no_grad()
    def embed(texts: list[str], bs: int = 32):
        import numpy as np
        out = []
        for i in range(0, len(texts), bs):
            b = tok(texts[i:i + bs], padding=True, truncation=True,
                    max_length=256, return_tensors="pt")
            h = mod(**b).last_hidden_state
            m = b["attention_mask"].unsqueeze(-1).float()
            v = (h * m).sum(1) / m.sum(1).clamp(min=1e-9)
            out.append(torch.nn.functional.normalize(v, dim=-1))
        return torch.cat(out).numpy()
    return embed


def fit(register_text: str) -> dict:
    import numpy as np
    pairs = register_pairs(register_text)
    if len(pairs) < 20:
        sys.exit(f"only {len(pairs)} matched was/now pairs — too few to fit an axis")
    embed = _embedder()
    diffs = embed([w for w, _ in pairs]) - embed([n for _, n in pairs])
    axis = diffs.mean(0)
    axis /= np.linalg.norm(axis)

    correct = 0                       # leave-one-out, so the number is honest
    W = embed([w for w, _ in pairs])
    N = embed([n for _, n in pairs])
    for i in range(len(pairs)):
        a = np.delete(diffs, i, axis=0).mean(0)
        a /= np.linalg.norm(a)
        correct += (W[i] @ a) > (N[i] @ a)
    return {"model": MODEL, "pairs": len(pairs),
            "leave_one_out": round(correct / len(pairs), 4),
            "axis": [round(float(x), 6) for x in axis]}


def load_axis():
    import numpy as np
    if not AXIS_PATH.exists():
        sys.exit(f"no fitted axis at {AXIS_PATH} — run with --fit")
    d = json.loads(AXIS_PATH.read_text())
    return np.asarray(d["axis"], dtype="float32"), d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fit", action="store_true", help="refit the axis from register.md")
    args = ap.parse_args()

    if args.fit:
        d = fit(REGISTER.read_text(encoding="utf-8"))
        AXIS_PATH.parent.mkdir(parents=True, exist_ok=True)
        AXIS_PATH.write_text(json.dumps(d, indent=1))
        print(f"fitted on {d['pairs']} pairs, leave-one-out {d['leave_one_out']:.0%} "
              f"(chance 50%) -> {AXIS_PATH}")
        return 0

    if not args.draft:
        ap.error("give a DRAFT, or --fit")
    axis, meta = load_axis()
    sents = sentences(Path(args.draft).read_text(encoding="utf-8"))
    if not sents:
        print("no sentences found")
        return 0
    scores = _embedder()(sents) @ axis
    ranked = sorted(zip(scores, sents), key=lambda x: -x[0])[:args.top]

    if args.json:
        print(json.dumps({"model": meta["model"], "sentences": len(sents),
                          "ranked": [{"score": round(float(s), 4), "sentence": t}
                                     for s, t in ranked]}, indent=1))
        return 0

    print(f"{len(sents)} sentences, {len(ranked)} most staged-looking "
          f"(axis fitted on {meta['pairs']} pairs, {meta['leave_one_out']:.0%} leave-one-out)\n")
    for i, (s, t) in enumerate(ranked, 1):
        print(f" {i:2}  {s:+.4f}  {t[:100]}")
    print("\nA shortlist, not a verdict, and not a count to track. Read each one and ask")
    print("the skill's question: is it saying the thing, or performing having had the")
    print("thought? A sentence that is stating it plainly can score high and stay.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
