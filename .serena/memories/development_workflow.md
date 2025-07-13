# Development Workflow and Guidelines

## PWIA Development Constitution (Critical Rules)

### Golden Principles
1. **Brilliant, amnesiac expert** - Always consult external memory files
2. **Never implement without user-approved plan** - No code without PLAN.md approval
3. **Test-Driven Development (TDD)** is mandatory
4. **PLAN.md is law** - No implementation outside checklist items
5. **Strict workflow**: Explore → Research → Plan → User Approval → Implement → Check/Test

### Workflow Stages

#### 🔍 Explore
- Ask: "What is the user trying to accomplish?"
- Ask targeted clarification questions if unclear

#### 📚 Research  
- Examine all relevant files in memory-bank/, workspace/, and codebase
- Scan for existing tools, functions, or patterns that may help

#### 🧾 Plan
- Break work into small, independently testable steps
- Update PLAN.md using strict checklist format
- Example format:
  ```markdown
  - [ ] Prompt: "Create the Pydantic model in `agent/memory.py`"
  - [ ] Prompt: "Write a failing test for the model"
  ```

#### ✅ User Approval
- **HALT** until user approves updated PLAN.md
- Only begin executing after confirmation

#### 🛠️ Implement
- Perform only ONE checklist item at a time
- Save output to correct file path, not inline
- Update todo.md with timestamps on completed items

#### ✔️ Check / Test
- Run associated unit tests or create them
- Record results in todo.md
- Log confidence and learnings in LLM Reflection Notes

## Prohibited Behaviors
❌ Implementing outside PLAN.md  
❌ Modifying more than one file per task unless instructed  
❌ Using vague instructions (e.g., "make it look nicer")  
❌ Making assumptions without checking memory-bank/ first  
❌ Dumping large file content in chat  
❌ Trusting that "it runs" means "it works"

## Memory System Requirements
- All external memory in memory-bank/ directory
- PLAN.md contains checklist prompt plan (approved)
- activeContext.md tracks current task + focus
- progress.md tracks what's done, what's next
- workspace/<task_id>/todo.md for runtime task logs

## Workflow Shortcuts
| Keyword | Effect |
|---------|--------|
| ultrathink | Use maximum reasoning and plan multiple approaches |
| sub-task with agents | Break complex file changes into AI-agent subtasks |
| checkpoint | Commit progress in progress.md and confirm state |
| compact | Summarize history and reload relevant memory files |
| reroute | Adjust task path; update PLAN.md and todo.md |

## Session Management
### When You Begin a Session
1. Load all files from memory-bank/
2. Read CLAUDE.md to refresh behavior constraints  
3. Consult activeContext.md to know current focus
4. Use progress.md to understand what's already done
5. Prompt user: "Hello. I've reloaded the project memory. Based on PLAN.md, the next item is..."

### When You End a Session
1. Update activeContext.md with current task state
2. Update progress.md with completed/blocked/next items  
3. Confirm with user: "Would you like me to summarize or generate a compact version before closing?"

## Scope Restrictions
- All tools, libraries, and packages must be defined in memory-bank/techContext.md
- Do not introduce new third-party packages without user approval
- Follow defined system architecture from systemPatterns.md