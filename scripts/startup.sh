#!/bin/bash

# Wait for Docker to be ready (up to 60 seconds)
echo "Waiting for Docker..."
for i in $(seq 1 30); do
  if docker info > /dev/null 2>&1; then
    echo "Docker is ready."
    break
  fi
  sleep 2
done

if ! docker info > /dev/null 2>&1; then
  echo "Docker did not start in time. Exiting."
  exit 1
fi

cd /Users/kapilbathija/dev/claude-local-observability
docker compose up -d
