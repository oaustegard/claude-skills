#!/usr/bin/env python3
"""Curate Muninn's own Bluesky reading list with Ettin topic models, plus an exploration share.

    curate.py build    [--dry-run]   create the curate list on Muninn's account and fill it (first run)
    curate.py refresh  [--dry-run]   weekly: re-score members, drop, add up to 10
    curate.py read     [--days 7]    the list's posts from the past week, as a digest to read
    curate.py status                 what the state holds
    curate.py add-topic NAME --terms "a,b,c" [--label L] [--lang xx|any]

Every command prints one JSON object on stdout (read also writes the digest file); progress goes to stderr.
Writes on Bluesky are list items on Muninn's own list and nothing else; see bsky.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bsky
import store as store_mod
import topics as topics_mod
import vet

VERSION = "0.1.0"
OSKAR = "austegard.com"
AI_LIST = "at://did:plc:r2whjvupgfw55mllpksnombn/app.bsky.graph.list/3lankcdrlip2f"
LIST_NAME = "Muninn reads"
LIST_DESCRIPTION = ("The accounts Muninn, Oskar Austegard's AI agent, reads each week: people who write on its "
                    "interests and on themes from Oskar's experiments, plus about a third chosen to explore beyond "
                    "them. Picked by a small text classifier and a model judge; refreshed weekly.")
DEFAULTS = {
    "target": 120, "max_size": 150, "explore_frac": 1 / 3,
    "topic_add": 0.45, "topic_drop": 0.30, "explore_max": 0.30,
    "weeks_below_drop": 2, "silent_days": 60, "explore_grace_days": 28, "insight_window_days": 28,
    "max_add": 10, "max_remove": 15, "days_back": 14, "search_pages": 2, "per_topic_candidates": 60,
    "member_follows_min": 3, "removed_cooldown_days": 120, "rejected_cooldown_days": 90, "skip_lists": [AI_LIST],
}
T0 = time.time()
PENDING = []   # candidates collected for an outside judge when the claude CLI is missing


def log(msg):
    print(f"[{time.time() - T0:6.0f}s] {msg}", file=sys.stderr, flush=True)


def utc_date():
    return dt.datetime.now(dt.UTC).date()


def today():
    return utc_date().isoformat()


def days_between(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def pmap(fn, items, workers=6):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


# ── topic models ───────────────────────────────────────────────────────

def build_topics(state, params, auth, enc):
    """Search every topic's terms, fit one model per topic. Returns (models, meta, author_hits{topic: Counter})."""
    specs = topics_mod.topic_specs(topics_mod.fetch_atlas(), state.get("extra_topics", []))
    since = (utc_date() - dt.timedelta(days=params["days_back"])).isoformat()
    jobs = sorted({(t, s.get("lang", "en")) for s in specs for t in s["terms"]}, key=str)
    log(f"{len(specs)} topics, {len(jobs)} search terms since {since}")
    res = pmap(lambda j: bsky.search_posts(j[0], since, auth, params["search_pages"], j[1]), jobs, 4)
    hits = dict(zip(jobs, res))
    neg = [t for t in bsky.discover_posts(1200) if topics_mod.words(t) >= 3]
    log(f"searches done; {len(neg)} Discover posts as background")
    Xdisc = enc.embed(neg)
    pos, X, kept_terms, ah_by = {}, {}, {}, {}
    for s in specs:
        lang = s.get("lang", "en")
        texts, kept, ah = topics_mod.positives(s, {t: hits.get((t, lang), []) for t in s["terms"]})
        pos[s["name"]], kept_terms[s["name"]], ah_by[s["name"]] = texts, kept, ah
        X[s["name"]] = enc.embed(texts) if texts else Xdisc[:0]
    import numpy as np
    models, meta, author_hits = {}, {}, {}
    for s in specs:
        name, texts = s["name"], pos[s["name"]]
        m = None
        if len(texts) >= topics_mod.MIN_POS:
            cross = topics_mod.cross_negatives(name, pos, kept_terms[name])
            Xneg = np.vstack([Xdisc] + [X[o][ix] for o, ix in cross.items() if ix])
            m = topics_mod.fit(X[name], Xneg)
        info = {"label": s["label"], "kind": s["kind"], "terms": kept_terms[name], "n_pos": len(texts)}
        if m is None:
            info["skipped"] = f"only {len(texts)} posts from {len(kept_terms[name])} terms"
        elif m["auc"] < topics_mod.MIN_AUC:
            info.update(auc=round(m["auc"], 3), skipped=f"AUC {m['auc']:.2f}: terms too general")
        else:
            models[name] = m
            author_hits[name] = ah_by[name]
            info.update(auc=round(m["auc"], 3), base=round(m["base"], 3), pos=round(m["pos"], 3))
        meta[name] = info
    log(f"{len(models)} topic models fitted, {len(meta) - len(models)} skipped")
    return models, meta, author_hits, neg


