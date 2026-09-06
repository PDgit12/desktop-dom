#!/usr/bin/env bash
set -e

echo "=== desktop-dom: PyPI Release Pre-Flight Checks ==="

# 1. Ensure working directory is clean
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ Error: Working tree has uncommitted changes. Commit or stash them first."
  exit 1
fi

# 2. Run test suite
echo "Running pytest test suite..."
pytest -v

# 3. Clean and build release distributions
echo "Building wheel and source distributions..."
rm -f dist/desktop_dom-*.whl dist/desktop_dom-*.tar.gz
python -m build --outdir dist/

# 4. Twine validation
echo "Validating distributions with twine..."
twine check dist/desktop_dom-*.whl dist/desktop_dom-*.tar.gz

# 5. Publishing
echo ""
echo "Distributions built and verified:"
ls -lh dist/desktop_dom-*.whl dist/desktop_dom-*.tar.gz
echo ""

read -p "Upload to PyPI (production)? (y/N) " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  twine upload dist/desktop_dom-*.whl dist/desktop_dom-*.tar.gz
  echo "✓ Successfully published to PyPI!"
else
  echo "Upload skipped. You can manually upload anytime via: twine upload dist/desktop_dom-*.whl dist/desktop_dom-*.tar.gz"
fi
