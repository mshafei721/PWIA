# Streamlit to React Translation Patterns

## Core Translation Strategies

### 1. State Management Migration

**Streamlit Patterns**:
```python
# Session state management
if 'agent_state' not in st.session_state:
    st.session_state.agent_state = {}

# Real-time updates through rerun
st.rerun()
```

**React Equivalent**:
```typescript
// Context API for global state
const AgentContext = createContext<AgentState>();

// WebSocket for real-time updates
const useWebSocket = (url: string) => {
  const [data, setData] = useState(null);
  // WebSocket implementation
};

// Component state with persistence
const usePersistedState = (key: string, defaultValue: any) => {
  const [state, setState] = useState(() => {
    const saved = localStorage.getItem(key);
    return saved ? JSON.parse(saved) : defaultValue;
  });
  
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(state));
  }, [key, state]);
  
  return [state, setState];
};
```

### 2. Component Architecture Translation

**Streamlit Modular Approach**:
- Function-based components with `st.` calls
- Expandable sections with `st.expander()`
- File uploads with `st.file_uploader()`
- Dynamic content rendering

**React Component Mapping**:
```typescript
// Expandable sections
interface ExpandablePanelProps {
  title: string;
  defaultExpanded?: boolean;
  children: React.ReactNode;
}

const ExpandablePanel: React.FC<ExpandablePanelProps> = ({ 
  title, 
  defaultExpanded = false, 
  children 
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  return (
    <div className="border rounded-lg">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 text-left flex justify-between items-center"
      >
        <span className="font-medium">{title}</span>
        <ChevronDownIcon className={`transform transition-transform ${
          isExpanded ? 'rotate-180' : ''
        }`} />
      </button>
      {isExpanded && (
        <div className="p-4 border-t">
          {children}
        </div>
      )}
    </div>
  );
};
```

### 3. Real-Time Updates Pattern

**Streamlit Auto-Refresh**:
- Automatic rerun on state changes
- `st.empty()` containers for dynamic content
- `time.sleep()` with `st.rerun()` for polling

**React Real-Time Implementation**:
```typescript
// WebSocket hook for real-time data
const useAgentUpdates = () => {
  const [agentState, setAgentState] = useState<AgentState>();
  const [isConnected, setIsConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/agent-updates');
    
    ws.onopen = () => setIsConnected(true);
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setAgentState(prev => ({ ...prev, ...update }));
    };
    ws.onclose = () => setIsConnected(false);
    
    return () => ws.close();
  }, []);
  
  return { agentState, isConnected };
};

// Component with real-time updates
const AgentMonitor: React.FC = () => {
  const { agentState, isConnected } = useAgentUpdates();
  
  return (
    <div className="space-y-4">
      <StatusIndicator connected={isConnected} />
      <TaskProgress tasks={agentState?.tasks || []} />
      <LogViewer logs={agentState?.logs || []} />
    </div>
  );
};
```

### 4. File Upload and Processing

**Streamlit File Upload**:
```python
uploaded_file = st.file_uploader(
    "Choose a file", 
    type=['txt', 'pdf', 'docx']
)
if uploaded_file:
    content = process_uploaded_file(uploaded_file)
```

**React File Upload Component**:
```typescript
interface FileUploadProps {
  onFileUpload: (content: string, filename: string) => void;
  acceptedTypes: string[];
}

const FileUpload: React.FC<FileUploadProps> = ({ 
  onFileUpload, 
  acceptedTypes 
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  
  const handleFile = async (file: File) => {
    try {
      const content = await processFile(file);
      onFileUpload(content, file.name);
    } catch (error) {
      console.error('File processing error:', error);
    }
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleFile(files[0]);
  };
  
  return (
    <div 
      className={`border-2 border-dashed p-8 text-center transition-colors ${
        isDragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
      }`}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
    >
      <input
        type="file"
        accept={acceptedTypes.join(',')}
        onChange={(e) => {
          if (e.target.files?.[0]) handleFile(e.target.files[0]);
        }}
        className="hidden"
        id="file-upload"
      />
      <label htmlFor="file-upload" className="cursor-pointer">
        <UploadIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2">Drop a file here or click to upload</p>
      </label>
    </div>
  );
};
```

