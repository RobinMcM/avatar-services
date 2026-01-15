#!/bin/bash
#
# Avatar Services Update Script
# 
# This script safely updates the avatar-services deployment by:
# 1. Pulling latest code from git
# 2. Backing up current state
# 3. Rebuilding Docker containers
# 4. Running health checks
#
# Usage: ./update.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=== Avatar Services Update Script ===${NC}\n"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found. Are you in the avatar-services directory?${NC}"
    exit 1
fi

# Check if git is clean (optional warning)
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${YELLOW}Warning: You have uncommitted changes${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: Pull latest code
echo -e "${BLUE}Step 1: Pulling latest code from git${NC}"
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "Current commit: $CURRENT_COMMIT"

if git pull origin main; then
    NEW_COMMIT=$(git rev-parse HEAD)
    if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
        echo -e "${GREEN}Already up to date${NC}"
    else
        echo -e "${GREEN}Updated to commit: $NEW_COMMIT${NC}"
    fi
else
    echo -e "${RED}Failed to pull from git${NC}"
    exit 1
fi

# Step 2: Backup current state
echo -e "\n${BLUE}Step 2: Backing up current state${NC}"
BACKUP_FILE=".backup-state-$(date +%Y%m%d-%H%M%S).txt"
docker compose ps > "$BACKUP_FILE"
echo "Backup saved to: $BACKUP_FILE"

# Step 3: Rebuild containers
echo -e "\n${BLUE}Step 3: Rebuilding Docker containers${NC}"
if docker compose up -d --build; then
    echo -e "${GREEN}Containers rebuilt successfully${NC}"
else
    echo -e "${RED}Failed to rebuild containers${NC}"
    echo -e "${YELLOW}Check logs with: docker compose logs${NC}"
    exit 1
fi

# Step 4: Wait for services to start
echo -e "\n${BLUE}Step 4: Waiting for services to start${NC}"
for i in {1..10}; do
    echo -n "."
    sleep 1
done
echo ""

# Step 5: Health checks
echo -e "\n${BLUE}Step 5: Running health checks${NC}"

# Check if containers are running
echo "Checking container status..."
if docker compose ps | grep -q "Exit"; then
    echo -e "${RED}Some containers have exited!${NC}"
    docker compose ps
    exit 1
else
    echo -e "${GREEN}All containers are running${NC}"
fi

# Check API health endpoint
echo "Checking API health endpoint..."
if curl -f -s http://localhost:8000/health > /dev/null; then
    HEALTH_OUTPUT=$(curl -s http://localhost:8000/health)
    echo -e "${GREEN}API is healthy${NC}"
    echo "$HEALTH_OUTPUT" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_OUTPUT"
else
    echo -e "${RED}API health check failed!${NC}"
    echo -e "${YELLOW}Check API logs with: docker compose logs api${NC}"
    exit 1
fi

# Check web demo
echo "Checking web demo..."
if curl -f -s -I http://localhost:8080 > /dev/null; then
    echo -e "${GREEN}Web demo is accessible${NC}"
else
    echo -e "${RED}Web demo is not accessible!${NC}"
    echo -e "${YELLOW}Check Nginx logs with: docker compose logs nginx${NC}"
fi

# Step 6: Display status
echo -e "\n${BLUE}=== Update Complete ===${NC}\n"
echo "Container Status:"
docker compose ps

echo -e "\n${GREEN}✓ Update successful!${NC}"
echo -e "\nYou can:"
echo "  - View logs: docker compose logs -f"
echo "  - Check health: curl http://localhost:8000/health"
echo "  - Access demo: http://localhost:8080"
echo "  - Rollback: git reset --hard $CURRENT_COMMIT && docker compose up -d --build"

# Cleanup old backups (keep last 5)
echo -e "\nCleaning up old backups..."
ls -t .backup-state-*.txt 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
