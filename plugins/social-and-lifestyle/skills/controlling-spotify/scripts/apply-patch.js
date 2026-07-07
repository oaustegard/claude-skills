const fs = require('fs');
const path = require('path');

const utilsPath = path.join(process.cwd(), 'src', 'utils.ts');

console.log(`Patching ${utilsPath}...`);

if (!fs.existsSync(utilsPath)) {
  console.error('Error: src/utils.ts not found');
  process.exit(1);
}

let content = fs.readFileSync(utilsPath, 'utf8');

const functionSignature = 'export function loadSpotifyConfig(): SpotifyConfig {';

if (content.includes(functionSignature)) {
  const injection = `
  // Injected by controlling-spotify skill
  const clientId = process.env.SPOTIFY_CLIENT_ID;
  const clientSecret = process.env.SPOTIFY_CLIENT_SECRET;
  const refreshToken = process.env.SPOTIFY_REFRESH_TOKEN;

  if (clientId && clientSecret) {
    return {
      clientId,
      clientSecret,
      redirectUri: process.env.SPOTIFY_REDIRECT_URI || 'http://127.0.0.1:8888/callback',
      refreshToken: refreshToken || undefined,
    };
  }
  // End injection
`;

  content = content.replace(functionSignature, functionSignature + injection);
  fs.writeFileSync(utilsPath, content);
  console.log('Successfully patched src/utils.ts');
} else {
  console.error('Error: Could not find loadSpotifyConfig function in src/utils.ts');
  console.error('Content preview:', content.substring(0, 200));
  process.exit(1);
}
