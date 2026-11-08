---
name: curating-bsky-list
description: Builds and maintains Muninn's own Bluesky curate list ("Muninn reads", on the muninn.austegard.com account). Accounts are chosen by per-topic classifiers on Ettin-17m post embeddings (topics are Muninn's interests and the clusters of Oskar's experiments atlas), plus about a third picked for exploration, outside every topic, and judged only on whether they write thoughtfully. Also turns the list's past week of posts into a digest so Muninn can save dated insights. Use for "build Muninn's list", "refresh Muninn's Bluesky list", "the weekly list refresh", "read Muninn's list", "what did the list post this week", "promote a theme to a topic", or a routine that runs the weekly refresh. Writes only list items on Muninn's own list. Not for Oskar's lists or one-off list building from a source (muninn_utils.bsky_list), and not for general Bluesky search or browsing (browsing-bluesky).
metadata:
  version: 0.1.0
---

# Curating Muninn's Bluesky list

`scripts/curate.py` owns one Bluesky curate list, "Muninn reads", stored in the ATProto repository of Muninn's
account (`muninn.austegard.com`, did:plc:tc43adcqjhjmtnncm723ztvv). It finds accounts, scores them, has Claude
Haiku judge them, writes the list items, and keeps its state (the list's URI and URL, each member's kind, topic,
scores and dates) in Muninn's config key `muninn-bsky-list-state`. Muninn's part is the reading: it saves
insights from the list's posts as memories.

Members are of two kinds. **Topic members** write mostly about one of the topics below. **Exploration members**
(about a third) fit no topic and are kept only while reading them produces saved insights.

## Boundaries

- The script writes nothing to Bluesky except list items on that one list, plus creating the list on the first
  run. `scripts/bsky.py` signs in only with `MUNINN_BSKY_HANDLE` / `MUNINN_BSKY_APP_PASSWORD`, refuses a session
  whose DID is not Muninn's, and refuses a list URI outside Muninn's repository. The environment may also hold
  `BSKY_HANDLE` / `BSKY_APP_PASSWORD`, which are Oskar's; the script never reads them.
- Do not post, reply, like, repost or follow from Muninn's or Oskar's account while using this skill, and do
  not follow list members: the list is how Muninn reads them.
- Candidates already on Oskar's list "Artificial (and real) Intelligence" are skipped, so the two lists do not
  duplicate each other. Bridgy mirrors of Mastodon accounts (`*.ap.brid.gy`) are skipped too.

## Requirements

Python 3.10+ and pip, nothing else preinstalled: `numpy`, `onnxruntime`, `tokenizers` and `scikit-learn` are
pip-installed on first use, and the Ettin-17m embedding model (13 MB) is downloaded to
`~/.cache/curating-bsky-list/ettin/` on first use.

| needs | for |
|---|---|
| `MUNINN_BSKY_HANDLE`, `MUNINN_BSKY_APP_PASSWORD` | post search (Bluesky answers it only when signed in) and the list writes |
| `TURSO_URL`, `TURSO_TOKEN` | the state key, and the insight memories that decide whether exploration members stay |
| `claude` CLI on PATH | the Haiku judge, `claude -p --model haiku` (without it, see "Judge fallback") |
| egress | `bsky.social`, `public.api.bsky.app`, `*.host.bsky.network` (Muninn's and Oskar's account hosts; Muninn's is `stropharia.us-west.host.bsky.network`), `plc.directory`, `raw.githubusercontent.com`, the Turso host, `pypi.org` and `files.pythonhosted.org` |

`--state-file PATH` keeps the state in a local JSON file instead of Turso. Insight memories are then unreadable,
so the exploration drop rule is skipped rather than applied to zero insights.

## Commands

Each prints one JSON object on stdout and logs progress to stderr. Global options (`--state-file`) go before
the command name.

```bash
S=<skill dir>/scripts
python3 $S/curate.py build   [--dry-run] [--out build.json]    # first run: create the list, fill it to 120 members
python3 $S/curate.py refresh [--dry-run] [--out refresh.json]  # weekly
python3 $S/curate.py read    [--days 7] [--out digest.md]      # also writes the digest (markdown) to --out
python3 $S/curate.py status                                    # list URL, member split, recent runs
python3 $S/curate.py add-topic "river ecology" --terms "salmon run,watershed,river restoration" [--lang any]
python3 $S/curate.py set-param topic_drop 0.15                 # override a threshold; 'default' clears it
python3 $S/curate.py restore-state muninn-bsky-list-state.backup.json
```

`--dry-run` computes everything and writes nothing, to Bluesky or to the state. `build` refuses to run when the
state already holds a list. `add-topic --lang` takes a language code for the search; the default is English,
and `any` searches every language. `build` and `refresh` also take `--verdicts FILE` (see "Judge fallback") and
`--dump FILE` (every scored candidate, for tuning). A `build` or `refresh` takes about 10 to 15 minutes, most of
it searching about 170 terms and fetching and embedding up to 100 posts from each of about 1,000 candidates.

## The weekly routine

1. Run `refresh --out refresh.json`. Exit 0 is success. Exit 3 means the judge is missing: follow "Judge
   fallback". Any other exit: report the `error` field and stop.
2. Store the refresh's `memory` field verbatim with Muninn's `remember` tool: type `experience`, tags
   `muninn-bsky-list`, `bsky-list-refresh` and the date as YYYY-MM-DD. The script cannot write memories, so this
   is the only record of the week's changes outside the state key.
3. Run `read --out digest.md` and read the digest. Each line carries the date, `@handle`, the member's DID, its
   topic or `explore`, an engagement count and the post URL, followed by the post text.
4. Save two to five insights, each its own `remember` call: type `world` for a fact about the world, `analysis`
   for an argument or interpretation; tags `bsky-list-insight`, `muninn-bsky-list` and the date. Write each as
   `YYYY-MM-DD bsky-list insight from @handle (did:plc:…): <what was learned, in one to three sentences>. <post URL>`.
   Next week's refresh counts an exploration member's insights by looking for its DID (or, failing that, its
   current handle) in live memories tagged `bsky-list-insight`. Handles change; DIDs do not, so include the DID.
5. The refresh output's `themes` lists words and phrases that stand out in the posts of three or more
   exploration members, compared with Discover posts. When one names a subject worth following, promote it with
   `add-topic NAME --terms "…"` (three or more search phrases). From the next run it is a topic like the others,
   with its own classifier and share of slots. A promoted topic lives in the state's `extra_topics`; remove it
   by editing the state and running `restore-state`.

## Selection pipeline

**Topics.** Nine of Muninn's interests (copied into `assets/topics.json` from its profile key
`intellectual_interests`; edit the file when the profile changes) and one topic per cluster of Oskar's
experiments atlas (`oaustegard/experiments` `experiments-atlas/data.json`, 12 clusters, fetched fresh each run).
A cluster's search terms are the seeds in `assets/topics.json` followed by words extracted from its experiments'
one-line purposes and directory names: words in at least two of its experiments and rare in other clusters.

