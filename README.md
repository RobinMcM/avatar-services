# Avatar Service

A production-ready avatar animation service that generates TTS audio and synchronized lip/eye animations for 2D avatars rendered in the browser.

## Features

- **Text-to-Speech**: Uses [Piper TTS](https://github.com/rhasspy/piper) for high-quality, local CPU-based speech synthesis
- **Lip Sync**: Extracts mouth animation cues using [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync)
- **Eye Animation**: Generates realistic blink and saccade events
- **Photoreal Avatars**: Composite-based 2D avatars using real photos/video with masked layers
- **Avatar Packs**: Modular system for custom avatar assets (base face, mouth sprites, eye frames)
- **Spatial Coherence Tracking (Phase 1)**: CPU-based face landmark detection eliminates "floating overlays"
- **Dynamic Anchor Positioning**: Overlays follow face during idle video playback using MediaPipe
- **Calibration Tools**: Browser-based calibration overlay for fine-tuning avatar positioning
- **Micro-Motion**: Subtle idle animations (head bob, breathing, natural blinks)
- **Caching**: Results cached by content hash for instant repeated requests
- **Job Queue**: Asynchronous processing via Valkey (Redis-compatible)
- **Web Demo**: Photoreal 2D avatar renderer with smooth interpolation and compositing

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│  FastAPI    │────▶│   Valkey    │
│  (static)   │     │   (API)     │     │   (queue)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │                                       ▼
       │                              ┌─────────────┐
       │                              │   Worker    │
       ▼                              │ (TTS+Sync)  │
┌─────────────┐                       └─────────────┘
│ /data/audio │◀──────────────────────────────┘
│  (shared)   │
└─────────────┘
```

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 2GB+ RAM (for TTS processing)
- x86_64 architecture (Piper and Rhubarb binaries)

## Quick Start

### 1. Clone and Build

```bash
cd avatar-services
docker compose build
```

### 2. Start Services

```bash
docker compose up -d
```

### 3. Access the Demo

Open http://localhost:8080 in your browser.

### 4. Check Service Health

```bash
curl http://localhost:8000/health
```

## API Endpoints

### Synchronous Render

Waits for the render to complete before returning.

```bash
curl -X POST http://localhost:8000/v1/avatar/render \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, I am a talking avatar!",
    "voice_id": "en_US-lessac-medium",
    "speed": 1.0
  }'
```

**Response:**
```json
{
  "render_id": "abc123...",
  "status": "completed",
  "audio_url": "http://localhost:8080/audio/abc123.ogg",
  "duration_ms": 2340,
  "mouth_cues": [
    {"t_ms": 0, "viseme": "REST", "weight": 1.0},
    {"t_ms": 120, "viseme": "AA", "weight": 0.85},
    ...
  ],
  "eye_events": [
    {"t_ms": 1500, "event_type": "blink", "duration_ms": 150},
    {"t_ms": 2800, "event_type": "saccade", "duration_ms": 300, "direction": "left"}
  ],
  "cached": false,
  "processing_time_ms": 1523
}
```

### Asynchronous Render

Returns immediately with a render ID for polling.

```bash
# Submit job
curl -X POST http://localhost:8000/v1/avatar/render_async \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is an async render request.",
    "voice_id": "en_US-lessac-medium",
    "speed": 1.0
  }'

# Response
# {"render_id": "xyz789...", "status": "pending", "poll_url": "..."}

