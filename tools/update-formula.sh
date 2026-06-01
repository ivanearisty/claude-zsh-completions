#!/usr/bin/env bash
# Bump the Homebrew formula's url + sha256 to a released tag.
#
# Usage: tools/update-formula.sh v2.1.159     (the tag must already be pushed)
#
# Release flow:
#   git tag v2.1.159 && git push origin v2.1.159
#   tools/update-formula.sh v2.1.159
#   git commit -am "brew: release v2.1.159" && git push
set -euo pipefail

tag="${1:?usage: update-formula.sh <tag, e.g. v2.1.159>}"
repo="ivanearisty/claude-zsh-completions"
url="https://github.com/${repo}/archive/refs/tags/${tag}.tar.gz"

tmp="$(mktemp)"
trap 'rm -f "$tmp" "$tmp.bak"' EXIT
echo "fetching $url"
curl -fsSL "$url" -o "$tmp"
sha="$(shasum -a 256 "$tmp" | awk '{print $1}')"

formula="$(cd "$(dirname "$0")/.." && pwd)/Formula/claude-zsh-completions.rb"
sed -i.bak -E \
  -e "s#archive/refs/tags/v[0-9][0-9.]*\.tar\.gz#archive/refs/tags/${tag}.tar.gz#" \
  -e "s/sha256 \"[0-9a-f]{64}\"/sha256 \"${sha}\"/" \
  "$formula"
rm -f "$formula.bak"

echo "updated $formula"
echo "  url    -> $url"
echo "  sha256 -> $sha"
