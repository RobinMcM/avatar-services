# Phase 1: Spatial Coherence - Landmark-Based Anchor Tracking

This document explains the Phase 1 implementation that eliminates "floating overlay" artifacts by using CPU-based face landmark detection to dynamically position mouth and eye overlays.

## Overview

**Problem**: Static anchors cause mouth and eye overlays to appear detached from the base face, especially when using idle videos with subtle movements (breathing, micro-motion).

**Solution**: Use MediaPipe Face Mesh to extract facial landmarks from idle videos, generate an anchor timeline, and dynamically position overlays frame-by-frame during playback.

## Components

### 1. Worker-Side Processing

#### Dependencies Added
- `mediapipe==0.10.9` - CPU-based face landmark detection
- `opencv-python-headless==4.8.1.78` - Video frame extraction
- `numpy==1.24.3` - Array operations

#### New Files
- `worker/landmarks.py` - MediaPipe helper functions
- `worker/anchor_timeline.py` - Timeline generation script

### 2. Generated Asset

**File**: `anchors_timeline.json` (stored in each avatar pack directory)

**Structure**:
```json
{
  "version": 1,
  "source": {
    "video": "idle.webm",
    "fps": 30.0,
    "frame_count": 120,
    "width": 512,
    "height": 640,
    "sample_every_n_frames": 3
  },
  "target": {
    "width": 512,
    "height": 640
  },
  "config": {
    "mouth_padding": 1.5,
    "eyes_padding": 1.3
  },
  "frames": [
    {
      "frame": 0,
      "time_ms": 0,
      "mouth": {
        "x": 176,
        "y": 400,
        "w": 160,
        "h": 120,
        "cx": 256,
        "cy": 460
      },
      "eyes": {
        "x": 140,
        "y": 240,
        "w": 232,
        "h": 80,
        "cx": 256,
        "cy": 280
      }
    },
    ...
  ]
}
```

### 3. Web Compositor Updates

The compositor now:
- Loads `anchors_timeline.json` if available
- Loads and plays idle video (if specified in manifest and timeline exists)
- Dynamically positions overlays using tracked anchors
- Falls back to static anchors if timeline is missing

**New Keyboard Shortcut**: Press `T` to toggle tracking debug overlay (shows anchor boxes and current frame)

## Usage

### Step 1: Create or Source an Idle Video

You need a short (~4 second) idle video showing natural breathing/micro-movements.

**Option A: Create from Image**
```bash
# Create a 4-second looping video from base_face.png using FFmpeg
cd /root/avatar-services/web-demo/avatars/realistic_female_v1
ffmpeg -loop 1 -i base_face.png -t 4 -c:v libvpx-vp9 -b:v 0 -crf 35 idle.webm
```

**Option B: Record with Camera**
- Record yourself or actor for ~4 seconds
- Keep face centered and still (natural breathing is OK)
- Even lighting
- Save as WebM or MP4

### Step 2: Generate Anchor Timeline

Run the timeline generation script inside the worker container:

```bash
# Method 1: Using docker compose exec
docker compose exec worker python -m anchor_timeline \
  --avatar-id realistic_female_v1 \
  --input idle.webm \
  --output anchors_timeline.json \
  --sample-rate 3

# Method 2: Run directly if worker is already running
docker compose exec worker python /app/anchor_timeline.py \
  --avatar-id realistic_female_v1 \
  --input idle.webm

# For development/testing (if worker has shell access)
docker compose exec worker bash
python -m anchor_timeline --avatar-id realistic_female_v1 --input idle.webm
```

**Parameters**:
- `--avatar-id`: Avatar directory name (required)
- `--input`: Idle video filename (default: `idle.webm`)
- `--output`: Output JSON filename (default: `anchors_timeline.json`)
- `--sample-rate`: Process every Nth frame (default: 3, lower = more accurate but slower)
- `--mouth-padding`: Mouth bbox expansion factor (default: 1.5 = 50% padding)
- `--eyes-padding`: Eyes bbox expansion factor (default: 1.3 = 30% padding)
- `--target-width`: Target coordinate width (default: 512)
- `--target-height`: Target coordinate height (default: 640)
- `--base-path`: Avatar base directory (default: `/usr/share/nginx/html/avatars`)

**Output**:
- Creates `anchors_timeline.json` in the avatar directory
- Logs number of frames processed
- Warns if face detection fails for any frames

### Step 3: Verify in Browser

1. Rebuild and restart services:
```bash
docker compose build
docker compose up -d
```

2. Open web demo: `http://YOUR_DROPLET_IP:8080/`

3. Select the avatar with tracking enabled

4. Press `T` key to enable tracking debug overlay
   - Green box: mouth anchor
   - Cyan box: eyes anchor
   - Crosshairs: anchor centers
   - Info panel shows current frame and tracking status

5. Observe idle video playback - anchors should follow the face

### Step 4: Test with Speech

1. Enter text and render