# Poll for result
curl http://localhost:8000/v1/avatar/render/xyz789...
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "valkey_connected": true, "pending_jobs": 0}
```

## Request Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `text` | string | required | 1-5000 chars | Text to synthesize |
| `voice_id` | string | `en_US-lessac-medium` | see below | Voice model ID |
| `speed` | float | `1.0` | 0.5-2.0 | Speech speed multiplier |

### Available Voices

| Voice ID | Language | Description |
|----------|----------|-------------|
| `en_US-lessac-medium` | English (US) | Default, high quality |
| `en_US-amy-medium` | English (US) | Female voice |
| `en_US-ryan-medium` | English (US) | Male voice |
| `en_GB-alan-medium` | English (GB) | British male voice |

Additional voices can be downloaded using `scripts/download_voices.sh`.

## Avatar Packs

The web demo uses a photoreal compositing system with modular avatar packs.

### Included Avatar

- **realistic_female_v1**: Placeholder avatar with colored blocks (demonstration only)

### Creating Your Own Avatar Pack

1. **Prepare Assets:**
   - Base face image (512x640px PNG)
   - Mouth viseme spritesheet (7 frames: REST, AA, EE, OH, OO, FF, TH)
   - Eye state images (open, half, closed)
   - Alpha masks for mouth and eyes

2. **Create Avatar Directory:**
   ```bash
   mkdir -p web-demo/avatars/my_avatar
   ```

3. **Add Assets:**
   - Copy your images to the avatar directory
   - Create `manifest.json` (see `realistic_female_v1` for template)
   - Set anchor coordinates for mouth/eyes positioning

4. **Test and Calibrate:**
   - Load avatar in demo
   - Enable "Calibration Mode"
   - Use arrow keys to adjust positioning
   - Coordinates save in browser localStorage

### Asset Requirements

| Asset | Size | Format | Description |
|-------|------|--------|-------------|
| `base_face.png` | 512x640px | PNG/WebP | Neutral face, front-facing |
| `mouth_sprites.png` | 1120x120px | PNG/WebP | 7 viseme frames (160x120 each) |
| `mouth_mask.png` | 160x120px | PNG | Grayscale mask with feathered edges |
| `eyes_open.png` | 232x80px | PNG/WebP | Eyes fully open |
| `eyes_half.png` | 232x80px | PNG/WebP | Eyes half-closed |
| `eyes_closed.png` | 232x80px | PNG/WebP | Eyes closed (blink) |
| `eyes_mask.png` | 232x80px | PNG | Grayscale mask for eyes |
| `idle_loop.webm` | 512x640px | WebM (optional) | Seamless idle animation |

**Detailed instructions:** See `web-demo/avatars/realistic_female_v1/README.md`

## Response Format

### Mouth Cues

```json
{
  "t_ms": 120,      // Timestamp in milliseconds
  "viseme": "AA",   // Viseme identifier
  "weight": 0.85    // Animation weight (0.0-1.0)
}
```

**Viseme Set:**
- `REST` - Neutral/closed mouth
- `AA` - Open mouth (ah, uh)
- `EE` - Wide mouth (ee, eh)
- `OH` - Rounded open (oh, ow)
- `OO` - Tight rounded (oo, w)
- `FF` - Upper teeth on lower lip (f, v)
- `TH` - Tongue visible (th, l)

### Eye Events

```json
{
  "t_ms": 1500,           // Timestamp
  "event_type": "blink",  // "blink" or "saccade"
  "duration_ms": 150,     // Event duration
  "direction": null       // Saccade direction (if applicable)
}
```

## Phase 1: Spatial Coherence Tracking

**NEW**: Avatar overlays now track face movements using CPU-based landmark detection, eliminating the "floating overlay" problem.

### What is it?

Traditional static anchors cause mouth and eye overlays to drift when the base face has subtle motion (breathing, micro-movements). Phase 1 uses MediaPipe Face Mesh to generate an anchor timeline that dynamically positions overlays frame-by-frame.

### Quick Setup

1. **Create or obtain an idle video** (~4 seconds) for your avatar:
```bash
# Option A: Create from static image
cd web-demo/avatars/realistic_female_v1
ffmpeg -loop 1 -i base_face.png -t 4 -c:v libvpx-vp9 -b:v 0 -crf 35 idle.webm
```

2. **Generate anchor timeline**:
```bash
docker compose exec worker python -m anchor_timeline \
  --avatar-id realistic_female_v1 \
  --input idle.webm
```

3. **Verify in browser**:
   - Open demo: `http://localhost:8080`
   - Press `T` key to toggle tracking debug overlay
   - Watch anchors follow face during idle video playback

