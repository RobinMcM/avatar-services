# Avatar Service

A production-ready avatar animation service that generates TTS audio and synchronized lip/eye animations for 2D avatars rendered in the browser.

## Features

- **Text-to-Speech**: Uses [Piper TTS](https://github.com/rhasspy/piper) for high-quality, local CPU-based speech synthesis
- **Lip Sync**: Extracts mouth animation cues using [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync)
- **Eye Animation**: Generates realistic blink and saccade events
- **Caching**: Results cached by content hash for instant repeated requests
- **Job Queue**: Asynchronous processing via Valkey (Redis-compatible)
- **Web Demo**: Canvas-based 2D avatar with smooth interpolation

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

# Update environment variables
export AUDIO_BASE_URL="http://your-droplet-ip:8080/audio"

# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f
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

1. Check CORS headers in browser console
2. Verify audio URL is accessible: `curl http://localhost:8080/audio/<file>.ogg`
3. Check Nginx logs: `docker compose logs nginx`

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

## Future Enhancements

- [ ] DigitalOcean Spaces integration for audio storage
- [ ] WebSocket streaming for real-time playback
- [ ] Additional language support
- [ ] Custom avatar sprite support
- [ ] Emotion detection and expression
- [ ] Background music mixing

## License

MIT License - See LICENSE file for details.

## Credits

- [Piper TTS](https://github.com/rhasspy/piper) - Fast local neural TTS
- [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync) - Automatic lip-sync
- [Valkey](https://valkey.io/) - Redis-compatible data store
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
