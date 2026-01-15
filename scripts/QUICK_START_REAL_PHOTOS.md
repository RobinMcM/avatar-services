# Quick Start: Create Realistic Avatar from Real Photos

This guide will help you create a production-ready photoreal avatar in under 30 minutes.

## Option 1: Free Stock Photos (Fastest - 20 minutes)

### Step 1: Download a Face Photo

**Best Free Sources (No attribution required):**

1. **Unsplash** - https://unsplash.com/s/photos/portrait-face
   - Search: "portrait face" or "headshot"
   - Filter: Portrait orientation
   - Look for: Front-facing, neutral expression, good lighting
   
2. **Pexels** - https://www.pexels.com/search/portrait/
   - Search: "portrait" or "face"
   - Free for commercial use
   
3. **Pixabay** - https://pixabay.com/images/search/portrait/
   - Search: "portrait face"
   - Public domain

**What to Look For:**
- ✅ Front-facing (not profile)
- ✅ Neutral or slight smile
- ✅ Good lighting (not too dark/bright)
- ✅ High resolution (minimum 1024x1280px)
- ✅ Clear face, no obscuring hair
- ✅ Eyes looking at camera
- ❌ Avoid: sunglasses, hand on face, extreme angles

### Step 2: Process the Photo

```bash
cd ~/avatar-services/scripts

# Install dependencies
pip3 install Pillow numpy opencv-python

# Create avatar pack
python3 create_avatar_from_photo.py /path/to/downloaded_photo.jpg demo_avatar/

# This creates:
# - demo_avatar/base_face.png
# - demo_avatar/mouth_sprites.png
# - demo_avatar/eyes_open.png (etc.)
# - demo_avatar/manifest.json
```

### Step 3: Install in Avatar Service

```bash
# Copy to web-demo
cp -r demo_avatar ~/avatar-services/web-demo/avatars/

# Update demo.js to include new avatar
nano ~/avatar-services/web-demo/demo.js
```

Add to the `loadAvatarList()` function:

```javascript
const avatars = [
    { id: 'realistic_female_v1', name: 'Realistic Female v1' },
    { id: 'demo_avatar', name: 'Demo Avatar' }  // Add this line
];
```

### Step 4: Test

```bash
# Restart nginx (it serves static files)
cd ~/avatar-services
docker compose restart nginx

# Open browser
# http://YOUR_DROPLET_IP:8080
# Select "Demo Avatar" from dropdown
```

### Step 5: Fine-Tune with Calibration

1. Enable "Calibration Mode" checkbox
2. Use arrow keys to adjust mouth/eyes position
3. Update manifest.json with final coordinates

---

## Option 2: Record Your Own (Best Quality - 1 hour)

### Equipment Needed:
- Smartphone camera (1080p minimum)
- Good lighting (window light or ring light)
- Tripod or stable surface

### Recording Steps:

1. **Setup:**
   - Position camera at eye level
   - Ensure even lighting on face
   - Plain background (or will remove later)
   - Frame: head and shoulders, centered

2. **Record Video (2-3 minutes):**
   ```
   Say each viseme clearly:
   - REST: Neutral, mouth closed
   - AA: Open wide, say "AH"
   - EE: Wide smile, say "EEE"
   - OH: Round lips, say "OH"
   - OO: Pursed lips, say "OOO"
   - FF: Upper teeth on lower lip, say "FFF"
   - TH: Tongue between teeth, say "THH"
   
   Also record:
   - Eyes fully open (normal)
   - Eyes half-closed (squinting)
   - Eyes fully closed (blink)
   - Look left, right, up, down
   ```

3. **Extract Frames:**
   ```bash
   # Install ffmpeg if needed
   apt-get install ffmpeg
   
   # Extract frame at specific time (adjust seconds)
   ffmpeg -i video.mp4 -ss 00:00:05 -vframes 1 base_face.jpg
   ffmpeg -i video.mp4 -ss 00:00:10 -vframes 1 mouth_aa.jpg
   # ... repeat for each viseme
   ```

4. **Process in Image Editor:**
   - Open in GIMP/Photoshop/Photopea (free web editor)
   - Remove background (use magic wand or background eraser)
   - Crop each mouth viseme to same size (160x120px)
   - Crop eyes to 232x80px
   - Save as PNG with alpha channel

