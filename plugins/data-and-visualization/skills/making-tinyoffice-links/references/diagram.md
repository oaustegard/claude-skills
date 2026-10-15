<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# diagram: a diagram drawn from a few lines

`kind:` in the head says which, and each is a list:

- `mind`: a nested list, the center then its branches.
- `org`: a nested list of `Name | Role`; a dotted line between two people is `~ Ben -- Eve: advises`.
- `family`: a nested list, a person or a couple each, `Rose + Albert Hale | m. 1948`.
- `lanes`: `- Who: what they do`, in order; a step ending in `?` is a decision.
- `timeline`: `- When: what happened`; dates or years are spaced as they fell, and a span (`- 2027-02-01 – 2027-08-02: Builders on site`) is a band.
- `venn`: `- Set: thing, thing` for two or three sets, `- A & B: thing` for what they share.
- `seating`: `- Table: Ann, Bob, Cy`.
- `net`: `~ A -> B: label` connections; `- name` a thing on its own.

What each is good for: `mind` ideas branching from one, `org` who reports to whom, `family` generations, `lanes` a process passed between people, `timeline` dates spaced as they fell, `venn` what two or three sets share, `seating` who sits where, `net` what talks to what.

The rules, before they are broken: a thing is a name, short (two to four words; a box holds no more), and its other words go in a child, in a connection's label, or in the notes. A connection's ends are names in the list, written exactly as the line writes them (the words before ` | `); in a tree an end naming no thing is not drawn, and a network makes a second thing of it. In a `net` a line is one thing named by the whole line: `- Header: the logo` is a thing called "Header: the logo", so write `- Header` and put "the logo" in a label. In `venn` and `seating` a comma separates things, a comma in a number too: "2,000 cases" is two things, so write 2000 or two thousand. A label is a few words: longer ones lie over each other. `lanes`, `timeline`, `venn` and `seating` draw no connections.

A small company:

```
---
title: Who reports to whom
kind: org
---
- Ada Diaz | Chief executive
  - Ben Okoro | Engineering
    - Cy Lund | Platform
    - Di Shah | Apps
  - Eve Marsh | Design
  - Flo Reyes | Sales
    - Gus Patel | Accounts

~ Cy Lund -- Eve Marsh: design partner
```

Cats and dogs:

```
---
title: Cats and dogs
kind: venn
---
- Cats: purr, climb curtains, use a litter box
- Dogs: fetch, need walks, guard the house
- Cats & Dogs: shed on the sofa, love a warm spot, wake you at six
```

Templates: Mind map, Launch plan, The garden this year, Moving abroad, Studying for an exam, Org chart, A small company, An elementary school, A restaurant kitchen, Family tree, Three generations, The Brontës, A family with a godmother, Swimlanes, From order to doorstep, Hiring someone, An expense report, Timeline, Computing, briefly, A building project, Apollo 11, Venn, Fast, cheap, good, Cats and dogs, Who can do what, Seating chart, A wedding dinner, Board game night, A classroom, Network, How an app hangs together, The water cycle, The house network. Its own files: `.svg`.
