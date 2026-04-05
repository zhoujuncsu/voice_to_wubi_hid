#!/usr/bin/env bash
set -euo pipefail

cfg="${1:-}"
if [[ -z "${cfg}" ]]; then
  cfg="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/config.txt"
fi

if [[ ! -f "${cfg}" ]]; then
  echo "config.txt not found: ${cfg}" >&2
  return 1 2>/dev/null || exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

awk '{
  sub(/\r$/, "", $0)
  if ($0 ~ /^[[:space:]]*$/) next
  if ($0 ~ /^[[:space:]]*#/) next
  print
}' "${cfg}" > "${tmp}"

set -a
source "${tmp}"
set +a

unset cfg tmp
