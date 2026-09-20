---
name: muninn-boot
metadata:
  version: 2.0.1
  source: https://github.com/oaustegard/muninn-utilities/tree/main/muninn-boot
description: 'Puts oaustegard/muninn-utilities on the container Python path — runs scripts/boot.sh, which shallow-clones the repo (codeload tarball as fallback) and writes the .pth. The boot payload itself comes from the Muninn MCP connector: call its `boot` tool after this script. Trigger on the first message of any new Muninn conversation, or when the user says "boot up" / "boot" — unless the message contains "skip boot". Idempotent: a warm container exits in ~0s via a sentinel.'
---

# Muninn Boot

Two steps, in this order:

```bash
bash "$(dirname "$(find / -name boot.sh -path '*muninn-boot*' 2>/dev/null | head -1)")/boot.sh"
```

then call the Muninn MCP `boot` tool. The script fetches code; the tool
delivers identity, ops, recent memories and reminders. Memory reads and writes
go through the connector's `recall` / `remember` / `forget` / `muninn_config`
tools, so the container holds no Turso credential and this skill reads no
`Turso.env`. Direction in memory ce3b8b75, the plan in 69f3301c.

Prior to 2.0.0 this skill sideloaded claude-skills and ran the Python `boot()`
itself. Marketplace sync now places claude-skills in every session
(`/root/.claude/skills/synced/<id>/` in Cowork, `/mnt/skills/user` on
Claude.ai), and the worker runs boot. "skinny boot" (`BOOT_MODE=perch`) has no
effect until the worker's `boot` takes a mode.

## MCP boot parts

The `boot` tool's payload is larger than the harness output cap, so it comes
in parts. Call `boot` with no arguments; its footer says whether the payload is
complete or names the next part (`boot({part: 2})`, then 3, and so on). Call
every part the footer names before replying. The harness may persist a part to
a file instead of showing it ("Output too large ... saved to ..."); read that
file in full. A part that was persisted has already been delivered, so never
call `boot` again with the same `part` to recover it.

## boot.sh steps

Check `metadata.version` at the top of this file right before running. Below
2.0.0 the on-disk script is the old one that sideloads claude-skills and runs
the Python `boot()` itself; marketplace sync can replace the copy mid-session,
so a session may run 1.x once and 2.x next.

1. Warm-path check: sentinel `/home/claude/.muninn-booted` present and
   `/home/claude/muninn-utilities/muninn_utils` exists → exit 0.
2. Source `$MUNINN_PROJECT_DIR/GitHub.env` (default `/mnt/project`) if present.
   Transitional — it goes once GitHub write tools exist on the worker. The
   container presets `GH_TOKEN=proxy-injected`, a truthy placeholder; without
   the file, GitHub API calls from the container 401 and the script says so.
   Memory tools are unaffected.
3. `git clone --depth 1` `oaustegard/muninn-utilities` at `MUNINN_UTILS_REF`
   (default `main`; branch, tag or full SHA) → `/home/claude/muninn-utilities`.
   Measured 1.3s cold in Cowork. Fallback where the git proxy refuses
   github.com: the codeload tarball, which works on Claude.ai and is 403 in
   Cowork (there git works). If both fail the script exits 1.
4. Write `muninn-remembering.pth` at a site-packages directory resolved from
   `sys.path` at runtime (`/root/.local/lib/python3.11/site-packages` in
   Cowork, measured 2026-09-19) listing the repo, `remembering/`, `$HOME`, and
   every skill `scripts/` directory found under either skills root.
5. Write the sentinel, print a four-line footer: transport and commit, pth
   path, and the reminder to call the MCP `boot` tool.

## GitHub.env in Cowork

Only `GitHub.env` matters now, and only for GitHub API work from the container.
`project_read` it and write it to `/mnt/project/GitHub.env` with the Write tool
(a bash heredoc carrying a secret trips the permission classifier), or skip it
when the task touches no GitHub API.

## Pinning

`MUNINN_UTILS_REF` defaults to `main`; the point of cloning is that changes land
on the next cold boot with no version bump. Pass a SHA to test an unmerged
state. `rm /home/claude/.muninn-booted` forces a re-pull in a warm container.

This file and `boot.sh` are the one thing that cannot self-update: the running
copy is whatever the session mounted (project upload or marketplace sync), so
a change here needs a push to both `muninn-utilities/muninn-boot` and the
`claude-skills/muninn-boot` mirror, with `metadata.version` bumped.
