#!/bin/bash

# Exit on any error
set -e

echo "=========================================="
echo "         Simba Linux Installer            "
echo "=========================================="

echo "🚀 [1/4] Checking prerequisites..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check for docker-compose or docker compose
DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "❌ docker-compose is neither available as 'docker compose' nor 'docker-compose'. Please install it first."
    exit 1
fi

echo "✅ Docker and Docker Compose are available."

echo "🛠️  [2/4] Setting up environment..."

# Initialize .env file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example. Please review and update the variables if necessary."
    else
        echo "⚠️ .env.example not found. Creating a blank .env file."
        touch .env
    fi
else
    echo "✅ .env file already exists."
fi

# Create required network if not already present
echo "🌐 [3/4] Creating Docker network 'simba_network'..."
if ! docker network ls | grep -q "simba_network"; then
    docker network create simba_network
    echo "✅ Created Docker network 'simba_network'."
else
    echo "✅ Docker network 'simba_network' already exists."
fi

# Make necessary directories to prevent permission issues when Docker creates them as root
echo "📁 [4/4] Creating necessary local volumes..."
mkdir -p uploads markdown vector_stores frontend/node_modules

echo "=========================================="
echo "    🐳 Building and Starting Services     "
echo "=========================================="

# Build and start services in the background
cd docker
$DOCKER_COMPOSE_CMD up --build -d

echo "=========================================================================="
echo "🎉 Installation initiated successfully!"
echo "Services are starting in the background. Note: The first build may take several minutes."
echo ""
echo "To check the logs and see when the services are ready, run:"
echo "   cd docker && $DOCKER_COMPOSE_CMD logs -f"
echo ""
echo "Once fully started, access the platform at:"
echo "   🖥️  Frontend:   http://<server-ip>:5173"
echo "   🔌 Backend API: http://<server-ip>:8000"
echo "=========================================================================="
