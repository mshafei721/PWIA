# PWIA Phase 1 Implementation Plan - Complete Foundation & Enhancement

## Overview

This comprehensive plan creates the PWIA system from scratch, incorporating research on modern UI frameworks while building all missing infrastructure. Currently only the Frontend shell exists with hardcoded data.

## Current State vs Target State

### What Exists Now:
```
PWIA/
├── Frontend/          ✅ React app shell with hardcoded data
├── memory-bank/       ⚠️ Development memory for Claude (NOT application memory)
└── CLAUDE.MD, PRD.MD  ✅ Documentation files
```

### What We're Building (from PRD.MD):
```
PWIA/
├── agent/             ❌ Python agent with Playwright browser automation
├── backend/           ❌ FastAPI server with WebSocket support
├── sandbox_vm/        ❌ QEMU/KVM VM configuration
├── app-memory/        ❌ Application's memory system (NOT development memory)
├── workspace/         ❌ Task outputs and logs
├── config/            ❌ Configuration files
└── Frontend/          ⚠️ Needs connection to real backend
```

## Phase 1A: Complete Infrastructure Setup (Week 1)

### Day 1: Project Foundation & Structure
- [ ] Prompt: "Create the complete PWIA project structure with directories: agent/, backend/, sandbox_vm/, app-memory/, workspace/, config/"
- [ ] Prompt: "Create requirements.txt with all Python dependencies from PRD: fastapi, uvicorn, websockets, playwright, typer, openai, tinydb, pydantic, pytest"
- [ ] Prompt: "Create package.json updates for Frontend with new dependencies: @copilotkit/react-core, @copilotkit/react-ui, zustand, @tanstack/react-query"
- [ ] Prompt: "Set up Python virtual environment initialization script setup.sh"
- [ ] Prompt: "Create .gitignore covering Python, Node.js, and VM artifacts"

### Day 2: Backend API Foundation
- [ ] Prompt: "Create backend/main.py with FastAPI application including health check, CORS configuration for Frontend"
- [ ] Prompt: "Create backend/models.py with Pydantic models for Task, Agent, Message matching Frontend's TaskDetailPanel expectations"
- [ ] Prompt: "Implement backend/api.py with task management endpoints: GET /tasks, POST /tasks, GET /tasks/{id}"
- [ ] Prompt: "Create backend/file_export.py with export functionality for CSV, Markdown, ZIP formats"
- [ ] Prompt: "Write API tests in tests/backend/test_api.py"

### Day 3: WebSocket & Real-time Infrastructure
- [ ] Prompt: "Create backend/websocket_manager.py with ConnectionManager class for handling multiple WebSocket clients"
- [ ] Prompt: "Implement WebSocket endpoint /ws/tasks/{task_id} with message queuing for offline clients"
- [ ] Prompt: "Add AG-UI Protocol event types to backend/models.py: message.delta, tool_call, state.patch"
- [ ] Prompt: "Create backend/event_bus.py for routing agent events to WebSocket clients"
- [ ] Prompt: "Write WebSocket tests in tests/backend/test_websocket.py"

### Day 4: Agent Core Implementation
- [ ] Prompt: "Create agent/main.py with Typer CLI supporting commands: start, stop, pause, resume, status"
- [ ] Prompt: "Implement agent/llm_agent.py integrating OpenAI Assistant API with streaming responses"
- [ ] Prompt: "Create agent/planner.py for task decomposition and todo.md generation in workspace/"
- [ ] Prompt: "Implement agent/confidence.py with scoring system (0-100) and completion thresholds"
- [ ] Prompt: "Create agent/utils.py with logging, error handling, and retry logic"

### Day 5: Browser & Web Automation - DETAILED IMPLEMENTATION PLAN

#### Phase 1: Environment Setup & Foundation (Steps 1-8)
**Environment Validation & Dependencies**
- [ ] Prompt: "Update requirements.txt to include browser automation dependencies: playwright>=1.40.0, tinydb>=4.8.0, aiofiles>=23.0.0, robotparser>=1.0.0"
- [ ] Prompt: "Create tests/agent/test_environment.py with pytest test_playwright_installation() that verifies Playwright can launch Chrome browser"
- [ ] Prompt: "Create tests/agent/test_memory_foundation.py with test_tinydb_basic_operations() for database create/read/write/delete operations"
- [ ] Prompt: "Implement agent/memory.py with AgentMemory class using TinyDB for basic CRUD operations on agent state"

