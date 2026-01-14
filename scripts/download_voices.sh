#!/bin/bash
# Download additional Piper TTS voices
# 
# Usage: ./download_voices.sh [output_directory]
#
# This script downloads popular Piper TTS voice models.
# The default voice (en_US-lessac-medium) is already included in the Docker image.

set -e

OUTPUT_DIR="${1:-./voices}"
PIPER_VOICES_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main"

mkdir -p "$OUTPUT_DIR"

echo "=== Piper TTS Voice Downloader ==="
echo "Output directory: $OUTPUT_DIR"
echo ""

# Function to download a voice
download_voice() {
    local lang=$1
    local region=$2
    local name=$3
    local quality=$4
    
    local voice_id="${lang}_${region}-${name}-${quality}"
    local base_path="${lang}/${lang}_${region}/${name}/${quality}"
    
    echo "Downloading: $voice_id"
    
    # Download ONNX model
    curl -L -o "$OUTPUT_DIR/${voice_id}.onnx" \
        "$PIPER_VOICES_URL/${base_path}/${voice_id}.onnx" 2>/dev/null
    
    # Download config JSON
    curl -L -o "$OUTPUT_DIR/${voice_id}.onnx.json" \
        "$PIPER_VOICES_URL/${base_path}/${voice_id}.onnx.json" 2>/dev/null
    
    echo "  ✓ Downloaded $voice_id"
}

# Available voices to download
# Uncomment the voices you want

echo "Downloading English (US) voices..."
# download_voice "en" "US" "lessac" "medium"  # Already in Docker image
download_voice "en" "US" "amy" "medium"
download_voice "en" "US" "ryan" "medium"

echo ""
echo "Downloading English (GB) voices..."
download_voice "en" "GB" "alan" "medium"

# echo ""
# echo "Downloading German voices..."
# download_voice "de" "DE" "thorsten" "medium"

# echo ""
# echo "Downloading French voices..."
# download_voice "fr" "FR" "siwis" "medium"

# echo ""
# echo "Downloading Spanish voices..."
# download_voice "es" "ES" "carlfm" "medium"

echo ""
echo "=== Download Complete ==="
echo ""
echo "Downloaded voices:"
ls -la "$OUTPUT_DIR"/*.onnx 2>/dev/null | awk '{print "  - " $NF}' || echo "  No voices found"
echo ""
echo "To use these voices:"
echo "1. Mount the voices directory to /opt/piper/voices in the worker container"
echo "2. Or copy files to the container: docker cp $OUTPUT_DIR/. avatar-worker:/opt/piper/voices/"
echo ""
