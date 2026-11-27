# Design register

Loaded from SKILL.md's design pass, for any HTML page, artifact, slide or UI
mock that a person will look at. It does for visual design what
`register.md`, this skill's catalogue of prose tics, does for prose: it names the patterns that mark a page as
model-generated and says what to do with each.

The catalogue comes from Mike Lacher's
[Slopstrap](https://slopstrap.mikelacher.com/agents/), a parody CSS kit whose
components are these patterns and whose agent checklist requires all of them on
one page. Read as a parody it is a list of things to avoid. Read as a design
reference it is a list of devices that each solved a real problem, which is why
models learned them, and which became a cliché through overuse, stacking and
fabricated content.

## The generative test

Ask of every visual element: does it tell the reader something about the
content, or does it perform "polished modern product page"? A gradient on the
one button a visitor must press tells them where to go. The same gradient on
the headline, the badge, the border and the stat card tells them nothing,
because when everything is emphasized nothing is.

Four rules follow from the test. They are what the entries below apply.

1. **Attention is a budget.** Every device on this list is an attention device.
   A viewport can spend attention once or twice before the devices cancel out.
   Pick the one thing on the screen the reader must see, give it the device,
   and keep everything else quiet.
2. **A signal must be true.** A pulsing dot claims something is live, a counter
   claims a measurement, a logo claims a customer, a testimonial claims a
   person. When the claim is false the device is fabrication. This is SKILL.md's
   "Do not invent specifics" applied to pixels, and it is the one rule that
   no budget relaxes.
3. **Clusters are the tell.** One frosted card over a photo is a design choice.
   Frosted cards, gradient text, a sparkle emoji, an eyebrow pill and a
   rainbow border together are the uniform. Judge the page by how many devices
   it stacks, the same way one em dash in prose is punctuation and a
   cluster of prose tics is evidence.
4. **Choose instead of defaulting.** Inter on slate-950 with a purple-to-cyan
   accent is what a page looks like when nobody chose. Choosing means deriving
   the palette, type and texture from the subject, the brand, or the data the
   page shows.

## The catalogue

Each entry gives what the device is for (For), when it is worth using (Earned
when), a budget (Budget), and the slop form next to the restrained one. Numbers carry a `D` so they do not
collide with the prose register's.

### Color and surface

**D1. Dark slate canvas with grid lines and blurred colour orbs.**
For: depth and atmosphere on an otherwise flat dark page.
Earned when the page is a hero or landing section with little else on it, and
the texture is faint enough that a reader notices it only when it is removed.
Budget: one texture, hero only, never behind body text or data. Orbs: none in
content areas. Honour `prefers-color-scheme`; dark should be a theme, and light
is the default for documents.
Slop: four orbs in four hues drifting behind every section, plus a grid.
Restrained: a plain background, with one radial tint behind the hero headline.

**D2. Purple-to-cyan gradient.**
For: making a primary action or brand surface feel lit rather than flat.
Earned when the hues come from the brand or the subject and the gradient sits
on one surface, usually the primary button or the hero. Adjacent hues (blue to
indigo) read as light falling on a surface. Distant hues (purple to cyan to
pink) read as a template.
Budget: one gradient surface per page.
Slop: the same purple-to-cyan on the headline, the buttons, the borders and
the badges.
Restrained: a solid accent colour on the primary button only, or a
two-stop shift within one hue family.

**D3. Gradient-filled headline text.**
For: making one display line the most prominent thing on the screen.
Earned at display sizes (32px and up) on a page whose only other accent is
neutral, applied to a phrase rather than a paragraph, with a contrast check on
the lightest stop.
Budget: one phrase per page, or none if D2 is already in use.
Slop: every section heading in animated rainbow text.
Restrained: the headline in the body text colour at a larger weight. Hierarchy
from size and weight costs nothing and survives printing and dark mode.

**D4. Frosted glass cards (`backdrop-filter: blur`).**
For: keeping text legible on a panel that floats over busy content.
Earned when something visible sits behind the panel: a map, a photo, a video, a
canvas. A blur over a solid background renders the same as a plain
translucent fill, so there the effect is invisible and only signals.
Budget: overlays only (a toolbar over a map, a caption over an image).
Slop: every card on a flat dark page frosted, with a hover lift and a cursor
spotlight.
Restrained: cards as a slightly raised surface colour with a 1px border.

**D5. Glow, beam and rotating conic borders.**
For: pointing at the one card a reader should compare the others against.
Earned once per page, on that card, when a static border or a label would not
do the job, which is rare.
Budget: zero by default; one if justified.
Slop: a beam border on the pricing card, the feature card and the CTA.
Restrained: a 2px border in the accent colour on the recommended card.

### Typography and emphasis

**D6. Inter, plus JetBrains Mono, plus one italic serif word.**
For: a readable UI face (Inter is a well-made one), a mono that marks code,
and a serif word that adds warmth to a sans headline.
Earned when each face is chosen for the job and the serif belongs to the type
system elsewhere on the page (pull quotes, a byline). The emphasized word must
be the one a reader would stress when reading the sentence aloud.
Budget: two families is usually enough. One serif emphasis per page, in the
headline.
Slop: "Ship at *unprecedented* scale", where *unprecedented* is the only serif
glyph on the page.
Restrained: one family at two weights, or a serif headline face used for every
heading so the contrast is part of the system.

**D7. Hand-drawn SVG underline under one word.**
For: an informal, hand-made accent on a page whose identity is informal.
Earned when the page has other hand-made elements (illustration, handwriting,
sketches) and the underlined word is the one the headline turns on.
Budget: one word, hero only, on pages with that identity.
Slop: a squiggle under "in" or "that". Emphasis on a function word is the
visual form of a staged reveal: it marks a word as important without anything
being important about it.
Restrained: no underline. If the sentence needs a word stressed, rewrite it so
the stress falls at the end, where readers put it anyway.

**D8. Eyebrow pill above the headline, and micro-badges.**
For: announcing news (a release, a launch date) before the reader reaches the
pitch; badges label a status that changes how the reader treats an item.
Earned when the pill carries a dated, linked fact ("v2.3 released 12 Nov:
changelog") and each badge marks a real distinction between items.
Budget: one pill, linked. Badges only where an item list has a real
distinction, and one badge type per item.
Slop: "✨ v2.0 Now Available" linking nowhere, plus "Popular", "AI" and "New"
badges on every card.
Restrained: a one-line text link above the headline, or nothing.

**D9. Sparkle emoji and emoji in tinted squircles.**
For: ✨ has become the learned convention for "this control invokes AI", and
icons help readers scan a list they will return to.
Earned when ✨ marks the AI action in an interface that also has non-AI actions,
so the glyph distinguishes something. Icons are earned when each item gets a
distinct, recognisable shape and the reader will come back to find it.
Budget: ✨ on AI controls only, never in headlines. One icon set, one style,
monochrome by default.
Slop: a 48px tinted squircle with a different emoji for each of six feature
cards.
Restrained: no icons on a feature list that is read once; a consistent line
icon set in a navigation or toolbar that is used repeatedly.

### Components

**D10. Pulsing status dot.**
For: telling the reader that something is live, recording or in progress.
Earned when the dot is wired to the state it reports. Pulse only for "changing
now"; a steady state gets a static dot.
Budget: one per real state indicator. Zero in the navbar of a static page.
Slop: a green "All Systems Operational" dot connected to nothing.
Restrained: no dot, or a static coloured dot next to a timestamp of the last
check.

**D11. Thick coloured left border on cards and callouts.**
For: marking a block as set apart (a note, a warning) so the reader can
classify it at a glance. GitHub's alert blocks use it well.
Earned when each colour encodes one category the reader can learn, and the
page uses three colours or fewer.
Budget: one semantic set (note, warning, danger) per document.
Slop: 4px borders in purple, cyan, emerald, amber and pink on consecutive
cards, the colours chosen for rhythm.
Restrained: no border on ordinary cards; a single-colour border on the one
callout that warns about something.

**D12. Bento grid.**
For: a dashboard or overview where items have different weights,
so cell size can encode importance.
Earned when the large cell holds the most important content (a headline
metric, a chart) and the small cells hold small content (a single number, a
short list).
Budget: cell sizes follow content sizes.
Slop: six equal-weight features forced into 8-4-4-8 spans to make the page
look designed.
Restrained: a uniform grid, or a list, when the items are peers.

**D13. Stat counters with count-up animation and a delta.**
For: putting the number a reader came for where they can find it.
Earned when the number is real and carries its unit, period and source, and
the delta names its baseline. The count-up adds nothing a reader needs; if it
stays, it runs once, finishes in under a second and respects
`prefers-reduced-motion`.
Budget: as many as there are real numbers worth surfacing, usually three or
fewer.
Slop: "99.99% Uptime" and "▲ +420% MoM" with no period, source or base.
Restrained: "Median build 41s (30 days to 20 Nov, n=1,212)" in static text.

**D14. Logo marquee and testimonials.**
For: social proof, which works on real readers.
Earned only when every logo is a customer who agreed to appear and every quote
is from a person who said it. There is no moderated version of an invented
testimonial. In a mockup, use labelled placeholders ("Customer logo",
"Quote from a pilot user") instead of borrowing real brands or inventing
people.
Budget: real ones only. A static row scans better than a scrolling one; scroll
only when there are more logos than fit.
Slop: OpenAI, Stripe and Vercel scrolling past, then five stars from "Dr.
Sarah Chen".
Restrained: one real quote with a name, role and link, or no section.

**D15. Three pricing tiers with an elevated middle card.**
For: guiding a buyer to the plan that suits most of them.
Earned when the middle plan is the one most buyers should pick, and the
highlight uses one device.
Budget: one highlight device (a border or a label), not a beam border, a badge
and a scale transform together.
Slop: "MOST POPULAR" on a beam-bordered card scaled 105% over two dimmed
siblings.
Restrained: equal cards with a "Recommended for teams" label on one.

**D16. Fake macOS terminal window.**
For: showing a reader a command to run.
Earned when the image depicts an actual application window the reader will
see. For a command, the window chrome adds three coloured dots and no
information.
Budget: real screenshots only.
Slop: traffic-light dots around `npm install`.
Restrained: a code block with a copy button.

**D17. "Ask AI anything" input bar and "AI Insight" callout.**
For: a working entry point to an assistant; a callout for content that is set
apart from the body.
Earned when the input does something, and when the callout's label names its
content (a warning, a prerequisite).
Budget: one live input. Callout labels name the content type, never the
author.
Slop: an input with a sparkle and a "⚡ Run" button wired to nothing; a callout
labelled "AI Insight" holding the paragraph's restatement.
Restrained: omit the input until it works; label the callout "Before you
start".

### Motion

**D18. Shimmer, rotating borders, sparkle bursts, cursor trails.**
For: motion tells a reader that something changed.
Earned when the motion accompanies a state change the reader caused or needs
to notice: a panel opening, a save completing, a value updating.
Budget: transitions on state change, 150 to 300 ms. Ambient loops: none, or one
on a page with nothing else moving. Always honour `prefers-reduced-motion`.
Slop: a shimmer sweep across every button, a rotating border on the CTA and a
sparkle trail behind the cursor.
Restrained: a 200 ms fade when a panel opens and nothing moving at rest.

### Copy on the page

The text inside these components is prose and goes through `register.md`.
Slopstrap's checklist asks for "It's not just X — it's Y" constructions and
generous em dashes; those are the negation-first reveal and em-dash drama,
`register.md` entries 2 and 16. Button labels, eyebrow text, stat labels and
alt text are reader-facing strings, so run `scripts/declaude_lint.py` on them
too.

## The design pass

1. **Inventory.** List every device from D1 to D18 on the page, with where it
   appears. The count is the cheapest signal, as the linter's `reuse` block
   (constructions used more than once) is for prose: a device
   used three times is a habit.
2. **Check every signal for truth.** Status dots, counters, logos, quotes,
   badges, inputs. Remove or label anything that claims a fact the page cannot
   back. Report invented content to the author, who is the only one who
   knows what is real, and do not swap in different invented content.
3. **Find the one thing.** Name, in a sentence, what the reader must see or do
   on each screen. Give that element the page's strongest device and strip the
   devices from everything competing with it.
4. **Replace defaults.** For the palette, type and texture, ask where each came
   from. If the answer is "it is what pages look like", derive it from the
   subject, the brand or the data instead.
5. **Check the budgets** in the entries above and cut to them.
6. **Render and look.** Take a screenshot at phone and desktop widths, in
   light and dark if both are supported, with reduced motion on. The inventory
   misses how devices interact; the screenshot shows it.

## Overcorrection

The failure mode is a page stripped to grey text on white with no hierarchy,
which is as unreadable as the slop and harder to fix, because it gives the
reader no clue where to look.

- Keep hierarchy. Size, weight, spacing and one accent colour do most of the
  work the cliché devices were reaching for.
- Keep one device where the page needs one. A landing page with no visual
  emphasis anywhere has not been restrained; it has been left unfinished.
- Keep the author's or brand's choices. A brand whose colour is purple keeps
  its purple; the rule is about defaults, and theirs is a decision.
- Keep conventions readers rely on. ✨ on the AI action, a coloured border on a
  warning and a highlighted recommended plan are learned signals, and removing
  them costs the reader time.

## Signs of a person designing

- Colours that come from the subject: a cycling page in the club's kit
  colours, a geology report in the strata's browns.
- Real screenshots, real data and real names, including unflattering ones.
- Uneven density: a lot of space where the author wants the reader to stop,
  tight lists where they want them to skim.
- One odd choice that is clearly deliberate, such as a typeface or a layout
  that no template would produce.
