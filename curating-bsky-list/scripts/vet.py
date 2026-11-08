"""Screen and judge candidate accounts, as experiments bsky-list-ai-share vet.py does.

Screen: at least 10 sampled posts, at most 40 posts a day, a post in the last 30 days, no bot / feed / news words
in handle, name or bio. Judge: a headless Claude Haiku reads bio, stats and six sample posts per account, 25
accounts a batch, and answers with keyed JSON. Topic candidates are judged as individuals writing substantively on
their topic; exploration candidates only as thoughtful individuals (not bots, feeds, marketers or organisations).
"""
from __future__ import annotations

import json
import random
import re
import shutil
import subprocess

BOTWORDS = re.compile(r"\b(bot|bots|feed|feeds|news|newsletter|digest|daily|hourly|updates|automated|headlines|"
                      r"briefing|aggregat\w*|curated|rss|jobs?|deals|crypto|signals|promo|giveaway)\b|-bot\b|bot\.",
                      re.IGNORECASE)
BRIDGY = re.compile(r"\.(ap\.)?brid\.gy$", re.IGNORECASE)
BATCH = 25


class JudgeUnavailable(Exception):
    pass


def stats(posts, now):
    """posts: [{t, text, reply}] -> {n, ppd, last_days, reply_frac} (None fields when there are no posts)."""
    ts = [p["t"] for p in posts if p.get("t")]
    if not ts:
        return {"n": len(posts), "ppd": None, "last_days": None, "reply_frac": None}
    span = max(1.0, (max(ts) - min(ts)) / 86400)
    return {"n": len(posts), "ppd": round(len(posts) / span, 2), "last_days": round((now - max(ts)) / 86400, 1),
            "reply_frac": round(sum(p["reply"] for p in posts) / len(posts), 2)}


def screen(handle, name, bio, st):
    """Return None if the account passes, else the reason it fails."""
    if BRIDGY.search(handle or ""):
        return "bridgy mirror"
    if BOTWORDS.search(f"{handle} {name} {bio}"):
        return "bot or feed words"
    if st["n"] < 10:
        return "fewer than 10 posts"
    if st["ppd"] is not None and st["ppd"] > 40:
        return "more than 40 posts a day"
    if st["last_days"] is None or st["last_days"] > 30:
        return "no post in 30 days"
    return None


def samples(did, posts, k=6):
    texts = [p["text"] for p in posts if p["text"]]
    longish = [t for t in texts if len(t) > 80] or texts
    rnd = random.Random(did)
    return [" ".join(t.split())[:220] for t in rnd.sample(longish, min(k, len(longish)))]


PROMPT_TOPIC = (
    "Below are {n} Bluesky accounts, numbered [0] to [{last}], each with handle, display name, bio, posting stats, "
    "the topic it was found for, and six sample posts. They are candidates for a curated reading list of PEOPLE "
    "whose own posts are thoughtful and substantive on their stated topic. Keep (1) an account only if it is an "
    "individual human whose own posts engage with that topic substantively. Reject (0) bots, automated or "
    "scheduled feeds, news or link aggregators, brand, company, conference or other organisation accounts, "
    "marketers and growth or 'make money' accounts, AI agents or personas posting as themselves, spam, and "
    "accounts whose posts are mostly not about the topic. Reply with ONLY a JSON object mapping each number as a "
    "string to {{\"keep\": 1 or 0, \"why\": \"at most 8 words\"}}, nothing else.")

PROMPT_EXPLORE = (
    "Below are {n} Bluesky accounts, numbered [0] to [{last}], each with handle, display name, bio, posting stats "
    "and six sample posts. They are candidates for the exploratory part of a curated reading list: people worth "
    "reading whatever they write about. Keep (1) an account only if it is an individual human who writes "
    "thoughtfully in their own voice: observations, arguments, expertise, craft, humour with substance. Reject (0) "
    "bots, automated or scheduled feeds, news or link aggregators, brand, company, conference or other "
    "organisation accounts, marketers and self-promotion accounts, AI agents or personas, spam, and accounts that "
    "mostly repost links or one-liners without thought of their own. Reply with ONLY a JSON object mapping each "
    "number as a string to {{\"keep\": 1 or 0, \"why\": \"at most 8 words\"}}, nothing else.")


def blob(rows, explore):
    parts = []
    for j, r in enumerate(rows):
        topic = "" if explore else f" | topic: {r.get('topic_label') or r.get('topic')}"
        parts.append(
            f"[{j}] @{r['handle']} | {r.get('name', '')} | bio: {r.get('bio', '')} | {r['ppd']} posts/day, "
            f"{int((r.get('reply_frac') or 0) * 100)}% replies, followers {r.get('followers')}{topic}\n"
            + "\n".join(f"  - {s}" for s in r.get("samples", [])))
    return "\n\n".join(parts)


def parse_verdict(raw, n):
    """Keyed JSON from the judge -> {index: (keep, why)}. Raises ValueError on a malformed reply."""
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        raise ValueError("no JSON object in the judge's reply")
    d = json.loads(m.group(0))
    if set(d) != {str(i) for i in range(n)}:
        raise ValueError(f"judge answered keys {sorted(d)[:5]}... for {n} accounts")
    return {int(k): (bool(int(v["keep"])), str(v.get("why", ""))[:80]) for k, v in d.items()}


def available():
    return shutil.which("claude") is not None


def judge(rows, explore=False, runner=None):
    """Set r['keep'] / r['why'] on every row. A batch the judge garbles twice gets keep=None (not judged)."""
    if runner is None:
        exe = shutil.which("claude")
        if not exe:
            raise JudgeUnavailable("the claude CLI is not on PATH; judge with Muninn decide and pass --verdicts")

        def runner(prompt):
            out = subprocess.run([exe, "-p", "--model", "haiku", "--output-format", "text", prompt],
                                 capture_output=True, text=True, timeout=900, check=False)
            return out.stdout
    tmpl = PROMPT_EXPLORE if explore else PROMPT_TOPIC
    for b in range(0, len(rows), BATCH):
        batch = rows[b:b + BATCH]
        prompt = tmpl.format(n=len(batch), last=len(batch) - 1) + "\n\n" + blob(batch, explore)
        verdict = None
        for _ in range(2):
            try:
                verdict = parse_verdict(runner(prompt), len(batch))
                break
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired):
                continue
        for j, r in enumerate(batch):
            r["keep"], r["why"] = verdict[j] if verdict else (None, "judge reply unusable")
    return rows


def apply_verdicts(rows, verdicts):
    """Verdicts from elsewhere (Muninn decide): {did: {keep, why}}. Rows without one get keep=None."""
    for r in rows:
        v = verdicts.get(r["did"])
        r["keep"], r["why"] = (bool(v["keep"]), v.get("why", "")) if v else (None, "no verdict")
    return rows
