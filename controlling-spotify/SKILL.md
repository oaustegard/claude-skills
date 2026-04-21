---
name: controlling-spotify
description: "Control Spotify playback and manage playlists via MCP server. Use when playing, pausing, or skipping music, searching songs and albums, creating or modifying playlists, viewing now-playing status, or managing saved tracks."
credentials:
- SPOTIFY_CLIENT_ID
- SPOTIFY_CLIENT_SECRET
- SPOTIFY_REFRESH_TOKEN
domains:
- api.spotify.com
- accounts.spotify.com
- raw.githubusercontent.com
- github.com
metadata:
  version: 0.1.0
---

# Controlling Spotify

Control Spotify playback, search music, and manage playlists via the Spotify MCP Server.

## Prerequisites

**Requires three credentials** — without them, guide the user through `references/setup-guide.md`:

1. Create a Spotify Developer app at https://developer.spotify.com/dashboard/ with redirect URI `http://127.0.0.1:8888/callback`
2. Run the helper script from `references/setup-guide.md` to obtain a refresh token
3. Configure `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN` as skill credentials (or via a Project Knowledge `.env` file)

## MCP Server Setup

```bash
bash scripts/install-mcp-server.sh
```

```python
from mcp import Client

env_vars = {
    "SPOTIFY_CLIENT_ID": credentials.get("SPOTIFY_CLIENT_ID"),
    "SPOTIFY_CLIENT_SECRET": credentials.get("SPOTIFY_CLIENT_SECRET"),
    "SPOTIFY_REFRESH_TOKEN": credentials.get("SPOTIFY_REFRESH_TOKEN")
}

async def initialize_spotify_mcp():
    client = Client()
    await client.connect_stdio("node",
        ["/home/claude/spotify-mcp-server/build/index.js"], env_vars)
    return client
```

## Available Tools

| Tool | Purpose | Key Params |
|------|---------|------------|
| `searchSpotify` | Search tracks/albums/artists/playlists | `query`, `type`, `limit` |
| `getNowPlaying` | Current playback info | — |
| `getMyPlaylists` | List user playlists | `limit`, `offset` |
| `getPlaylistTracks` | Tracks from a playlist | `playlistId` |
| `getRecentlyPlayed` | Recent play history | `limit` |
| `getUsersSavedTracks` | Liked songs | `limit`, `offset` |
| `playMusic` | Play track/album/playlist | `uri` or `type`+`id` |
| `pausePlayback` | Pause playback | — |
| `skipToNext` / `skipToPrevious` | Skip tracks | — |
| `addToQueue` | Queue a track | `uri` |
| `createPlaylist` | Create playlist | `name`, `description`, `public` |
| `addTracksToPlaylist` | Add tracks to playlist | `playlistId`, `trackUris` |
| `getAlbums` / `getAlbumTracks` | Album info and tracks | `albumIds` / `albumId` |
| `saveOrRemoveAlbumForUser` | Save/unsave albums | `albumIds`, `action` |

## Workflow: Search → Play

```python
# Search for song, then play it
result = await client.call_tool("searchSpotify", {
    "query": "bohemian rhapsody", "type": "track", "limit": 1
})
track_uri = result["tracks"][0]["uri"]
await client.call_tool("playMusic", {"uri": track_uri})
```

## Workflow: Create Genre Playlist

```python
tracks = await client.call_tool("searchSpotify", {
    "query": "genre:rock year:2020-2024", "type": "track", "limit": 20
})
playlist = await client.call_tool("createPlaylist", {
    "name": "Modern Rock Mix", "description": "Recent rock tracks", "public": False
})
await client.call_tool("addTracksToPlaylist", {
    "playlistId": playlist["id"],
    "trackUris": [t["uri"] for t in tracks["tracks"]]
})
```

## Constraints and Troubleshooting

- **Spotify Premium required** for playback control (play, pause, skip, queue). Read operations work on free accounts.
- **Active device required** — user must have Spotify open somewhere. If "no active device" error, have them open Spotify and play/pause once.
- **Rate limits**: ~180 requests/min. Add delays for bulk operations.
- **URI format**: `spotify:track:ID`, `spotify:album:ID`, `spotify:artist:ID`, `spotify:playlist:ID`
- **Always search before playing** — don't assume URIs.

**Security**: Refresh tokens grant full account access. Never log or expose them. Users can revoke at https://www.spotify.com/account/apps/.

## References

- Setup Guide: `references/setup-guide.md`
- Spotify Web API: https://developer.spotify.com/documentation/web-api/
