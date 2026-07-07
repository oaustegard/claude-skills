const http = require('http');
const https = require('https');
const url = require('url');
const { exec } = require('child_process');

// Configuration
const PORT = 8888;
const REDIRECT_URI = `http://127.0.0.1:${PORT}/callback`;

// ANSI Colors
const COLORS = {
  RESET: '\x1b[0m',
  GREEN: '\x1b[32m',
  BLUE: '\x1b[34m',
  CYAN: '\x1b[36m',
  RED: '\x1b[31m',
  YELLOW: '\x1b[33m',
  BOLD: '\x1b[1m'
};

// Get credentials from args or env
const clientId = process.env.SPOTIFY_CLIENT_ID || process.argv[2];
const clientSecret = process.env.SPOTIFY_CLIENT_SECRET || process.argv[3];

if (!clientId || !clientSecret) {
  console.error(`${COLORS.RED}Error: Missing credentials${COLORS.RESET}`);
  console.log(`
Usage:
  ${COLORS.CYAN}node get-refresh-token.js <CLIENT_ID> <CLIENT_SECRET>${COLORS.RESET}

Or using environment variables:
  ${COLORS.CYAN}SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... node get-refresh-token.js${COLORS.RESET}
`);
  process.exit(1);
}

function openBrowser(url) {
  const platform = process.platform;
  let command;

  if (platform === 'darwin') command = `open "${url}"`;
  else if (platform === 'win32') command = `start "" "${url}"`;
  else command = `xdg-open "${url}"`;

  exec(command, (error) => {
    if (error) {
      console.log(`${COLORS.YELLOW}Please open this URL in your browser:${COLORS.RESET}`);
      console.log(url);
    }
  });
}

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);

  if (parsedUrl.pathname === '/callback') {
    const code = parsedUrl.query.code;
    const error = parsedUrl.query.error;

    if (error) {
      res.writeHead(400, { 'Content-Type': 'text/html' });
      res.end(`<h1>Error</h1><p>${error}</p>`);
      console.error(`${COLORS.RED}Authorization failed: ${error}${COLORS.RESET}`);
      server.close();
      process.exit(1);
      return;
    }

    if (code) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end('<h1>Authentication Successful!</h1><p>You can close this window and check your terminal.</p>');

      console.log(`${COLORS.GREEN}✓ Authorization code received${COLORS.RESET}`);
      exchangeCodeForToken(code);
    }
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

function exchangeCodeForToken(code) {
  const postData = new URLSearchParams({
    grant_type: 'authorization_code',
    code: code,
    redirect_uri: REDIRECT_URI
  }).toString();

  const options = {
    hostname: 'accounts.spotify.com',
    port: 443,
    path: '/api/token',
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + Buffer.from(clientId + ':' + clientSecret).toString('base64')
    }
  };

  const req = https.request(options, (res) => {
    let data = '';

    res.on('data', (chunk) => {
      data += chunk;
    });

    res.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        if (parsed.refresh_token) {
          printSuccess(parsed.refresh_token);
        } else {
          console.error(`${COLORS.RED}Error getting token:${COLORS.RESET}`, parsed);
        }
      } catch (e) {
        console.error(`${COLORS.RED}Error parsing response:${COLORS.RESET}`, e);
      }
      server.close();
      process.exit(0);
    });
  });

  req.on('error', (e) => {
    console.error(`${COLORS.RED}Request error:${COLORS.RESET}`, e);
    server.close();
    process.exit(1);
  });

  req.write(postData);
  req.end();
}

function printSuccess(refreshToken) {
  console.log('\n' + '═'.repeat(60));
  console.log(`${COLORS.GREEN}${COLORS.BOLD}   ✅ SUCCESS!   ${COLORS.RESET}`);
  console.log('═'.repeat(60));
  console.log('\nYour Spotify Refresh Token:\n');
  console.log(`${COLORS.CYAN}${refreshToken}${COLORS.RESET}`);
  console.log('\n' + '─'.repeat(60));
  console.log('\nAdd this to your configuration or .env file:');
  console.log(`${COLORS.BLUE}SPOTIFY_REFRESH_TOKEN=${refreshToken}${COLORS.RESET}`);
  console.log('\n' + '═'.repeat(60) + '\n');
}

// Start flow
server.listen(PORT, () => {
  const scopes = [
    'user-read-private',
    'user-read-email',
    'user-read-playback-state',
    'user-modify-playback-state',
    'user-read-currently-playing',
    'playlist-read-private',
    'playlist-modify-private',
    'playlist-modify-public',
    'user-library-read',
    'user-library-modify',
    'user-read-recently-played'
  ].join(' ');

  const authUrl = `https://accounts.spotify.com/authorize?response_type=code&client_id=${clientId}&scope=${encodeURIComponent(scopes)}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}`;

  console.log(`${COLORS.BLUE}Starting Spotify Authentication...${COLORS.RESET}`);
  console.log(`Server listening on http://127.0.0.1:${PORT}`);
  console.log('Opening browser...');

  openBrowser(authUrl);
});
