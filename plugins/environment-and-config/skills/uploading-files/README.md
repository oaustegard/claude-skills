# uploading-files

File-upload bridge for Claude Code on the Web. CCotw has no native file mount; this skill creates a throwaway GitHub branch the user can drop files onto via the github.com web UI, then fetches them locally on the next turn. Use when the user wants to upload, share, or send files into the session, or when a task clearly needs files the user has on disk that aren't in the repo.
