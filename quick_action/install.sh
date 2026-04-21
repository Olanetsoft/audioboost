#!/usr/bin/env bash
# Install the AudioBoost Finder Quick Action into ~/Library/Services.
#
# Usage:
#   ./quick_action/install.sh         # install / replace
#   ./quick_action/install.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW_SRC="$SCRIPT_DIR/AudioBoost.workflow"
SERVICES_DIR="$HOME/Library/Services"
WORKFLOW_DST="$SERVICES_DIR/AudioBoost.workflow"

if [[ "${1:-}" == "--uninstall" ]]; then
  if [[ -d "$WORKFLOW_DST" ]]; then
    rm -rf "$WORKFLOW_DST"
    /System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
    echo "✓ Removed $WORKFLOW_DST"
  else
    echo "Nothing to uninstall — no workflow at $WORKFLOW_DST"
  fi
  exit 0
fi

if [[ ! -d "$WORKFLOW_SRC" ]]; then
  echo "Workflow source not found at $WORKFLOW_SRC" >&2
  exit 1
fi

mkdir -p "$SERVICES_DIR"

if [[ -d "$WORKFLOW_DST" ]]; then
  rm -rf "$WORKFLOW_DST"
fi
cp -R "$WORKFLOW_SRC" "$WORKFLOW_DST"

# Rebuild the Services cache so the menu item shows up without logout.
/System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true

echo "✓ Installed AudioBoost Quick Action"
echo ""
echo "Try it:"
echo "  1. Open Finder"
echo "  2. Right-click any .mp4 / .mov / .mkv / .webm file"
echo "  3. Quick Actions → Boost Audio with AudioBoost"
echo ""
echo "If the menu item is missing, sign out and back in (macOS caches Services"
echo "aggressively) or run \`killall Finder\` then right-click again."