## PWIA-Specific Adaptations

### 1. Enhanced Task Monitoring

**Current PWIA Pattern**:
```typescript
// Static task data rendering
const taskData = {
  title: 'Update Teaching Plans Using Latest Free Resources',
  subtasks: [...]
};
```

**Enhanced with Multi-Agent Patterns**:
```typescript
// Dynamic task state with real-time updates
interface TaskState {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed';
  progress: number;
  subtasks: SubTask[];
  agentNotes: AgentNote[];
  confidence: number;
  lastUpdated: Date;
}

const useTaskMonitoring = (taskId: string) => {
  const [taskState, setTaskState] = useState<TaskState>();
  const { agentState } = useAgentUpdates();
  
  useEffect(() => {
    if (agentState?.currentTask?.id === taskId) {
      setTaskState(agentState.currentTask);
    }
  }, [agentState, taskId]);
  
  return taskState;
};
```

### 2. Agent Communication Interface

**Multi-Agent Inspired Chat**:
```typescript
interface AgentMessage {
  id: string;
  timestamp: Date;
  type: 'thinking' | 'action' | 'result' | 'error';
  content: string;
  confidence?: number;
  metadata?: Record<string, any>;
}

const AgentCommunicationPanel: React.FC = () => {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  
  const sendMessage = async (content: string) => {
    const message: AgentMessage = {
      id: Date.now().toString(),
      timestamp: new Date(),
      type: 'action',
      content
    };
    
    setMessages(prev => [...prev, message]);
    
    // Send to agent via WebSocket
    await sendToAgent(content);
  };
  
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(message => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                sendMessage(input);
                setInput('');
              }
            }}
            placeholder="Send message to agent..."
            className="flex-1 p-2 border rounded"
          />
          <button
            onClick={() => { sendMessage(input); setInput(''); }}
            className="px-4 py-2 bg-blue-500 text-white rounded"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};
```

### 3. Configuration and Control Panel

**Inspired by Multi-Agent Configuration**:
```typescript
interface AgentConfig {
  model: string;
  temperature: number;
  maxTokens: number;
  enableWebBrowsing: boolean;
  confidenceThreshold: number;
  retryAttempts: number;
}

const AgentConfigPanel: React.FC = () => {
  const [config, setConfig] = usePersistedState<AgentConfig>('agent-config', {
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 4000,
    enableWebBrowsing: true,
    confidenceThreshold: 0.85,
    retryAttempts: 3
  });
  
  const updateConfig = (updates: Partial<AgentConfig>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };
  
  return (
    <ExpandablePanel title="Agent Configuration" defaultExpanded={false}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Model</label>
          <select
            value={config.model}
            onChange={(e) => updateConfig({ model: e.target.value })}
            className="w-full p-2 border rounded"
          >
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">
            Temperature: {config.temperature}
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={config.temperature}
            onChange={(e) => updateConfig({ temperature: parseFloat(e.target.value) })}
            className="w-full"
          />
        </div>
        
        <div className="flex items-center">
          <input
            type="checkbox"
            checked={config.enableWebBrowsing}
            onChange={(e) => updateConfig({ enableWebBrowsing: e.target.checked })}
            className="mr-2"
          />
          <label className="text-sm">Enable Web Browsing</label>
        </div>
      </div>
    </ExpandablePanel>
  );
};
```

## Implementation Priority

1. **WebSocket Integration**: Implement real-time updates for agent communication
2. **Enhanced Task Visualization**: Add expandable sections and progress tracking
3. **Configuration Panel**: Create agent parameter tuning interface
4. **File Upload Enhancement**: Add drag-and-drop and multiple file support
5. **Export Functionality**: Implement multiple export formats
6. **Error Handling**: Add robust error boundaries and recovery mechanisms
7. **Performance Monitoring**: Add metrics tracking and visualization

These patterns provide a clear roadmap for enhancing the PWIA interface with proven multi-agent UI concepts adapted for single-agent monitoring and control.