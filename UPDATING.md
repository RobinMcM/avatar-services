# Updating Docker Containers

This guide covers how to update and rebuild your avatar-services Docker containers in various scenarios.

## Quick Reference

```bash
# After code changes - rebuild and restart
docker compose up -d --build

# Pull latest code and update
git pull
docker compose up -d --build

# Force complete rebuild (no cache)
docker compose build --no-cache
docker compose up -d

# Update specific service only
docker compose up -d --build api
docker compose up -d --build worker
```

---

## Scenarios

### 1. After Making Code Changes (Local Development)

When you modify Python code, HTML, or configuration files:

```bash
cd /root/avatar-services

# Rebuild and restart affected containers
docker compose up -d --build

# Or rebuild specific service
docker compose up -d --build api      # If you changed API code
docker compose up -d --build worker   # If you changed worker code
```

**Note:** Most code changes require a rebuild. The `--build` flag ensures Docker rebuilds the images before starting containers.

### 2. Pulling Updates from Git

When you or a team member pushes updates to GitHub:

```bash
cd /root/avatar-services

# Pull latest code
git pull origin main

# Rebuild and restart all services
docker compose up -d --build

# View logs to verify update
docker compose logs -f
```

### 3. Updating Python Dependencies

When `requirements.txt` files change:

```bash
cd /root/avatar-services

# Force rebuild without cache (ensures fresh pip install)
docker compose build --no-cache api
docker compose build --no-cache worker

# Restart services
docker compose up -d
```

### 4. Updating Nginx Configuration

When modifying `docker/nginx.conf`:

```bash
cd /root/avatar-services

# Rebuild nginx (it's a lightweight image, very fast)
docker compose up -d --build nginx

# Or just restart if only config changed
docker compose restart nginx
```

### 5. Updating Environment Variables

When changing environment variables in `docker-compose.yml`:

```bash
cd /root/avatar-services

# Recreate containers with new environment
docker compose up -d --force-recreate

# Or for specific service
docker compose up -d --force-recreate api
```

### 6. Clean Rebuild (Nuclear Option)

When things are acting weird or you want a completely fresh start:

```bash
cd /root/avatar-services

# Stop all containers
docker compose down

# Remove all containers, networks, and volumes
docker compose down -v

# Remove old images (optional)
docker compose down --rmi all

# Rebuild from scratch
docker compose build --no-cache

# Start fresh
docker compose up -d

# Verify everything is working
docker compose ps
docker compose logs -f
```

### 7. Updating Base Images

To get the latest Python, Nginx, or Valkey versions:

```bash
cd /root/avatar-services

# Pull latest base images
docker compose pull

# Rebuild with new base images
docker compose build --no-cache

# Restart
docker compose up -d
```

---

## Production Deployment Updates

### Zero-Downtime Update (with multiple workers)

```bash
cd /root/avatar-services

# Pull latest code
git pull origin main

# Scale workers down to 1
docker compose up -d --scale worker=1

# Rebuild API (no downtime with 2 uvicorn workers)
docker compose up -d --build --no-deps api

# Rebuild worker
docker compose up -d --build --no-deps worker

# Scale workers back up
docker compose up -d --scale worker=3

# Rebuild nginx (very fast)
docker compose up -d --build nginx
```

### Standard Production Update

```bash
cd /root/avatar-services

# Pull latest
git pull origin main

# Rebuild and restart (brief downtime)
docker compose up -d --build

# Monitor logs for errors
docker compose logs -f --tail=100

# Check health
curl http://localhost:8000/health
```

### Rollback to Previous Version

If an update causes issues:

```bash
cd /root/avatar-services

# Revert to previous commit
git log --oneline -5  # Find the previous commit hash
git reset --hard <previous-commit-hash>

# Rebuild with old code
docker compose up -d --build

# Or checkout specific commit
git checkout <commit-hash>
docker compose up -d --build
```

---

## Updating Individual Components

### Update Piper TTS Voices

```bash
# Download new voices
cd /root/avatar-services
./scripts/download_voices.sh

# Copy to running worker container
docker cp voices/. avatar-worker:/opt/piper/voices/

# Or mount as volume in docker-compose.yml:
# volumes:
#   - ./voices:/opt/piper/voices:ro
```

