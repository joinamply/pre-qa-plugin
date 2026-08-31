#!/usr/bin/env bash
# Build a distributable zip of the amply plugin.
# The manifest must sit at the ZIP ROOT (.claude-plugin/plugin.json), not inside a
# wrapper folder, or --plugin-dir won't find it.
set -euo pipefail
cd "$(dirname "$0")/amply"
out="../dist/amply-audit-plugin.zip"
mkdir -p ../../dist && rm -f "$out"
zip -rq "$out" . -x '*.DS_Store' '*/__pycache__/*'
echo "built $out ($(du -h "$out" | cut -f1))"
unzip -l "$out" | grep -q '\.claude-plugin/plugin\.json' && echo "manifest at zip root ✓"