### Features

- ✅ CPU-only (MediaPipe Face Mesh)
- ✅ ~3-5 seconds processing per 4-second video
- ✅ Backwards compatible (falls back to static anchors if timeline missing)
- ✅ Debug visualization (`T` key in browser)
- ✅ Works with existing calibration tools

### Documentation

See [PHASE1_TRACKING.md](PHASE1_TRACKING.md) for complete guide including:
- Timeline generation parameters
- Troubleshooting
- Performance tuning
- Developer notes

## Deployment to DigitalOcean

### 1. Create a Droplet

- Size: Basic, 2GB RAM minimum (4GB recommended)
- Image: Ubuntu 22.04 LTS
- Region: Choose nearest to your users

### 2. Install Docker

```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt-get update && apt-get install -y docker-compose-plugin
```

### 3. Deploy the Service

```bash
# Clone or copy your project
git clone <your-repo> avatar-services
cd avatar-services

# Create .env file from template
cp .env.example .env

# Get your droplet IP
DROPLET_IP=$(curl -4 -s ifconfig.me)

# Update .env with your droplet IP
sed -i "s/YOUR_DROPLET_IP_HERE/$DROPLET_IP/g" .env

# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f
```

**Important:** If you change `AUDIO_BASE_URL` after initial deployment, you must clear the cache:
```bash
docker compose exec valkey valkey-cli FLUSHDB
docker compose restart api
```

### 4. Configure Firewall

```bash
ufw allow 8080/tcp  # Nginx (web demo + audio)
ufw allow 8000/tcp  # API (optional, can proxy through Nginx)
ufw enable
```

### 5. (Optional) Add SSL with Caddy

For production, consider using Caddy as a reverse proxy with automatic HTTPS:

```bash
# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Configure Caddy (/etc/caddy/Caddyfile)
your-domain.com {
    reverse_proxy localhost:8080
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `valkey` | Valkey/Redis host |
| `VALKEY_PORT` | `6379` | Valkey/Redis port |
| `DATA_DIR` | `/data` | Shared data directory |
| `AUDIO_BASE_URL` | `http://localhost:8080/audio` | Base URL for audio files |
| `SYNC_TIMEOUT_SECONDS` | `60` | Sync render timeout |
| `MAX_CONCURRENT_REQUESTS` | `10` | API concurrency limit |
| `PIPER_MODEL` | `/opt/piper/voices/en_US-lessac-medium.onnx` | Default voice model |
| `LOG_LEVEL` | `INFO` | Logging level |

### Scaling

To run multiple workers:

```bash
docker compose up -d --scale worker=3
```

## Performance Notes

### Caching

- Results are cached by `hash(voice_id + speed + text)`
- Cache TTL: 7 days
- Subsequent requests for the same content return instantly

### Processing Times

Typical processing times on a 2-core droplet:
- Short text (< 100 chars): 1-3 seconds
- Medium text (100-500 chars): 3-8 seconds
- Long text (500-2000 chars): 8-20 seconds

### Memory Usage

- API container: ~100MB
- Worker container: ~300-500MB (during TTS processing)
- Valkey container: ~50MB base + cache data

### Bandwidth

- OGG/Opus audio: ~6KB/second of speech
- WAV audio: ~86KB/second (fallback if OGG conversion fails)

## Troubleshooting

### Worker Not Processing Jobs

```bash
# Check worker logs
docker compose logs worker

# Verify Valkey connection
docker compose exec valkey valkey-cli ping

# Check queue length
docker compose exec valkey valkey-cli llen avatar:jobs
```

### Audio Not Playing

**If audio URLs show `localhost` instead of your droplet IP:**

This happens when cached responses contain old URLs. Clear the cache:
```bash
# Clear Valkey cache
docker compose exec valkey valkey-cli FLUSHDB

# Restart API to ensure fresh responses
docker compose restart api
```

**Other audio issues:**