### Update Nginx Static Files (Web Demo)

```bash
# Edit web-demo files
cd /root/avatar-services/web-demo
# ... make changes ...

# Restart nginx (no rebuild needed, volume mounted)
docker compose restart nginx

# Or if you want to rebuild
docker compose up -d --build nginx
```

---

## Troubleshooting Updates

### Containers Won't Start After Update

```bash
# Check what's wrong
docker compose ps
docker compose logs

# Try clean rebuild
docker compose down
docker compose up -d --build
```

### Port Conflicts

```bash
# Check if ports are in use
sudo lsof -i :8000  # API port
sudo lsof -i :8080  # Nginx port
sudo lsof -i :6379  # Valkey port

# Stop conflicting services or change ports in docker-compose.yml
```

### Out of Disk Space

```bash
# Clean up old Docker resources
docker system prune -a --volumes

# Remove specific old images
docker images | grep avatar
docker rmi <image-id>

# Remove old audio files
docker compose exec api rm -rf /data/audio/*.ogg
```

### Worker Not Processing After Update

```bash
# Check worker logs
docker compose logs worker

# Restart worker
docker compose restart worker

# Check Valkey connection
docker compose exec worker ping valkey -c 1

# Check job queue
docker compose exec valkey valkey-cli llen avatar:jobs
```

### Cache Issues

```bash
# Clear Valkey cache
docker compose exec valkey valkey-cli FLUSHDB

# Or clear specific cache pattern
docker compose exec valkey valkey-cli --scan --pattern "avatar:cache:*" | xargs docker compose exec valkey valkey-cli DEL
```

---

## Monitoring After Updates

### Check All Services Are Running

```bash
docker compose ps

# Should show all services as "Up"
```

### Watch Logs for Errors

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f worker
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Test render
curl -X POST http://localhost:8000/v1/avatar/render \
  -H "Content-Type: application/json" \
  -d '{"text": "Update test", "voice_id": "en_US-lessac-medium", "speed": 1.0}'

# Test web demo
curl -I http://localhost:8080
```

### Check Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

---

## Automation

### Auto-Update Script

Create `/root/avatar-services/update.sh`:

```bash
#!/bin/bash
set -e

cd /root/avatar-services

echo "=== Pulling latest code ==="
git pull origin main

echo "=== Backing up current state ==="
docker compose ps > .backup-state-$(date +%Y%m%d-%H%M%S).txt

echo "=== Rebuilding containers ==="
docker compose up -d --build

echo "=== Waiting for services to start ==="
sleep 5

echo "=== Checking health ==="
curl -f http://localhost:8000/health || echo "Health check failed!"

echo "=== Update complete ==="
docker compose ps
```

Make it executable:
```bash
chmod +x /root/avatar-services/update.sh
```

Run updates:
```bash
cd /root/avatar-services
./update.sh
```

### Scheduled Updates (Optional)

```bash
# Add to crontab for weekly updates
crontab -e

# Add this line (updates every Sunday at 2 AM)
0 2 * * 0 cd /root/avatar-services && git pull && docker compose up -d --build >> /var/log/avatar-update.log 2>&1
```

---

## Best Practices

1. **Always check logs** after updates: `docker compose logs -f`
2. **Test in development** before updating production
3. **Backup data volumes** before major updates
4. **Keep git history clean** for easy rollbacks
5. **Monitor resource usage** after updates
6. **Document changes** in commit messages
7. **Use semantic versioning** for releases (tags)

---

## Quick Commands Cheat Sheet

```bash
# Standard update
git pull && docker compose up -d --build

# View what's running
docker compose ps

# Follow logs
docker compose logs -f

# Restart specific service
docker compose restart <service-name>

# Stop everything
docker compose down

# Start everything
docker compose up -d

# Clean rebuild
docker compose down && docker compose build --no-cache && docker compose up -d

# Check health
curl http://localhost:8000/health

# Access container shell
docker compose exec api bash
docker compose exec worker bash

# View container resource usage
docker stats
```

---

For more help, see:
- Main documentation: `README.md`
- Docker Compose docs: https://docs.docker.com/compose/
- Project repository: https://github.com/RobinMcM/avatar-services
