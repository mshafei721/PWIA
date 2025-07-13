import React, { useEffect, useState } from 'react';
interface ChatMessage {
  id: string;
  content: string;
  timestamp: string;
  type: 'status' | 'action' | 'result' | 'error';
}
export const ChatPanel: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isRunning, setIsRunning] = useState(true);
  useEffect(() => {
    // Initial messages
    const initialMessages: ChatMessage[] = [{
      id: '1',
      content: 'Task received: "Compare top open-source agent orchestration frameworks" → Decomposing intent using LLM...',
      timestamp: '15:12:01',
      type: 'status'
    }, {
      id: '2',
      content: '✅ → Goals: Google search → Crawl → Scrape GitHub → Extract metrics',
      timestamp: '15:12:05',
      type: 'result'
    }, {
      id: '3',
      content: 'Starting Google search...',
      timestamp: '15:12:30',
      type: 'action'
    }, {
      id: '4',
      content: '→ Found 20 links → Crawling github.com/langgraph/langgraph',
      timestamp: '15:13:15',
      type: 'action'
    }, {
      id: '5',
      content: '→ Extracted: 21.3k stars, docs ✅',
      timestamp: '15:14:22',
      type: 'result'
    }, {
      id: '6',
      content: '→ Confidence: 77% — need more diversity',
      timestamp: '15:14:45',
      type: 'status'
    }, {
      id: '7',
      content: '→ Repeating with new query...',
      timestamp: '15:15:00',
      type: 'action'
    }];
    setMessages(initialMessages);
    // Simulate new messages coming in
    const interval = setInterval(() => {
      if (isRunning) {
        const newMessages = [{
          id: String(Date.now()),
          content: 'Crawling github.com/crewai/crewai → Extracted: 14.2k stars, docs ✅',
          timestamp: new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          }),
          type: 'action' as const
        }];
        setMessages(prev => [...prev, ...newMessages]);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [isRunning]);
  const toggleAgentStatus = () => {
    setIsRunning(!isRunning);
    setMessages(prev => [...prev, {
      id: String(Date.now()),
      content: isRunning ? '⏸️ Agent paused by user' : '▶️ Agent resumed by user',
      timestamp: new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }),
      type: 'status'
    }]);
  };
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    setMessages(prev => [...prev, {
      id: String(Date.now()),
      content: `👤 User: ${inputValue}`,
      timestamp: new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }),
      type: 'status'
    }]);
    setInputValue('');
  };
  return <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">Agent Chat</h1>
          <div className="flex gap-2">
            <button onClick={toggleAgentStatus} className={`px-3 py-1 rounded-md ${isRunning ? 'bg-yellow-500 text-white' : 'bg-green-500 text-white'}`}>
              {isRunning ? '⏸️ Pause' : '▶️ Resume'}
            </button>
            <button className="px-3 py-1 rounded-md bg-red-500 text-white">
              ⏹️ Stop
            </button>
          </div>
        </div>
        <div className="text-sm text-muted-foreground mt-1">
          Task: Compare top open-source agent orchestration frameworks
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(message => <div key={message.id} className={`p-3 rounded-lg ${message.type === 'status' ? 'bg-muted' : message.type === 'action' ? 'bg-blue-50 dark:bg-blue-900/20' : message.type === 'result' ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
            <div className="flex justify-between items-start">
              <div className="text-sm">{message.content}</div>
              <div className="text-xs text-muted-foreground ml-2">
                {message.timestamp}
              </div>
            </div>
          </div>)}
      </div>
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input type="text" value={inputValue} onChange={e => setInputValue(e.target.value)} className="flex-1 p-2 border border-input rounded-md bg-background" placeholder="Send a message to the agent..." />
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-md">
            Send
          </button>
        </div>
      </form>
    </div>;
};