#!/bin/bash

# Configuration
REDIS_HOST="localhost"
REDIS_PORT="6379"

# Color Configuration
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Simba Local Environment Check ===${NC}"

# Function to check command existence
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 could not be found.${NC}"
        echo "Please install $1 before proceeding."
        exit 1
    else
        echo -e "${GREEN}✓ $1 is installed${NC}"
    fi
}

# 1. Check Requirements
echo -e "\n${BLUE}Checking requirements...${NC}"
check_command python3
check_command poetry
check_command npm
check_command ollama
check_command redis-cli

# 2. Check Ollama Service
echo -e "\n${BLUE}Checking Ollama service...${NC}"
if ! pgrep -x "ollama" > /dev/null; then
    echo -e "${RED}Ollama is not running.${NC}"
    echo "Please start Ollama (e.g., 'ollama serve' in a separate terminal)"
    exit 1
fi

echo -e "${GREEN}✓ Ollama is running${NC}"

# 3. Check Models
echo -e "\n${BLUE}Checking Ollama models...${NC}"
AVAILABLE_MODELS=$(ollama list)
REQUIRED_LLM="llama3.2"
REQUIRED_EMBED="llama3.2:latest"

if [[ $AVAILABLE_MODELS != *"$REQUIRED_LLM"* ]]; then
    echo "Pulling $REQUIRED_LLM..."
    ollama pull $REQUIRED_LLM
else
    echo -e "${GREEN}✓ Model $REQUIRED_LLM found${NC}"
fi

if [[ $AVAILABLE_MODELS != *"$REQUIRED_EMBED"* ]]; then
    echo "Pulling $REQUIRED_EMBED..."
    ollama pull $REQUIRED_EMBED
else
    echo -e "${GREEN}✓ Model $REQUIRED_EMBED found${NC}"
fi

# 4. Check Redis
echo -e "\n${BLUE}Checking Redis...${NC}"
if ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep "PONG" > /dev/null; then
    echo -e "${RED}Redis is not reachable at $REDIS_HOST:$REDIS_PORT${NC}"
    echo "Please ensure Redis server is running ('brew services start redis' or 'redis-server')"
    exit 1
else
    echo -e "${GREEN}✓ Redis is reachable${NC}"
fi

# 5. Environment Setup
echo -e "\n${BLUE}Setting up environment...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example"
        cp .env.example .env
        # Update redis host in .env for local run if needed, but .env.example defaults are good for localhost
    else 
        echo -e "${RED}No .env or .env.example found!${NC}"
        exit 1
    fi
fi

# 6. Installation
echo -e "\n${BLUE}Installing Python dependencies...${NC}"
poetry install

echo -e "\n${BLUE}=== Starting Simba ===${NC}"
echo "In separate terminals, run the following commands:"
echo -e "1. ${GREEN}poetry run simba server${NC}"
echo -e "2. ${GREEN}poetry run simba parsers${NC}"
echo -e "3. ${GREEN}poetry run simba front${NC}"

# Optional: Attempt to run them (simple implementation just exits)
echo -e "\nAlternatively, use 'make run-local' if configured."
