---
name: dunking-anonymously
description: Renders a Bluesky post as an anonymised screenshot so its words can be criticised without a link back to whoever wrote them. Blacks out avatar, display name, handle and any at-mentions in declassified-document styling, then emits a PNG and its alt text. Use for anonymous dunk-quoting, "dunk on this without linking it", "screenshot this post with the author hidden", "quote this without naming them", "redact this before I share it", or when a bad take from a small account deserves an answer and its author does not deserve your followers.
metadata:
  version: 0.1.0
---

# Dunking anonymously

A quote-post delivers your whole audience to the original author. For an account
with forty followers that is a pile-on whatever your caption said. This renders
the post as an image instead, so the words can be quoted without the handle.

Idea from Luis Villa, who built the same feature for himself
(https://bsky.app/profile/lu.is/post/3mv6ynbcjr62b). His render greys the
identity out; this one blacks it out.

## Procedure

```bash
python3 scripts/dunk.py https://bsky.app/profile/someone.bsky.social/post/3mv6...
```

Takes a bsky.app URL, an `at://` URI, or `handle/rkey`. Writes `<rkey>.png` to
the working directory, prints the alt text to stdout, and writes `<rkey>.json`
holding the source URI for your own records. The source URI stays out of both
the image and the alt text.

| flag | effect |
|---|---|
| `--redact "phrase"` | blacks out a literal phrase, repeatable |
| `--stamp` | adds the rotated REDACTED stamp |
| `--show-date` | prints the post date in the footer |
| `--out PATH` | output path |
| `--width N` | image width, default 1200 |

Then read the rendered PNG, actually open it, and re-run with `--redact` for
anything in the body that identifies the author. This is the step
that gets skipped.

Deps are PIL and the standard library. DejaVu Mono ships with the container. The
API call is unauthenticated, so it needs no token and leaves no trace in anyone's
notifications. See [README.md](README.md) for the host fallback and network
surface.

## Redactions applied

Avatar, display name and handle become black bars. Every at-mention facet in the
body is blacked out, since a mention is a second person's handle and a strong
search key for finding the original. Embedded images, video, link cards and quoted
posts render as `[image not shown]` and friends rather than being fetched, since
an embedded image can carry a face, a location or a watermark.

Engagement counts are dropped. The date is dropped unless `--show-date`, because
a date plus one distinctive sentence narrows a search to a single post.

The script cannot strip identity from the post's own words. Bluesky indexes full
post text, so a post naming its author's employer, town or cat stays traceable by
anyone who pastes a sentence into search. `--redact` is the only defence and it
is manual.

## When NOT to use this skill

| situation | what owns it |
|---|---|
| reading, searching or sampling Bluesky content | `browsing-bluesky` |
| sorting an account list by topic | `categorizing-bsky-accounts` |
| posting a link with a card preview | `muninn_utils.bsky_card` |
| bulk-classifying the repliers under a post | `muninn_utils.bsky_moderation` |

Quote-post public figures and large accounts normally. Anonymising a senator is
not protection. It removes the reader's ability to check the source while
protecting nobody. The skill is for accounts small enough that attention itself
is the harm.

**Earned exceptions.** Anonymising a large account is earned when the post is
being shown as a specimen of a pattern rather than as one person's position, and
the handle would pull the thread toward the individual. It is not earned when the
reader would reasonably want to verify who said it.

**Abandon mid-run** when the post cannot be anonymised, meaning the author's
identity is the claim, the text names them, or the render still reads as them
after `--redact` has eaten half the body. At that point either quote-post it with the
link or drop it. A half-redacted post that everyone recognises is worse than
both, because it performs restraint while doing the pile-on.

Do not use it to launder something you would not say with the link attached. If
the criticism only works because nobody can read the original in context, fix
the criticism.

## Common failure modes

**Black bars in the header, author named in the body.** The render looks
correctly anonymised and one sentence still says "when I worked at Foo". Signal:
you did not read the PNG, you read the terminal. Open the image every time and
pass `--redact` per identifying phrase.

**Two bars where one phrase should be.** A multi-word `--redact` phrase renders
as separate bars with visible gaps, and word lengths leak. Signal: gaps inside
what should be one black run. Adjacent redacted tokens are meant to merge across the
spaces between them. If they do not, the merge logic in `render()` broke.

**Mentions survive the redaction.** Signal: an `@handle` renders as readable
text. The script reads mention *facets*, not the `@` character, so a post whose
facets were stripped by the client that wrote it has no mention to find. Catch
it by reading the PNG and use `--redact "@handle"` as the fallback.

**`no post at at://...`.** The post is deleted, the author blocks the public
AppView, or the rkey is wrong. Not a transport failure, so refetching will not
fix it.

**403 from the AppView.** `public.api.bsky.app` refuses some proxied
environments. The script retries on `api.bsky.app`, which serves the same
lexicon, and only gives up when both refuse.

## Verification

```bash
python3 scripts/dunk.py <url> --stamp
```

Then open the PNG. Three checks: no handle or display name anywhere in the image,
no at-mention rendered as text, and the alt text opening with "Screenshot of a
Bluesky post, author hidden:".

A bad success here is a clean-looking render that still identifies its author —
every bar in place, and the body naming a workplace or a town. It passes every
automated check the script can make, which is why the read-through is part of the
procedure rather than a nicety.

## Posting it

Attach the PNG in whatever client you post from and paste the printed alt text.
It opens with "Screenshot of a Bluesky post, author hidden:" so screen-reader
users get the framing that sighted readers get from the black bars.
