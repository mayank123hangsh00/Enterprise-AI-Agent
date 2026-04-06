#!/bin/bash
# Azure App Service startup script
# Azure passes the port via the $PORT environment variable

set -e

echo "=== AcmeAssist Startup ==="
echo "PORT: ${PORT:-8000}"

# Build vector index if not exists (handles cold start on Azure)
if [ ! -f "vectorstore/index.faiss" ]; then
  echo "Vector index not found — building now..."
  python scripts/index_documents.py
  echo "Index built successfully."
else
  echo "Vector index found — skipping rebuild."
fi

echo "Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
