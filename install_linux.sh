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
    # Check for :PORT followed by space, tab, or end of line/colon
    (command -v ss >/dev/null && ss -tuln | grep -qE "[:.]$PORT(\s|$)") || \
    (command -v netstat >/dev/null && netstat -tuln | grep -qE "[:.]$PORT(\s|$)") || \
    (command -v lsof >/dev/null && lsof -i :$PORT >/dev/null 2>&1)
}

function check_and_fix_port() {
    local PORT_VAR=$1
    local DEFAULT_PORT=$2
    local START_PORT=$3
    
    # Extract current value and strip whitespace
    local CURRENT_VAL=$(grep "^$PORT_VAR=" .env | cut -d'=' -f2 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || echo "")
    
    # If empty or not set, use default
    if [ -z "$CURRENT_VAL" ]; then
        CURRENT_VAL=$DEFAULT_PORT
    fi
    
    if is_port_in_use "$CURRENT_VAL"; then
        echo "⚠️  Port $CURRENT_VAL (for $PORT_VAR) is already in use."
        
        local NEW_PORT=$START_PORT
        while is_port_in_use "$NEW_PORT"; do
            NEW_PORT=$((NEW_PORT + 1))
        done
        
        echo "   Found free port: $NEW_PORT. Updating .env..."
        
        if ! grep -q "^$PORT_VAR=" .env; then
            echo "$PORT_VAR=$NEW_PORT" >> .env
        else
            sed -i "s|^$PORT_VAR=.*|$PORT_VAR=$NEW_PORT|g" .env
        fi
        export $PORT_VAR=$NEW_PORT
    else
        export $PORT_VAR=$CURRENT_VAL
    fi
}

check_and_fix_port "REDIS_PORT" 6379 6380
check_and_fix_port "POSTGRES_PORT" 5432 5433
check_and_fix_port "SERVER_PORT" 8000 8080
check_and_fix_port "FRONTEND_PORT" 5173 5174

# Force export all variables from .env to the current shell for Docker Compose
set -a
[ -f .env ] && . ./.env
set +a

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
ACTUAL_SERVER_PORT=${SERVER_PORT:-8000}

# Update VITE_API_URL in .env
if grep -q "VITE_API_URL" .env; then
    sed -i "s|VITE_API_URL=.*|VITE_API_URL=http://$SERVER_IP:$ACTUAL_SERVER_PORT|g" .env
else
    echo "VITE_API_URL=http://$SERVER_IP:$ACTUAL_SERVER_PORT" >> .env
fi

# Set default RUNTIME to empty to avoid Docker Compose warnings
if ! grep -q "^RUNTIME=" .env; then
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
# CRITICAL: We pass --env-file .env explicitly because the compose file is in a subdirectory
echo "🏗️  Running: $DOCKER_COMPOSE_CMD --env-file .env -f docker/docker-compose.yml up --build -d"
$DOCKER_COMPOSE_CMD --env-file .env -f docker/docker-compose.yml up --build -d

# Extract actual ports used for final output
ACTUAL_SERVER_PORT=${SERVER_PORT:-8000}
ACTUAL_FRONTEND_PORT=${FRONTEND_PORT:-5173}

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