2. Watch mouth and eye overlays during playback

3. They should remain perfectly aligned with the base face, even during subtle movements

## Configuration

### Adjusting Anchor Detection

If anchors are misaligned, adjust padding factors:

```bash
# Larger mouth region (more padding)
docker compose exec worker python -m anchor_timeline \
  --avatar-id realistic_female_v1 \
  --mouth-padding 1.8 \
  --eyes-padding 1.4

# Tighter fit (less padding)
docker compose exec worker python -m anchor_timeline \
  --avatar-id realistic_female_v1 \
  --mouth-padding 1.3 \
  --eyes-padding 1.2
```

### Sample Rate Trade-offs

| Sample Rate | Processing Time | Accuracy | Use Case |
|-------------|----------------|----------|----------|
| 1 | Slowest (~10-20s) | Highest | Final production |
| 3 | Fast (~3-5s) | Good | Default, recommended |
| 5 | Faster (~2-3s) | Acceptable | Quick testing |
| 10 | Fastest (~1-2s) | Lower | Rough draft |

## Troubleshooting

### "No face detected" warnings

**Causes**:
- Face too small in frame
- Poor lighting
- Extreme angles
- Occlusions (hands, hair)

**Solutions**:
- Ensure face occupies 30-50% of frame height
- Use even, frontal lighting
- Keep face centered and looking at camera
- Remove glasses/hats if causing detection issues

### Anchors drift during playback

**Causes**:
- Sample rate too high (missing key frames)
- Video FPS mismatch
- Browser video decoding variance

**Solutions**:
- Lower sample rate to 1 or 2
- Ensure video FPS matches timeline.source.fps
- Use WebM with VP9 codec for consistency

### Timeline file not loading

**Causes**:
- File not served by nginx
- CORS issues
- Incorrect path

**Solutions**:
- Verify file exists: `ls /usr/share/nginx/html/avatars/AVATAR_ID/`
- Check nginx logs: `docker compose logs nginx`
- Test direct access: `curl http://localhost:8080/avatars/realistic_female_v1/anchors_timeline.json`

### Tracking not activating

**Causes**:
- No idle video specified in manifest
- Idle video failed to load
- Timeline JSON missing or malformed

**Solutions**:
- Check browser console for errors
- Verify manifest.json has `"idleVideo": "idle.webm"`
- Verify idle.webm exists and is valid
- Check compositor log: "Tracking: ON" vs "Tracking: OFF"

## Performance

### CPU Usage

- **Timeline generation**: ~2-5 seconds per 4-second video (sample rate 3)
- **Browser playback**: Negligible overhead (<1% CPU)
- **Memory**: +2-5MB per avatar pack for timeline JSON

### Timeline File Size

- ~1-10 KB depending on sample rate and video length
- Highly compressible (gzip reduces by ~70%)

## Backwards Compatibility

- **Avatars without timeline**: Compositor automatically falls back to static anchors from manifest
- **Existing API endpoints**: Unchanged, no breaking changes
- **Calibration system**: Still works, adjustments apply on top of tracked anchors

## What This Solves

✅ Overlays stay locked to face during idle video playback  
✅ No visible drift or "floating" during subtle head movements  
✅ Breathing and micro-motions no longer cause misalignment  
✅ Works on CPU with reasonable processing time  

## What This Doesn't Solve (Future Phases)

❌ Lighting mismatches between overlays and base  
❌ Multi-frame viseme extraction and averaging  
❌ Color correction and feathering improvements  
❌ Capture Studio UI (coming in later phases)  

## Next Steps

After verifying Phase 1 works:
1. Create idle videos for all avatar packs
2. Generate timelines for each
3. Test with various speech lengths
4. Proceed to Phase 2: Enhanced extraction and color correction

## Quick Reference

```bash
# Generate timeline for an avatar
docker compose exec worker python -m anchor_timeline --avatar-id AVATAR_ID

# View timeline in browser
# Press T key to toggle debug overlay

# Check if tracking is active
# Look for green/cyan anchor boxes following the face

# Disable tracking (for testing)
# Simply remove or rename anchors_timeline.json
```

## Developer Notes

### Code Locations

- Landmark detection: `worker/landmarks.py`
- Timeline generation: `worker/anchor_timeline.py`
- Compositor tracking: `web-demo/compositor.js` (getTrackedAnchor method)
- Debug overlay: `web-demo/compositor.js` (renderTrackingDebugOverlay method)

### Extending

To add new landmark-based features:
1. Extract additional landmarks in `landmarks.py`
2. Store in timeline JSON under new keys
3. Use in compositor during rendering

Example: Adding head rotation tracking:
```python
# In landmarks.py
def extract_head_rotation(landmarks, width, height):
    # Use nose tip, chin, and forehead landmarks
    # Compute rotation angles
    return {"pitch": pitch_angle, "yaw": yaw_angle, "roll": roll_angle}
```

Then use in compositor to adjust overlay rotation.
