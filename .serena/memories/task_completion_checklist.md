# Task Completion Checklist

## When Completing Any Task

### 1. Code Quality Checks

#### Frontend Tasks
```bash
cd Frontend
npm run lint        # Run ESLint to check code quality
npm run build       # Ensure production build succeeds
```

#### Python Tasks (When Implemented)
```bash
# Type checking
mypy agent/ backend/

# Linting  
ruff check agent/ backend/
# OR
flake8 agent/ backend/

# Testing
pytest

# Security check (if configured)
bandit -r agent/ backend/
```

### 2. Testing Requirements

#### Frontend
- Manual testing in development server (`npm run dev`)
- Verify responsive design works
- Check component interactions
- Test with different browser sizes

#### Python (When Implemented)
- Unit tests for all new functions/classes
- Integration tests for API endpoints
- Test error handling and edge cases
- Mock external dependencies (OpenAI API, etc.)

### 3. Documentation Updates
- Update relevant memory files if architecture changes
- Update CLAUDE.md if new commands or patterns are introduced
- Add inline comments for complex logic
- Update todo.md with completion timestamps

### 4. Workflow Compliance (Per CLAUDE.md)
- Follow Explore → Research → Plan → User Approval → Implement → Check/Test
- Update PLAN.md with completed checklist items
- Record results in todo.md with timestamps
- Log confidence and learnings in LLM Reflection Notes

### 5. Git Workflow
```bash
git status          # Check what files changed
git add .           # Stage changes
git commit -m "descriptive message"  # Commit with clear message
# Include Claude Code attribution if AI-generated
```

### 6. Memory System Updates (When Implemented)
- Update activeContext.md with current task state
- Update progress.md with completed/blocked/next items
- Save task-specific outputs to workspace/<task_id>/

### 7. Integration Checks
- Verify Frontend still works with any backend changes
- Test WebSocket connections (when implemented)
- Validate API contracts match Frontend expectations
- Check file export functionality (when implemented)

## Critical Reminders
- **Never implement without user-approved plan**
- **Test-Driven Development is mandatory**
- **Only modify one file per task unless explicitly instructed**
- **Frontend contains hardcoded data - don't modify until backend exists**