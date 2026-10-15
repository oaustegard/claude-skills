<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# anim: a drawing that moves

A drawing's table, then a table `Shape | Keys`: for each moving shape (its row number from 0), keys separated by `; `, each `frame,dx,dy,depth,size,spin[,effects]`: where it is at that frame as an offset in pixels from where it was drawn, its depth (nearer when positive), its size as a scale (1 as drawn), its spin in degrees, and effect letters (`i` impact, `3` 3D, `d` shadow, `n` neon, `o` outline, `g` rainbow, `m` mirror, `w` wobble, `b` blur). Between keys it moves in straight lines. The head holds `frames` (2 to 120), `fps` (1 to 30) and `loop` (`once`, a number, or `bounce`; for ever otherwise).

Lift off:

```
---
title: Lift off
frames: 24
fps: 8
alt: A rocket lifts off and flies up and away to the right, under the words Lift off.
---
Kind | X | Y | W | H | Style | Label
--- | --- | --- | --- | --- | --- | ---
t | 4 | 20 | 20 | 4 | 04 | Lift off
i | 8 | 36 | 8 | 8 | 0b | rocket

Shape | Keys
--- | ---
0 | 0,0,0,0,1,0; 23,0,-80,0,1,0,i
1 | 0,0,0,0,1,0; 23,200,-200,80,1,-30,d
```

Templates: Lift off, Bouncing ball, Loading spinner, Title card, Birthday card, Quick standup, Build is green, Flash card, Weather this week, New Year countdown, Flight path, Neon sign, Sunrise. Its own files: `.gif`, `.webm`, `.svg`.