# ── account scoring ────────────────────────────────────────────────────

def score_accounts(dids, models, enc, prune=True, keep_texts=False):
    """Profile, last 100 posts and topic norms for each DID. Returns {did: row}; a missing DID has no profile."""
    dids = list(dict.fromkeys(dids))
    profs = bsky.profiles(dids)
    now = time.time()
    rows = {}
    for did in dids:
        if did not in profs:
            continue                    # the AppView has no such account
        pr = profs[did]
        if pr is None:
            rows[did] = {"did": did, "handle": did, "name": "", "bio": "", "fail": "feed unavailable"}
            continue
        r = {"did": did, "handle": pr.get("handle", did), "name": (pr.get("displayName") or "")[:80],
             "bio": " ".join((pr.get("description") or "").split())[:240], "followers": pr.get("followersCount"),
             "posts_count": pr.get("postsCount") or 0}
        if prune and (vet.BRIDGY.search(r["handle"]) or r["posts_count"] < 20
                      or vet.BOTWORDS.search(f"{r['handle']} {r['name']} {r['bio']}")):
            r["fail"] = "pruned on profile"
        rows[did] = r
    todo = [d for d, r in rows.items() if "fail" not in r]
    log(f"scoring {len(todo)} accounts ({len(dids) - len(rows)} without a profile, "
        f"{len(rows) - len(todo)} pruned on profile)")
    for c in range(0, len(todo), 60):
        chunk = todo[c:c + 60]
        feeds = dict(zip(chunk, pmap(bsky.author_posts, chunk)))
        flat = [(d, p["text"]) for d in chunk for p in (feeds[d] or []) if topics_mod.words(p["text"]) >= 3]
        X = enc.embed([t for _, t in flat]) if flat else None
        idx = defaultdict(list)
        for i, (d, _) in enumerate(flat):
            idx[d].append(i)
        for d in chunk:
            r, posts = rows[d], feeds[d]
            if posts is None:
                r["fail"] = "feed unavailable"
                continue
            r.update(vet.stats(posts, now))
            r["samples"] = vet.samples(d, posts)
            r["scores"] = topics_mod.norm_scores(models, X[idx[d]]) if idx[d] else {}
            r["topic"], r["norm"] = topics_mod.best(r["scores"])
            if keep_texts:
                r["texts"] = [p["text"] for p in posts if p["text"]]
        log(f"  scored {min(c + 60, len(todo))}/{len(todo)}")
    return rows


# ── candidate sources ──────────────────────────────────────────────────

def skip_set(state, params, auth):
    skip = {auth["did"], bsky.resolve(OSKAR)}
    for uri in params["skip_lists"]:
        skip |= set(bsky.list_dids(uri))
    for did, r in state.get("removed", {}).items():
        if days_between(r["date"], today()) < params["removed_cooldown_days"]:
            skip.add(did)
    for did, r in state.get("rejected", {}).items():
        if days_between(r["date"], today()) < params["rejected_cooldown_days"]:
            skip.add(did)
    return skip


