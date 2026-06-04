# querying-markdown - Changelog

All notable changes to the `querying-markdown` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-06-04

### Other

- querying-markdown v0.2.0: use-gate + empirical findings (#687)

## [0.2.0] - 2026-06-04

### Added

- Use-gate decision table ("Before you use mq: is this actually a structural task?") routing line-prefix/substring work to grep/awk and code-structure to tree-sitting, reserving mq for language-filtered code blocks, structured links, and valid-Markdown transforms.
- "Empirical findings" section: parse-bound performance (latency tracks document size, not selector/match count; ~1.3 MB/s), selectors-return-nodes-not-concepts, and the ambiguous-empty-result trap.

### Notes

- Findings measured against a full KJV smoke test. The cheatsheet's `.code("lang") | to_text()` idiom is correct (an earlier "bug" report was a `dash` `time: not found` error misread as empty output).

## [0.1.0] - 2026-06-04

### Other

- Add querying-markdown skill (mq, jq-for-Markdown) (#686)