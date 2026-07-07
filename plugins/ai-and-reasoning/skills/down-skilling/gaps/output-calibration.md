# Output Length and Format Calibration

**Opus**: Intuitively matches response length to task complexity and
user expectations.

**Haiku**: Tends toward either too brief or too verbose. May pad with
unnecessary caveats or preamble.

**Mitigation**: Specify word/token bounds and structural constraints.

```
Respond in 80-120 words. Begin with the recommendation.
End with one supporting reason. Do not include disclaimers.
```

Always specify:
- Word or sentence count range
- What the response should begin with
- What the response should end with
- What to omit (preamble, caveats, hedging)
