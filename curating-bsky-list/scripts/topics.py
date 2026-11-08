"""Topics: Muninn's interests plus the experiments-atlas clusters, and one topic model per topic.

A topic model is List Scout's (oaustegard.github.io bsky/list-scout/topic.js): logistic regression, balanced
classes, C=1, on Ettin unit vectors; positives are posts found by searching the topic's terms (at most 1,500, at
most 25 per author), negatives are posts from Bluesky's Discover feed. Raw shares run high and differ between
topics, so an account's score on a topic is normalised against that topic's held-out examples:
    norm = (share - mean P on held-out Discover posts) / (mean P on held-out term posts - mean P on Discover)
0 reads like Discover, 1 reads like the term-search posts. Norms are comparable across topics, which is what
"an account's topic score is its best topic" needs.
"""
from __future__ import annotations

import json
import math
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ATLAS_URL = "https://raw.githubusercontent.com/oaustegard/experiments/main/experiments-atlas/data.json"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
MAX_POS, MAX_PER_AUTHOR = 1500, 25
MIN_TERM_HITS = 15        # a term with fewer posts in the window is dropped for this run
MIN_POS = 80              # a topic with fewer positive posts is skipped for this run
MIN_AUC = 0.80            # below this the terms are too general to define a topic
MAX_TERMS = 10

# Words that describe experiments rather than name a subject.
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "before", "being", "but", "by", "can", "could", "did",
    "does", "done", "each", "for", "from", "had", "has", "have", "how", "if", "in", "into", "is", "it", "its",
    "may", "more", "most", "much", "not", "of", "on", "one", "or", "our", "out", "over", "per", "run", "runs",
    "same", "so", "than", "that", "the", "their", "then", "there", "these", "this", "those", "three", "through",
    "to", "two", "under", "up", "us", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "why", "will", "with", "within", "without", "would", "you", "your", "yes", "no", "new", "first", "last",
    "best", "both", "every", "only", "also", "just", "about", "after", "again", "against", "all", "any",
    "because", "between", "down", "during", "few", "further", "here", "less", "many", "must", "off", "once",
    "other", "own", "should", "some", "such", "too", "very", "via", "vs", "result", "results", "readme",
    "results.md", "md", "png", "html", "py", "js", "json", "verdict", "negative", "positive", "phase", "built",
    "verified", "tested", "pending", "issue", "closed", "open", "test", "tests", "note", "notes", "split",
    "prior", "default", "reversed", "upheld", "wins", "win", "beats", "beat", "lifts", "drops", "cut", "cuts",
    "half", "full", "real", "exact", "exactly", "live", "page", "pages", "model", "models", "using", "use",
    "used", "makes", "make", "shows", "show", "running", "works", "work", "worked", "across", "held",
    "baseline", "gold", "eval", "evals", "score", "scores", "mb", "ms", "gb", "kb", "oskar", "oskar's",
    "muninn", "muninn's", "jev", "bluesky", "austegard", "austegard.com", "document", "student", "account",
    "questions", "address", "assessment", "execution", "session", "sessions", "installable", "untested",
    "rendered", "explainer", "recall", "queries", "paper", "training", "weights", "decision", "hand-written",
    "account-wide", "expansion", "bridges", "rectified", "m-parameter",
}

# Model names that are also ordinary words on Bluesky (a search for Haiku returns poems).
AMBIGUOUS = {"haiku", "sonnet", "opus", "metal", "semantic", "memories", "supervisor", "held-out", "quora", "python"}
STOP |= AMBIGUOUS


def load_assets():
    return json.loads((ASSETS / "topics.json").read_text())


def fetch_atlas(url=ATLAS_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "curating-bsky-list"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


_TOKEN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9]*(?:[-.][A-Za-z0-9]+)*")


def _candidates(text):
    """Searchable-looking tokens: acronyms (WGSL, LoRA), CamelCase (WebGPU), and long lowercase words."""
    out = set()
    for tok in _TOKEN.findall(text):
        tok = tok.strip(".-")
        low = tok.lower()
        if low in STOP or len(tok) < 3 or "." in tok:
            continue
        caps = sum(ch.isupper() for ch in tok)
        if caps >= 2 or (caps == 1 and not tok[0].isupper()):      # WGSL, LoRA, WebGPU, iPhone
            out.add(tok)
        elif tok.islower() and len(tok) >= 8 and not any(ch.isdigit() for ch in tok):
            out.add(low)
        elif tok[0].isupper() and len(tok) >= 5 and tok[1:].islower():  # Proper nouns: Remotion, Strudel
            out.add(tok)
    return out


