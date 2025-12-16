# Artifact Template

Copy `zeitgeist-template.html` from the assets folder, then inject the DATA object. The template handles all rendering.

## Velocity Calculation

**Formula:** `(total_mentions / total_duration_seconds) * 60 = mentions_per_minute`

Example: 25 mentions of "trump" across 30 seconds = `(25/30)*60 = 50/min`

## Data Island Schema

Generate this JSON and inject it into the template's DATA constant:

```json
{
  "aggregate": {
    "totalPosts": 1029,
    "totalDurationSec": 30,
    "avgPostsPerSecond": 34.3,
    "timestamp": "2025-12-16T03:05:42Z"
  },
  "windows": [
    { 
      "label": "Window 1", 
      "posts": 331, 
      "postsPerSecond": 33.1, 
      "durationSec": 10,
      "topTerms": [["trump", 11], ["reiner", 5]]
    }
  ],
  "clusters": [
    { 
      "name": "US Politics", 
      "emoji": "🇺🇸",
      "terms": ["trump", "republican", "democrat"],
      "searchQuery": "trump OR republican OR democrat",
      "totalMentions": 25,
      "mentionsPerMin": 50.0,
      "trend": "stable",
      "windowCounts": [11, 7, 7],
      "samples": ["Sample post text 1", "Sample post text 2"]
    }
  ],
  "entities": [
    { "name": "Rob Reiner", "count": 6, "perMin": 12.0 }
  ],
  "phrases": [
    { "phrase": "rob reiner", "count": 4, "perMin": 8.0 }
  ],
  "languages": { "en": 689, "ja": 101, "pt": 39 }
}
```

## Trend Detection

Compare window counts to determine trend:
- **up**: Last window > first window by >30%
- **down**: Last window < first window by >30%  
- **stable**: Within ±30%

## Cluster Detection Patterns

Look for these signals when grouping terms:

| Cluster | Signal Terms |
|---------|-------------|
| Politics/News | trump, biden, republican, democrat, congress, vote, election |
| Tech/AI | ai, llm, claude, gpt, code, github, api, dev |
| Entertainment | movie, show, watch, album, song, game, trailer |
| Sports | game, win, score, team, season, match |
| Breaking News | Named entities with high velocity (>20/min) |

## Bsky Search Integration

Generate search URLs: `https://bsky.app/search?q={encodeURIComponent(searchQuery)}`

For multi-term clusters, use OR: `trump OR republican OR congress`
