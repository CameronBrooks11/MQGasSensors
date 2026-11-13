#!/usr/bin/env bash
# Fail if a tracked file is a Git LFS pointer instead of the file itself, or if
# a Markdown file links to a path in the repository that does not exist.
#
# The repository does not use LFS. A pointer left behind looks like a normal
# file in a listing and renders as a broken image.
set -euo pipefail
cd "$(dirname "$0")/.."

pointers=$(git grep -l -I -e '^version https://git-lfs.github.com/spec/v1$' -- . ':!scripts/check-assets.sh' || true)
if [ -n "$pointers" ]; then
  echo "error: these tracked files are Git LFS pointers, not their content:" >&2
  echo "$pointers" | sed 's/^/  /' >&2
  exit 1
fi
echo "assets: no Git LFS pointers among $(git ls-files | wc -l) tracked files"
python3 scripts/check-links.py
