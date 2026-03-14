#!/bin/sh
# Ensure data directory is writable by appuser (don't chown git-tracked files)
mkdir -p /data/users 2>/dev/null || true
chown appuser:appuser /data /data/users 2>/dev/null || true

exec gosu appuser uvicorn server.api:app --host 0.0.0.0 --port 8000
