#!/usr/bin/env bash
# Install the AudioBoost Finder Quick Actions into ~/Library/Services.
# One menu item per loudness target: YouTube (-14), Podcast (-16),
# Broadcast (-23).
#
# Usage:
#   ./quick_action/install.sh         # install / replace all three
#   ./quick_action/install.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="$HOME/Library/Services"

WORKFLOWS=(
  "Boost Audio - YouTube.workflow"
  "Boost Audio - Podcast.workflow"
  "Boost Audio - Broadcast.workflow"
)
# Single-workflow name from before the per-target split; always cleaned up.
LEGACY="AudioBoost.workflow"

flush_services_cache() {
  /System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
}

if [[ "${1:-}" == "--uninstall" ]]; then
  removed=0
  for wf in "${WORKFLOWS[@]}" "$LEGACY"; do
    if [[ -d "$SERVICES_DIR/$wf" ]]; then
      rm -rf "$SERVICES_DIR/$wf"
      echo "✓ Removed $SERVICES_DIR/$wf"
      removed=1
    fi
  done
  if [[ "$removed" == 0 ]]; then
    echo "Nothing to uninstall."
  else
    flush_services_cache
  fi
  exit 0
fi

for wf in "${WORKFLOWS[@]}"; do
  if [[ ! -d "$SCRIPT_DIR/$wf" ]]; then
    echo "Workflow source not found: $SCRIPT_DIR/$wf" >&2
    exit 1
  fi
done

mkdir -p "$SERVICES_DIR"

# Drop the pre-split single workflow so users don't get four menu items.
rm -rf "$SERVICES_DIR/$LEGACY"

for wf in "${WORKFLOWS[@]}"; do
  rm -rf "$SERVICES_DIR/$wf"
  cp -R "$SCRIPT_DIR/$wf" "$SERVICES_DIR/$wf"
  echo "✓ Installed $wf"
done

flush_services_cache

echo ""
echo "Try it:"
echo "  1. Open Finder"
echo "  2. Right-click any .mp4 / .mov / .mkv / .webm file"
echo "  3. Quick Actions → Boost Audio · YouTube / Podcast / Broadcast"
echo ""
echo "If the menu items are missing, sign out and back in (macOS caches"
echo "Services aggressively) or run \`killall Finder\` then right-click again."
