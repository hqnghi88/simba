#!/bin/bash
set -e

# Run database migrations if necessary
echo "🚀 Running database migrations..."
if command -v supabase &> /dev/null; then
  make migrate || echo "⚠️ Migration failed, but continuing..."
else
  echo "ℹ️ supabase CLI not found. (Tables will be created by SQLAlchemy if using Postgres)"
fi

# Execute the main container command
echo "🎬 Starting application..."
exec "$@"