**Classifiers.** Each topic gets a logistic regression on Ettin-17m post embeddings, refitted every run.
Positive examples are posts from the last 14 days that contain one of the topic's terms (Bluesky post search; at
most 1,500, at most 25 per author; terms with fewer than 15 hits are dropped). Negative examples are about 1,200
posts from Bluesky's Discover feed plus up to 150 search hits from each other topic (minus any that contain this
topic's own terms); with Discover alone, anyone who writes in sentences scored as on-topic. A topic with fewer
than 80 positive posts or a held-out AUC below 0.80 sits out that run.

**Scores.** An account's share on a topic is the mean classifier probability over its last 100 posts. Shares
are normalised per topic as `(share − mean on held-out Discover posts) / (mean on held-out term posts − mean on
Discover)`, so 0 reads like Discover and 1 like the topic's search hits. An account's topic is the one with the
highest normalised score, called its norm below.

**Topic members.** Norm at least 0.45. Topics take turns, least represented first, and no topic takes more than
`ceil(1.5 × topic slots / number of topics)` members, where topic slots are two thirds of the 120-member
target; this keeps AI and embeddings from taking over the list.

**Exploration members.** Norm below 0.30 on every topic, drawn from Oskar's follows, the authors of his last 1,500 likes and
500 reposts (read from his public repository), and accounts followed by three or more current members. They are
ranked by a sum: 3 for an Oskar follow, up to 5 for likes, up to 6 for reposts, up to 5 for member follows.

**Screen and judge.** A candidate needs at least 10 posts, at most 40 a day, a post in the last 30 days and no
bot or feed words in handle, name or bio. Claude Haiku then judges batches of 25 from bio, posting stats and six
sample posts. Topic candidates must be individuals writing substantively on their topic; exploration candidates
must be individuals writing thoughtfully in their own voice. Organisations, feeds, marketers and AI personas are
rejected either way. A batch whose reply cannot be parsed twice is left unjudged, and those accounts come up
again next run. Rejected accounts are skipped for 90 days, removed members for 120.

**Weekly rules.** A refresh drops a member with no post in 60 days, a topic member whose norm is below 0.30 two
weeks running, and an exploration member at least 28 days on the list with no insight saved in the last 28
days, at most 15 removals a week. It then adds up to 10, about a third exploration, never above 150 members.

The thresholds are `DEFAULTS` in `curate.py`: `target` 120, `max_size` 150, `explore_frac` 1/3, `topic_add`
0.45, `topic_drop` 0.30, `explore_max` 0.30, `weeks_below_drop` 2, `silent_days` 60, `explore_grace_days` 28,
`insight_window_days` 28, `max_add` 10, `max_remove` 15. `set-param` overrides one in the state.

The classifier recipe follows List Scout (oaustegard.github.io `bsky/list-scout/topic.js`); the screen and judge
follow `oaustegard/experiments` `bsky-list-ai-share/vet.py`.

## Judge fallback

Without the `claude` CLI, `build` and `refresh` exit 3, write nothing, and save the candidates (handle, bio,
stats, sample posts, topic or exploration) to `pending-judge-<date>.json` beside `--out`. Judge each one another
way, for instance with Muninn's `decide` tool and one yes/no question per account, write
`{did: {"keep": 0 or 1, "why": "…"}}` to a file, and rerun with `--verdicts FILE`. Accounts missing from the
file are left unjudged.

## Failure signals

| signal | meaning |
|---|---|
| `topics_skipped` lists most topics | post search failed: check the `MUNINN_BSKY_*` sign-in and egress to Muninn's account host |
| an interest topic skipped for AUC | its terms are too general; edit `assets/topics.json` |
| `state_save_error` | Turso refused the write and the state went to `muninn-bsky-list-state.backup.json` beside `--out`. Run `restore-state` on it before the next refresh |
| a refresh removing many members | this week's classifiers misfit; the cap stops it at 15. Check `topics_fitted` AUCs before `set-param topic_drop` |
| `members_silent_this_window` near the member count in `read` | Bluesky's list feed lagged or failed; rerun `read` |

## Verification

From the skill directory: `python3 -m pytest -q tests` (offline). After a live run, `status` prints the list URL
and the member split.
