#!/usr/bin/env bash
# Copy shared reference files into each skill. A skill's references must live inside its own folder.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

for skill in "$root"/skills/*/; do
    mkdir -p "${skill}references"
    cp "$root/shared/version-matrix.md" "${skill}references/version-matrix.md"
done
