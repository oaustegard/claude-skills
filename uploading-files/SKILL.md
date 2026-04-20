---
name: uploading-files
description: File-upload bridge for Claude Code on the Web. CCotw has no native file mount; this skill creates a throwaway GitHub branch the user can drop files onto via the github.com web UI, then fetches them locally on the next turn. Use when the user wants to upload, share, or send files into the session, or when a task clearly needs files the user has on disk that aren't in the repo.
metadata:
  version: 0.1.0
---

# Uploading Files

Claude Code on the Web has no file-upload widget and no shared mount. Whenever the user needs to get a file (image, PDF, CSV, doc, archive, anything) into the session, route them through a temporary GitHub branch on the working repo's `origin` remote.

## When to use

Trigger this skill when:

- The user asks to upload, attach, share, or send a file
- A task clearly needs a file the user has locally that isn't in the repo (e.g. "summarize this PDF", "the spreadsheet I exported", "the screenshot from earlier")
- You're about to ask the user to paste a long binary or large text blob — offer upload instead

Don't trigger when the file is already in the repo, on a public URL you can fetch, or short enough to paste inline.

## Workflow

The script lives at `/mnt/skills/user/uploading-files/scripts/upload.py` once installed. It must be run from inside the working git repo (it uses `origin` and `cwd`).

### Step 1 — Create the upload branch

```bash
python3 /mnt/skills/user/uploading-files/scripts/upload.py init
```

This creates `upload-<short-session-id>` on origin (from the default branch) and prints a GitHub upload URL. **Show that URL to the user verbatim** and tell them:

> Open that link, drag the file(s) into the page, scroll to the bottom and click **Commit changes** (the default options are fine). Reply here when done.

Then stop and wait for the user. Do not pretend they've uploaded.

### Step 2 — Fetch files

After the user confirms the upload:

```bash
python3 /mnt/skills/user/uploading-files/scripts/upload.py fetch
```

This downloads everything on the branch (vs default) into `./.uploads/` (filenames are flattened to basenames) and ensures `.uploads/` is in `.gitignore`. Treat the files in `.uploads/` like any other local input.

If the script reports "No files on branch yet", the user probably forgot to click commit. Ask them to refresh the upload page and verify they committed, then re-run `fetch`.

### Step 3 — Cleanup

When the uploaded files are no longer needed — typically after the work is done and anything worth keeping has been moved into the repo proper, **and before opening a PR** — delete the remote branch:

```bash
python3 /mnt/skills/user/uploading-files/scripts/upload.py cleanup
```

Local files in `./.uploads/` are kept (they're gitignored). If the user might want them again, leave them; otherwise `rm -rf .uploads` after cleanup.

### Optional — status

```bash
python3 /mnt/skills/user/uploading-files/scripts/upload.py status
```

Prints the repo, branch name, whether the branch exists on origin, and the upload URL. Useful when you've context-switched and want to recover the URL without recreating the branch.

## How it works

- **Branch name** — `upload-<short>` where `<short>` is the first hyphen-segment of `$CLAUDE_SESSION_ID`, or of the most recent transcript filename under `~/.claude/projects/<encoded-cwd>/`, or a UTC timestamp `tsYYYYMMDD-HHMMSS` as fallback. The same session always resolves to the same branch, so re-running `init` is idempotent.
- **Repo** — parsed from `git remote get-url origin`. Must be a github.com remote.
- **Auth** — uses `$GH_TOKEN` (then `$GITHUB_TOKEN`, `$GITHUB_PAT`, `$GH_PAT`). Token needs `Contents: write` on the working repo.
- **Network calls** — only `api.github.com` and `raw.githubusercontent.com`.

## Constraints

- GitHub web upload caps at **25 MB per file**. Larger files won't work via this flow.
- Filenames are flattened to basenames in `.uploads/`. If the user uploads two files with the same name in different subdirs, the second overwrites the first. Tell them to rename first if it matters.
- Binary files survive the round-trip fine (raw download, byte-exact).
- The skill does not read the upload branch's history beyond "what's there now vs default". If the user pushes multiple commits, you get the union of files.

## Anti-patterns

- Don't ask the user to paste binary content (base64, hex dumps). Use this skill.
- Don't create the branch and immediately try to fetch — the user has to upload first.
- Don't leave the upload branch around after a PR is opened. It clutters the repo's branch list.
- Don't commit anything in `.uploads/` to the working repo. If a file should be persisted, copy it to a proper location first (and `git add` from there).
