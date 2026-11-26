#!/bin/bash
# render.sh <svg> <bg:light|dark> <out.png> [width] [fontoverride]
svg=$(realpath "$1"); bg=$2; out=$3; w=${4:-830}; font=${5:-}
S=$(cd "$(dirname "$0")" && pwd)
col="#ffffff"; [ "$bg" = dark ] && col="#0d1117"
read vw vh < <(grep -o 'viewBox="0 0 [0-9.]* [0-9.]*"' "$svg" | head -1 | tr -d '"' | awk '{print $3, $4}')
iw=$w; [ $(echo "$vw < $w" | bc) = 1 ] && iw=$vw
h=$(echo "$iw * $vh / $vw + 32" | bc)
src="$svg"
if [ -n "$font" ]; then sed "s/font-family=\"[^\"]*\"/font-family=\"$font\"/g" "$svg" > "$S/.tmp-font.svg"; src="$S/.tmp-font.svg"; fi
cat > "$S/.page.html" <<H
<html><body style="margin:0;padding:16px;background:$col"><img src="file://$src" style="width:${iw}px;display:block"></body></html>
H
google-chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=$((w+32)),$h --screenshot="$(realpath -m "$out")" "file://$S/.page.html" >/dev/null 2>&1
