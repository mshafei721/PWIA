import React from 'react';
export const VMViewer: React.FC = () => {
  return <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="text-xl font-bold">VM Viewer</h2>
        <p className="text-xs text-muted-foreground">Live browser actions</p>
      </div>
      <div className="flex-1 flex items-center justify-center bg-black">
        <div className="bg-white w-full h-full max-h-[calc(100vh-80px)] overflow-hidden relative">
          {/* Simulated VM screen with a browser */}
          <div className="w-full h-8 bg-gray-200 flex items-center px-2 border-b">
            <div className="flex space-x-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
            <div className="ml-4 text-xs text-gray-600">
              Chrome - Google Search: agent orchestration frameworks
            </div>
          </div>
          <div className="w-full h-10 bg-white border-b flex items-center px-4 space-x-4">
            <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
            <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
            <div className="flex-1 h-6 bg-gray-100 rounded-md text-xs flex items-center px-2 text-gray-400">
              https://github.com/langgraph/langgraph
            </div>
          </div>
          <div className="p-4 text-xs">
            <div className="mb-4 flex items-center">
              <div className="w-8 h-8 bg-gray-200 rounded-full mr-2"></div>
              <div>
                <div className="font-bold">langgraph/langgraph</div>
                <div className="text-gray-500">
                  Building language agent systems with graphs
                </div>
              </div>
            </div>
            <div className="flex space-x-4 mb-4">
              <div className="flex items-center">
                <div className="w-3 h-3 bg-gray-300 rounded-full mr-1"></div>
                <span>Stars: 21.3k</span>
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-gray-300 rounded-full mr-1"></div>
                <span>Forks: 1.8k</span>
              </div>
            </div>
            <div className="border-t pt-2">
              <p>
                LangGraph is a library for building stateful, multi-actor
                applications with LLMs, built on top of LangChain. It extends
                LangChain's capabilities with...
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="p-4 border-t border-border">
        <div className="flex justify-between">
          <span className="text-xs text-muted-foreground">
            VM Status: Running
          </span>
          <div className="space-x-2">
            <button className="px-2 py-1 text-xs rounded-md bg-muted">
              Refresh
            </button>
            <button className="px-2 py-1 text-xs rounded-md bg-muted">
              Fullscreen
            </button>
          </div>
        </div>
      </div>
    </div>;
};