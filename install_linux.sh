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

echo "�️  [2/5] Setting up environment..."

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

# Check and fix port conflicts
echo "🔍 Checking for port conflicts..."
function is_port_in_use() {
    local PORT=$1
    (command -v ss >/dev/null && ss -tuln | grep -q ":$PORT ") || \
    (command -v netstat >/dev/null && netstat -tuln | grep -q ":$PORT ") || \
    (command -v lsof >/dev/null && lsof -i :$PORT >/dev/null)
}

function check_and_fix_port() {
    local PORT_VAR=$1
    local DEFAULT_PORT=$2
    local ALT_PORT=$3
    
    if is_port_in_use "$DEFAULT_PORT"; then
        echo "⚠️  Port $DEFAULT_PORT is already in use."
        if ! grep -q "^$PORT_VAR=" .env; then
            echo "   Configuring $PORT_VAR=$ALT_PORT in .env to avoid conflict."
            echo "$PORT_VAR=$ALT_PORT" >> .env
        else
            # Also check if the current value in .env is the one in use
            CURRENT_VAL=$(grep "^$PORT_VAR=" .env | cut -d'=' -f2)
            if [ "$CURRENT_VAL" == "$DEFAULT_PORT" ]; then
                echo "   Updating $PORT_VAR to $ALT_PORT in .env (previous value was conflicted)."
                sed -i "s|^$PORT_VAR=.*|$PORT_VAR=$ALT_PORT|g" .env
            fi
        fi
    fi
}

check_and_fix_port "REDIS_PORT" 6379 6380
check_and_fix_port "POSTGRES_PORT" 5432 5433
check_and_fix_port "SERVER_PORT" 8000 8080
check_and_fix_port "FRONTEND_PORT" 5173 5174

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

# Extract actual server port for VITE_API_URL
ACTUAL_SERVER_PORT=$(grep "SERVER_PORT=" .env | cut -d'=' -f2 || echo "8000")

# Update VITE_API_URL in .env
if grep -q "VITE_API_URL" .env; then
    sed -i "s|VITE_API_URL=.*|VITE_API_URL=http://$SERVER_IP:$ACTUAL_SERVER_PORT|g" .env
else
    echo "VITE_API_URL=http://$SERVER_IP:$ACTUAL_SERVER_PORT" >> .env
fi

# Set default RUNTIME to empty to avoid Docker Compose warnings
if ! grep -q "RUNTIME=" .env; then
    echo "RUNTIME=" >> .env
fi
echo "✅ Configuration updated in .env (using port: $ACTUAL_SERVER_PORT)"

# Attempt to clean up manually created network to avoid Compose label conflicts
if docker network ls | grep -q "simba_network"; then
    echo "🌐 [3/5] Cleaning up existing 'simba_network' to let Docker Compose manage it..."
    docker network rm simba_network || echo "⚠️ Could not remove network, Docker Compose will try to handle it."
else
    echo "🌐 [3/5] Docker Compose will manage the 'simba_network' automatically."
fi

# Make necessary directories to prevent permission issues when Docker creates them as root
echo "📁 [4/5] Creating necessary local volumes..."
mkdir -p uploads markdown vector_stores frontend/node_modules

echo "=========================================="
echo "    🐳 [5/5] Building and Starting Services     "
echo "=========================================="

# Build and start services in the background
echo "🏗️  Running: $DOCKER_COMPOSE_CMD -f docker/docker-compose.yml up --build -d"
$DOCKER_COMPOSE_CMD -f docker/docker-compose.yml up --build -d

# Extract actual ports used for final output
ACTUAL_SERVER_PORT=$(grep "SERVER_PORT=" .env | cut -d'=' -f2 || echo "8000")
ACTUAL_FRONTEND_PORT=$(grep "FRONTEND_PORT=" .env | cut -d'=' -f2 || echo "5173")

echo "=========================================================================="
echo "🎉 Simba installation initiated successfully!"
echo "Services are starting in the background. Note: The first build may take several minutes."
echo ""
echo "To check the logs and see when the services are ready, run:"
echo "   $DOCKER_COMPOSE_CMD -f docker/docker-compose.yml logs -f"
echo ""
echo "Once fully started, access the platform at:"
echo "   🖥️  Frontend:   http://$SERVER_IP:$ACTUAL_FRONTEND_PORT"
echo "   🔌 Backend API: http://$SERVER_IP:$ACTUAL_SERVER_PORT"
echo "=========================================================================="
