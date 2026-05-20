# Antigravity CLI — auth internals

Detail behind the headless-auth flow in SKILL.md. `agy` is v1.0.0
(released at I/O 2026); behaviour below was verified empirically.

## Install notes

`curl -fsSL https://antigravity.google/cli/install.sh | bash` is a clean
installer: it fetches a per-platform manifest, downloads a ~52 MB tarball,
**verifies a SHA-512 checksum**, and expands a ~183 MB Go binary to
`~/.local/bin/agy`. It is idempotent, takes ~3 s, and `agy` self-updates
afterward. Distribution is install-script only — the `antigravity-cli`
package on npm is an unrelated squatter; ignore it.

## The 30-second print-mode timeout

`agy -p` (print mode), with no stored token, prints the
`accounts.google.com` OAuth URL and waits **30 seconds** for a pasted
authorization code, then aborts. The 30 s is hardcoded in
`printmode.waitForAuth`; `--print-timeout` governs the *response* wait
(default 5m), not the auth wait. There is no flag to extend it.

`agy -i` (interactive TUI) has **no auth timeout** — it waits
indefinitely. That is why the broker drives `-i`, not `-p`.

## Driving the TUI

The TUI queries the terminal for capabilities (DECRQM for modes 2026/2027,
primary device attributes, cursor position) and will not render until the
terminal answers. A plain pipe never answers, so the TUI hangs. The broker
runs `agy -i` under a real pty and writes back synthetic replies
(`capability_replies()` in `scripts/agy_auth_broker.py`), after which the
TUI renders normally: a login menu, then the OAuth URL, then an
authorization-code input field.

The login menu offers "1. Google OAuth" and "2. Use a Google Cloud
project". The broker auto-selects option 1.

## Token storage: keyring vs file

`agy` defaults to OS-keyring token storage, which on Linux needs D-Bus
(`dbus-launch`). Where D-Bus is absent the keyring write fails silently:

```
keyringAuth: failed to persist token to keyring:
  exec: "dbus-launch": executable file not found in $PATH
consumerOAuth: authentication completed successfully
```

Auth *succeeds* but the token is never persisted — it dies with the
process. `agy` switches to **file-based storage when it detects an SSH
session** (logs `Using file-based token storage because SSH session
detected`). Exporting `SSH_CONNECTION` / `SSH_CLIENT` / `SSH_TTY` triggers
that path. The broker sets them on the `agy` child automatically; export
them yourself before any later `agy -p` call too.

## The token file

Path: `~/.gemini/antigravity-cli/antigravity-oauth-token`. JSON:

```json
{
  "token": {
    "access_token": "ya29....",
    "token_type": "Bearer",
    "refresh_token": "1//04....",
    "expiry": "2026-05-20T17:19:27.000000000Z"
  },
  "auth_method": "consumer"
}
```

The `refresh_token` is the durable credential — `agy` refreshes the access
token from it automatically. To reuse auth on a fresh container, write this
file back (with SSH env set) instead of re-running the OAuth dance. A stale
`access_token`/`expiry` is fine; `agy` refreshes on use.

OAuth scopes requested: `cloud-platform`, `userinfo.email`,
`userinfo.profile`, `cclog`, `experimentsandconfigs`, `openid`. The request
uses `access_type=offline` so a refresh token is issued.

## Ephemeral containers

Cloud sandboxes (e.g. Claude Code on the Web) pause on session inactivity;
a pause kills the live `agy` process the broker is holding. The OAuth dance
must finish before that — in practice within a few minutes. If the process
dies mid-auth the authorization code is bound (via PKCE) to the dead
process and cannot be reused; relaunch the broker for a fresh URL.

The robust pattern is therefore: authenticate once, **save the token
file**, and re-plant it on each fresh container.

## State layout

`agy` reuses the Gemini CLI config tree:

```
~/.gemini/config/mcp_config.json                   # shared MCP server config
~/.gemini/config/projects/<uuid>.json               # per-project metadata
~/.gemini/antigravity-cli/antigravity-oauth-token    # the credential
~/.gemini/antigravity-cli/conversations/             # history (--conversation)
~/.gemini/antigravity-cli/{brain,knowledge}/
```

`agy` also drops a `.antigravitycli/` symlink dir in the working repo —
gitignore it.

## Network

| Host | Phase |
|---|---|
| `antigravity.google`, `antigravity-cli-auto-updater-*.run.app` | install, self-update |
| `storage.googleapis.com` | install payload |
| `accounts.google.com`, `oauth2.googleapis.com` | OAuth |
| `www.googleapis.com` | userinfo |
| `cloudcode-pa.googleapis.com` | runtime agent calls |

## Provisioning options, worst to best

1. **Broker per container** — `agy_auth_broker.py` + one prompt human
   OAuth dance. Repeats on every fresh container.
2. **Persist the token file** — dance once, save
   `antigravity-oauth-token`, re-plant on boot. No further dances; ships a
   personal credential, so keep it out of git and logs.
3. **GCP service account (ADC)** — the binary references
   `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_CLOUD_PROJECT`; the
   `cloud-platform` scope and enterprise "connect your GCP project" path
   imply a fully non-interactive option. Unverified, but the correct
   answer for unattended orchestration — no keyring, no personal token.

## Troubleshooting

- **`agy -p` keeps prompting for auth** — the token file is missing, or
  `agy` used the keyring path. Confirm the SSH env vars are exported in the
  current shell and `~/.gemini/antigravity-cli/antigravity-oauth-token`
  exists.
- **Broker captures no URL** — inspect `/tmp/agybroker/status` and
  `/tmp/agybroker/log`; usually `agy` is not installed or not on `PATH`.
- **Process died mid-auth** — the container idle-paused; relaunch the
  broker for a fresh URL and complete the login faster.
