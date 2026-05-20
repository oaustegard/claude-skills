---
name: invoking-antigravity
description: Installs and drives Google's Antigravity CLI (`agy`) as a non-interactive sub-agent — headless OAuth via a pty broker, then `agy -p` for orchestration. Use when orchestrating agy, running Antigravity agents from a script or sandbox, or wanting a Gemini-3-backed peer agent alongside Claude.
metadata:
  version: 0.1.0
---

# Invoking Antigravity

Run Google's **Antigravity CLI** (`agy`) headless and use `agy -p "<task>"`
as an orchestrated sub-agent — a second opinion on Google's agent harness
(Gemini 3.5 Flash) alongside Claude.

`agy` is built for interactive terminal use and gates every call behind a
Google OAuth login with no API-key path. This skill covers the two things
that make it work unattended: driving the login through a pseudo-terminal,
and getting the token to persist without an OS keyring.

## When to use

- Orchestrating `agy` as a sub-agent (shell out, capture stdout, fold back).
- Running Antigravity agents from a script, CI, or a sandboxed container.
- Wanting a Gemini-backed peer agent for a second opinion.

Not needed for interactive local use — there `agy` just opens your browser.

## Install agy (~3 s)

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Clean installer: SHA-512-verified, ~52 MB download, expands to a ~183 MB
Go binary at `~/.local/bin/agy`. Idempotent — no-ops if `agy` exists, and
`agy` self-updates after that. Not on npm (the `antigravity-cli` npm
package is an unrelated squatter).

## Authenticate headless

Two problems block unattended auth; both are solved below.

**1. The prompt blocks.** `agy -p` gives the OAuth prompt a hardcoded 30 s
— too short for a human round trip. The interactive TUI (`agy -i`) has *no*
auth timeout but must be driven through a pty.

**2. Token storage needs a keyring.** `agy` saves the token to the OS
keyring (needs D-Bus). Where D-Bus is absent the write fails silently and
the token is lost. `agy` falls back to a **file** when it thinks it is in
an SSH session — so export fake SSH env vars before launching it:

```bash
export SSH_CONNECTION="203.0.113.1 50000 203.0.113.2 22"
export SSH_CLIENT="203.0.113.1 50000 22"
export SSH_TTY="/dev/pts/0"
```

### Run the broker

`scripts/agy_auth_broker.py` spawns `agy -i` under a pty, answers the
terminal capability queries so the TUI renders, auto-selects "Google
OAuth", scrapes the OAuth URL, and feeds back an authorization code. It
sets the SSH env vars itself.

```bash
python3 scripts/agy_auth_broker.py &           # spawns agy, captures the URL
# wait ~15 s, then:
cat /tmp/agybroker/url                         # → hand this URL to a human
# human opens it, signs in, consents, copies the authorization code:
printf '<code>' > /tmp/agybroker/code          # broker types it into agy
```

On success `agy` writes the token to
`~/.gemini/antigravity-cli/antigravity-oauth-token` and every later
`agy -p` call runs silently.

> **Be prompt.** In an ephemeral/idle-paused container the live `agy`
> process dies if the human dawdles — complete the OAuth dance within a
> few minutes. See [references/auth-internals.md](references/auth-internals.md).

## Orchestrate: `agy -p`

With the token file in place (and SSH env still exported):

```bash
agy --dangerously-skip-permissions -p "<task>"
```

**Flag ordering matters** — `-p` consumes the next argument as the prompt,
so put other flags *before* `-p`. Useful flags: `--add-dir <path>`,
`--print-timeout 10m` (response budget, default 5m), `--conversation <id>`
to resume. `agy` reads `~/.gemini/config/mcp_config.json`, so it can be
handed the same MCP servers as the rest of the fleet.

An orchestrator shells out, captures stdout, and folds the result back —
same shape as `invoking-gemini`, but a full agent harness rather than a
single model call.

## Persist auth across containers

The token file is the durable artifact. The `refresh_token` inside it does
not expire on a schedule; `agy` refreshes the access token itself. To skip
the OAuth dance on a fresh container, save
`~/.gemini/antigravity-cli/antigravity-oauth-token` somewhere safe and
write it back (with the SSH env vars set). Keep it out of git and logs —
it is a personal Google credential. Format and details:
[references/auth-internals.md](references/auth-internals.md).

For fully unattended use with no personal token, a GCP service account
(`GOOGLE_APPLICATION_CREDENTIALS`) is the cleaner path — `agy` references
it, though it is unverified here.

## Troubleshooting

- **`agy -p` keeps asking for auth** — the token file is missing or the
  keyring path was used. Confirm the SSH env vars are exported and
  `~/.gemini/antigravity-cli/antigravity-oauth-token` exists.
- **Broker captures no URL** — check `/tmp/agybroker/status` and
  `/tmp/agybroker/log`; `agy` may not be installed or on `PATH`.
- **Process died mid-auth** — the container idle-paused; relaunch the
  broker and complete the dance faster.
