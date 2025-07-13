import React, { useState } from 'react';
interface TaskDetailPanelProps {
  taskId: string;
}
interface SubTask {
  id: string;
  title: string;
  completed: boolean;
  description?: string;
  file?: string;
}
export const TaskDetailPanel: React.FC<TaskDetailPanelProps> = ({
  taskId
}) => {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    design_analysis: true,
    reports: false
  });
  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId]
    }));
  };
  // Task data for the "Update Teaching Plans" task
  const taskData = {
    title: 'Update Teaching Plans Using Latest Free Resources',
    description: 'Create updated Design and Analysis of Algorithms teaching report with 14-week plan',
    subtasks: [{
      id: 'design_analysis',
      title: 'Knowledge recalled(2)',
      subtasks: [{
        id: 'create_report',
        title: 'Creating the updated Design and Analysis of Algorithms report.',
        completed: false
      }, {
        id: 'creating_file',
        title: 'Creating file',
        description: 'Updated_Design_and_Analysis_of_Algorithms_Report.md',
        completed: true,
        file: 'Updated_Design_and_Analysis_of_Algorithms_Report.md'
      }, {
        id: 'marking_complete',
        title: 'Marking Design and Analysis of Algorithms report creation as complete.',
        completed: true
      }, {
        id: 'editing_file',
        title: 'Editing file',
        description: 'todo.md',
        completed: true,
        file: 'todo.md'
      }]
    }, {
      id: 'reports',
      title: 'Deliver final updated reports to user',
      subtasks: [{
        id: 'knowledge_recalled',
        title: 'Knowledge recalled(4)',
        completed: false
      }]
    }]
  };
  const [currentTaskData] = useState(taskData);
  const renderSubtask = (subtask: SubTask) => {
    return <div key={subtask.id} className="flex items-start mb-3 ml-6">
        <div className="mr-3 mt-0.5">
          {subtask.completed ? <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div> : <div className="w-5 h-5 rounded-full border border-gray-300"></div>}
        </div>
        <div className="flex-1">
          <div className={`font-medium ${subtask.completed ? 'text-muted-foreground' : ''}`}>
            {subtask.title}
          </div>
          {subtask.description && <div className="text-sm text-muted-foreground mt-1">
              {subtask.file ? <div className="flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  {subtask.description}
                </div> : subtask.description}
            </div>}
        </div>
      </div>;
  };
  return <div className="h-full flex flex-col">
      <div className="p-6 border-b border-border">
        <h1 className="text-2xl font-bold">{currentTaskData.title}</h1>
        <p className="text-muted-foreground mt-1">
          {currentTaskData.description}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {currentTaskData.subtasks.map(section => <div key={section.id} className="mb-6">
            <div className="flex items-center cursor-pointer" onClick={() => toggleSection(section.id)}>
              <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center mr-3">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
              </div>
              <h2 className="text-lg font-medium">{section.title}</h2>
              <div className="ml-auto">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`transform transition-transform ${expandedSections[section.id] ? 'rotate-180' : ''}`}>
                  <path d="m18 15-6-6-6 6" />
                </svg>
              </div>
            </div>
            {expandedSections[section.id] && <div className="mt-4">
                {section.subtasks?.map(subtask => renderSubtask(subtask))}
              </div>}
          </div>)}
        {taskId === 'agent_frameworks_2025' && <div className="mt-8 border-t border-border pt-4">
            <div className="flex items-center mb-4">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mr-3">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
              </div>
              <h2 className="text-lg font-medium">manus</h2>
            </div>
            <div className="ml-11">
              <p className="text-sm mb-3">
                Here are the updated comprehensive reports with the latest free
                and open-source resources and 14-week teaching plans:
              </p>
              <div className="flex flex-col gap-3">
                <div className="flex items-start border border-border rounded-md p-3">
                  <div className="w-8 h-10 bg-blue-100 rounded flex items-center justify-center mr-3">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                  <div>
                    <div className="font-medium">
                      Updated Comprehensive Big Data Teaching Resources
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Markdown · 20.12 KB
                    </div>
                  </div>
                  <div className="ml-auto">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 3v12" />
                      <path d="m8 11 4 4 4-4" />
                      <path d="M8 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4" />
                    </svg>
                  </div>
                </div>
                <div className="flex items-start border border-border rounded-md p-3">
                  <div className="w-8 h-10 bg-blue-100 rounded flex items-center justify-center mr-3">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                  <div>
                    <div className="font-medium">
                      Updated Comprehensive Report on Big Data
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Markdown · 22.82 KB
                    </div>
                  </div>
                  <div className="ml-auto">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 3v12" />
                      <path d="m8 11 4 4 4-4" />
                      <path d="M8 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4" />
                    </svg>
                  </div>
                </div>
                <button className="text-sm text-blue-600 flex items-center mt-1">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
                    <rect width="18" height="18" x="3" y="3" rx="2" />
                    <path d="M7 12h10" />
                    <path d="M12 7v10" />
                  </svg>
                  View all files in this task
                </button>
              </div>
              <div className="mt-4 p-3 bg-green-50 rounded-md flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="green" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <span className="text-green-700">
                  Manus has completed the current task
                </span>
              </div>
              <div className="mt-4 flex items-center">
                <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center mr-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
                    <circle cx="9" cy="9" r="2" />
                    <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
                  </svg>
                </div>
                <span className="text-sm text-blue-600">
                  Share Manus's creation as an interactive website
                </span>
                <button className="ml-auto bg-gray-900 text-white text-xs px-3 py-1 rounded">
                  Create website
                </button>
              </div>
            </div>
          </div>}
      </div>
      <div className="border-t border-border p-4">
        <div className="flex">
          <input type="text" placeholder="Send message to Manus" className="flex-1 p-2 border border-input rounded-md bg-background" />
          <div className="flex ml-2 gap-2">
            <button className="p-2 rounded-md hover:bg-accent">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" x2="12" y1="3" y2="15" />
              </svg>
            </button>
            <button className="p-2 rounded-md hover:bg-accent">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
                <circle cx="9" cy="9" r="2" />
                <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
              </svg>
            </button>
            <button className="p-2 rounded-md hover:bg-accent">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>;
};