# Memory

The remembering skill provides persistent memory across sessions via a Turso/libSQL database with two tables: memories and config. It is the most complex skill in the collection, with 11 script modules and deep integration into the boot sequence.

## Core Operations

The primary API: [[remembering/scripts/memory.py#remember]] and [[remembering/scripts/memory.py#recall]].

`remember()` generates a UUID, computes an FTS5-compatible summary, writes to Turso, and returns the memory ID. `recall()` combines BM25 full-text search with tag filtering, type filtering, and confidence thresholds to produce ranked results.

Supporting operations include [[remembering/scripts/memory.py#supersede]] for replacing memories while preserving provenance, [[remembering/scripts/memory.py#forget]] for deletion, and [[remembering/scripts/memory.py#strengthen]] / [[remembering/scripts/memory.py#weaken]] for priority adjustment.

## Batch Operations

[[remembering/scripts/memory.py#recall_batch]] runs multiple queries in a single call, deduplicating results across queries. [[remembering/scripts/memory.py#remember_batch]] stores multiple memories atomically. Both exist to reduce round-trip latency when the calling agent needs several operations.

## Temporal Queries

[[remembering/scripts/memory.py#recall_since]] and [[remembering/scripts/memory.py#recall_between]] enable time-windowed retrieval using the `valid_from` field. These power workflows like "what did we discuss last week" without requiring full-text search.

## Background Writes

[[remembering/scripts/memory.py#remember_bg]] uses [[remembering/scripts/memory.py#flush]] to queue writes on a background thread. This prevents memory storage from blocking the main conversation flow. The atexit handler ensures pending writes complete before the process exits.

## Result Wrapping

[[remembering/scripts/result.py#MemoryResult]] provides attribute-style access to memory dictionaries with field validation.

It generates helpful error messages when accessing deprecated or renamed fields. [[remembering/scripts/result.py#wrap_results]] converts raw SQL rows into `MemoryResult` lists. This layer catches common mistakes like accessing `.content` (deprecated) instead of `.summary`.

## Consolidation & Curation

[[remembering/scripts/memory.py#consolidate]] clusters related memories by tags and merges them.

[[remembering/scripts/memory.py#curate]] is the autonomous maintenance function — it identifies stale memories, low-priority candidates for pruning, and consolidation opportunities. Both support `dry_run` mode for review before action.

## Decision Traces

[[remembering/scripts/memory.py#decision_trace]] captures structured decision records with choice, context, rationale, alternatives, and tradeoffs. Stored as type="decision" memories with refs linking to related context.

## Boot Sequence

[[remembering/scripts/boot.py#boot]] orchestrates full startup: config loading, cache population, and context injection.

It loads config entries (profile and ops), populates a cache for fast in-session recall, detects GitHub access, loads due reminders, and formats everything for context injection. The `mode` parameter supports "perch" for autonomous exploration.

Config entries are grouped by [[remembering/scripts/boot.py#classify_ops_key]] which assigns topic categories, then organized by [[remembering/scripts/boot.py#group_ops_by_topic]] for readable boot output.

## Config System

[[remembering/scripts/config.py#config_get]] and [[remembering/scripts/config.py#config_set]] manage the config table — key-value pairs loaded at boot.

The config table stores operational knowledge (procedures, settings, reference data) while the memories table stores searchable knowledge. [[remembering/scripts/config.py#config_set_boot_load]] controls which entries appear in boot output.

## Session Continuity

[[remembering/scripts/boot.py#session_save]] and [[remembering/scripts/boot.py#session_resume]] persist conversation state across sessions. [[remembering/scripts/boot.py#sessions]] lists recent sessions with optional counts. Sessions use the session_id managed by [[remembering/scripts/state.py#get_session_id]] and [[remembering/scripts/state.py#set_session_id]].

## Journal

[[remembering/scripts/boot.py#journal]] writes timestamped entries to the config table under the "journal" category. [[remembering/scripts/boot.py#journal_recent]] retrieves recent entries. [[remembering/scripts/boot.py#journal_prune]] caps the journal at a configurable size.

## Therapy & Self-Improvement

[[remembering/scripts/boot.py#therapy_scope]] generates statistics about memory health. [[remembering/scripts/boot.py#therapy_reflect]] runs automated reflection — sampling memories, finding duplicates via similarity, and suggesting consolidation. [[remembering/scripts/boot.py#therapy_session_count]] tracks therapy frequency.

## Task Discipline

[[remembering/scripts/task.py#Task]] enforces structured workflow: declare steps, mark done, gate completion.

The [[remembering/scripts/task.py#task]] factory creates tasks with auto-added "store" requirements. [[remembering/scripts/task.py#Task#complete]] refuses to close unless all required steps (including storage) are finished. [[remembering/scripts/task.py#task_resume]] and [[remembering/scripts/task.py#incomplete_tasks]] support resuming interrupted work.

## Recall Hints

[[remembering/scripts/hints.py#recall_hints]] scans conversation context for terms that match known recall triggers — proper nouns, project names, topic keywords. Returns suggestions for what to recall before responding, implementing the recall-discipline ops pattern.

## Schema & Database

[[remembering/scripts/bootstrap.py#create_tables]] defines the two-table schema. [[remembering/scripts/bootstrap.py#migrate_schema]] handles version upgrades. [[remembering/scripts/bootstrap.py#seed_config]] populates default config entries. [[remembering/scripts/bootstrap.py#verify]] validates the schema is correct.

The database layer in [[remembering/scripts/turso.py]] handles HTTP communication with the Turso cloud database, including retry logic and connection management.

## Utility Installation

[[remembering/scripts/utilities.py#install_utilities]] materializes muninn_utils modules from utility-code memories. These are Python modules stored as memories that get written to disk at boot time, providing runtime capabilities like blog publishing, Strava access, and therapy helpers.
