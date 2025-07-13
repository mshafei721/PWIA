# Code Style and Conventions

## TypeScript/React Conventions (Frontend)

### File Naming
- React components use PascalCase: `TaskDetailPanel.tsx`
- Utility files use camelCase: `utils.ts`
- Configuration files use lowercase: `package.json`, `tailwind.config.js`

### Component Structure
- Use TypeScript interfaces for props: `interface TaskDetailPanelProps`
- Export components as named exports: `export const TaskDetailPanel: React.FC<Props>`
- Use React functional components with hooks
- State management with `useState` hook

### TypeScript Configuration
- Strict mode enabled (`"strict": true`)
- No unused locals/parameters (`"noUnusedLocals": true`, `"noUnusedParameters": true`)
- Path mapping enabled: `"@/*": ["./src/*"]`
- Target ES2020 with modern features
- JSX mode: `react-jsx`

### Styling Conventions
- Tailwind CSS with custom design system
- CSS custom properties for theming (HSL color format)
- Utility-first approach with `cn()` helper for conditional classes
- Responsive design with mobile-first approach

### ESLint Rules
- Uses `@typescript-eslint/recommended`
- React hooks rules enabled
- React refresh warnings for hot reload compatibility

## Python Conventions (Planned - Not Yet Implemented)

### File Structure
- Snake_case for Python files: `llm_agent.py`, `output_writer.py`
- Package structure with `__init__.py` files
- Module-based architecture: `agent/`, `backend/`

### Expected Python Style
- Type hints required (based on project requirements)
- Pydantic models for data validation
- Async/await patterns for I/O operations
- FastAPI for REST API endpoints
- Pytest for testing

## Documentation Standards
- Markdown format for all documentation
- Clear section headers with emoji indicators
- Code blocks with language specification
- Status indicators (✅ ❌) for implementation tracking

## Git Conventions
- Descriptive commit messages
- Feature-based branching (when team grows)
- Claude Code attribution in commits when AI-generated