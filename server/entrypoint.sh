#!/bin/sh
# Ensure data directory is writable by appuser
chown -R appuser:appuser /data 2>/dev/null || true

exec gosu appuser uvicorn server.api:app --host 0.0.0.0 --port 8000
