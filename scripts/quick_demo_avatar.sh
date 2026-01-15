#!/bin/bash
# Quick Demo Avatar Creator
# Downloads a free stock photo and creates a working avatar

set -e

echo "=== Quick Demo Avatar Creator ==="
echo ""
echo "This script will:"
echo "1. Download a free stock photo (Unsplash)"
echo "2. Process it into avatar assets"
echo "3. Install it in your avatar-services"
echo ""

# Check if running from correct directory
if [ ! -f "create_avatar_from_photo.py" ]; then
    echo "Error: Run this from the scripts/ directory"
    echo "Usage: cd avatar-services/scripts && ./quick_demo_avatar.sh"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -q Pillow numpy opencv-python 2>/dev/null || {
    echo "Note: Some dependencies may already be installed"
}

# Example Unsplash URLs (these are specific photo IDs that work well)
# These are curated for front-facing, good lighting, neutral expression
PHOTO_OPTIONS=(
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=1080&q=80"  # Female 1
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1080&q=80"  # Male 1
    "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=1080&q=80"  # Female 2
)

# Pick one (or cycle through)
PHOTO_URL="${PHOTO_OPTIONS[0]}"

echo ""
echo "Downloading stock photo..."
wget -q -O source_photo.jpg "$PHOTO_URL" || {
    echo "Error: Failed to download photo"
    echo "You can manually download a portrait from:"
    echo "  https://unsplash.com/s/photos/portrait"
    echo "And save it as source_photo.jpg"
    exit 1
}

echo "✓ Photo downloaded"

# Create avatar
echo ""
echo "Processing photo into avatar assets..."
python3 create_avatar_from_photo.py source_photo.jpg stock_avatar/ --name stock_avatar

# Install
echo ""
echo "Installing avatar..."
cp -r stock_avatar ../web-demo/avatars/

# Update demo.js if needed
DEMO_JS="../web-demo/demo.js"
if ! grep -q "stock_avatar" "$DEMO_JS"; then
    echo ""
    echo "⚠️  You need to add 'stock_avatar' to the avatar dropdown"
    echo ""
    echo "Edit: web-demo/demo.js"
    echo "Find: const avatars = ["
    echo "Add:  { id: 'stock_avatar', name: 'Stock Photo Avatar' },"
    echo ""
fi

echo ""
echo "=== Success! ==="
echo ""
echo "Next steps:"
echo "1. Add avatar to demo.js dropdown (if not already done)"
echo "2. Restart nginx: cd ../  && docker compose restart nginx"
echo "3. Open browser: http://YOUR_IP:8080"
echo "4. Select 'Stock Photo Avatar' from dropdown"
echo "5. Test with calibration mode if positioning needs adjustment"
echo ""
echo "The avatar is installed at: web-demo/avatars/stock_avatar/"
