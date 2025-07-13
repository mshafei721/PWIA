// React Hook for WebSocket Integration
import { useCallback, useEffect, useRef, useState } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import {
  WebSocketMessage,
  WebSocketEventType,
  ConnectionStatus,
  EventHandler,
  WebSocketUtils,
  DEFAULT_WEBSOCKET_CONFIG,
  TaskUpdateData,
  ProgressUpdateData,
  AgentStatusData
} from '../lib/websocket';

export interface UseWebSocketProps {
  taskId: string;
  enabled?: boolean;
  onTaskUpdate?: EventHandler<TaskUpdateData>;
  onProgress?: EventHandler<ProgressUpdateData>;
  onAgentStatus?: EventHandler<AgentStatusData>;
  onMessage?: EventHandler<WebSocketMessage>;
  onError?: (error: Event) => void;
}

export interface UseWebSocketReturn {
  connectionStatus: ConnectionStatus;
  sendMessage: (message: any) => void;
  sendHeartbeat: () => void;
  lastMessage: WebSocketMessage | null;
  messageHistory: WebSocketMessage[];
  isConnected: boolean;
  reconnect: () => void;
}

export const useTaskWebSocket = ({
  taskId,
  enabled = true,
  onTaskUpdate,
  onProgress,
  onAgentStatus,
  onMessage,
  onError
}: UseWebSocketProps): UseWebSocketReturn => {
  const [lastParsedMessage, setLastParsedMessage] = useState<WebSocketMessage | null>(null);
  const [messageHistory, setMessageHistory] = useState<WebSocketMessage[]>([]);
  const [connectionCount, setConnectionCount] = useState(0);
  const didUnmount = useRef(false);

  // Build WebSocket URL
  const socketUrl = enabled ? WebSocketUtils.getWebSocketUrl(taskId) : null;

  // WebSocket connection with react-use-websocket
  const {
    sendMessage: sendRawMessage,
    lastMessage,
    readyState,
    getWebSocket
  } = useWebSocket(
    socketUrl,
    {
      // Connection event handlers
      onOpen: () => {
        console.log(`WebSocket connected to task ${taskId}`);
        setConnectionCount(prev => prev + 1);
      },
      
      onClose: (event) => {
        console.log(`WebSocket disconnected from task ${taskId}:`, event.code, event.reason);
      },
      
      onError: (error) => {
        console.error(`WebSocket error for task ${taskId}:`, error);
        onError?.(error);
      },

      // Reconnection configuration
      shouldReconnect: (closeEvent) => {
        return didUnmount.current === false && WebSocketUtils.shouldReconnect(closeEvent);
      },
      reconnectAttempts: DEFAULT_WEBSOCKET_CONFIG.reconnectAttempts,
      reconnectInterval: WebSocketUtils.getReconnectInterval,

      // Message filtering for heartbeat handling
      filter: (message) => {
        const parsed = WebSocketUtils.parseMessage(message.data);
        if (parsed?.event_type === WebSocketEventType.HEARTBEAT) {
          // Handle heartbeat silently, don't propagate to UI
          return false;
        }
        return true;
      },

      // Heartbeat configuration
      heartbeat: {
        message: 'ping',
        returnMessage: 'pong',
        timeout: 60000, // 1 minute timeout
        interval: DEFAULT_WEBSOCKET_CONFIG.heartbeatInterval
      }
    },
    enabled
  );

  // Parse incoming messages
  useEffect(() => {
    if (lastMessage?.data) {
      const parsed = WebSocketUtils.parseMessage(lastMessage.data);
      if (parsed) {
        setLastParsedMessage(parsed);
        setMessageHistory(prev => [...prev.slice(-99), parsed]); // Keep last 100 messages
        
        // Route messages to specific handlers
        switch (parsed.event_type) {
          case WebSocketEventType.TASK_UPDATED:
            onTaskUpdate?.(parsed.data as TaskUpdateData);
            break;
          case WebSocketEventType.PROGRESS_UPDATE:
            onProgress?.(parsed.data as ProgressUpdateData);
            break;
          case WebSocketEventType.AGENT_STATUS_CHANGE:
            onAgentStatus?.(parsed.data as AgentStatusData);
            break;
          default:
            // Forward all messages to general handler
            onMessage?.(parsed);
            break;
        }
      }
    }
  }, [lastMessage, onTaskUpdate, onProgress, onAgentStatus, onMessage]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      didUnmount.current = true;
    };
  }, []);

  // Send structured message
  const sendMessage = useCallback((message: any) => {
    if (readyState === ReadyState.OPEN) {
      sendRawMessage(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, message not sent:', message);
    }
  }, [sendRawMessage, readyState]);

  // Send heartbeat manually
  const sendHeartbeat = useCallback(() => {
    sendMessage({
      type: 'heartbeat',
      timestamp: Date.now()
    });
  }, [sendMessage]);

  // Reconnect manually
  const reconnect = useCallback(() => {
    const ws = getWebSocket();
    if (ws) {
      ws.close();
    }
  }, [getWebSocket]);

  // Build connection status
  const connectionStatus: ConnectionStatus = {
    ...WebSocketUtils.getConnectionStatus(readyState),
    connectionCount,
    lastPingTimestamp: Date.now() // Updated by heartbeat
  };

  return {
    connectionStatus,
    sendMessage,
    sendHeartbeat,
    lastMessage: lastParsedMessage,
    messageHistory,
    isConnected: readyState === ReadyState.OPEN,
    reconnect
  };
};

// Simplified hook for basic WebSocket usage
export const useSimpleWebSocket = (taskId: string, enabled = true) => {
  return useTaskWebSocket({ taskId, enabled });
};