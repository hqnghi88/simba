#!/bin/bash

# Kill all background processes on exit
trap "exit" INT TERM ERR
trap "kill 0" EXIT

echo "🚀 Starting Simba Environment Setup..."

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

# Create frontend .env if it doesn't exist
if [ ! -f frontend/.env ]; then
    echo "📝 Creating frontend/.env..."
    echo "VITE_API_URL=http://localhost:8000" > frontend/.env
fi

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
        echo "⚠️  Redis not found (tried local and docker). Parsers (Celery) might not work correctly."
        echo "Please install redis: 'brew install redis' or start it manually."
    fi
else
    echo "✅ Redis is already running."
fi

echo "✅ Setup complete. Starting Simba services..."
echo "------------------------------------------------"
echo "🖥️  FastAPI Server: http://localhost:8000"
echo "🌐 React Frontend: http://localhost:5173"
echo "------------------------------------------------"

# Start the server
echo "📡 Starting FastAPI server..."
python3 -m poetry run simba server &

# Start the worker
echo "⚙️  Starting Celery worker (parsers)..."
python3 -m poetry run simba parsers &

# Start the frontend
echo "🎨 Starting React frontend..."
python3 -m poetry run simba front &

# Wait for all processes to finish
wait
