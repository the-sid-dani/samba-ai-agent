# SambaAI Environment Configuration

## Overview
This document describes the environment configuration for SambaAI deployment.

## Configuration File
The main configuration is stored in `deployment/docker_compose/.env`

## Key Environment Variables

### Core Settings
- `AUTH_TYPE=disabled` - Authentication disabled for development
- `LOG_LEVEL=info` - Logging level
- `POSTGRES_PASSWORD=sambaai123` - Database password
- `SECRET_KEY=sambaai-secret-key-change-in-prod` - Application secret key

### Model Configuration (LiteLLM)
- `GEN_AI_MODEL_PROVIDER=litellm` - Using LiteLLM as the model provider
- `GEN_AI_MODEL_VERSION=claude-3-sonnet-20240229` - Primary model
- `FAST_GEN_AI_MODEL_VERSION=claude-3-haiku-20240307` - Fast model for simple tasks
- `GEN_AI_API_KEY=sk-ant-xxx` - **PLACEHOLDER: Replace with actual Anthropic API key**

### Slack Configuration
- `DANSWER_BOT_SLACK_APP_TOKEN=xapp-xxx` - **PLACEHOLDER: Replace after creating Slack app**
- `DANSWER_BOT_SLACK_BOT_TOKEN=xoxb-xxx` - **PLACEHOLDER: Replace after creating Slack app**

### Database Configuration
- `POSTGRES_USER=postgres` - Database user
- `POSTGRES_DB=sambaai` - Database name

### Other Settings
- `WEB_DOMAIN=http://localhost:3000` - Web interface URL
- `SESSION_EXPIRE_TIME_SECONDS=604800` - Session timeout (7 days)

## Validation

Run the validation script to check your configuration:
```bash
cd deployment/docker_compose
./validate_env.sh
```

## Next Steps

1. **Get Anthropic API Key**:
   - Visit https://console.anthropic.com/
   - Create an API key
   - Replace `sk-ant-xxx` in `.env` with your actual key

2. **Create Slack App** (Task 3):
   - Go to https://api.slack.com/apps
   - Create new app using the provided manifest
   - Get the App-level token and Bot token
   - Update the placeholder values in `.env`

3. **Start the Application**:
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

4. **Verify Installation**:
   - Visit http://localhost:3000
   - Check logs: `docker compose -f docker-compose.dev.yml logs -f`

## Security Notes
- The `.env` file is gitignored and should never be committed
- Change `SECRET_KEY` and `POSTGRES_PASSWORD` for production
- Enable proper authentication (`AUTH_TYPE`) for production use