def oskar_signals():
    """Oskar's follows, and how often he liked or reposted each author lately (public repo reads)."""
    did = bsky.resolve(OSKAR)
    pds = bsky.pds_of(did)
    fol = set(bsky.follows(did, limit=5000))
    likes, reposts = Counter(), Counter()
    for coll, ctr, n in (("app.bsky.feed.like", likes, 1500), ("app.bsky.feed.repost", reposts, 500)):
        for rec in bsky.repo_records(did, coll, limit=n, pds=pds):
            uri = ((rec.get("value") or {}).get("subject") or {}).get("uri", "")
            if uri.startswith("at://did:") and "/app.bsky.feed.post/" in uri:
                ctr[uri.split("/")[2]] += 1
    return fol, likes, reposts


def member_follows(members, limit=1000):
    counts = Counter()
    for fl in pmap(lambda d: bsky.follows(d, limit), list(members)):
        counts.update(set(fl))
    return counts


def explore_signal(did, fol, likes, reposts, mfol):
    return 3 * (did in fol) + min(5, likes[did]) + 2 * min(3, reposts[did]) + min(10, mfol[did]) / 2


# ── selection ──────────────────────────────────────────────────────────

def topic_order(groups, counts):
    """Round-robin over topics, least-represented first, each topic offering its best remaining candidate.

    groups: {topic: [did, ...]} best first; counts: members already on each topic. Yields (topic, did).
    """
    counts = Counter(counts)
    queues = {t: list(v) for t, v in groups.items() if v}
    while queues:
        for t in sorted(queues, key=lambda t: (counts[t], t)):
            counts[t] += 1
            yield t, queues[t].pop(0)
            if not queues[t]:
                queues.pop(t)


def pick(order, n, rows, explore, verdicts=None, counts=None, cap=None, judge=None):
    """Judge candidates from an ordered stream until n are kept. Returns (kept, rejected) rows.

    With `cap`, a topic that already holds `cap` members (counts plus keeps) takes no more, and its remaining
    candidates are not sent to the judge.
    """
    counts = Counter(counts or {})
    kept, rejected, stream = [], [], iter(order)
    if verdicts is None and judge is None and not vet.available():
        # No judge here: collect three candidates per slot for an outside judge and keep none this run.
        for t, did in ((it if isinstance(it, tuple) else (None, it)) for it in stream):
            if len([r for r in PENDING if r["explore"] == explore]) >= 3 * n:
                break
            if cap is None or counts[t] < cap:
                r = rows[did]
                PENDING.append({k: r.get(k) for k in ("did", "handle", "name", "bio", "followers", "ppd",
                                                      "reply_frac", "topic_label", "samples")} | {"explore": explore})
        return kept, rejected
    while len(kept) < n:
        chunk = []
        for item in stream:
            t, did = item if isinstance(item, tuple) else (None, item)
            if cap is not None and counts[t] >= cap:
                continue
            chunk.append((t, rows[did]))
            if len(chunk) >= max(5, 2 * (n - len(kept))):
                break
        if not chunk:
            break
        batch = [r for _, r in chunk]
        if verdicts is not None:
            vet.apply_verdicts(batch, verdicts)
        else:
            vet.judge(batch, explore=explore, runner=judge)
        for t, r in chunk:
            if r.get("keep") and len(kept) < n and (cap is None or counts[t] < cap):
                kept.append(r)
                counts[t] += 1
            elif r.get("keep") is False:
                rejected.append(r)
        log(f"  judged {len(chunk)} {'exploration' if explore else 'topic'} candidates, kept {len(kept)}/{n}")
    return kept, rejected


def screened(rows, pool):
    out = []
    for did in pool:
        r = rows.get(did)
        if r and "fail" not in r and "n" in r and vet.screen(r["handle"], r["name"], r["bio"], r) is None:
            out.append(did)
    return out


