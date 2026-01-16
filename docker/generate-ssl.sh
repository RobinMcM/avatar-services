#!/bin/bash
# Generate self-signed SSL certificate for avatar-services

mkdir -p /root/avatar-services/docker/ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /root/avatar-services/docker/ssl/nginx-selfsigned.key \
  -out /root/avatar-services/docker/ssl/nginx-selfsigned.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=138.68.187.23"

echo "✓ SSL certificate generated successfully"
echo "  Certificate: docker/ssl/nginx-selfsigned.crt"
echo "  Key: docker/ssl/nginx-selfsigned.key"
