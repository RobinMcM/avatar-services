# Realistic Female v1 Avatar Pack

This avatar pack uses photoreal compositing to create a lifelike 2D talking head.

## Current Assets (Placeholders)

The included assets are **colored placeholder blocks** to demonstrate the system. They are NOT photoreal.

To create a production-quality avatar, replace these placeholders with real captured footage.

## Asset Requirements

### 1. Base Face (`base_face.png`)
- **Format:** PNG, 512x640px (or any 4:5 aspect ratio)
- **Content:** Neutral face photo, front-facing, good lighting
- **Requirements:**
  - Mouth closed (neutral expression)
  - Eyes open, looking forward
  - Even lighting, no shadows
  - High resolution (minimum 512px wide)
  - Background removed or solid color

### 2. Mouth Spritesheet (`mouth_sprites.png`)
- **Format:** PNG with alpha, 1120x120px (7 frames × 160px wide)
- **Content:** Horizontal strip of 7 mouth viseme poses
- **Frame order (left to right):**
  1. `REST` - Mouth closed/neutral
  2. `AA` - Open mouth (say "ah")
  3. `EE` - Wide mouth (say "ee")
  4. `OH` - Rounded open (say "oh")
  5. `OO` - Lips pursed (say "oo")
  6. `FF` - Upper teeth on lower lip (say "f")
  7. `TH` - Tongue visible (say "th")
- **Each frame:** 160x120px, cropped to mouth region only
- **Alpha channel:** Transparent background

### 3. Mouth Mask (`mouth_mask.png`)
- **Format:** PNG grayscale, 160x120px
- **Content:** Soft-edged mask defining mouth region
- **White** = opaque, **Black** = transparent
- **Feathered edges** (8-12px gaussian blur) for smooth blending

### 4. Eye Frames
- `eyes_open.png` - Eyes fully open (232x80px)
- `eyes_half.png` - Eyes half-closed (232x80px)
- `eyes_closed.png` - Eyes fully closed (232x80px)
- **Format:** PNG with alpha
- **Content:** Both eyes, cropped to eye region
- **Alpha channel:** Feathered edges for blending

### 5. Eyes Mask (`eyes_mask.png`)
- **Format:** PNG grayscale, 232x80px
- **Content:** Soft-edged mask for eye region
- **Feathered edges** for natural blending

### 6. Idle Loop Video (Optional, `idle_loop.webm`)
- **Format:** WebM (VP9), 512x640px
- **Content:** 3-5 second subtle idle animation
- **Loop:** Seamlessly looping
- **Use case:** Instead of static base, adds micro-movements

## Creating Real Assets

### Method 1: From Video Footage

1. **Record Source Video:**
   - 1080p or higher
   - Front-facing, eye-level camera
   - Even, soft lighting (ring light or window light)
   - Neutral background or green screen
   - Record person saying visemes: "REST, AH, EE, OH, OO, FF, TH"
   - Record blinks: open, half-closed, fully closed
   - Record 5 seconds of idle (breathing, micro-movements)

2. **Extract Frames:**
   ```bash
   # Use ffmpeg to extract frames
   ffmpeg -i source.mp4 -vf "select='eq(n,FRAME_NUMBER)'" -vframes 1 frame.png
   ```

3. **Process in Image Editor (Photoshop, GIMP, Affinity Photo):**
   - Remove background (use alpha channel)
   - Crop base face to 512x640px
   - Crop each viseme mouth to 160x120px
   - Align all mouths to same position
   - Crop eyes to 232x80px for each state
   - Create masks using Select > Feather (8px) then save as grayscale

4. **Create Spritesheet:**
   ```bash
   # Use ImageMagick to combine frames
   convert REST.png AA.png EE.png OH.png OO.png FF.png TH.png +append mouth_sprites.png
   ```

5. **Create Masks:**
   - Load cropped mouth/eyes in editor
   - Select visible region
   - Feather selection (8-12px)
   - Fill with white on black background
   - Save as grayscale PNG

### Method 2: From Photos

1. Take 10+ photos:
   - 1 neutral base
   - 7 viseme poses (use a mirror, practice each sound)
   - 3 eye states (open, squinting, closed)

2. Process similar to Method 1

3. Less natural than video, but workable

### Method 3: AI-Generated (Experimental)

Use tools like Midjourney/DALL-E/Stable Diffusion:
- Generate base face
- Generate mouth visemes with consistent style
- Generate eye states
- **Warning:** Results vary, may need manual touch-up

## Calibration

After replacing assets:

1. Load the avatar in the demo
2. Enable "Calibration Overlay" in UI
3. Adjust anchor positions:
   - Arrow keys: move anchor
   - Shift+Arrow keys: resize anchor
4. Positions are saved in browser localStorage
5. Update `manifest.json` with final anchor values

## Optimization Tips

### File Sizes
- Use **WebP** for mouth sprites (60-80% smaller than PNG)
- Use **WebM** with VP9 codec for idle video
- Compress PNGs with `pngquant` or `optipng`

### Performance
- Keep spritesheet under 500KB
- Base face under 200KB
- Total pack under 1MB for fast loading

### Quality vs Size
- Mouth sprites: high quality (80-90%) - most visible
- Eye frames: medium quality (70-80%)
- Masks: low quality (50%) - just shapes
- Base: medium quality (75%)

## Example Commands

```bash
# Optimize PNG
pngquant --quality=70-85 mouth_sprites.png -o mouth_sprites_opt.png

# Convert to WebP
cwebp -q 85 mouth_sprites.png -o mouth_sprites.webp

# Create seamless loop video
ffmpeg -i idle.mp4 -c:v libvpx-vp9 -b:v 500k -loop 0 idle_loop.webm
```

## Troubleshooting

**Mouth doesn't align:**
- Check anchor x, y values in manifest
- Use calibration overlay to adjust
- Ensure spritesheet frames are same size

**Jagged edges:**
- Increase featherPx in manifest
- Check mask has soft edges
- Ensure alpha channel is correct

**Eyes look flat:**
- Add pupil layer (separate image)
- Enable pupil offset in manifest
- Increase saccade events

**Doesn't look realistic:**
- Check lighting consistency across all assets
- Ensure color matching between base and layers
- Add subtle shadows to mouth/eyes layers
- Use micro-motion settings in manifest

## Licensing

If using real person footage:
- Obtain proper rights/releases
- Include attribution if required
- Check usage terms for your application

## Support

See main repository README for more details on the avatar system.
