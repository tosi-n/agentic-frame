#!/bin/bash
# Claim a new post video project and stage everything the build needs.
# Usage: new.sh <slug> <ProjectName> <music-file.wav|mp3> [videos-dir]
set -euo pipefail
SLUG="${1:?slug}"; NAME="${2:?ProjectName (CamelCase, used for .tsrct/.mp4)}"; TRACK="${3:?music file}"
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIDEOS="${4:-$PWD/videos}"
DIR="$VIDEOS/$SLUG"
[ -f "$TRACK" ] || { echo "music file not found: $TRACK" >&2; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is required to prepare the music track" >&2; exit 1; }
mkdir "$DIR" || { echo "refusing: $DIR already exists"; exit 1; }
mkdir -p "$DIR/assets/fonts" "$DIR/assets/sfx" "$DIR/.tesseract-work/checks" "$DIR/Previews" "$DIR/Versions"
cp "$SKILL"/assets/fonts/*.ttf "$DIR/assets/fonts/"
cp "$SKILL"/assets/sfx/*.wav "$DIR/assets/sfx/"
ffmpeg -hide_banner -loglevel error -nostdin -i "$TRACK" -map 0:a:0 -c:a libmp3lame -q:a 2 "$DIR/assets/music.mp3"
sed -e "s#__SKILL_LIB__#$SKILL/lib#" -e "s#__NAME__#$NAME#g" "$SKILL/templates/build.py" > "$DIR/.tesseract-work/build.py"
sed -e "s#__NAME__#$NAME#g" -e "s#__SKILL__#$SKILL#g" "$SKILL/templates/rebuild.sh" > "$DIR/.tesseract-work/rebuild.sh"
chmod +x "$DIR/.tesseract-work/rebuild.sh"
echo "$DIR"
