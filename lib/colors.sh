#!/usr/bin/env bash
set -euo pipefail
info(){ printf "\nℹ️  %s\n" "$*"; }
ok(){ printf "✅ %s\n" "$*"; }
warn(){ printf "⚠️  %s\n" "$*"; }
err(){ printf "❌ %s\n" "$*"; }