def cluster_terms(atlas, k=8):
    """Terms per cluster from its experiments' purpose lines and ids, ranked by in-cluster spread x rarity.

    A term must occur in at least two of the cluster's experiments; rarity is inverse cluster frequency.
    Returns {cluster: [term, ...]} best first.
    """
    by = defaultdict(list)
    for e in atlas:
        by[e["c"]].append(_candidates((e.get("p") or "") + " " + e["id"].replace("-", " ")))
    df = Counter()
    for sets in by.values():
        df.update(set().union(*sets) if sets else set())
    n = len(by)
    out = {}
    for c, sets in by.items():
        cnt = Counter(t for s in sets for t in s)
        scored = [(cnt[t] * math.log((n + 1) / df[t]), t) for t in cnt if cnt[t] >= 2 and df[t] < n]
        out[c] = [t for _, t in sorted(scored, key=lambda x: (-x[0], x[1]))[:k]]
    return out


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def topic_specs(atlas, extra=()):
    """All topics for this run: interests, one per atlas cluster, and topics promoted into state."""
    a = load_assets()
    specs = [dict(t, kind="interest") for t in a["interests"]]
    extracted = cluster_terms(atlas)
    for c in sorted(extracted):
        seeds = a["cluster_seeds"].get(c, [])
        terms = list(dict.fromkeys(seeds + [t for t in extracted[c] if t.lower() not in {s.lower() for s in seeds}]))
        specs.append({"name": "atlas-" + slug(c), "label": c, "terms": terms[:MAX_TERMS + 4], "kind": "atlas"})
    for t in extra:
        specs.append(dict(t, kind="promoted"))
    return specs


def words(text):
    return sum(1 for w in text.split() if any(ch.isalpha() for ch in w))


def positives(spec, hits_by_term):
    """Pick a topic's positive posts from per-term search hits. Returns (texts, kept_terms, author_hits)."""
    kept = [t for t in spec["terms"] if len(hits_by_term.get(t, [])) >= MIN_TERM_HITS][:MAX_TERMS]
    seen, per_author, texts, author_hits = set(), Counter(), [], Counter()
    for t in kept:
        for p in hits_by_term[t]:
            if p["uri"] in seen:
                continue
            seen.add(p["uri"])
            did = p["author"]["did"]
            author_hits[did] += 1
            text = (p.get("record") or {}).get("text") or ""
            if words(text) >= 3 and per_author[did] < MAX_PER_AUTHOR and len(texts) < MAX_POS:
                per_author[did] += 1
                texts.append(text)
    return texts, kept, author_hits


def term_matcher(terms):
    """Whole-word, case-insensitive match for any term, as Bluesky's phrase search matches them."""
    alt = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<![\w])(?:{alt})(?![\w])", re.IGNORECASE)


def cross_negatives(name, texts_by_topic, terms, per_topic=150, seed=0):
    """Indices of other topics' positive posts to use as negatives for `name`: at most `per_topic` from each,
    leaving out any post that matches one of this topic's own terms. Returns {other_topic: [index, ...]}.

    Discover posts alone are the wrong background: against memes and photos, anyone writing sentences reads as
    on-topic, and in the first dry run (2026-11-08) 1,210 of 1,223 candidates scored above the exploration
    ceiling on some topic. Posts about other subjects teach each model what its topic is not.
    """
    import random

    rnd = random.Random(f"{seed}:{name}")
    match = term_matcher(terms) if terms else None
    out = {}
    for other, texts in texts_by_topic.items():
        if other == name:
            continue
        ok = [i for i, t in enumerate(texts) if not (match and match.search(t))]
        out[other] = sorted(rnd.sample(ok, min(per_topic, len(ok))))
    return out


def fit(Xpos, Xneg, seed=0):
    """Fit one topic model. Returns {w, b, auc, base, pos, n_pos} or None when the classes are too thin."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    if len(Xpos) < MIN_POS or len(Xneg) < MIN_POS:
        return None
    X = np.vstack([Xpos, Xneg])
    y = np.r_[np.ones(len(Xpos)), np.zeros(len(Xneg))]
    rng = np.random.default_rng(seed)
    test = rng.random(len(y)) < 0.2
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000).fit(X[~test], y[~test])
    p = clf.predict_proba(X[test])[:, 1]
    auc = float(roc_auc_score(y[test], p))
    base, pos = float(p[y[test] == 0].mean()), float(p[y[test] == 1].mean())
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000).fit(X, y)
    return {"w": clf.coef_[0].astype("float32"), "b": float(clf.intercept_[0]), "auc": auc,
            "base": base, "pos": pos, "n_pos": len(Xpos)}


def norm_scores(models, X):
    """Per-topic normalised share for one account's post vectors X. Returns {topic: norm}."""
    import numpy as np

    if not len(X) or not models:
        return {}
    names = list(models)
    W = np.stack([models[n]["w"] for n in names])
    b = np.array([models[n]["b"] for n in names])
    P = 1 / (1 + np.exp(-(X @ W.T + b)))
    share = P.mean(axis=0)
    out = {}
    for i, n in enumerate(names):
        m = models[n]
        out[n] = round(float((share[i] - m["base"]) / max(1e-6, m["pos"] - m["base"])), 4)
    return out


def best(scores):
    if not scores:
        return None, None
    t = max(scores, key=scores.get)
    return t, scores[t]
