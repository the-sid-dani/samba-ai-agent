# SambaAI: Slack-First Knowledge Assistant
## Claude Code Configuration & Task Master Workflow Guide

### 🚀 Essential Commands (Most Used)

**Task Master Workflow (ALWAYS USE):**
```bash
# CRITICAL: Always start with Task Master context
mcp_taskmaster-ai_next_task              # Get next task to work on
mcp_taskmaster-ai_get_task --id "3"      # View specific task details  
mcp_taskmaster-ai_set_task_status --id "3.1" --status "in-progress"  # Start subtask
mcp_taskmaster-ai_update_subtask --id "3.1" --prompt "Progress notes..." # Log progress
mcp_taskmaster-ai_set_task_status --id "3.1" --status "done" # Complete subtask
```

**Docker & Development:**
```bash
# Start development stack
cd onyx/deployment/docker_compose && docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f onyx/deployment/docker_compose/docker-compose.dev.yml logs -f [service]

# Stop all services  
docker-compose -f onyx/deployment/docker_compose/docker-compose.dev.yml down
```

**Git & GitHub:**
```bash
gh issue view [number]    # Read GitHub issues
gh pr create             # Create pull request 
git status              # Check repo status
git add . && git commit -m "feat: [description]" # Commit changes
```

**Testing & Validation:**
```bash
cd onyx/web && npm run test        # Run frontend tests
cd onyx/web && npm run typecheck   # TypeScript validation
cd onyx/web && npm run lint        # Linting
cd onyx/backend && python -m pytest # Backend tests
```

### 📁 Project Structure
```
SambaAI Agent/
├── onyx/                    # Main codebase (to rebrand → sambaai/)
│   ├── backend/             # Python API server & connectors
│   │   ├── onyx/           # Core app (rename to sambaai/)
│   │   │   ├── server/     # FastAPI endpoints  
│   │   │   ├── slack/      # Slack bot logic
│   │   │   ├── connectors/ # Confluence/Drive connectors
│   │   │   └── document_index/ # Vespa integration
│   │   └── deployment/
│   │       └── docker_compose/ # Docker configuration
│   └── web/                # React frontend (Next.js)
├── .taskmaster/            # Task management (118 subtasks!)
│   ├── tasks/             # Individual task files
│   ├── docs/prd.txt       # Complete PRD 
│   └── reports/           # Complexity analysis
├── .cursor/               # Cursor IDE config & MCP
├── additional-docs/       # Onyx guides & SambaTV logos
└── scripts/              # Utility scripts
```

### 🎯 Current Project Status: 16 Tasks, 114 Subtasks (6.25% Complete)

**✅ Completed:** Tasks 1-2 (Fork & rebrand setup, base environment)  
**🔄 Next Priority:** Task 3 (Slack App), Task 4 (Bot functionality)  
**🎯 End Goal:** Slack bot providing instant answers from Confluence/Drive

### 🔥 MANDATORY Task Master Workflow

**CRITICAL: EVERY coding session MUST start with Task Master context**

#### 1. Start Every Session (Explore Phase)
```bash
# ALWAYS start here - no exceptions!
mcp_taskmaster-ai_next_task

# Get task details (use exact task ID from next_task)
mcp_taskmaster-ai_get_task --id "4"

# Mark as in-progress  
mcp_taskmaster-ai_set_task_status --id "4" --status "in-progress"
```

**IMPORTANT:** Tell Claude to `think hard` about the task before coding. Use subagents for complex investigation:
- "Use a subagent to investigate how Slack Socket Mode works"  
- "Have a subagent analyze the existing bot structure in `onyx/backend/onyx/slack/`"

#### 2. Plan Phase (Before Any Code)
**NEVER start coding immediately.** Always:
1. Read relevant files first
2. Ask Claude to create a plan
3. Use `ultrathink` for complex tasks
4. Document the plan in task updates

```bash
# Log your planning findings
mcp_taskmaster-ai_update_subtask --id "4.1" --prompt "Analysis complete:
- Found existing Slack classes in backend/onyx/slack/
- Need to implement mention handling in SlackBot class
- Dependencies: Socket Mode setup, message parsing
- Plan: [detailed steps]"
```

#### 3. Implementation Phase  
**Work subtask by subtask.** For each subtask:

```bash
# Start subtask
mcp_taskmaster-ai_set_task_status --id "4.1" --status "in-progress"

# [Implement code]

# CRITICAL: Log progress frequently
mcp_taskmaster-ai_update_subtask --id "4.1" --prompt "Implementation notes:
- Modified SlackBot class to handle mentions
- Added message parsing logic
- Issue found: [specific problem]
- Solution: [what worked]"

# Complete subtask
mcp_taskmaster-ai_set_task_status --id "4.1" --status "done"
```

#### 4. Completion Phase
```bash
# Mark main task complete only when ALL subtasks done
mcp_taskmaster-ai_set_task_status --id "4" --status "done"

# Get next task
mcp_taskmaster-ai_next_task
```

### 🎯 Task-Specific Implementation Patterns

#### For Infrastructure Tasks (Docker, Env Setup)
1. Use Task Master to track configuration steps
2. Test each component before marking subtask complete
3. Document all environment variables and their purposes

