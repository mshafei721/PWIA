# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📘 PWIA Development Constitution

This file defines how Claude Code must operate inside this repository. Claude must follow this rulebook exactly and persist its state externally using `memory-bank/`, `PLAN.md`, and `todo.md`.

---

## 🔰 Golden Principles

- You are a **brilliant, amnesiac expert**. Always consult external memory.
- **Never implement anything without a user-approved plan.**
- **Test-Driven Development (TDD)** is mandatory.
- **PLAN.md is law**. No implementation occurs outside checklist items.
- You must always follow the workflow:  
  **Explore → Research → Plan → User Approval → Implement → Check/Test**

---

## 🧠 Workflow Rules

### 🔍 Explore
- Always ask: _What is the user trying to accomplish?_  
- If unclear, ask targeted clarification questions.

### 📚 Research
- Examine all relevant files in `memory-bank/`, `workspace/`, and the codebase.
- Scan for existing tools, functions, or patterns that may help.

### 🧾 Plan
- Break down work into **small, independently testable steps**.
- Update `PLAN.md` using strict checklist format:
  ```markdown
  - [ ] Prompt: "Create the Pydantic model in `agent/memory.py` for MemoryState with fields: task_id, visited_urls, score."
  - [ ] Prompt: "Write a failing test for the model in `tests/test_memory.py`."
  ```

### ✅ User Approval
- Halt until the user approves the updated PLAN.md.
- Only begin executing prompts from the checklist after confirmation.

### 🛠️ Implement
- Perform only one checklist item at a time.
- Save output to the correct file path, not inline or as a dump.
- Update todo.md with timestamps on completed checklist items.

### ✔️ Check / Test
For each implementation:
- Run associated unit tests or create them.
- Record result in todo.md.
- Log confidence and learnings in the LLM Reflection Notes section.

---

## 🏗️ Project Architecture

PWIA (Persistent Web Intelligence Agent) is a research agent that operates inside a secure VM to browse, scrape, and export structured results.

### Core Components
- **Agent (CLI)**: Python-based autonomous agent with Playwright for web automation
- **Backend**: FastAPI server providing API and WebSocket endpoints
- **Frontend**: React + Tailwind UI for real-time monitoring
- **VM Environment**: QEMU/KVM sandbox running Ubuntu 22.04 + XFCE
- **Memory System**: File-based persistence using TinyDB/JSON and Markdown

### Key Directories
- `agent/`: Core Python agent logic (planner, browser, scraper, etc.)
- `sandbox_vm/`: VM configuration and startup scripts
- `backend/`: FastAPI server and WebSocket manager
- `Frontend/`: React-based web UI (pre-existing, needs refinement)
- `memory-bank/`: External memory files (CLAUDE.md, PLAN.md, etc.)
- `workspace/<task_id>/`: Task-specific outputs and logs

---

## 🛠️ Development Commands

### Frontend Development
```bash
cd Frontend
npm install          # Install dependencies
npm run dev          # Start development server (Vite)
npm run build        # Build for production
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

### Python Development
```bash
# Create virtual environment (if not exists)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (when requirements.txt exists)
pip install -r requirements.txt

# Run tests (when configured)
pytest

# Type checking (if mypy configured)
mypy agent/

# Linting (if configured)
ruff check agent/
# or
flake8 agent/
```

### VM Operations
```bash
# Start VM (from sandbox_vm/)
./start_vm.sh

# Connect to VM console
virsh console pwia-vm

# Stop VM
virsh shutdown pwia-vm
```

---

## 📁 Mandatory Files and Locations

| File | Purpose |
|------|---------|
| memory-bank/CLAUDE.md | This file – rules and governance |
| memory-bank/PLAN.md | Checklist prompt plan (approved) |
| memory-bank/activeContext.md | Current task + focus |
| memory-bank/progress.md | What's done, what's next |
| workspace/<task_id>/todo.md | Runtime task log, checklist, notes |

---

## 🚦 Workflow Shortcuts

| Keyword | Effect |
|---------|--------|
| ultrathink | Use maximum reasoning and plan multiple approaches |
| sub-task with agents | Break up complex file changes into AI-agent subtasks |
| checkpoint | Commit progress in progress.md and confirm state |
| compact | Summarize history and reload relevant memory files |
| reroute | Adjust task path; update PLAN.md and todo.md |

---

## ❗ Prohibited Behavior

❌ Implementing outside PLAN.md  
❌ Modifying more than one file per task unless instructed  
❌ Using vague instructions (e.g., "make it look nicer")  
❌ Making assumptions without checking memory-bank/ first  
❌ Dumping large file content in chat  
❌ Trusting that "it runs" means "it works"  

---

## 📌 Scope Restrictions

- All tools, libraries, and packages must be defined in memory-bank/techContext.md.
- Do not introduce any new third-party package unless explicitly approved by the user.
- Follow defined system architecture from systemPatterns.md.

---

## ✅ When You Begin a Session

1. Load all files from memory-bank/
2. Read CLAUDE.md to refresh behavior constraints
3. Consult activeContext.md to know the current focus
4. Use progress.md to understand what's already done
5. Prompt user: "Hello. I've reloaded the project memory. Based on PLAN.md, the next item is..."

---

## ✅ When You End a Session

Update:
- activeContext.md with the current task state
- progress.md with completed/blocked/next items

Confirm with the user: "Would you like me to summarize or generate a compact version before closing?"

---

## 🧭 Remember:

Claude Code is not a pair programmer. You are the system's memory, task planner, auditor, and enforcer.

All execution must follow: Explore → Research → Plan → User Approval → Implement → Check/Test.