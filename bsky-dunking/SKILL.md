---
name: bsky-dunking
description: Render a Bluesky post as an anonymised screenshot so it can be criticised without pointing a crowd at its author. Fetches through the public unauthenticated API, blacks out avatar, display name, handle and any @mentions in declassified-document styling, and emits a PNG plus alt text. Use when asked to dunk anonymously, quote a post without linking it, screenshot a post with the author hidden, or redact a post before sharing it.
metadata:
  version: 0.1.0
---

# Anonymous dunk-quoting

A quote-post carries the whole audience to the original author. For an account
with 40 followers that is a pile-on, whatever the quote said. This renders the
post as an image instead, so the words can be quoted without the handle.

Idea from Luis Villa, who built the same feature for himself
(https://bsky.app/profile/lu.is/post/3mv6ynbcjr62b). His version greys the
identity out; this one blacks it out.

## Use it

```bash
python3 scripts/dunk.py https://bsky.app/profile/someone.bsky.social/post/3mv6...
```

Writes `<rkey>.png` next to the working directory, prints the alt text, and
writes `<rkey>.json` holding the source URI for your own records. The source URI
stays out of both the image and the alt text. The argument can be a bsky.app
URL, an `at://` URI, or `handle/rkey`.

| flag | effect |
|---|---|
| `--redact "phrase"` | blacks out a literal phrase, repeatable |
| `--stamp` | adds the rotated REDACTED stamp |
| `--show-date` | prints the post date in the footer |
| `--out PATH` | output path |
| `--width N` | image width, default 1200 |

## Redactions applied

Avatar, display name and handle are replaced by black bars. Every `@mention`
facet in the body is blacked out — a mention is a second person's handle and
also a strong search key for finding the original. Embedded images, videos,
link cards and quoted posts render as `[image not shown]` and friends rather
than being fetched; an embedded image can carry a face, a location, or a
watermark.

Engagement counts and the date are omitted by default. A date plus a distinctive
sentence narrows a search to one post.

What the tool cannot strip is the text itself. A post that names the author's
employer, town or cat is still traceable by search, and Bluesky's own search
indexes full post text. Read the rendered PNG before posting it and pass
`--redact` for anything that identifies. This is the step that gets skipped.

## When not to use it

Public figures and large accounts: quote-post them normally. Anonymising a
senator is not protection, it just strips the reader's ability to check the
source. The tool is for the small account whose bad take deserves an answer and
whose week does not deserve your followers.

Do not use it to launder something you would not say with the link attached. If
the criticism only works because nobody can go read the original in context, the
criticism is the problem.

## Posting it

Attach the PNG in whatever client you post from and paste the printed alt text.
It starts with "Screenshot of a Bluesky post, author hidden:" so screen-reader
users get the same framing sighted readers get from the black bars.
