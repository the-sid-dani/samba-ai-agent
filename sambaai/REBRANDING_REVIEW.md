# SambaAI Rebranding Review & Docker Setup Guide

## 1. Environment Configuration (.env) Status

### ✅ Required Variables (Already Set)
- `AUTH_TYPE=disabled` - Authentication disabled for development
- `LOG_LEVEL=info` - Logging level
- `POSTGRES_PASSWORD=sambaai123` - Database password
- `POSTGRES_USER=postgres` - Database user
- `POSTGRES_DB=sambaai` - Database name
- `SECRET_KEY=sambaai-secret-key-change-in-prod` - Application secret

### ⚠️ Placeholder Variables (Need Real Values)
1. **Anthropic API Key** (CRITICAL for LLM functionality):
   - `GEN_AI_API_KEY=sk-ant-xxx` 
   - Get from: https://console.anthropic.com/

2. **Slack Tokens** (For Task 3):
   - `DANSWER_BOT_SLACK_APP_TOKEN=xapp-xxx`
   - `DANSWER_BOT_SLACK_BOT_TOKEN=xoxb-xxx`
   - Will be obtained when creating Slack app

### ✅ Optional Variables (Can Leave as Default)
All other variables in the .env file have sensible defaults and can be left as-is for development.

## 2. Running Docker Services

To test the current setup:

```bash
# Navigate to docker compose directory
cd sambaai/deployment/docker_compose

# Validate environment
./validate_env.sh

# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Check service status
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8080
```

**Note**: Without a valid Anthropic API key, the LLM features won't work, but the application should still start.

## 3. Rebranding Review Results

### ✅ Successfully Rebranded
1. **Folder Structure**: Main folder renamed from `onyx/` to `sambaai/`
2. **Python Package**: `backend/onyx/` → `backend/sambaai/`
3. **Docker Images**: All images use `sambaaidotapp/sambaai-*`
4. **Python Imports**: All `from onyx` → `from sambaai`
5. **Database Name**: Uses `sambaai` database
6. **Cookie Names**: Use `sambaai_` prefix
7. **Email Domains**: Use `sambaai.app`

### ❌ Remaining Issues to Fix

#### 1. Folder Renames Needed
```bash
# Rename onyxbot folder
mv sambaai/backend/sambaai/onyxbot sambaai/backend/sambaai/sambaaibot

# Rename onyx_jira connector
mv sambaai/backend/sambaai/connectors/onyx_jira sambaai/backend/sambaai/connectors/sambaai_jira
```

#### 2. Python Constants to Update
Files containing `ONYX_` constants that need to be changed to `SAMBAAI_`:
- `ONYX_DEFAULT_APPLICATION_NAME`
- `ONYX_SLACK_URL`
- `ONYX_EMAILABLE_LOGO_MAX_DIM`
- `ONYX_METADATA_FILENAME`
- `ONYX_QUERY_HISTORY_TYPE`

#### 3. Comment in Dockerfile
- Line 63 in `backend/Dockerfile`: "Onyx functionality" → "SambaAI functionality"

#### 4. Frontend Files
Several web files still contain "onyx" references:
- `/sambaai/web/src/components/context/NRFPreferencesContext.tsx`
- `/sambaai/web/src/lib/extension/constants.ts`
- `/sambaai/web/src/lib/extension/utils.ts`

#### 5. Documentation
- Folder `/additional-docs/onyx-guides/` contains PDFs with "Onyx" in filenames

## 4. Quick Test Commands

After starting Docker:

```bash
# Test API health
curl http://localhost:8080/health

# Test database connection
docker-compose -f docker-compose.dev.yml exec api_server python -c "from sambaai.db.engine import get_session_with_tenant; print('DB connection OK')"

# Check Vespa search engine
curl http://localhost:8081/ApplicationStatus

# View running containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## 5. Next Steps

### Immediate Actions
1. **Get Anthropic API Key** and update `.env`
2. **Fix remaining "onyx" references** (run the rename commands above)
3. **Test Docker setup** with the commands provided

### For Task 3 (Slack App)
1. Go to https://api.slack.com/apps
2. Create app with the manifest from PRD
3. Get tokens and update `.env`
4. Restart Docker services

### Monitoring
- Frontend logs: `docker-compose logs -f web_server`
- API logs: `docker-compose logs -f api_server`
- Database logs: `docker-compose logs -f relational_db`