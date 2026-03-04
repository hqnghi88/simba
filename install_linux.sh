#!/bin/bash

# Exit on any error
set -e

echo "=========================================="
echo "         Simba Linux Installer            "
echo "=========================================="

echo "🚀 [1/5] Checking prerequisites..."

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

echo "🛠️  [2/5] Setting up environment..."

# Initialize .env file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example."
    else
        echo "⚠️ .env.example not found. Creating a minimal .env file."
        echo "OPENAI_API_KEY=" > .env
    fi
else
    echo "✅ .env file already exists."
fi

# Try to detect Public IP for Frontend access
echo "🔍 Detecting server IP for frontend configuration..."
SERVER_IP=$(curl -s ifconfig.me || echo "localhost")
echo "   Detected IP: $SERVER_IP"

read -p "❓ Is this the correct IP/Hostname to access the platform? (y/n/manual): " ip_confirm
if [[ "$ip_confirm" == "manual" ]]; then
    read -p "   Enter IP/Hostname: " SERVER_IP
elif [[ "$ip_confirm" != "y" ]]; then
    SERVER_IP="localhost"
fi

# Update VITE_API_URL in .env
if grep -q "VITE_API_URL" .env; then
    sed -i "s|VITE_API_URL=.*|VITE_API_URL=http://$SERVER_IP:8000|g" .env
else
    echo "VITE_API_URL=http://$SERVER_IP:8000" >> .env
fi
echo "✅ Configured VITE_API_URL=http://$SERVER_IP:8000"

# Create required network if not already present
echo "🌐 [3/5] Checking Docker network 'simba_network'..."
if ! docker network ls | grep -q "simba_network"; then
    docker network create simba_network
    echo "✅ Created Docker network 'simba_network'."
else
    echo "✅ Docker network 'simba_network' already exists."
fi

# Make necessary directories to prevent permission issues when Docker creates them as root
echo "📁 [4/5] Creating necessary local volumes..."
mkdir -p uploads markdown vector_stores frontend/node_modules

echo "=========================================="
echo "    🐳 [5/5] Building and Starting Services     "
echo "=========================================="

# Build and start services in the background
cd docker
$DOCKER_COMPOSE_CMD up --build -d

echo "=========================================================================="
echo "🎉 Simba installation initiated successfully!"
echo "Services are starting in the background. Note: The first build may take several minutes."
echo ""
echo "To check the logs and see when the services are ready, run:"
echo "   cd docker && $DOCKER_COMPOSE_CMD logs -f"
echo ""
echo "Once fully started, access the platform at:"
echo "   🖥️  Frontend:   http://$SERVER_IP:5173"
echo "   🔌 Backend API: http://$SERVER_IP:8000"
echo "=========================================================================="
