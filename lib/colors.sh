#!/usr/bin/env bash
set -euo pipefail
info() { echo -e "ℹ️  \033[1;34m$*\033[0m"; }
warn() { echo -e "⚠️  \033[1;33m$*\033[0m"; }
err() { echo -e "❌ \033[1;31m$*\033[0m" >&2; }
ok() { echo -e "✅ \033[1;32m$*\033[0m"; }
