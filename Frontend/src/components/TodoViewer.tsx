import React from 'react';
export const TodoViewer: React.FC = () => {
  const todoContent = `# 🧠 PWIA Task Plan: agent_frameworks_2025
## 📝 User Prompt
"Compare top open-source agent orchestration frameworks"
## 🎯 Objectives
- Discover current leading frameworks
- Extract key GitHub stats and official docs
- Ensure 5+ diverse, trusted sources
## ✅ Success Criteria
- At least 5 unique high-confidence sources
- Metadata extracted for each (stars, docs)
- Confidence score ≥ 85%
## 📋 Task Checklist
- [x] Parsed prompt and created task plan – 2025-07-13 15:12
- [x] Performed Google search – 2025-07-13 15:14
- [x] Crawled GitHub: LangGraph – 2025-07-13 15:15
- [ ] Crawled GitHub: CrewAI
- [ ] Confidence check
- [ ] Final output writing
## 🧠 LLM Reflection Notes
- 2025-07-13 15:15 — Genspark denied in robots.txt
- 2025-07-13 15:16 — Re-planning after duplicate GitHub domains`;
  return <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <h1 className="text-xl font-bold">todo.md</h1>
        <p className="text-xs text-muted-foreground">
          Auto-generated task plan
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-6 bg-background">
        <div className="prose dark:prose-invert max-w-none">
          {todoContent.split('\n').map((line, index) => {
          // Render headers
          if (line.startsWith('# ')) {
            return <h1 key={index} className="text-2xl font-bold mt-4 mb-2">
                  {line.substring(2)}
                </h1>;
          }
          if (line.startsWith('## ')) {
            return <h2 key={index} className="text-xl font-bold mt-4 mb-2">
                  {line.substring(3)}
                </h2>;
          }
          // Render lists
          if (line.startsWith('- [x] ')) {
            return <div key={index} className="flex items-start mb-1">
                  <input type="checkbox" checked readOnly className="mt-1 mr-2" />
                  <span>{line.substring(6)}</span>
                </div>;
          }
          if (line.startsWith('- [ ] ')) {
            return <div key={index} className="flex items-start mb-1">
                  <input type="checkbox" readOnly className="mt-1 mr-2" />
                  <span>{line.substring(6)}</span>
                </div>;
          }
          if (line.startsWith('- ')) {
            return <div key={index} className="ml-4 mb-1">
                  • {line.substring(2)}
                </div>;
          }
          // Empty lines
          if (line.trim() === '') {
            return <div key={index} className="h-4"></div>;
          }
          // Default paragraph
          return <div key={index} className="mb-1">
                {line}
              </div>;
        })}
        </div>
      </div>
      <div className="p-4 border-t border-border flex justify-between">
        <span className="text-xs text-muted-foreground">
          Last updated: 15:16:22
        </span>
        <button className="px-3 py-1 text-sm rounded-md bg-primary text-primary-foreground">
          Download
        </button>
      </div>
    </div>;
};