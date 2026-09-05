#!/usr/bin/env bash
set -e

echo "=== @desktop-dom/core: npm Release Pre-Flight Checks ==="

cd "$(dirname "$0")/../typescript"

# 1. Compile TypeScript SDK
echo "Compiling TypeScript SDK..."
npm run build

# 2. Dry run packing
echo "Verifying npm pack..."
npm pack --dry-run

echo ""
read -p "Publish @desktop-dom/core to npm public registry? (y/N) " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  npm publish --access public
  echo "✓ Successfully published @desktop-dom/core to npm!"
else
  echo "Publish skipped. You can manually publish anytime via: cd typescript && npm publish --access public"
fi