def select_topic(rows, pool, models, meta, n, counts, params, verdicts):
    groups = defaultdict(list)
    for did in screened(rows, pool):
        r = rows[did]
        if r["topic"] in models and r["norm"] is not None and r["norm"] >= params["topic_add"]:
            groups[r["topic"]].append(did)
    for t in groups:
        groups[t].sort(key=lambda d: -rows[d]["norm"])
        for d in groups[t]:
            rows[d]["topic_label"] = meta[t]["label"]
    slots = round(params["target"] * (1 - params["explore_frac"]))
    cap = max(3, math.ceil(1.5 * slots / max(1, len(models))))
    log(f"topic candidates: {sum(map(len, groups.values()))} over {len(groups)} topics; cap {cap} per topic")
    return pick(topic_order(groups, counts), n, rows, False, verdicts, counts, cap)


def select_explore(rows, pool, n, sig, params, verdicts, exclude=()):
    cands = [d for d in screened(rows, pool) if d not in exclude
             and (rows[d]["norm"] is None or rows[d]["norm"] < params["explore_max"])]
    cands.sort(key=lambda d: -sig(d))
    log(f"exploration candidates: {len(cands)}")
    return pick(cands, n, rows, True, verdicts)


# ── themes among exploration members ───────────────────────────────────

