import React, { useState } from 'react';
interface SidebarProps {
  activeTask: string;
  onSelectTask: (taskId: string) => void;
}
export const Sidebar: React.FC<SidebarProps> = ({
  activeTask,
  onSelectTask
}) => {
  const tasks = [{
    id: 'agent_frameworks_2025',
    name: 'Update Teaching Plans Using Latest Free Resources',
    description: 'Here are the updated comprehensive reports with the latest free and open-source resources',
    date: 'Thu',
    status: 'in-progress'
  }, {
    id: 'manus_development',
    name: 'How Was Manus Developed and Built?',
    description: 'We can not process your request now, please try again later',
    date: 'Tue',
    status: 'completed'
  }, {
    id: 'roadmaps',
    name: 'Roadmaps for Web, Mobile, and Desktop Development',
    description: 'I have completed your comprehensive software development roadmap',
    date: 'Mon',
    status: 'completed'
  }, {
    id: 'big_data_courses',
    name: 'Free Resources for Big Data Courses',
    description: "I've found several excellent free downloadable books for your course",
    date: '7/6',
    status: 'completed'
  }, {
    id: 'ai_frameworks',
    name: 'AI Agent Frameworks and Tools Comparison',
    description: 'I have completed your comprehensive report on AI agent frameworks',
    date: '7/6',
    status: 'completed'
  }];
  const categories = [{
    id: 'all',
    name: 'All'
  }, {
    id: 'favorites',
    name: 'Favorites'
  }, {
    id: 'scheduled',
    name: 'Scheduled'
  }];
  const [activeCategory, setActiveCategory] = useState('all');
  return <div className="h-full flex flex-col">
      <div className="p-4 flex items-center border-b border-border">
        <div className="mr-2 p-2 bg-gray-100 rounded-full">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 21V9" />
          </svg>
        </div>
        <div>
          <h1 className="text-lg font-medium">Tasks</h1>
        </div>
      </div>
      <div className="p-3 border-b border-border">
        <div className="flex items-center mb-2">
          <button className="flex items-center justify-center w-full py-2 px-3 bg-primary text-primary-foreground rounded-md">
            <span className="mr-1">+</span>
            <span>New task</span>
            <span className="ml-auto text-xs opacity-70">Ctrl K</span>
          </button>
        </div>
        <div className="flex space-x-2 mt-3">
          {categories.map(category => <button key={category.id} onClick={() => setActiveCategory(category.id)} className={`px-3 py-1 rounded-full text-sm ${activeCategory === category.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted'}`}>
              {category.name}
            </button>)}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {tasks.map(task => <div key={task.id} className={`p-3 border-b border-border cursor-pointer ${activeTask === task.id ? 'bg-accent/30' : 'hover:bg-accent/10'}`} onClick={() => onSelectTask(task.id)}>
            <div className="flex items-center mb-1">
              <div className="w-6 h-6 mr-2 flex-shrink-0">
                {task.id === 'agent_frameworks_2025' ? <div className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 8V4H8" />
                      <rect width="16" height="12" x="4" y="8" rx="2" />
                      <path d="M2 14h2" />
                      <path d="M20 14h2" />
                      <path d="M15 13v2" />
                      <path d="M9 13v2" />
                    </svg>
                  </div> : <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center">
                    {task.id.charAt(0).toUpperCase()}
                  </div>}
              </div>
              <div className="font-medium">{task.name}</div>
              <div className="ml-auto text-xs text-muted-foreground">
                {task.date}
              </div>
            </div>
            <div className="text-sm text-muted-foreground pl-8 line-clamp-1">
              {task.description}
            </div>
          </div>)}
      </div>
      <div className="mt-auto p-3 border-t border-border">
        <div className="flex items-center">
          <div className="w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center mr-2">
            M
          </div>
          <div>
            <div className="text-sm font-medium">Share Manus with a friend</div>
            <div className="text-xs text-muted-foreground">
              Get 500 credits each
            </div>
          </div>
          <div className="ml-auto">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m9 18 6-6-6-6" />
            </svg>
          </div>
        </div>
      </div>
    </div>;
};