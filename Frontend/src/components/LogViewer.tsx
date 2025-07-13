import React, { useState, Component } from 'react';
interface Log {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  component: string;
  message: string;
}
export const LogViewer: React.FC = () => {
  const [logFilter, setLogFilter] = useState<'all' | 'info' | 'warning' | 'error' | 'debug'>('all');
  const logs: Log[] = [{
    timestamp: '2025-07-13 15:12:01',
    level: 'info',
    component: 'TaskManager',
    message: 'Task initialized with ID: agent_frameworks_2025'
  }, {
    timestamp: '2025-07-13 15:12:03',
    level: 'debug',
    component: 'LLMPlanner',
    message: 'Sending prompt to GPT-4 for task decomposition'
  }, {
    timestamp: '2025-07-13 15:12:30',
    level: 'info',
    component: 'Browser',
    message: 'Starting Playwright browser instance'
  }, {
    timestamp: '2025-07-13 15:12:45',
    level: 'info',
    component: 'SearchEngine',
    message: 'Executing Google search for "agent orchestration frameworks"'
  }, {
    timestamp: '2025-07-13 15:13:10',
    level: 'debug',
    component: 'Scraper',
    message: 'Extracted 20 search result links'
  }, {
    timestamp: '2025-07-13 15:14:05',
    level: 'warning',
    component: 'RobotsChecker',
    message: 'Site genspark.ai disallows crawling in robots.txt'
  }, {
    timestamp: '2025-07-13 15:15:22',
    level: 'error',
    component: 'Browser',
    message: 'Connection timeout when accessing autogpt.dev'
  }, {
    timestamp: '2025-07-13 15:15:45',
    level: 'info',
    component: 'Crawler',
    message: 'Successfully crawled github.com/langgraph/langgraph'
  }];
  const filteredLogs = logFilter === 'all' ? logs : logs.filter(log => log.level === logFilter);
  return <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">System Logs</h1>
          <div className="flex gap-2">
            <select value={logFilter} onChange={e => setLogFilter(e.target.value as any)} className="text-xs p-1 border border-input rounded bg-background">
              <option value="all">All Logs</option>
              <option value="info">Info</option>
              <option value="warning">Warnings</option>
              <option value="error">Errors</option>
              <option value="debug">Debug</option>
            </select>
            <button className="px-2 py-1 text-xs rounded-md bg-muted">
              Export Logs
            </button>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase bg-muted">
            <tr>
              <th className="px-4 py-2 text-left">Time</th>
              <th className="px-4 py-2 text-left">Level</th>
              <th className="px-4 py-2 text-left">Component</th>
              <th className="px-4 py-2 text-left">Message</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log, index) => <tr key={index} className={`border-b border-border ${log.level === 'error' ? 'bg-red-50 dark:bg-red-900/20' : log.level === 'warning' ? 'bg-yellow-50 dark:bg-yellow-900/20' : 'bg-transparent'}`}>
                <td className="px-4 py-2 text-xs font-mono">{log.timestamp}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${log.level === 'info' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300' : log.level === 'warning' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300' : log.level === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300' : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'}`}>
                    {log.level}
                  </span>
                </td>
                <td className="px-4 py-2">{log.component}</td>
                <td className="px-4 py-2">{log.message}</td>
              </tr>)}
          </tbody>
        </table>
      </div>
      <div className="p-4 border-t border-border">
        <div className="flex justify-between items-center">
          <span className="text-xs text-muted-foreground">
            Showing {filteredLogs.length} of {logs.length} logs
          </span>
          <button className="px-2 py-1 text-xs rounded-md bg-muted">
            Clear Logs
          </button>
        </div>
      </div>
    </div>;
};