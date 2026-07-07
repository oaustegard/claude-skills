---
name: invoking-antigravity
description: Install and drive Google's Antigravity CLI (`agy`) as a non-interactive sub-agent. Use when orchestrating agy, running Antigravity agents from a script or sandbox, delegating a task to Google's agent harness, or wanting a Gemini-backed peer agent alongside Claude.
metadata:
  version: 0.1.1
---

# Invoking Antigravity

Run Google's Antigravity CLI (`agy`) headless, then call `agy -p "<task>"`
as an orchestrated sub-agent on Google's harness (Gemini 3.5 Flash).

Install, authenticate once, orchestrate. For the *why* behind any step —
the 30 s timeout, the keyring fallback, the token format, network hosts,
troubleshooting — read [references/auth-internals.md](references/auth-internals.md).

## When to use

- Orchestrating `agy` as a sub-agent: shell out, capture stdout, fold back.
- Running Antigravity agents from a script, CI, or sandboxed container.
- Wanting a second opinion from Google's harness alongside Claude.

For interactive local use, skip this — run `agy` directly and it opens a browser.

## 1. Install

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Idempotent, ~3 s, installs `~/.local/bin/agy`.

## 2. Authenticate — once, human-in-the-loop

Export these in every shell that runs `agy`, so it stores the token in a
file rather than an OS keyring:

```bash
export SSH_CONNECTION="203.0.113.1 50000 203.0.113.2 22"
export SSH_CLIENT="203.0.113.1 50000 22"
export SSH_TTY="/dev/pts/0"
```

Run the broker, then relay the login to a human:

```bash
python3 scripts/agy_auth_broker.py &      # spawns agy, captures the OAuth URL
sleep 15 && cat /tmp/agybroker/url         # a human opens this and consents
printf '<code>' > /tmp/agybroker/code      # paste the authorization code back
```

`agy` writes the token to `~/.gemini/antigravity-cli/antigravity-oauth-token`;
later `agy -p` calls run silently. Complete the login within a few minutes —
an idle container pause kills the broker's `agy` process.

## 3. Orchestrate

```bash
agy --dangerously-skip-permissions -p "<task>"
```

Place every flag before `-p` — it treats the next argument as the prompt.
Add `--add-dir <path>`, `--print-timeout 10m`, or `--conversation <id>` as
the task needs.

## Reuse auth on a fresh container

Save `~/.gemini/antigravity-cli/antigravity-oauth-token` and write it back
(with the SSH vars set) — its `refresh_token` is durable, so no repeat
OAuth. Keep the file out of git and logs; it is a personal Google credential.
