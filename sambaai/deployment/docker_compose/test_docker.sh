#!/bin/bash

echo "SambaAI Docker Test Script"
echo "========================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please ensure you're in the deployment/docker_compose directory"
    exit 1
fi

# Source the .env file
set -a
source .env
set +a

echo "1. Environment Check:"
echo "   - AUTH_TYPE: $AUTH_TYPE"
echo "   - POSTGRES_DB: $POSTGRES_DB"
echo "   - WEB_DOMAIN: $WEB_DOMAIN"
echo "   - GEN_AI_MODEL_PROVIDER: $GEN_AI_MODEL_PROVIDER"

# Check for placeholder values
if [[ "$GEN_AI_API_KEY" == *"xxx"* ]]; then
    echo "   ⚠️  GEN_AI_API_KEY has placeholder value - LLM features won't work"
else
    echo "   ✅ GEN_AI_API_KEY is set"
fi

echo ""
echo "2. Docker Status:"
docker --version
docker compose version

echo ""
echo "3. Starting Core Services (without Slack bot)..."
echo "   This will start: PostgreSQL, Redis, Vespa, API Server"
echo ""

# Start only essential services
echo "Starting database..."
docker compose -f docker-compose.dev.yml up -d relational_db

echo "Waiting for database to be ready..."
sleep 10

echo "Starting other core services..."
docker compose -f docker-compose.dev.yml up -d cache index model_server

echo "Waiting for services to initialize..."
sleep 15

echo "Starting API server..."
docker compose -f docker-compose.dev.yml up -d api_server

echo ""
echo "4. Service Status:"
docker compose -f docker-compose.dev.yml ps

echo ""
echo "5. Quick Health Checks:"
echo -n "   - PostgreSQL: "
docker compose -f docker-compose.dev.yml exec -T relational_db pg_isready && echo "✅ Ready" || echo "❌ Not ready"

echo -n "   - Redis: "
docker compose -f docker-compose.dev.yml exec -T cache redis-cli ping && echo "✅ Ready" || echo "❌ Not ready"

echo -n "   - API Server: "
curl -s http://localhost:8080/health > /dev/null 2>&1 && echo "✅ Ready" || echo "❌ Not ready (may still be starting)"

echo ""
echo "6. Access Points:"
echo "   - API: http://localhost:8080"
echo "   - Web UI: http://localhost:3000 (if web_server is started)"
echo ""
echo "7. View Logs:"
echo "   docker compose -f docker-compose.dev.yml logs -f api_server"
echo ""
echo "8. Stop Services:"
echo "   docker compose -f docker-compose.dev.yml down"
echo ""
echo "========================="
echo "Test complete!"