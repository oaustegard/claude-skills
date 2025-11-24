# Spotify MCP Setup Guide

This guide walks you through setting up the Spotify MCP integration for use in Claude.ai skills or other ephemeral compute environments.

## Overview

The setup involves:
1. Creating a Spotify Developer application
2. Running a helper script to obtain a refresh token
3. Configuring credentials in your skill

**Time Required**: ~10 minutes (one-time setup)

## Step-by-Step Setup

### Step 1: Create Spotify Developer Application

1. **Visit Spotify Developer Dashboard**
   - Go to https://developer.spotify.com/dashboard/
   - Log in with your Spotify account

2. **Create New App**
   - Click **"Create app"** button
   - Fill in the form:
     - **App name**: Any name (e.g., "Claude Spotify Control")
     - **App description**: Any description (e.g., "MCP server for Claude")
     - **Website**: Can leave blank or use any URL
     - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ Must be exact
   - Check the boxes to agree to terms
   - Click **"Save"**

3. **Get Your Credentials**
   - You'll see your app's dashboard
   - Note the **Client ID** (visible)
   - Click **"Show client secret"** and note the **Client Secret**
   - **IMPORTANT**: Keep these secret! Don't share them publicly

4. **Verify Redirect URI**
   - Click **"Edit Settings"**
   - Under "Redirect URIs", verify `http://127.0.0.1:8888/callback` is listed
   - If not, add it and click **"Add"**
   - Click **"Save"** at the bottom

### Step 2: Obtain Refresh Token

You need to run the helper script included in this skill **on your local machine** to obtain a refresh token.

1. **Locate the Script**
   The script is located at `controlling-spotify/scripts/get-refresh-token.js`.

2. **Run the Script**
   You need Node.js installed on your machine.

   ```bash
   # Navigate to the script directory
   cd controlling-spotify/scripts

   # Run the script with your credentials
   node get-refresh-token.js YOUR_CLIENT_ID YOUR_CLIENT_SECRET
   ```

   *Replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with the values from Step 1.*

3. **Authorize in Browser**
   - The script will open your browser automatically
   - You'll see Spotify's authorization page
   - Click **"Agree"** to grant permissions
   - The browser will show "Authentication Successful!"

4. **Copy Your Refresh Token**
   - Look in your terminal - you'll see your refresh token displayed.
   - **Copy this entire token** - you'll need it for Step 3.

### Step 3: Configure Skill Credentials

Now add your credentials to the skill configuration. You have two options:

#### Option A: Skill Configuration (Recommended)

1. **Edit Skill Credentials**
   - Open your skill's credential configuration
   - Add three credentials:

   ```json
   {
     "SPOTIFY_CLIENT_ID": "your_client_id_from_step_1",
     "SPOTIFY_CLIENT_SECRET": "your_client_secret_from_step_1",
     "SPOTIFY_REFRESH_TOKEN": "your_refresh_token_from_step_2"
   }
   ```

2. **Verify Domains**
   - Ensure the skill has these domains whitelisted:
     - `api.spotify.com`
     - `accounts.spotify.com`

#### Option B: Project Knowledge File

If you are using this skill within a specific Project, you can provide credentials via a Project Knowledge file.

1. Create a file (e.g., `spotify-credentials.txt` or a `.env` file) in your Project Knowledge.
2. Add the following content:

```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REFRESH_TOKEN=your_refresh_token
```

Claude will scan the context for these values if they are not found in the skill configuration.

#### For Local Development (Claude Desktop, Cursor, etc.)

Add to your MCP configuration file:

**macOS/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "spotify": {
      "command": "node",
      "args": ["/absolute/path/to/spotify-mcp-server/build/index.js"],
      "env": {
        "SPOTIFY_CLIENT_ID": "your_client_id",
        "SPOTIFY_CLIENT_SECRET": "your_client_secret",
        "SPOTIFY_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

### Step 4: Test the Integration

1. **Start Claude** (or restart if already running)

2. **Test a Simple Command**
   ```
   Ask Claude: "What's currently playing on my Spotify?"
   ```

3. **If it works**: You'll see your current track info
   **If it fails**: See Troubleshooting section below

## Security Best Practices

### Storing Credentials Securely

**❌ DON'T:**
- Commit credentials to git/version control
- Share credentials publicly
- Hardcode credentials in skill files
- Store credentials in plain text files (except for protected config files)

**✅ DO:**
- Use environment variables
- Use secrets management services (AWS Secrets Manager, HashiCorp Vault, etc.)
- Store in password managers for personal use
- Rotate credentials if compromised

### Understanding Token Permissions

The refresh token grants **full access** to your Spotify account, including:
- ✅ View your playlists and library
- ✅ Control playback on your devices
- ✅ Create and modify playlists
- ✅ Add/remove songs from your library
- ❌ Cannot change account settings
- ❌ Cannot access payment info
- ❌ Cannot delete your account

### Revoking Access

If your token is compromised or you want to revoke access:

1. Visit https://www.spotify.com/account/apps/
2. Find your application in the list
3. Click **"Remove Access"**
4. Generate a new refresh token using the helper script

## Troubleshooting

### "Redirect URI mismatch"

**Cause**: The redirect URI in your Spotify app doesn't match the one used by the helper script

**Solution**:
1. Go to Spotify Developer Dashboard
2. Click "Edit Settings" on your app
3. Ensure `http://127.0.0.1:8888/callback` is in the Redirect URIs list
4. The URI must match **exactly** (including http, port, and path)

### "Invalid client"

**Cause**: Client ID or Client Secret is incorrect

**Solution**:
1. Go to Spotify Developer Dashboard
2. Verify your Client ID
3. Click "Show client secret" to verify Client Secret
4. Re-run the helper script with correct credentials

### "Token has expired"

**Cause**: The refresh token was revoked or is invalid

**Solution**:
- Run the helper script again to get a new refresh token
- Update your skill configuration with the new token

### "No active device found"

**Cause**: Spotify is not running on any of your devices

**Solution**:
1. Open Spotify on any device (phone, computer, web browser)
2. Start playing any song (you can pause it immediately)
3. Try the command again

### "Premium required"

**Cause**: You're using a Spotify Free account

**Solution**:
- Playback control (play, pause, skip) requires Spotify Premium
- Read operations (search, view playlists) work with free accounts
- Consider upgrading to Premium if you need playback control

### Helper script won't open browser

**Cause**: System can't automatically open browser

**Solution**:
- Look for the authorization URL in the terminal output
- Manually copy and paste it into your browser
- Complete the authorization
- The script will still detect the callback

### Port 8888 already in use

**Cause**: Another application is using port 8888

**Solution**:
```bash
# Use a different port (modify the script or free the port)
lsof -i :8888  # Find process using port (macOS/Linux)
```

## FAQ

**Q: How long is the refresh token valid?**

A: Spotify refresh tokens from Authorization Code Flow have no documented expiration. They remain valid indefinitely unless you revoke them.

**Q: Can I use the same refresh token on multiple devices/environments?**

A: Yes! The same refresh token can be used simultaneously across multiple environments (unlike PKCE tokens which rotate).

**Q: What if I lose my refresh token?**

A: Simply run the helper script again to obtain a new one. The old token will remain valid unless you revoke it.

**Q: Do I need to keep the MCP server running?**

A: No. For skills in ephemeral environments, the MCP server is started automatically when needed and stopped when the session ends.

**Q: Can I see what permissions I granted?**

A: Yes, visit https://www.spotify.com/account/apps/ to see all authorized applications and their permissions.
