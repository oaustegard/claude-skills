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

You need to run a helper script **on your local machine** to obtain a refresh token.

#### Option A: Using the Modified Spotify MCP Server

1. **Clone and Setup**
   ```bash
   # Clone the repository
   git clone https://github.com/YOUR-FORK/spotify-mcp-server.git
   cd spotify-mcp-server

   # Install dependencies
   npm install
   npm run build
   ```

2. **Run Helper Script**
   ```bash
   # Set your credentials as environment variables
   export SPOTIFY_CLIENT_ID="your_client_id_here"
   export SPOTIFY_CLIENT_SECRET="your_client_secret_here"

   # Run the script
   node get-refresh-token.js
   ```

   **Or pass credentials as arguments:**
   ```bash
   node get-refresh-token.js your_client_id your_client_secret
   ```

3. **Authorize in Browser**
   - The script will open your browser automatically
   - You'll see Spotify's authorization page
   - Click **"Agree"** to grant permissions
   - The browser will show "Authentication Successful!"

4. **Copy Your Refresh Token**
   - Look in your terminal - you'll see output like:
     ```
     ╔══════════════════════════════════════════════════════╗
     ║                ✅ SUCCESS!                           ║
     ╚══════════════════════════════════════════════════════╝

     Your Spotify Refresh Token:

     ┌──────────────────────────────────────────────────────┐
     │ AQDQcj...very-long-string...7w                       │
     └──────────────────────────────────────────────────────┘
     ```
   - **Copy this entire token** - you'll need it for Step 3

#### Option B: Manual Method (If Helper Script Unavailable)

If you can't run the helper script, you can get a refresh token manually:

1. **Generate Authorization URL**
   ```
   https://accounts.spotify.com/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://127.0.0.1:8888/callback&scope=user-read-private%20user-read-email%20user-read-playback-state%20user-modify-playback-state%20user-read-currently-playing%20playlist-read-private%20playlist-modify-private%20playlist-modify-public%20user-library-read%20user-library-modify%20user-read-recently-played
   ```
   Replace `YOUR_CLIENT_ID` with your actual client ID

2. **Visit URL and Authorize**
   - Paste the URL in your browser
   - Log in to Spotify and click "Agree"
   - You'll be redirected to `http://127.0.0.1:8888/callback?code=XXXXXX`
   - The page won't load (that's OK!)
   - Copy the `code` parameter from the URL

3. **Exchange Code for Token**
   ```bash
   curl -X POST "https://accounts.spotify.com/api/token" \
     -H "Authorization: Basic $(echo -n 'YOUR_CLIENT_ID:YOUR_CLIENT_SECRET' | base64)" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code&code=YOUR_CODE&redirect_uri=http://127.0.0.1:8888/callback"
   ```

   Replace:
   - `YOUR_CLIENT_ID` with your client ID
   - `YOUR_CLIENT_SECRET` with your client secret
   - `YOUR_CODE` with the code from step 2

4. **Extract Refresh Token**
   - The response will be JSON containing `refresh_token`
   - Copy the value of `refresh_token`

### Step 3: Configure Skill Credentials

Now add your credentials to the skill configuration.

#### For Claude.ai Skills

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

Replace `/absolute/path/to/spotify-mcp-server` with the actual path where you cloned the repository.

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
# Use a different port
node get-refresh-token.js YOUR_CLIENT_ID YOUR_CLIENT_SECRET 8889

# Remember to update your Spotify app's redirect URI to match:
# http://127.0.0.1:8889/callback
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

**Q: What happens if Spotify changes their API?**

A: The MCP server may need updates. Check for updates regularly if you encounter issues.

**Q: Can I limit what the refresh token can access?**

A: Permissions are determined when you authorize. To change permissions, revoke access and re-authorize with different scopes (requires modifying the helper script).

## Advanced Topics

### Custom Scopes

If you want to limit permissions, edit the `SCOPES` array in `get-refresh-token.js`:

```javascript
const SCOPES = [
  'user-read-playback-state',  // View what's playing
  'user-modify-playback-state', // Control playback
  'playlist-read-private',      // Read playlists
  // Remove any you don't need
].join(' ');
```

### Using with CI/CD

For automated environments:

1. Get refresh token manually (one-time)
2. Store in secrets manager (GitHub Secrets, AWS Secrets Manager, etc.)
3. Inject as environment variable in CI/CD pipeline

Example for GitHub Actions:
```yaml
- name: Run Spotify integration
  env:
    SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
    SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
    SPOTIFY_REFRESH_TOKEN: ${{ secrets.SPOTIFY_REFRESH_TOKEN }}
  run: node run-spotify-task.js
```

### Monitoring Token Usage

To monitor API usage and detect compromised tokens:

1. Check Spotify API rate limit headers in responses
2. Review authorized devices in Spotify account settings
3. Monitor for unexpected playback activity

### Token Rotation

While refresh tokens don't expire, you may want to rotate them periodically for security:

1. Set a reminder (e.g., every 6 months)
2. Run helper script to get new token
3. Update all configurations
4. Revoke old token from Spotify account settings

## Support

### Resources

- Spotify Web API Docs: https://developer.spotify.com/documentation/web-api/
- MCP Specification: https://modelcontextprotocol.io/
- Original MCP Server: https://github.com/marcelmarais/spotify-mcp-server

### Getting Help

If you encounter issues:

1. Check this troubleshooting guide
2. Verify all credentials are correct
3. Test with a simple command first
4. Check Spotify service status: https://status.spotify.com/
5. Review MCP server logs for error messages

## Summary Checklist

- [ ] Created Spotify Developer application
- [ ] Added redirect URI: `http://127.0.0.1:8888/callback`
- [ ] Noted Client ID and Client Secret
- [ ] Ran helper script to get refresh token
- [ ] Added all three credentials to skill configuration
- [ ] Whitelisted required domains
- [ ] Tested with a simple command
- [ ] Stored credentials securely
- [ ] Understood security implications

Once all items are checked, your Spotify MCP integration is ready to use!
