# delegating-with-context

Delegate by writing only the task. A PreToolUse hook reads the session
transcript, asks Jev (TypeSafe) which chunks the task needs, and appends them
to the subagent's prompt. See `SKILL.md` for the procedure and the hook entry,
and `oaustegard/experiments/subagent-context-filter` for the eval.

Needs a Jev transport: `CF_ACCOUNT_ID` + `CF_API_TOKEN` (+ `CF_GATEWAY_ID`) for
the Cloudflare AI Gateway with a stored TypeSafe key, or `TYPESAFE_API_KEY`.
