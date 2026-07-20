#!/bin/bash

# Trap signals to ensure clean exit if running interactively
trap "exit" INT TERM ERR

echo "🚀 Starting Simba Environment Setup (vLLM-MLX Edition)..."

# Find poetry executable
POETRY_BIN=$(which poetry)
if [ -z "$POETRY_BIN" ] && [ -f "$HOME/.local/bin/poetry" ]; then
    POETRY_BIN="$HOME/.local/bin/poetry"
fi

# Fallback to just "poetry" if we can't find an absolute path
if [ -z "$POETRY_BIN" ]; then
    POETRY_BIN="poetry"
fi

echo "✅ Using poetry command: $POETRY_BIN"

# Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "⚠️  No .env or .env.example found. Please create a .env file."
    fi
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Create/Update frontend .env to point to Simba on 8081
echo "📝 Updating frontend/.env..."
echo "VITE_API_URL=http://localhost:8081" > frontend/.env

# Check if redis is running (required for Celery)
if ! nc -z localhost 6379 > /dev/null 2>&1; then
    echo "🔄 Redis is not running on port 6379..."
    if command -v redis-server >/dev/null 2>&1; then
        echo "Starting local redis-server..."
        redis-server --daemonize yes
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "🐳 Starting Redis via Docker Compose..."
        docker-compose -f docker/redis-only.yml up -d
    else
        echo "⚠️  Redis not found. Parsers (Celery) might not work correctly."
    fi
else
    echo "✅ Redis is already running."
fi

# Start vLLM-MLX server
echo "🧠 Starting vLLM-MLX server on port 8000..."
# Running it in the background. We use port 8000 as requested by user.
$POETRY_BIN run vllm-mlx serve mlx-community/Llama-3.2-3B-Instruct-4bit --port 8000 --continuous-batching > vllm.log 2>&1 &

# Wait a bit for vLLM to initialize (it can be slow)
echo "⏳ Waiting for vLLM to start (check vllm.log for details)..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s http://localhost:8000/v1/models > /dev/null || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  sleep 2
  echo -n "."
  RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ vLLM failed to start within timeout. Check vllm.log."
else
    echo "✅ vLLM is ready!"
fi

echo "✅ Setup complete. Starting Simba services..."
echo "------------------------------------------------"
echo "🧠 vLLM Server: http://localhost:8000"
echo "🖥️  Simba API:   http://localhost:8081"
echo "🌐 React Frontend: http://localhost:5173"
echo "------------------------------------------------"

# Start the Simba server on port 8081
export SIMBA_PORT=8081
echo "📡 Starting Simba FastAPI server on port 8081..."
$POETRY_BIN run simba server --port 8081 > simba.log 2>&1 &

# Start the worker
echo "⚙️  Starting Celery worker (parsers)..."
$POETRY_BIN run simba parsers &

# Start the frontend
echo "🎨 Starting React frontend..."
$POETRY_BIN run simba front &

# Wait for all processes to finish
wait
