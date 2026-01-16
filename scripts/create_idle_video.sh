#!/bin/bash
# Create a simple idle video from a static base face image
# This is a placeholder/testing utility for Phase 1 tracking

set -e

AVATAR_ID="${1:-realistic_female_v1}"
DURATION="${2:-4}"
QUALITY="${3:-35}"

AVATAR_DIR="/usr/share/nginx/html/avatars/${AVATAR_ID}"
BASE_FACE="${AVATAR_DIR}/base_face.png"
OUTPUT="${AVATAR_DIR}/idle.webm"

echo "Creating idle video for avatar: ${AVATAR_ID}"
echo "Duration: ${DURATION} seconds"
echo "Quality: CRF ${QUALITY} (lower = better quality, larger file)"

if [ ! -f "${BASE_FACE}" ]; then
    echo "Error: Base face not found at ${BASE_FACE}"
    exit 1
fi

# Create a simple looping video from the static image
# For now, this is just a static loop - no actual motion
# Real idle videos should be recorded with subtle breathing/micro-movements
ffmpeg -y \
    -loop 1 \
    -i "${BASE_FACE}" \
    -t "${DURATION}" \
    -c:v libvpx-vp9 \
    -b:v 0 \
    -crf "${QUALITY}" \
    -pix_fmt yuv420p \
    -an \
    "${OUTPUT}"

echo "✓ Idle video created: ${OUTPUT}"
echo ""
echo "Note: This is a static loop. For better results:"
echo "  1. Record a real person breathing naturally for ${DURATION} seconds"
echo "  2. Export as WebM or MP4"
echo "  3. Replace ${OUTPUT}"
echo ""
echo "Next step: Generate anchor timeline"
echo "  docker compose exec worker python -m anchor_timeline --avatar-id ${AVATAR_ID}"
