#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

echo "Starting APT repository cleanup…"

# List of known repo identifiers / canonical .list filenames
declare -A REPO_LISTS=(
  ["docker"]="docker.list"
  ["tailscale"]="tailscale.list"
  ["microsoft-vscode"]="microsoft.list"
  ["debian-backports"]="debian-backports.list"
)

# 1️⃣ Remove duplicate files for each repo
for repo_id in "${!REPO_LISTS[@]}"; do
  canonical="/etc/apt/sources.list.d/${REPO_LISTS[$repo_id]}"
  for f in /etc/apt/sources.list.d/*"$repo_id"*.list; do
    [[ "$f" == "$canonical" ]] && continue
    echo "Removing duplicate repo file: $f"
    safe_rm -f "$f"
  done
done

# 2️⃣ Deduplicate lines inside canonical files
for repo_id in "${!REPO_LISTS[@]}"; do
  canonical="/etc/apt/sources.list.d/${REPO_LISTS[$repo_id]}"
  if [[ -f "$canonical" ]]; then
    echo "Deduplicating lines in $canonical"
    tmp="$(mktemp)"
    awk '!seen[$0]++' "$canonical" > "$tmp"
    safe_mv "$tmp" "$canonical"
  fi
done

# 3️⃣ Cleanup stale keyrings (ending with .gpg.old or duplicates)
for key in /etc/apt/keyrings/*.gpg /etc/apt/keyrings/*.gpg.old; do
  [[ -f "$key" ]] || continue
  base=$(basename "$key")
  if [[ "$base" =~ \.old$ ]]; then
    echo "Removing stale key: $key"
    safe_rm -f "$key"
  fi
done

echo "APT repository cleanup completed ✅"
