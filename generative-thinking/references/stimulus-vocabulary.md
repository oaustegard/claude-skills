# Stimulus vocabulary — 128 nouns for the hashed random stimulus

Load this file only when running the **Random stimulus** move with an internal seed (String Seed of Thought, Misaki & Akiba 2025). 128 entries so the index is `hash mod 128`.

## Procedure

1. Write out a random string of 40+ characters — mixed letters, digits, symbols, no visible pattern.
2. Write out the reduction over the **whole** string. Either:
   - **Sum-mod**: sum of the character codes (ASCII/Unicode code points), then `mod 128`.
   - **Rolling hash**: `h = (h * 31 + code) mod 128` for each character in order, starting from `h = 0`.
   Show the arithmetic. A derivation that is not on the page gets hallucinated.
3. Take the word at that index. Commit to it; do not re-roll.

Worked example (sum-mod, short string for illustration — use a longer one in practice):

```
seed:  q7#Vx2!mLp9
codes: 113 55 35 86 120 50 33 109 76 112 57
sum:   846
846 mod 128 = 78   ->  "pollen"
```

Two measured failure modes: reading only the first character (LLM seeds carry strong positional bias — the paper found 947 of 1000 QwQ-32B strings opened with "7"), and adopting a strategy without writing it out.

## Vocabulary

| index | noun |
|---|---|
| 0 | anvil |
| 1 | tide |
| 2 | lichen |
| 3 | ledger |
| 4 | sonar |
| 5 | compost |
| 6 | hinge |
| 7 | sieve |
| 8 | glacier |
| 9 | hymn |
| 10 | abacus |
| 11 | bellows |
| 12 | kiln |
| 13 | quorum |
| 14 | ballast |
| 15 | marrow |
| 16 | loom |
| 17 | estuary |
| 18 | tourniquet |
| 19 | mortar |
| 20 | scrimmage |
| 21 | prism |
| 22 | tithe |
| 23 | rookery |
| 24 | sextant |
| 25 | fallow |
| 26 | gasket |
| 27 | cistern |
| 28 | relay |
| 29 | furrow |
| 30 | pendulum |
| 31 | quarry |
| 32 | saddle |
| 33 | harrow |
| 34 | mosaic |
| 35 | embargo |
| 36 | tuning-fork |
| 37 | peat |
| 38 | nomad |
| 39 | scaffold |
| 40 | beacon |
| 41 | ferment |
| 42 | cartilage |
| 43 | tariff |
| 44 | moraine |
| 45 | lullaby |
| 46 | spindle |
| 47 | brine |
| 48 | coral |
| 49 | sluice |
| 50 | armistice |
| 51 | quill |
| 52 | trellis |
| 53 | ration |
| 54 | wick |
| 55 | shale |
| 56 | tremor |
| 57 | overture |
| 58 | gauntlet |
| 59 | silt |
| 60 | canopy |
| 61 | metronome |
| 62 | dowry |
| 63 | stencil |
| 64 | drumhead |
| 65 | ossuary |
| 66 | cargo |
| 67 | flint |
| 68 | ledge |
| 69 | bobbin |
| 70 | monsoon |
| 71 | almanac |
| 72 | rudder |
| 73 | tannin |
| 74 | sanctuary |
| 75 | cog |
| 76 | bramble |
| 77 | tribunal |
| 78 | pollen |
| 79 | keel |
| 80 | mildew |
| 81 | vault |
| 82 | lantern |
| 83 | reef |
| 84 | grist |
| 85 | choir |
| 86 | levee |
| 87 | tendon |
| 88 | parapet |
| 89 | foal |
| 90 | plumb-line |
| 91 | sermon |
| 92 | hive |
| 93 | scree |
| 94 | caravan |
| 95 | gutter |
| 96 | mantle |
| 97 | turnstile |
| 98 | yeast |
| 99 | fresco |
| 100 | dam |
| 101 | ricochet |
| 102 | orchard |
| 103 | ballot |
| 104 | piston |
| 105 | murmur |
| 106 | snare |
| 107 | compass |
| 108 | rind |
| 109 | sediment |
| 110 | vigil |
| 111 | cloister |
| 112 | forge |
| 113 | hourglass |
| 114 | vine |
| 115 | capstan |
| 116 | dune |
| 117 | ember |
| 118 | tapestry |
| 119 | warden |
| 120 | kelp |
| 121 | anthem |
| 122 | gimbal |
| 123 | thaw |
| 124 | ration-book |
| 125 | ossify |
| 126 | treble |
| 127 | plinth |