**Memory System Foundation**
- [ ] Prompt: "Create Pydantic models in agent/memory.py: CrawlState, VisitedURL, ExtractedData, AgentSession with proper validation"
- [ ] Prompt: "Implement AgentMemory.save_crawl_state(), load_crawl_state(), get_visited_urls() methods with async operations"
- [ ] Prompt: "Write tests in test_memory_foundation.py covering memory persistence, concurrent access, and error handling"
- [ ] Prompt: "Create app-memory/ directory structure with agent_crawl.json, visited_urls.json, extracted_data.json files"

#### Phase 2: Browser Management & Core Automation (Steps 9-16)
**Browser Manager Implementation**
- [ ] Prompt: "Create agent/browser.py with BrowserManager class supporting both headless and headful Playwright configurations"
- [ ] Prompt: "Implement BrowserManager.launch_browser(), close_browser(), get_page() methods with proper resource cleanup"
- [ ] Prompt: "Add browser session management with context isolation and cookie/storage persistence"
- [ ] Prompt: "Write tests/agent/test_browser_manager.py with test_browser_launch_headless(), test_browser_launch_headful(), test_resource_cleanup()"

**Web Crawler Implementation**  
- [ ] Prompt: "Create agent/crawler.py with WebCrawler class implementing robots.txt parsing and compliance checking"
- [ ] Prompt: "Implement WebCrawler.crawl_url(), queue_urls(), check_robots_allowed() with rate limiting and delay management"
- [ ] Prompt: "Add URL queue management with priority handling and duplicate detection using memory persistence"
- [ ] Prompt: "Write tests/agent/test_crawler.py covering robots.txt compliance, rate limiting, and queue management"

#### Phase 3: Data Extraction & Processing (Steps 17-24)
**Data Scraper Implementation**
- [ ] Prompt: "Create agent/scraper.py with DataScraper class supporting CSS selectors, XPath, and BeautifulSoup extraction"
- [ ] Prompt: "Implement DataScraper.extract_text(), extract_links(), extract_structured_data() with multiple selector strategies"
- [ ] Prompt: "Add data cleaning and validation methods with confidence scoring integration"
- [ ] Prompt: "Write tests/agent/test_scraper.py covering all extraction methods, edge cases, and malformed HTML handling"

**Integration Layer Development**
- [x] Prompt: "Create agent/browser_automation.py integrating BrowserManager, WebCrawler, and DataScraper classes"
- [ ] Prompt: "Implement BrowserAutomation.automated_crawl() orchestrating full crawl workflow with error recovery"
- [ ] Prompt: "Add WebSocket status broadcasting for real-time browser operation updates"
- [ ] Prompt: "Write tests/agent/test_browser_automation.py for end-to-end workflow testing"

#### Phase 4: System Integration & Optimization (Steps 25-32)
**Agent Core Integration**
- [ ] Prompt: "Update agent/main.py to include browser automation commands: crawl, extract, browser-status"
- [ ] Prompt: "Integrate browser automation with agent/planner.py for task decomposition into crawl subtasks"
- [ ] Prompt: "Add browser operation confidence scoring to agent/confidence.py for extraction quality assessment"
- [ ] Prompt: "Update agent/utils.py with browser-specific logging and error handling utilities"

**WebSocket Integration**
- [ ] Prompt: "Update backend/websocket_manager.py to handle browser status events: browser.started, page.loaded, data.extracted"
- [ ] Prompt: "Add browser event broadcasting to backend/event_bus.py for real-time frontend updates"
- [ ] Prompt: "Create browser status models in backend/models.py: BrowserStatus, CrawlProgress, ExtractionResult"
- [ ] Prompt: "Write tests/backend/test_browser_websocket.py for real-time browser communication"

#### Phase 5: Validation & Documentation (Steps 33-40)
**Comprehensive Testing**
- [ ] Prompt: "Create tests/agent/test_browser_integration.py with full system tests for complete crawl workflows"
- [ ] Prompt: "Add performance tests in tests/agent/test_browser_performance.py measuring crawl speed and memory usage"
- [ ] Prompt: "Implement error recovery tests in tests/agent/test_browser_resilience.py for network failures and browser crashes"
- [ ] Prompt: "Create tests/e2e/test_browser_automation_e2e.py for end-to-end user workflow validation"