5. **Create Spritesheet:**
   ```bash
   # Install ImageMagick
   apt-get install imagemagick
   
   # Combine mouth frames
   convert REST.png AA.png EE.png OH.png OO.png FF.png TH.png +append mouth_sprites.png
   ```

6. **Use the script:**
   ```bash
   python3 create_avatar_from_photo.py base_face.png my_avatar/
   
   # Replace the auto-generated mouth_sprites.png with your manual one
   cp mouth_sprites.png my_avatar/
   ```

---

## Option 3: AI-Generated Face (Quick Test - 15 minutes)

### Using This Person Does Not Exist

1. Visit: https://thispersondoesnotexist.com/
2. Refresh until you find a good front-facing face
3. Right-click → Save image
4. Process with script:
   ```bash
   python3 create_avatar_from_photo.py downloaded_face.jpg ai_avatar/
   ```

**Note:** These are AI-generated and free to use, but quality varies.

---

## Recommended Workflow for Your Demo (2 Days)

### Day 1 (Tonight - 30 minutes):

1. **Download 2-3 stock photos from Unsplash**
   - Look for variety: male, female, different ages
   - Front-facing, neutral expression

2. **Process with script:**
   ```bash
   python3 create_avatar_from_photo.py photo1.jpg avatar1/
   python3 create_avatar_from_photo.py photo2.jpg avatar2/
   ```

3. **Install and test:**
   ```bash
   cp -r avatar1 avatar2 ~/avatar-services/web-demo/avatars/
   # Update demo.js
   docker compose restart nginx
   ```

4. **Fine-tune in calibration mode**

### Day 2 (Tomorrow - 1 hour):

1. **If needed, record your own:**
   - Better quality than stock
   - More control over expressions
   - Can customize to your needs

2. **Polish:**
   - Test all avatars
   - Verify lip sync quality
   - Prepare demo script
   - Take screenshots

---

## Troubleshooting

### Mouth doesn't align:
```bash
# Adjust bounding box when creating
python3 create_avatar_from_photo.py photo.jpg output/ \
  --mouth-bbox 170,420,342,540
```

### Eyes don't look right:
```bash
# Adjust eyes bounding box
python3 create_avatar_from_photo.py photo.jpg output/ \
  --eyes-bbox 130,200,382,280
```

### Face is cut off:
- Use higher resolution source image
- Ensure photo has space around face
- Photo should be portrait orientation

### Quality is low:
- Start with higher resolution source (2000px+ width)
- Use photos with good lighting
- Avoid compressed/low-quality JPEGs

---

## Quick Links

**Free Stock Photos:**
- Unsplash: https://unsplash.com/s/photos/portrait
- Pexels: https://www.pexels.com/search/portrait/
- Pixabay: https://pixabay.com/images/search/portrait/

**Free Photo Editors:**
- Photopea (web): https://www.photopea.com/
- GIMP (desktop): https://www.gimp.org/
- Remove.bg (background removal): https://www.remove.bg/

**AI Face Generator:**
- This Person Does Not Exist: https://thispersondoesnotexist.com/

---

## Example Commands

```bash
# Complete workflow
cd ~/avatar-services/scripts

# Download photo from Unsplash (paste URL)
wget -O source.jpg "https://images.unsplash.com/photo-XXXXX?w=1080"

# Create avatar
python3 create_avatar_from_photo.py source.jpg demo_avatar/

# Install
cp -r demo_avatar ../web-demo/avatars/

# Restart nginx
cd ..
docker compose restart nginx

# Test at http://YOUR_IP:8080
```

---

## For Your Demo

**Talking Points:**
- ✅ "Using real photographs for natural appearance"
- ✅ "Lip-sync extracted from audio automatically"
- ✅ "Smooth transitions between mouth shapes"
- ✅ "Natural eye blinking and movements"
- ✅ "System works with any face photo"
- ✅ "Easy to customize with your own assets"

**Have ready:**
- 2-3 different avatars to show variety
- Different text samples (short and long)
- Different voices
- Calibration mode to show the technology

Good luck with your demo! 🚀