def themes(texts_by_member, background, min_members=3, top=12):
    """Terms distinctive for at least `min_members` exploration members, against Discover posts."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = [" ".join(t) for t in texts_by_member.values() if t]
    if len(docs) < min_members:
        return []
    bg = [" ".join(background[i:i + 30]) for i in range(0, len(background), 30)]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_df=0.4,
                          token_pattern=r"(?u)\b[^\W\d_][\w'-]{2,}\b")
    M = vec.fit_transform(docs + bg)[:len(docs)]
    vocab = vec.get_feature_names_out()
    cnt = Counter()
    for i in range(M.shape[0]):
        row = M.getrow(i)
        best = row.indices[row.data.argsort()[::-1][:top]]
        cnt.update(vocab[j] for j in best)
    return [f"{t} ({k})" for t, k in cnt.most_common(15) if k >= min_members]


# ── commands ───────────────────────────────────────────────────────────

def member_entry(r, kind, source):
    return {"handle": r["handle"], "kind": kind, "topic": r.get("topic") if kind == "topic" else None,
            "norm": r.get("norm"), "added": today(), "last_post_days": r.get("last_days"), "weeks_below": 0,
            "source": source, "insights": 0, "why": r.get("why", "")}


def summarize(state, meta):
    ms = state["members"]
    by = Counter(m["topic"] for m in ms.values() if m["kind"] == "topic")
    return {"total": len(ms), "topic": sum(m["kind"] == "topic" for m in ms.values()),
            "explore": sum(m["kind"] == "explore" for m in ms.values()),
            "by_topic": {(meta.get(t) or {}).get("label", t): k for t, k in by.most_common()}}


def memory_text(mode, out):
    def names(rows):
        return ", ".join(f"@{r['handle']}" + (f" ({r['topic_label']})" if r.get("topic_label") else
                                                  f" ({r['reason']})" if r.get("reason") else " (explore)")
                         for r in rows) or "none"
    m = out["members"]
    t = (f"{out['date']} muninn-bsky-list {mode}: list {out['list_url']} now {m['total']} members "
         f"({m['topic']} topic, {m['explore']} exploration). Added {len(out['added'])}: {names(out['added'])}. "
         f"Removed {len(out['removed'])}: {names(out['removed'])}. "
         f"{len(out['topics_fitted'])} topic models fitted; skipped: "
         f"{', '.join(out['topics_skipped']) or 'none'}. Run took {out['seconds']} s.")
    if out.get("themes"):
        t += f" Recurring among exploration members: {', '.join(out['themes'][:8])}."
    return t


def cmd_curate(args, mode):
    import deps
    deps.ensure()
    import ettin

    st = store_mod.Store(args.state_file, VERSION)
    state = st.load()
    params = {**DEFAULTS, **state.get("params", {})}
    if mode == "build" and state.get("list_uri") and not args.dry_run:
        raise SystemExit("the list already exists (" + state["list_uri"] + "); run refresh")
    if mode == "refresh" and not state.get("list_uri"):
        raise SystemExit("no list in the state yet; run build first")
    verdicts = json.loads(Path(args.verdicts).read_text()) if args.verdicts else None
    auth = bsky.session()
    enc = ettin.Ettin()
    models, meta, author_hits, background = build_topics(state, params, auth, enc)
    skip = skip_set(state, params, auth)
    fol, likes, reposts = oskar_signals()
    log(f"Oskar: {len(fol)} follows; {len(likes)} liked and {len(reposts)} reposted authors; skip {len(skip)}")

    members = dict(state.get("members", {}))
    removed = []
    if mode == "refresh":
        live = bsky.own_items(auth, state["list_uri"])
        for did in [d for d in members if d not in live]:
            removed.append({"did": did, "handle": members[did]["handle"], "reason": "removed outside the skill"})
            members.pop(did)
        rows_m = score_accounts(list(live), models, enc, prune=False, keep_texts=True)
        for did in live:
            if did not in members and did in rows_m:
                r = rows_m[did]
                kind = "topic" if (r.get("norm") or -1) >= params["topic_add"] else "explore"
                members[did] = member_entry(r, kind, "added outside the skill")
        removed += evaluate_members(members, rows_m, st, params)
        for r in removed:
            members.pop(r["did"], None)
    else:
        rows_m = {}

    # candidates
    topic_pool = set(fol)
    for ah in author_hits.values():
        topic_pool |= {d for d, k in ah.most_common(params["per_topic_candidates"]) if k >= 2}
    explore_pool = set(fol) | {d for d in set(likes) | set(reposts) if likes[d] + 2 * reposts[d] >= 2}
    mfol = Counter()
    if members:
        mfol = member_follows(members)
        explore_pool |= {d for d, k in mfol.items() if k >= params["member_follows_min"]}
    exclude = skip | set(members) | {r["did"] for r in removed}
    topic_pool -= exclude
    explore_pool -= exclude
    explore_pool = set(sorted(explore_pool, key=lambda d: -explore_signal(d, fol, likes, reposts, mfol))[:600])
    rows = score_accounts(topic_pool | explore_pool, models, enc)

    if mode == "build":
        n_topic = round(params["target"] * (1 - params["explore_frac"]))
        n_explore = params["target"] - n_topic
    else:
        room = params["max_size"] - len(members)
        n_add = max(0, min(params["max_add"], room))
        n_explore = round(n_add * params["explore_frac"])
        share = sum(m["kind"] == "explore" for m in members.values()) / max(1, len(members))
        n_explore += (share < params["explore_frac"] - 0.05) - (share > params["explore_frac"] + 0.05)
        n_explore = max(0, min(n_add, n_explore))
        n_topic = n_add - n_explore
    counts = Counter(m["topic"] for m in members.values() if m["kind"] == "topic")
    topic_new, rej_t = select_topic(rows, topic_pool, models, meta, n_topic, counts, params, verdicts)
    picked = {r["did"] for r in topic_new}

    if mode == "build":
        # exploration also draws on the follows of the members just chosen
        mfol = member_follows(picked)
        extra = {d for d, k in mfol.items() if k >= params["member_follows_min"]} - exclude - set(rows)
        extra = set(sorted(extra, key=lambda d: -mfol[d])[:300])
        log(f"{len(extra)} more exploration candidates from the topic members' follows")
        rows.update(score_accounts(extra, models, enc))
        explore_pool |= extra
    def sig(d):
        return explore_signal(d, fol, likes, reposts, mfol)
    explore_new, rej_e = select_explore(rows, explore_pool, n_explore, sig, params, verdicts, picked)
    if args.dump:
        keys = ("handle", "topic", "norm", "n", "ppd", "last_days", "reply_frac", "fail", "keep", "why")
        Path(args.dump).write_text(json.dumps({d: {k: r.get(k) for k in keys} | {"signal": sig(d)}
                                               for d, r in rows.items()}, ensure_ascii=False))
    for r in rej_t + rej_e:
        state.setdefault("rejected", {})[r["did"]] = {"date": today(), "handle": r["handle"], "why": r.get("why", "")}

    if PENDING:
        path = Path(args.out or "curate.json").resolve().parent / f"pending-judge-{today()}.json"
        path.write_text(json.dumps(PENDING, ensure_ascii=False, indent=1))
        raise vet.JudgeUnavailable(f"the claude CLI is not on PATH; {len(PENDING)} candidates written to {path}. "
                                   "Judge them, then rerun with --verdicts FILE. Nothing was written.")

    # writes
    added = []
    for r in topic_new:
        members[r["did"]] = member_entry(r, "topic", "search" if r["did"] not in fol else "oskar follows")
        added.append(r)
    for r in explore_new:
        src = ("oskar follows" if r["did"] in fol else "oskar likes/reposts" if likes[r["did"]] + reposts[r["did"]]
               else "member follows")
        members[r["did"]] = member_entry(r, "explore", src)
        added.append(r)
    if not args.dry_run:
        if mode == "build":
            state["list_uri"] = bsky.create_list(auth, LIST_NAME, LIST_DESCRIPTION)
            state["list_url"] = f"https://bsky.app/profile/{auth['handle']}/lists/{state['list_uri'].rsplit('/', 1)[1]}"
            state["created"] = today()
            log(f"created {state['list_uri']}")
        if removed:
            bsky.remove_items(auth, state["list_uri"], [r["did"] for r in removed if r["reason"] !=
                                                         "removed outside the skill"])
        bsky.add_items(auth, state["list_uri"], [r["did"] for r in added])
    for r in removed:
        state.setdefault("removed", {})[r["did"]] = {"date": today(), "reason": r["reason"], "handle": r["handle"]}
    state["members"] = members

    exp_texts = {d: rows_m.get(d, rows.get(d, {})).get("texts") or [] for d, m in members.items()
                 if m["kind"] == "explore"}
    out = {"date": today(), "mode": mode + (" (dry run)" if args.dry_run else ""),
           "list_uri": state.get("list_uri"), "list_url": state.get("list_url"),
           "added": [{k: r.get(k) for k in ("handle", "did", "topic", "topic_label", "norm", "why")}
                     | {"kind": members[r["did"]]["kind"]} for r in added],
           "removed": removed, "members": summarize(state, meta),
           "topics_fitted": {t: meta[t] for t in models},
           "topics_skipped": [f"{meta[t]['label']} ({meta[t]['skipped']})" for t in meta if t not in models],
           "themes": themes(exp_texts, background) if mode == "refresh" else [],
           "seconds": round(time.time() - T0)}
    out["memory"] = memory_text(mode, out)
    state.setdefault("runs", []).append({"date": today(), "mode": out["mode"], "added": len(added),
                                         "removed": len(removed), "seconds": out["seconds"],
                                         "topics": {t: meta[t].get("auc") for t in models}})
    state["runs"] = state["runs"][-12:]
    state["topics_last_run"] = {t: {k: v for k, v in meta[t].items()} for t in meta}
    if not args.dry_run:
        try:
            st.save(state)
        except store_mod.StoreError as e:
            backup = Path(args.out or "curate.json").resolve().parent / "muninn-bsky-list-state.backup.json"
            backup.write_text(json.dumps(state))
            out["state_save_error"] = f"{e}; state written to {backup}"
    emit(out, args.out)


def evaluate_members(members, rows, st, params):
    """Apply the weekly drop rules. Mutates weeks_below / norm / topic; returns the removals (capped)."""
    win = params["insight_window_days"]
    since = (utc_date() - dt.timedelta(days=win)).isoformat()
    try:
        ins_rows = st.insights(since)
    except store_mod.StoreError as e:
        log(f"insight query failed ({e}); exploration rule skipped this week")
        ins_rows = None
    counts = store_mod.insight_counts(ins_rows, members) if ins_rows is not None else None
    drops = []
    for did, m in members.items():
        r = rows.get(did)
        if r is None:
            drops.append((0, {"did": did, "handle": m["handle"], "reason": "account gone"}))
            continue
        if r.get("fail") == "feed unavailable":
            continue
        m["handle"] = r["handle"]
        m["last_post_days"] = r.get("last_days")
        m["norm"], best_topic = r.get("norm"), r.get("topic")
        if counts is not None:
            m["insights"] = counts.get(did, 0)
        if r.get("last_days") is not None and r["last_days"] > params["silent_days"]:
            drops.append((1, {"did": did, "handle": m["handle"], "reason": f"silent {r['last_days']:.0f} days"}))
            continue
        if m["kind"] == "topic":
            if m["norm"] is None or m["norm"] < params["topic_drop"]:
                m["weeks_below"] = m.get("weeks_below", 0) + 1
            else:
                m["weeks_below"] = 0
                m["topic"] = best_topic
            if m["weeks_below"] >= params["weeks_below_drop"]:
                drops.append((2 + (m["norm"] or 0), {"did": did, "handle": m["handle"],
                                                     "reason": f"below topic threshold {m['weeks_below']} weeks"}))
        elif counts is not None and days_between(m["added"], today()) >= params["explore_grace_days"] \
                and counts.get(did, 0) == 0:
            drops.append((3, {"did": did, "handle": m["handle"], "reason": f"no insight in {win} days"}))
    drops.sort(key=lambda x: x[0])
    return [d for _, d in drops[:params["max_remove"]]]


def cmd_read(args):
    st = store_mod.Store(args.state_file, VERSION)
    state = st.load()
    if not state.get("list_uri"):
        raise SystemExit("no list in the state yet; run build first")
    since = time.time() - args.days * 86400
    feed = bsky.list_feed(state["list_uri"], since)
    members = state["members"]
    by = defaultdict(list)
    for it in feed:
        p = it["post"]
        did = p["author"]["did"]
        t = bsky.parse_time(p.get("indexedAt"))
        if "reason" in it or did not in members or t is None or t < since:
            continue
        text = ((p.get("record") or {}).get("text") or "").strip()
        if topics_mod.words(text) < 4:
            continue
        eng = p.get("likeCount", 0) + 2 * p.get("repostCount", 0) + p.get("replyCount", 0) + p.get("quoteCount", 0)
        by[did].append({"t": t, "text": text, "eng": eng, "uri": p["uri"],
                        "reply": bool((p.get("record") or {}).get("reply"))})
    picked = []
    for did, ps in by.items():
        ps.sort(key=lambda x: (-(x["eng"] + min(len(x["text"]), 280) / 40 - 3 * x["reply"])))
        picked += [(did, p) for p in ps[:args.per_member]]
    picked.sort(key=lambda x: -(x[1]["eng"] + min(len(x[1]["text"]), 280) / 40))
    picked = picked[:args.max_posts]
    meta = state.get("topics_last_run", {})
    start = dt.datetime.fromtimestamp(since, dt.UTC).date()
    lines = [f"# Muninn reads: {start} to {today()}",
             (f"{len(picked)} posts from {len({d for d, _ in picked})} of {len(members)} members "
              f"({sum(len(v) for v in by.values())} posts in the window)."), ""]
    for did, p in sorted(picked, key=lambda x: (x[0], -x[1]["t"])):
        m = members[did]
        tag = "explore" if m["kind"] == "explore" else (meta.get(m.get("topic")) or {}).get("label", m.get("topic"))
        url = f"https://bsky.app/profile/{did}/post/{p['uri'].rsplit('/', 1)[1]}"
        day = dt.datetime.fromtimestamp(p["t"], dt.UTC).date()
        lines.append(f"- {day} @{m['handle']} ({did}) [{tag}] eng {p['eng']}{' reply' if p['reply'] else ''} {url}")
        lines.append("  " + " ".join(p["text"].split()))
    digest = Path(args.out or f"bsky-list-digest-{today()}.md")
    digest.write_text("\n".join(lines) + "\n")
    silent = [m["handle"] for d, m in members.items() if d not in by]
    emit({"date": today(), "digest": str(digest.resolve()), "posts": len(picked), "members_posting": len(by),
          "members_silent_this_window": len(silent), "seconds": round(time.time() - T0)}, None)


def cmd_status(args):
    state = store_mod.Store(args.state_file, VERSION).load()
    ms = state.get("members", {})
    emit({"list_uri": state.get("list_uri"), "list_url": state.get("list_url"), "created": state.get("created"),
          "members": summarize(state, state.get("topics_last_run", {})),
          "exploration_insights": {m["handle"]: m.get("insights", 0) for m in ms.values() if m["kind"] == "explore"},
          "removed": len(state.get("removed", {})), "extra_topics": state.get("extra_topics", []),
          "runs": state.get("runs", [])[-4:]}, None)


def cmd_add_topic(args):
    st = store_mod.Store(args.state_file, VERSION)
    state = st.load()
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    if len(terms) < 3:
        raise SystemExit("give at least three search terms")
    spec = {"name": "promoted-" + topics_mod.slug(args.name), "label": args.label or args.name, "terms": terms}
    if args.lang:
        spec["lang"] = None if args.lang == "any" else args.lang
    state["extra_topics"] = [t for t in state.get("extra_topics", []) if t["name"] != spec["name"]] + [spec]
    st.save(state)
    emit({"added_topic": spec, "extra_topics": len(state["extra_topics"])}, None)


def cmd_set_param(args):
    st = store_mod.Store(args.state_file, VERSION)
    state = st.load()
    params = state.setdefault("params", {})
    if args.value == "default":
        params.pop(args.name, None)
    else:
        params[args.name] = json.loads(args.value)
    st.save(state)
    emit({"params": {**DEFAULTS, **params}, "overridden": params}, None)


def cmd_restore_state(args):
    state = json.loads(Path(args.file).read_text())
    if not isinstance(state.get("members"), dict) or "list_uri" not in state:
        raise SystemExit(f"{args.file} does not look like a curating-bsky-list state")
    store_mod.Store(args.state_file, VERSION).save(state)
    emit({"restored": args.file, "members": len(state["members"]), "list_uri": state["list_uri"]}, None)


def emit(obj, path):
    text = json.dumps(obj, ensure_ascii=False, indent=1, default=str)
    if path:
        Path(path).write_text(text)
    print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-file", help="use a local JSON file instead of the Muninn config key")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "refresh"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true", help="compute everything, write nothing")
        p.add_argument("--verdicts", help="JSON {did: {keep, why}} from another judge, used instead of Haiku")
        p.add_argument("--out", help="also write the JSON summary here")
        p.add_argument("--dump", help="write every scored candidate (handle, topic, norm, screen, verdict) here")
    p = sub.add_parser("read")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--max-posts", type=int, default=150)
    p.add_argument("--per-member", type=int, default=4)
    p.add_argument("--out", help="digest path (default bsky-list-digest-<date>.md)")
    sub.add_parser("status")
    p = sub.add_parser("add-topic")
    p.add_argument("name")
    p.add_argument("--terms", required=True)
    p.add_argument("--label")
    p.add_argument("--lang", help="language code for the search, or 'any'")
    p = sub.add_parser("set-param", help="override one of DEFAULTS in the state, e.g. topic_drop 0.15")
    p.add_argument("name", choices=sorted(DEFAULTS))
    p.add_argument("value", help="a JSON value (number, list, ...); 'default' removes the override")
    p = sub.add_parser("restore-state", help="write a saved state file (e.g. the backup) to the state key")
    p.add_argument("file")
    args = ap.parse_args(argv)
    try:
        if args.cmd in ("build", "refresh"):
            cmd_curate(args, args.cmd)
        elif args.cmd == "read":
            cmd_read(args)
        elif args.cmd == "status":
            cmd_status(args)
        elif args.cmd == "add-topic":
            cmd_add_topic(args)
        elif args.cmd == "set-param":
            cmd_set_param(args)
        else:
            cmd_restore_state(args)
    except vet.JudgeUnavailable as e:
        emit({"error": str(e)}, None)
        return 3
    except (bsky.BskyError, store_mod.StoreError) as e:
        emit({"error": f"{type(e).__name__}: {e}"}, None)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
