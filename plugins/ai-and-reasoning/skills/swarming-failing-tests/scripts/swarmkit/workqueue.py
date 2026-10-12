"""Build the work queue from test results: cluster failures by signature.

A signature is "<stage>: <normalised reason>", e.g.
    "parse: expected <id> in struct declarator"
Numbers, file:line:col, absolute paths, hex constants and quoted identifiers are
masked, so the same bug in different tests lands in one cluster. Short
punctuation, the config's `queue.keep_words` and CamelCase names in quotes are
kept ("expected ';'" stays specific).

A work item is one cluster (or one shard of a big cluster) with 1-3
representative tests. Priority = ladder level of the suite, then cluster size,
minus a penalty for earlier failed attempts. Items whose key or tests are in
flight are skipped, so two live workers never get the same cluster.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field


def level(qcfg: dict, suite: str) -> int:
    for prefix, lv in qcfg["ladder"]:
        if suite.startswith(prefix):
            return int(lv)
    return int(qcfg["default_level"])


def normalise(reason: str, keep_words: frozenset = frozenset()) -> str:
    r = (reason or "").strip().splitlines()[-1:] or [""]   # last line: exception / message
    r = r[0]
    r = re.sub(r"(?<![\w.])(?:/[\w.+-]+){2,}/?", "<path>", r)                       # absolute paths
    r = re.sub(r"(?<![\w<])[\w.+-]+\.(?:c|h|s|S|o|i|cc|cpp|py|rs|go|js|ts)\b", "<file>", r)
    # strip "file:line:col: error:" BEFORE truncation handling, or every message keeps its location
    r = re.sub(r"^\s*(?:<path>|<file>)(?::\d+)*:\s*(?:(?:fatal )?error:\s*)?", "", r)
    r = re.sub(r"\bline \d+", "line <n>", r)
    r = r.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    def quoted(m: re.Match) -> str:
        q, s = m.group(1), m.group(2)
        keep = (s in keep_words or (len(s) <= 3 and not re.search(r"\w", s))
                or re.fullmatch(r"[A-Z][a-z]+(?:[A-Z][a-z]*)+|[A-Z][a-z]{3,}", s) is not None)
        return f"{q}{s}{q}" if keep else f"{q}<id>{q}"

    r = re.sub(r"(['\"`])(.*?)\1", quoted, r)
    r = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", r)
    r = re.sub(r"\b\d+(\.\d+)?\b", "<n>", r)
    r = re.sub(r"(<path>|<file>)(\s*<(?:path|file)>)+", r"\1", r)
    r = re.sub(r"\s+", " ", r).strip(" :")
    r = re.sub(r"^\[\w+\]\s*", "", r)                  # "[parse] msg": stage is already in the signature
    if r.endswith("..."):                                # runners truncate at varying lengths:
        words = r[:-3].rstrip().split(" ")[:-1]          # drop the cut word, keep a stable prefix
        r = " ".join(words[:3]) + " ..."
    return r[:110] or "<no reason>"


def signature(rec: dict, keep_words: frozenset = frozenset()) -> str:
    stage = rec.get("stage") or "unknown"
    reason = normalise(rec.get("reason", ""), keep_words)
    if reason.startswith(stage + ":"):
        reason = reason[len(stage) + 1:].strip()
    return f"{stage}: {reason}"


@dataclass
class WorkItem:
    key: str                  # unique cluster/shard key used for in-flight exclusion
    signature: str
    priority: float
    size: int                 # tests in the whole cluster (all shards)
    tests: list[str]          # 1-3 representatives the worker must fix
    targets: list[str]        # cluster members the gate checks (includes tests)
    reasons: dict[str, str] = field(default_factory=dict)


def _shard(test_id: str, n: int) -> int:
    return int(hashlib.sha1(test_id.encode()).hexdigest(), 16) % n


def clusters(results: dict, keep_words: frozenset = frozenset()) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tid, rec in results.items():
        if rec.get("status") in ("PASS", "SKIP"):
            continue
        out.setdefault(signature(rec, keep_words), []).append(tid)
    return out


def counted_failures(ledger: dict, epoch: float) -> list[dict]:
    """Ledger records that count as a failed attempt: not a lost merge race, not before the epoch."""
    return [r for r in ledger.values()
            if r.get("status") in ("rejected", "failed", "reverted")
            and not (r.get("status") == "rejected" and str(r.get("reason", "")).startswith(("conflict", "main kept moving")))
            and (r.get("t_launch") or 0) >= epoch]


def build(qcfg: dict, results: dict, ledger: dict | None = None, source_size=None, limit: int = 0,
          epoch: float = 0.0) -> list[WorkItem]:
    """Work items, best first. `ledger` gives in-flight exclusion and attempt penalties;
    `source_size(test_id) -> int` ranks representatives (smallest first: easiest for a small model)."""
    ledger = ledger or {}
    keep = frozenset(qcfg["keep_words"])
    busy_keys, busy_tests = set(), set()
    for r in ledger.values():
        if r.get("status") in ("launched", "finished"):
            busy_keys.add(r.get("key"))
            busy_tests.update(r.get("tests", []))
    attempts: dict[str, float] = {}
    sig_fails: dict[str, int] = {}
    for r in counted_failures(ledger, epoch):
        sig_fails[r.get("signature")] = sig_fails.get(r.get("signature"), 0) + 1
        for t in r.get("tests", []):     # a worker that died without a result counts half
            attempts[t] = attempts.get(t, 0) + (1 if r.get("result") else 0.5)
    size_of = source_size or (lambda t: 0)
    suite = lambda t: t.split("/", 1)[0]
    items: list[WorkItem] = []
    for sig, tids in clusters(results, keep).items():
        n = len(tids)
        # A fully concrete signature (nothing masked, e.g. one undefined symbol) is one root cause:
        # shards would only make several workers write the same fix and conflict.
        concrete = not re.search(r"<(id|n|file|path|hex)>", sig)
        shards = 1 if concrete else max(1, min(qcfg["max_shards"], n // qcfg["shard_size"]))
        for k in range(shards):
            members = [t for t in tids if shards == 1 or _shard(t, shards) == k]
            key = sig if shards == 1 else f"{sig} #{k + 1}/{shards}"
            if key in busy_keys:
                continue
            free = [t for t in members if t not in busy_tests and attempts.get(t, 0) < qcfg["max_test_attempts"]]
            if not free:
                continue
            lv = max(level(qcfg, suite(t)) for t in free)
            free.sort(key=lambda t: (-level(qcfg, suite(t)), attempts.get(t, 0), size_of(t), t))
            reps = free[:qcfg["reps"]]
            targets = reps + [t for t in members if t not in reps][:qcfg["gate_targets"] - len(reps)]
            prio = 10 * lv + 3 * math.log2(1 + n) - 4 * sig_fails.get(sig, 0) / shards
            items.append(WorkItem(key, sig, round(prio, 2), n, reps, targets,
                                  {t: results[t].get("reason", "")[:300] for t in reps}))
    items.sort(key=lambda w: (-w.priority, w.key))
    return items[:limit] if limit else items
