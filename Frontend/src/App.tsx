import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TaskDetailPanel } from './components/TaskDetailPanel';
import { DocumentViewer } from './components/DocumentViewer';
export function App() {
  const [rightPanelVisible, setRightPanelVisible] = useState(true);
  const [leftPanelVisible, setLeftPanelVisible] = useState(true);
  const [activeTask, setActiveTask] = useState('agent_frameworks_2025');
  return <div className="flex h-screen w-full bg-background text-foreground">
      {/* Left Sidebar */}
      {leftPanelVisible && <div className="w-72 border-r border-border bg-background overflow-y-auto">
          <Sidebar activeTask={activeTask} onSelectTask={setActiveTask} />
        </div>}
      {/* Toggle button for left sidebar */}
      <button onClick={() => setLeftPanelVisible(!leftPanelVisible)} className="absolute top-4 left-2 z-10 bg-primary text-primary-foreground p-1 rounded-md">
        {leftPanelVisible ? '←' : '→'}
      </button>
      {/* Main Content - Task Details */}
      <div className={`flex-1 overflow-y-auto ${!rightPanelVisible ? 'mr-4' : ''}`}>
        <TaskDetailPanel taskId={activeTask} />
      </div>
      {/* Right Panel - Document Viewer */}
      {rightPanelVisible && <div className="w-1/3 border-l border-border bg-white overflow-y-auto">
          <DocumentViewer taskId={activeTask} />
        </div>}
      {/* Toggle button for right panel */}
      <button onClick={() => setRightPanelVisible(!rightPanelVisible)} className="absolute top-4 right-2 z-10 bg-primary text-primary-foreground p-1 rounded-md">
        {rightPanelVisible ? '→' : '←'}
      </button>
    </div>;
}