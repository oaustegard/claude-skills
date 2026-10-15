<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# draw: a drawing, or pixel art

A table `Kind | X | Y | W | H | Style | Label`, a row per shape, on a grid of 8px squares. Kinds: `r` rectangle, `o` rounded box, `e` ellipse, `d` diamond, `h` hexagon, `p` parallelogram, `c` cylinder, `n` note, `t` text, `i` icon (its label is the icon's name), `l` line, `a` arrow (X, Y the start; W, H the distance to the end). `k` joins two shapes with an arrow and `j` with a line: their X and Y are the row numbers (from 0) of the shapes joined. Style is a fill (`0` none, `1` tint, `2` solid), then a color letter (`r o g b p`) and a text size (`1` to `4`); a text (`t`) may end it with `=` to center its words or `>` to set them right. `alt:` in the head describes the drawing for people who cannot see it. Prefer a diagram when one fits: it lays itself out.

Request flow:

```
---
title: How a page loads
alt: A browser asks a server, which reads the data.
---
Kind | X | Y | W | H | Style | Label
--- | --- | --- | --- | --- | --- | ---
o | 4 | 6 | 16 | 8 | 1b | Browser
o | 32 | 6 | 16 | 8 | 1b | Server
c | 60 | 5 | 14 | 10 | 1g | Data
k | 0 | 1 | 0 | 0 | 0 | asks
k | 1 | 2 | 0 | 0 | 0 | reads
```

Pixel art: `grid: 16` (or 8, 32, 64) in the head, then a line per row and a letter per square, `.` clear and `a` to `h` the inks.

Pixel heart:

```
---
title: A heart
grid: 16
---
....cc....cc....
...cccc..cccc...
..cccccccccccc..
..chccccccccccc.
..chccccccccccc.
..cccccccccccc..
...cccccccccc...
....cccccccc....
.....cccccc.....
......cccc......
.......cc.......
```

Templates: Flowchart, Birthday card, Event map, Floor plan, Room plan, Wireframe, Logo sketch, Badge, Order to doorstep, Request flow, Three tiers, Pixel heart, Weather icons, Game sprite, Background tile. Its own files: `.svg`, `.tile.svg`, `.tile.png`.
