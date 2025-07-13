# Suggested Commands for PWIA Development

## Frontend Development Commands (Available Now)
```bash
cd Frontend
npm install          # Install dependencies
npm run dev          # Start development server (Vite)
npm run build        # Build for production
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

## Python Development Commands (TO BE IMPLEMENTED)
```bash
# First, create the Python project structure:
mkdir -p agent backend sandbox_vm memory-bank workspace config

# Create requirements.txt with expected dependencies:
# fastapi, uvicorn, websockets, playwright, openai, pydantic, typer, etc.

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (once requirements.txt is created)
pip install -r requirements.txt

# These commands will work once the Python modules are created:
python -m agent.main      # Run main agent (when implemented)
python -m backend.api     # Start FastAPI server (when implemented)
pytest                    # Run tests (when implemented)
mypy agent/              # Type checking (when configured)
ruff check agent/        # Linting (when configured)
```

## VM Operations Commands (TO BE IMPLEMENTED)
```bash
# These commands will work once VM infrastructure is created:
cd sandbox_vm/
./start_vm.sh           # Start VM (when script exists)
virsh console pwia-vm   # Connect to VM console (when VM exists)
virsh shutdown pwia-vm  # Stop VM (when VM exists)
```

## Git Commands (Available Now)
```bash
git status              # Check repository status
git add .               # Stage all changes
git commit -m "message" # Commit changes
git push                # Push to remote
git pull                # Pull from remote
```

## Linux System Commands
```bash
ls -la                  # List files with details
find . -name "*.py"     # Find Python files
grep -r "pattern" .     # Search for patterns in files
cd directory           # Change directory
pwd                     # Print working directory
```

## Priority Implementation Order
1. **Backend API**: Create FastAPI server with WebSocket support
2. **Memory System**: Create memory-bank/ directory structure  
3. **Agent Core**: Implement basic agent/ modules
4. **Integration**: Connect Frontend to backend APIs