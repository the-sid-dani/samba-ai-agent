#!/bin/bash

# Script to validate .env file configuration

echo "Validating SambaAI environment configuration..."
echo "============================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found in current directory"
    exit 1
fi

# Source the .env file
set -a
source .env
set +a

# Define required variables
REQUIRED_VARS=(
    "AUTH_TYPE"
    "LOG_LEVEL"
    "POSTGRES_PASSWORD"
    "SECRET_KEY"
    "GEN_AI_MODEL_PROVIDER"
    "GEN_AI_MODEL_VERSION"
    "FAST_GEN_AI_MODEL_VERSION"
    "GEN_AI_API_KEY"
    "DANSWER_BOT_SLACK_APP_TOKEN"
    "DANSWER_BOT_SLACK_BOT_TOKEN"
    "POSTGRES_USER"
    "POSTGRES_DB"
    "WEB_DOMAIN"
)

# Check each required variable
MISSING_VARS=()
PLACEHOLDER_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    elif [[ "${!var}" == *"xxx"* ]] || [[ "${!var}" == *"placeholder"* ]]; then
        PLACEHOLDER_VARS+=("$var")
    fi
done

# Report results
echo "✓ Found ${#REQUIRED_VARS[@]} required variables"
echo ""

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ Missing variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
fi

if [ ${#PLACEHOLDER_VARS[@]} -gt 0 ]; then
    echo "⚠️  Variables with placeholder values (need to be updated):"
    for var in "${PLACEHOLDER_VARS[@]}"; do
        echo "   - $var = ${!var}"
    done
    echo ""
fi

# Check Docker connectivity
echo "Checking Docker setup..."
if docker compose version > /dev/null 2>&1; then
    echo "✓ Docker Compose is available"
else
    echo "❌ Docker Compose is not available or not running"
fi

# Validate docker-compose syntax
echo ""
echo "Validating docker-compose.dev.yml syntax..."
if docker compose -f docker-compose.dev.yml config > /dev/null 2>&1; then
    echo "✓ docker-compose.dev.yml syntax is valid"
else
    echo "❌ docker-compose.dev.yml has syntax errors"
fi

echo ""
echo "============================================="
if [ ${#MISSING_VARS[@]} -eq 0 ]; then
    echo "✅ Environment configuration is valid!"
    echo ""
    echo "Note: Some variables have placeholder values that need to be updated:"
    echo "- GEN_AI_API_KEY: Add your Anthropic API key"
    echo "- DANSWER_BOT_SLACK_APP_TOKEN: Add after creating Slack app"
    echo "- DANSWER_BOT_SLACK_BOT_TOKEN: Add after creating Slack app"
    exit 0
else
    echo "❌ Environment configuration has errors"
    exit 1
fi