1. Check CORS headers in browser console
2. Verify audio URL is accessible: `curl http://your-droplet-ip:8080/audio/<file>.ogg`
3. Ensure you're accessing the demo from the droplet IP, not `localhost`
4. Check Nginx logs: `docker compose logs nginx`

### Out of Memory

Increase worker memory or reduce concurrent requests:

```yaml
# docker-compose.yml
worker:
  deploy:
    resources:
      limits:
        memory: 1G
```

## Development

### Running Locally (without Docker)

```bash
# Start Valkey
docker run -d -p 6379:6379 valkey/valkey:7.2-alpine

# Install API dependencies
cd api && pip install -r requirements.txt

# Run API
VALKEY_HOST=localhost uvicorn main:app --reload

# In another terminal, install worker dependencies
cd worker && pip install -r requirements.txt

# Install Piper and Rhubarb (see Dockerfiles for URLs)

# Run worker
VALKEY_HOST=localhost python worker.py
```

### Project Structure

```
avatar-services/
├── docker-compose.yml      # Service orchestration
├── docker/
│   ├── Dockerfile.api      # API container
│   ├── Dockerfile.worker   # Worker with TTS/lip-sync
│   └── nginx.conf          # Static file serving
├── api/
│   ├── main.py             # FastAPI application
│   ├── valkey.py           # Valkey client & queue
│   ├── models.py           # Pydantic models
│   └── requirements.txt
├── worker/
│   ├── worker.py           # Job processor
│   ├── tts.py              # Piper TTS wrapper
│   ├── lipsync.py          # Rhubarb wrapper
│   └── requirements.txt
├── web-demo/
│   ├── index.html          # Demo page
│   ├── demo.js             # Canvas animation
│   └── assets/             # (optional sprites)
├── scripts/
│   └── download_voices.sh  # Additional voices
└── README.md
```

## Photoreal Avatar System

The web demo uses a sophisticated photoreal compositor that blends real photo/video assets in real-time.

### How It Works

1. **Layered Composition:**
   - Base face layer (static image or idle video loop)
   - Eyes layer (blends between open/half/closed states)
   - Mouth layer (extracts frames from spritesheet based on visemes)
   - All layers composited with alpha masks for seamless blending

2. **Animation Timeline:**
   - API returns mouth cues (viseme + timestamp)
   - API returns eye events (blinks, saccades)
   - Compositor interpolates smoothly between states
   - No frame snapping or jarring transitions

3. **Micro-Motion (Idle):**
   - Subtle head bobbing (2-3px)
   - Slight rotation/tilt
   - Breathing motion (scale pulsing)
   - Natural blinks every 3-6 seconds
   - All configurable per-avatar

### Calibration

The built-in calibration system allows fine-tuning avatar positioning without editing code:

1. Enable "Calibration Mode" checkbox
2. Green rectangle shows selected anchor (mouth or eyes)
3. Use keyboard controls:
   - **Arrow keys:** Move anchor position
   - **Shift+Arrows:** Resize anchor
   - **Tab:** Switch between mouth/eyes
   - **C:** Toggle calibration mode
4. Adjustments save to browser localStorage
5. Copy final coordinates to `manifest.json` for persistence

### Performance

- All rendering happens in browser using Canvas 2D
- No WebGL required (works on all devices)
- Typical frame rate: 60fps
- Total asset size per avatar: <1MB (with optimization)
- Instant loading with cached assets

## Future Enhancements

- [ ] DigitalOcean Spaces integration for audio storage
- [ ] WebSocket streaming for real-time playback
- [ ] Additional language support
- [ ] Additional photoreal avatar packs
- [ ] Emotion detection and dynamic expression switching
- [ ] Background music mixing
- [ ] WebGL renderer for advanced effects
- [ ] Video export functionality

## License

MIT License - See LICENSE file for details.

## Credits

- [Piper TTS](https://github.com/rhasspy/piper) - Fast local neural TTS
- [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync) - Automatic lip-sync
- [Valkey](https://valkey.io/) - Redis-compatible data store
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
