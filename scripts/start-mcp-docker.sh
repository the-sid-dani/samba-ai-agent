#!/bin/bash

# Docker MCP Gateway Startup Script

echo "🐳 Docker MCP Gateway Startup"
echo "============================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and add your API keys."
    echo "Run: cp .env.example .env"
    exit 1
fi

# Source environment variables
source .env

# Check for required API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set in .env"
fi

# Create necessary directories
mkdir -p workspace data

echo ""
echo "Choose startup method:"
echo "1) Docker Compose (Recommended)"
echo "2) MCP-Compose Tool"
echo "3) Individual Containers"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "Starting with Docker Compose..."
        docker-compose -f docker-compose.mcp.yml up -d
        echo ""
        echo "✅ MCP servers started!"
        echo "View logs: docker-compose -f docker-compose.mcp.yml logs -f"
        echo "Gateway URL: http://localhost:8080"
        ;;
    2)
        echo "Starting with MCP-Compose..."
        if [ ! -f ./mcp-compose ]; then
            echo "MCP-Compose not found. Please install it first."
            exit 1
        fi
        ./mcp-compose up
        ;;
    3)
        echo "Starting individual containers..."
        
        # Filesystem server
        docker run -d --name mcp-filesystem \
            -v $(pwd)/workspace:/workspace \
            mcp/filesystem /workspace
        
        # GitHub server
        docker run -d --name mcp-github \
            -e GITHUB_TOKEN=${GITHUB_TOKEN} \
            mcp/github
        
        # Time server
        docker run -d --name mcp-time mcp/time
        
        # Fetch server
        docker run -d --name mcp-fetch mcp/fetch
        
        echo "✅ Individual MCP containers started!"
        echo "View status: docker ps"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "🚀 MCP servers are running!"
echo ""
echo "Next steps:"
echo "1. Configure Claude Desktop with the gateway endpoint"
echo "2. Use /mcp command in Claude to verify connection"
echo "3. Check docs/docker-mcp-setup.md for more details"