**Documentation & Optimization**
- [ ] Prompt: "Update README.md with browser automation setup instructions and usage examples"
- [ ] Prompt: "Create docs/browser_automation.md with architecture overview and component integration guide"
- [ ] Prompt: "Add configuration examples in config/ for different crawling scenarios and browser settings"
- [ ] Prompt: "Perform final validation: run all 78+ existing tests plus new browser tests to ensure no regressions"

### Day 6: Output & Memory Systems
- [ ] Prompt: "Create agent/output_writer.py supporting multiple export formats (MD, CSV, ZIP) in workspace/"
- [ ] Prompt: "Implement app-memory/ structure with task_db.json, agent_state.json using TinyDB"
- [ ] Prompt: "Create workspace/{task_id}/ directory structure with todo.md, output files, and logs"
- [ ] Prompt: "Implement config/ directory with prompt.txt, task.yaml templates, and .env.example"
- [ ] Prompt: "Write memory persistence tests in tests/agent/test_memory.py"

### Day 7: Frontend-Backend Integration
- [ ] Prompt: "Create Frontend/.env.local with VITE_API_URL=http://localhost:8000 and VITE_WS_URL=ws://localhost:8000"
- [ ] Prompt: "Create Frontend/src/lib/api.ts with typed API client using fetch"
- [ ] Prompt: "Implement Frontend/src/lib/websocket.ts with WebSocket connection management and reconnection"
- [ ] Prompt: "Update TaskDetailPanel.tsx to fetch real data from API instead of hardcoded mock"
- [ ] Prompt: "Create Frontend/src/components/ConnectionStatus.tsx showing API/WebSocket health"

## Phase 1B: UI Enhancement with Modern Frameworks (Week 2)

### Day 8: CopilotKit Integration (Research Priority #1)
- [ ] Prompt: "Install and configure CopilotKit in Frontend with npm install @copilotkit/react-core @copilotkit/react-ui"
- [ ] Prompt: "Wrap App.tsx with CopilotKitProvider configured for our backend endpoints"
- [ ] Prompt: "Replace ChatPanel.tsx with CopilotKit-powered chat supporting streaming messages"
- [ ] Prompt: "Create custom CopilotKit actions in Frontend/src/copilot/actions.ts for agent control"
- [ ] Prompt: "Test streaming performance with large responses"

### Day 9: State Management Setup
- [ ] Prompt: "Install Zustand and TanStack Query: npm install zustand @tanstack/react-query"
- [ ] Prompt: "Create Frontend/src/stores/agentStore.ts managing agent state, confidence, and lifecycle"
- [ ] Prompt: "Create Frontend/src/stores/taskStore.ts for task list and current task management"
- [ ] Prompt: "Create Frontend/src/stores/websocketStore.ts for connection state and message queue"
- [ ] Prompt: "Implement persistence middleware for Zustand stores using localStorage"

### Day 10: Shadcn UI Migration (Research Priority #3)
- [ ] Prompt: "Initialize Shadcn UI with npx shadcn-ui@latest init, selecting New York style"
- [ ] Prompt: "Install essential Shadcn components: button, card, dialog, tabs, badge, skeleton, toast, alert"
- [ ] Prompt: "Migrate existing components to use Shadcn UI primitives while maintaining functionality"
- [ ] Prompt: "Implement dark/light theme toggle with system preference detection"
- [ ] Prompt: "Update Tailwind config to work with Shadcn UI CSS variables"

### Day 11: Real-time Monitoring Dashboard
- [ ] Prompt: "Install visualization libraries: npm install recharts react-flow-renderer"
- [ ] Prompt: "Create Frontend/src/components/AgentMonitor.tsx with real-time status indicators"
- [ ] Prompt: "Implement Frontend/src/components/ProgressChart.tsx showing task completion over time"
- [ ] Prompt: "Create Frontend/src/components/ConfidenceGauge.tsx with intervention thresholds"
- [ ] Prompt: "Add Frontend/src/components/ToolCallViewer.tsx for visualizing agent actions"

