#!/usr/bin/env bash
# يجيب خطوط العناوين (Anton للكلمة الكبيرة، Poppins Bold للسطر الصغير) من npm ويحوّلها لـTTF.
# الاستخدام: bash garage/get_fonts.sh <مجلد_الخطوط>
# يعطيك: <مجلد>/Anton.ttf و <مجلد>/Poppins-Bold.ttf  (رخصة OFL)
set -euo pipefail
OUT=${1:?مجلد الخطوط}
mkdir -p "$OUT"; TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cd "$TMP"
npm pack @fontsource/anton @fontsource/poppins --silent >/dev/null
mkdir a p; tar -xzf fontsource-anton-*.tgz -C a; tar -xzf fontsource-poppins-*.tgz -C p
pip install -q --target "$TMP/lib" fonttools >/dev/null 2>&1 || true
PYTHONPATH="$TMP/lib" python3 - "$OUT" a/package/files/anton-latin-400-normal.woff p/package/files/poppins-latin-700-normal.woff <<'E'
import sys
from fontTools.ttLib import TTFont
out, a, p = sys.argv[1:4]
for src, name in ((a, "Anton.ttf"), (p, "Poppins-Bold.ttf")):
    f = TTFont(src); f.flavor = None; f.save(f"{out}/{name}"); print("ok", name)
E