#### For Development Tasks (Bot, Connectors, UI)
1. **Write tests first** - use Task Master to track TDD progress
2. **Course correct early** - update subtasks if approach changes
3. **Use visual feedback** - screenshots for UI tasks

#### For Integration Tasks (Slack, Confluence, Drive APIs)
1. **Research first** - use research MCP tool for current API docs
2. **Test incrementally** - each API endpoint gets a subtask update
3. **Handle errors robustly** - document edge cases in subtasks

### 🔧 Code Style Guidelines

**TypeScript/React (Web):**
- Use ES modules (`import/export`), not CommonJS
- Destructure imports: `import { foo } from 'bar'`  
- Async/await over Promise chains
- JSDoc comments for public APIs

**Python (Backend):**
- Type hints for all functions
- FastAPI async patterns  
- Pydantic models for data validation
- Follow existing `onyx` naming conventions

**Docker:**
- Health checks for all services
- Resource limits in production
- Environment variables via .env files

### 🚨 Critical Implementation Notes

**Slack Bot (Task 4):**
- Socket Mode required for real-time events
- Message parsing must extract mentions and commands
- Responses MUST include citations from sources
- Thread replies for maintaining context

**Confluence Connector (Tasks 5-6):**
- Token-based auth for SambaTv instance
- Incremental sync every 10 minutes
- Extract page content + comments + metadata
- Preserve space permissions

**Google Drive Connector (Tasks 7-8):**
- Service account with domain delegation
- Support: Docs, Sheets, PDFs, Slides  
- Real-time updates via push notifications
- Mirror folder permissions

**Vector Search (Task 9):**
- Vespa configuration in `backend/onyx/configs/app_configs.py`
- Hybrid search: semantic + keyword
- Chunk size: 512 tokens, mini-chunk: 128
- Sub-second query response time

### 🔄 Multi-Claude Workflows (Advanced)

**Pattern 1: Code + Review**
1. Have Claude write implementation in first session
2. `/clear` and start new session
3. Have second Claude review the code
4. Third Claude incorporates feedback

**Pattern 2: Parallel Development**
1. Use `git worktree` for multiple features
2. One Claude per worktree/terminal tab  
3. Independent tasks: UI + API development

**Pattern 3: TDD Pattern**
1. Claude writes tests (don't implement yet)
2. Commit tests
3. Claude implements code to pass tests
4. Iterate until all pass

### 📊 Task Master Analytics & Reporting

```bash
# View all tasks and progress
mcp_taskmaster-ai_get_tasks --withSubtasks true

# Check complexity analysis  
mcp_taskmaster-ai_complexity_report

# Filter by status
mcp_taskmaster-ai_get_tasks --status "in-progress,review"

# View specific task with all subtasks
mcp_taskmaster-ai_get_task --id "4"
```

### 🎨 Visual Development Workflow

**For UI Tasks:**
1. Use Puppeteer MCP server for screenshots
2. Compare against design mocks
3. Iterate until pixel-perfect
4. Update Task Master with visual progress

**For API Tasks:**  
1. Test endpoints with curl/Postman
2. Screenshot API responses  
3. Validate against OpenAPI spec

### 🐛 Debugging & Course Correction

**When Things Go Wrong:**
1. **Press Escape** to interrupt Claude
2. **Double-tap Escape** to edit previous prompt
3. **Ask Claude to undo changes** if needed
4. **Update subtask** with what didn't work

**Error Handling Pattern:**
```bash
mcp_taskmaster-ai_update_subtask --id "4.2" --prompt "Issue encountered:
- Problem: [specific error]  
- Attempted: [what was tried]
- Root cause: [analysis]
- Solution: [what actually worked]
- Prevention: [how to avoid next time]"
```

### 🔒 Security & Production

**Environment Variables (NEVER commit):**
```env
# Slack tokens
DANSWER_BOT_SLACK_APP_TOKEN=xapp-xxx
DANSWER_BOT_SLACK_BOT_TOKEN=xoxb-xxx

# LLM API keys
GEN_AI_API_KEY=sk-ant-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Database
POSTGRES_PASSWORD=sambaai123
```

**Required for Production:**
- All secrets in environment variables
- Docker health checks configured  
- Resource limits set
- Monitoring & logging enabled

### 🎯 Success Metrics & Testing

**MVP Success Criteria:**
- [ ] Bot responds in #engineering channel
- [ ] < 5 second response time
- [ ] Confluence documents searchable  
- [ ] 90% positive user feedback

**Testing Checklist:**
- [ ] Unit tests: 80% coverage target
- [ ] Integration tests for Slack events
- [ ] Load test: 100 concurrent users
- [ ] E2E test: mention → response → citation

### 🚀 Deployment Options

**Development:** Local Docker Compose
**Staging:** GCP Compute Engine (e2-standard-4)  
**Production:** GCP with Terraform (Tasks 15-16)

### 🎯 Remember: Task Master is Your Guide

**NEVER work without Task Master context!**
1. ✅ Always start with `next_task`
2. ✅ Update subtasks with findings
3. ✅ Mark progress incrementally  
4. ✅ Use `research` MCP for fresh information
5. ✅ Course correct via subtask updates

**Every session should leave a paper trail in Task Master showing:**
- What was attempted
- What worked/didn't work  
- Specific code changes made
- Next steps identified

This ensures continuity across sessions and enables effective collaboration!