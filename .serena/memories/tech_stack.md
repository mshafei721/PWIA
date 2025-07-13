# PWIA Tech Stack

## Core Technology Stack

| Layer | Stack | Status |
|-------|--------|--------|
| Agent (CLI) | Python 3.11, Playwright, Typer, asyncio | ❌ Not implemented |
| LLM | OpenAI GPT-4 via Assistant API Boilerplate | ❌ Not implemented |
| Backend | FastAPI (API + WebSocket) | ❌ Not implemented |
| Frontend | React + Tailwind CSS + TypeScript | ✅ Complete |
| VM Engine | QEMU + KVM | ❌ Not implemented |
| VM OS | Ubuntu 22.04 + XFCE | ❌ Not implemented |
| GUI Streaming | noVNC or SPICE | ❌ Not implemented |
| Memory | TinyDB / JSON + Markdown (todo.md) | ❌ Not implemented |
| Outputs | `.md`, `.csv`, `.zip` | ❌ Not implemented |

## Frontend Technology Details
- **React**: 18.3.1
- **TypeScript**: 5.5.4 with strict mode enabled
- **Build Tool**: Vite 5.2.0
- **Styling**: Tailwind CSS 3.4.17 with custom design system
- **Utilities**: clsx for conditional classes, tailwind-merge for class merging
- **Linting**: ESLint with TypeScript, React hooks plugins
- **Module System**: ES modules with bundler resolution

## Planned Python Dependencies (Not Yet Implemented)
- fastapi - Web framework for backend API
- uvicorn - ASGI server
- websockets - Real-time communication
- playwright - Web automation
- openai - LLM integration
- pydantic - Data validation
- typer - CLI framework
- asyncio - Async operations