#!/bin/bash
# Persistent brainstorm visual companion server for Leerio.
# Usage: run via Claude Code Bash with run_in_background: true
#
# Unlike the superpowers start-server.sh, this does NOT set BRAINSTORM_OWNER_PID,
# so the server won't exit when the parent bash process dies.
# It will only exit on idle timeout (30 min) or explicit stop.

SCRIPT_DIR="C:/Users/User/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/skills/brainstorming/scripts"
PROJECT_DIR="E:/leerio"

SESSION_ID="$$-$(date +%s)"
SCREEN_DIR="${PROJECT_DIR}/.superpowers/brainstorm/${SESSION_ID}"
mkdir -p "$SCREEN_DIR"

cd "$SCRIPT_DIR"

# No BRAINSTORM_OWNER_PID = server stays alive until idle timeout (30 min)
exec env \
  BRAINSTORM_DIR="$SCREEN_DIR" \
  BRAINSTORM_HOST="127.0.0.1" \
  BRAINSTORM_URL_HOST="localhost" \
  node server.js
