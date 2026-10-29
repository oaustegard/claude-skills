#!/usr/bin/env bash
# Scaffold a Remotion project with pinned versions, local fonts and the
# environment fixes this container needs.
# Usage: scaffold.sh <dir> [remotion-version]
set -euo pipefail
DIR=${1:?usage: scaffold.sh <dir> [remotion-version]}
VER=${2:-4.0.535}  # last version verified here; bump only to one >= 2 weeks old
HERE=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$DIR"/src "$DIR"/public/fonts
cd "$DIR"
cat > package.json <<JSON
{
  "name": "$(basename "$DIR")",
  "private": true,
  "type": "module",
  "dependencies": {
    "@remotion/cli": "$VER",
    "@remotion/fonts": "$VER",
    "@remotion/transitions": "$VER",
    "remotion": "$VER",
    "react": "19.1.0",
    "react-dom": "19.1.0"
  },
  "devDependencies": { "@types/react": "19.1.8", "typescript": "5.8.3" }
}
JSON
cat > tsconfig.json <<'JSON'
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler", "jsx": "react-jsx",
    "strict": true, "skipLibCheck": true, "resolveJsonModule": true, "noEmit": true
  },
  "include": ["src"]
}
JSON
printf 'node_modules/\nout/\n' > .gitignore
cat > src/index.ts <<'TS'
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
TS
cat > src/Root.tsx <<'TS'
import React from "react";
import { AbsoluteFill, Composition, interpolate, useCurrentFrame } from "remotion";

const Hello: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "#F6F3EE", justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontSize: 120, opacity: interpolate(f, [0, 30], [0, 1], { extrapolateRight: "clamp" }) }}>frame {f}</div>
    </AbsoluteFill>
  );
};

export const Root: React.FC = () => (
  <Composition id="Main" component={Hello} durationInFrames={90} fps={30} width={1080} height={1920} />
);
TS
cp "$HERE"/assets/components/*.tsx src/
npm install --no-audit --no-fund --loglevel=error
echo "scaffolded $DIR (remotion $VER). Next: vendor fonts, then scripts/render.sh still."
