#!/bin/bash
# Azure / AWS App Service startup script
# Environment passes the port via the $PORT environment variable

set -e

echo "=== AcmeAssist Startup (Supabase Cloud Mode) ==="
echo "PORT: ${PORT:-8000}"

# No local indexing required - we use live Supabase Cloud!

echo "Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
