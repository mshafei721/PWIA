# PWIA Codebase Structure

## Current Directory Structure

```
PWIA/
├── Frontend/              ✅ COMPLETE - React + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/    ✅ All UI components implemented
│   │   │   ├── App.tsx                 # Main layout with collapsible sidebars
│   │   │   ├── TaskDetailPanel.tsx     # Task view with hardcoded data
│   │   │   ├── DocumentViewer.tsx      # Document display component
│   │   │   ├── Sidebar.tsx            # Navigation sidebar
│   │   │   ├── ChatPanel.tsx          # Chat interface component
│   │   │   ├── VMViewer.tsx           # VM streaming viewer
│   │   │   ├── LogViewer.tsx          # Log display component
│   │   │   └── TodoViewer.tsx         # Todo management component
│   │   ├── lib/
│   │   │   └── utils.ts               # Utility functions (cn helper)
│   │   ├── index.tsx                  # React app entry point
│   │   └── index.css                  # Global styles
│   ├── package.json       ✅ Configured with Vite + ESLint
│   ├── tailwind.config.js ✅ Custom design system configuration
│   ├── tsconfig.json      ✅ TypeScript configuration
│   ├── vite.config.ts     ✅ Vite build configuration
│   └── .eslintrc.cjs      ✅ ESLint configuration
├── CLAUDE.MD              ✅ Development guidance and workflow rules
├── PRD.MD                 ✅ Project requirements document
├── .git/                  ✅ Git repository (active, on master branch)
├── .claude/               ✅ Claude Code IDE configuration
└── .serena/               ✅ Serena agent configuration

[TO BE CREATED] ❌ All directories below need implementation:
├── agent/                 ❌ Core Python agent logic
│   ├── main.py           ❌ Entry point
│   ├── planner.py        ❌ Task planning logic
│   ├── llm_agent.py      ❌ OpenAI LLM integration
│   ├── browser.py        ❌ Web browsing automation
│   ├── crawler.py        ❌ Web crawling logic
│   ├── scraper.py        ❌ Data extraction
│   ├── confidence.py     ❌ Confidence scoring
│   ├── memory.py         ❌ Persistent memory management
│   ├── output_writer.py  ❌ Report generation
│   └── utils.py          ❌ Utility functions
├── backend/              ❌ FastAPI server and WebSocket manager
│   ├── api.py           ❌ REST API endpoints
│   ├── file_export.py   ❌ File export functionality
│   └── websocket_manager.py ❌ Real-time communication
├── sandbox_vm/           ❌ VM configuration and startup scripts
│   ├── start_vm.sh      ❌ VM startup script
│   ├── image.qcow2      ❌ VM disk image
│   ├── cloud-init/      ❌ VM initialization
│   └── preinstall/      ❌ Pre-installed software
├── memory-bank/          ❌ External memory files (PLAN.md, etc.)
│   ├── PLAN.md          ❌ Checklist prompt plan (approved)
│   ├── activeContext.md ❌ Current task + focus
│   ├── progress.md      ❌ What's done, what's next
│   ├── techContext.md   ❌ Technology constraints
│   └── systemPatterns.md ❌ Architecture patterns
├── workspace/            ❌ Task-specific outputs and logs
│   └── <task_id>/       ❌ Per-task workspace
│       ├── todo.md      ❌ Task goals, status, reflections
│       ├── output.md    ❌ Markdown-formatted results
│       ├── output.csv   ❌ Tabular data
│       └── logs.json    ❌ Agent memory state
└── config/               ❌ Environment and task configuration
    ├── prompt.txt       ❌ Default prompts
    ├── task.yaml        ❌ Task configuration
    └── .env             ❌ Environment variables
```

## Key Frontend Components Analysis

### App.tsx
- Main layout with collapsible left/right sidebars
- State management for panel visibility
- Integrates Sidebar, TaskDetailPanel, and DocumentViewer

### TaskDetailPanel.tsx  
- **Contains hardcoded mock data** (lines 26-62)
- Implements expandable task sections
- Uses TypeScript interfaces for type safety
- Ready for real API integration

### Component Patterns
- Functional components with TypeScript
- Props interfaces defined per component
- Consistent use of Tailwind CSS classes
- SVG icons embedded inline
- State management with React hooks

## Integration Points for Backend Development
1. **WebSocket connection** for real-time updates (currently mock)
2. **Task management APIs** matching hardcoded task structure  
3. **File export endpoints** for downloading results
4. **VM streaming integration** for VMViewer component