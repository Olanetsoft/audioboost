#!/usr/bin/env bash
# Download static FFmpeg + FFprobe binaries into vendor/ffmpeg/ so
# build_app.sh can bundle them inside AudioBoost.app.
#
# Source: https://github.com/eugeneware/ffmpeg-static releases (GPL builds).
# The tag is pinned; release assets on GitHub are immutable.
#
# Usage:
#   ./scripts/fetch_ffmpeg.sh          # fetch if missing
#   ./scripts/fetch_ffmpeg.sh --force  # re-fetch

set -euo pipefail

TAG="b6.1.1"
BASE="https://github.com/eugeneware/ffmpeg-static/releases/download/${TAG}"
ARCH="darwin-arm64"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO_ROOT/vendor/ffmpeg"

if [[ "${1:-}" != "--force" && -x "$DEST/ffmpeg" && -x "$DEST/ffprobe" ]]; then
  echo "vendor/ffmpeg already present ($("$DEST/ffmpeg" -version | head -1))"
  exit 0
fi

mkdir -p "$DEST"

fetch() {
  local asset="$1" out="$2"
  echo "fetching ${asset}…"
  curl -fsSL --retry 3 -o "$DEST/$out" "$BASE/$asset"
}

fetch "ffmpeg-${ARCH}"    "ffmpeg"
fetch "ffprobe-${ARCH}"   "ffprobe"
fetch "${ARCH}.LICENSE"   "LICENSE"
fetch "${ARCH}.README"    "README"

chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"

echo "verifying…"
"$DEST/ffmpeg" -version | head -1
"$DEST/ffprobe" -version | head -1

cat > "$DEST/SOURCE.txt" <<EOF
FFmpeg static binaries bundled with AudioBoost.

Build:   eugeneware/ffmpeg-static release ${TAG} (${ARCH})
Fetched: ${BASE}
License: see LICENSE in this directory (GPL build — FFmpeg with GPL
         components such as libx264). AudioBoost invokes these binaries
         as separate programs; AudioBoost itself remains MIT-licensed.
Sources: https://ffmpeg.org/download.html and the build scripts at
         https://github.com/eugeneware/ffmpeg-static
EOF

echo "✓ vendor/ffmpeg ready"
