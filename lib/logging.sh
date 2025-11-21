#!/usr/bin/env bash
set -euo pipefail
log_info() { if [[ "${QUIET:-false}" != true ]]; then info "$*"; fi }
log_ok() { if [[ "${QUIET:-false}" != true ]]; then ok "$*"; fi }
log_warn() { if [[ "${QUIET:-false}" != true ]]; then warn "$*"; fi }
log_err() { err "$*"; }
