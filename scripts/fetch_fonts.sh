#!/usr/bin/env bash
# Setup fonts buat PDFGeneratorTool.
# Strategy: copy Noto Sans dari system (fonts-noto-core, biasanya udah ke-install
# di Ubuntu/WSL) ke assets/fonts/ — biar font ke-bundle sama repo (portable).
#
# Kalau Noto gak ada di system, script print instruksi install. Tidak fatal.
#
# Idempotent: skip kalau file udah ada (kecuali --force).
#
# Usage:
#   ./scripts/fetch_fonts.sh           # copy yang belum ada
#   ./scripts/fetch_fonts.sh --force   # overwrite

set -euo pipefail

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

ROOT="/home/bima_lucian/BIMA_CORE"
DEST="${ROOT}/assets/fonts"
mkdir -p "${DEST}"

# Source candidates (ordered by preference)
NOTO_SRC="/usr/share/fonts/truetype/noto"

color() { printf "\033[0;%sm%s\033[0m\n" "$1" "$2"; }

color 36 "=== Setup fonts: Noto Sans → ${DEST} ==="

if [ ! -d "${NOTO_SRC}" ]; then
    color 31 "Noto fonts gak ada di ${NOTO_SRC}."
    color 33 "Install dulu: sudo apt install -y fonts-noto-core"
    color 33 "Atau fallback ke Helvetica built-in (otomatis di PDFGeneratorTool)."
    exit 1
fi

declare -A FILES=(
    [NotoSans-Regular.ttf]="NotoSans-Regular.ttf"
    [NotoSans-Bold.ttf]="NotoSans-Bold.ttf"
    [NotoSans-Italic.ttf]="NotoSans-Italic.ttf"
    [NotoSans-BoldItalic.ttf]="NotoSans-BoldItalic.ttf"
)

n_copied=0
n_skipped=0
n_missing=0
for local_name in "${!FILES[@]}"; do
    src="${NOTO_SRC}/${FILES[$local_name]}"
    target="${DEST}/${local_name}"

    if [ ! -f "${src}" ]; then
        color 31 "  MISSING source: ${src}"
        n_missing=$((n_missing + 1))
        continue
    fi
    if [ -f "${target}" ] && [ "${FORCE}" -eq 0 ]; then
        color 32 "  SKIP (ada): ${local_name}"
        n_skipped=$((n_skipped + 1))
        continue
    fi

    cp "${src}" "${target}"
    color 32 "  OK: ${local_name} ($(stat -c%s "${target}") bytes)"
    n_copied=$((n_copied + 1))
done

echo ""
color 36 "Summary: copied=${n_copied}, skipped=${n_skipped}, missing=${n_missing}"
if [ "${n_missing}" -gt 0 ]; then
    color 33 "Some files missing — PDFGeneratorTool akan fallback ke Helvetica untuk weight yang gak ada."
fi
ls -la "${DEST}"