### Day 12: Advanced Features
- [ ] Prompt: "Implement drag-and-drop file upload in Frontend/src/components/FileUploader.tsx"
- [ ] Prompt: "Create Frontend/src/components/ExportPanel.tsx with multi-format export options"
- [ ] Prompt: "Add keyboard shortcuts for power users using react-hotkeys-hook"
- [ ] Prompt: "Implement search and filtering for task history and logs"
- [ ] Prompt: "Create Frontend/src/components/ErrorBoundary.tsx for graceful error handling"

### Day 13: VM Integration Preparation
- [ ] Prompt: "Create sandbox_vm/start_vm.sh script for launching QEMU/KVM virtual machine"
- [ ] Prompt: "Implement backend/vm_manager.py for VM lifecycle management"
- [ ] Prompt: "Create basic VM configuration in sandbox_vm/vm.conf"
- [ ] Prompt: "Add VM status endpoint GET /vm/status to backend API"
- [ ] Prompt: "Update VMViewer.tsx component to show placeholder for future noVNC integration"

### Day 14: Testing & Polish
- [ ] Prompt: "Create comprehensive E2E tests in tests/e2e/ using Playwright"
- [ ] Prompt: "Add loading skeletons to all data-fetching components"
- [ ] Prompt: "Implement proper error states and retry mechanisms"
- [ ] Prompt: "Create Storybook stories for main components"
- [ ] Prompt: "Run performance optimization and bundle size analysis"

## Key Technical Decisions (from Research)

### Communication Architecture
```
1. REST API for CRUD operations
2. WebSocket for real-time updates using AG-UI Protocol
3. Server-Sent Events as fallback
4. Message queuing for offline resilience
```

### State Management Strategy
```
1. Zustand for client-side state (UI preferences, local data)
2. TanStack Query for server state (caching, synchronization)
3. WebSocket for real-time updates
4. TinyDB for agent persistence
```

### UI Component Architecture
```
1. Shadcn UI for consistent design system
2. CopilotKit for AI-enhanced interactions
3. Tailwind CSS for custom styling
4. React Hook Form for form handling
```

## Success Metrics

### Phase 1A Completion
- Backend API responds to all endpoints
- WebSocket connections stable with auto-reconnect
- Agent can start, browse, and save results
- Frontend displays real data from backend
- All tests passing (unit, integration)

### Phase 1B Completion
- CopilotKit chat shows streaming responses
- Real-time monitoring dashboard operational
- State persists across page refreshes
- UI response time < 200ms
- Export functionality working for all formats

## Risk Mitigation

### High Priority Risks
1. **WebSocket Connection Stability**
   - Implement exponential backoff
   - Add connection health monitoring
   - Fallback to polling if needed

2. **Type Mismatches Frontend/Backend**
   - Generate TypeScript types from Pydantic
   - Add runtime validation
   - Use shared schema definitions

3. **Agent Crash Recovery**
   - Implement checkpoint saving
   - Add process monitoring
   - Enable resume from last state

## Directory Structure Reference

```
PWIA/
├── agent/                    # Python agent application
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── llm_agent.py         # OpenAI integration
│   ├── planner.py           # Task planning
│   ├── browser.py           # Playwright automation
│   ├── crawler.py           # Web crawling logic
│   ├── scraper.py           # Data extraction
│   ├── confidence.py        # Scoring system
│   ├── memory.py            # Persistence layer
│   └── output_writer.py     # Export functionality
├── backend/                  # FastAPI server
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── api.py               # REST endpoints
│   ├── models.py            # Pydantic models
│   ├── websocket_manager.py # WebSocket handling
│   ├── event_bus.py         # Event routing
│   ├── file_export.py       # Export logic
│   └── vm_manager.py        # VM control
├── Frontend/                 # React application
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── lib/            # Utilities
│   │   ├── stores/         # Zustand stores
│   │   ├── hooks/          # Custom hooks
│   │   └── copilot/        # CopilotKit config
│   └── [config files]
├── sandbox_vm/              # VM configuration
├── app-memory/              # Application memory (TinyDB)
├── workspace/               # Task outputs
├── config/                  # Configuration files
├── tests/                   # Test suites
└── docs/                    # Documentation
```

## Next Steps

1. **Get user approval** for this plan
2. **Create project structure** following the directory layout
3. **Set up development environment** with Python and Node.js
4. **Begin Day 1 implementation** with test-first approach
5. **Daily progress updates** in workspace/progress.log

---

*This plan builds the complete PWIA system from the ground up, creating all missing infrastructure while incorporating modern UI frameworks researched earlier.*