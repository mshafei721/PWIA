// WebSocket Connection Status Component
import React from 'react';
import { ConnectionStatus as ConnectionStatusType } from '../lib/websocket';

interface ConnectionStatusProps {
  status: ConnectionStatusType;
  className?: string;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ 
  status, 
  className = '' 
}) => {
  const getStatusText = () => {
    if (status.isConnected) return 'Connected';
    if (status.isConnecting) return 'Connecting...';
    return 'Disconnected';
  };

  const getStatusColor = () => {
    if (status.isConnected) return 'bg-green-500';
    if (status.isConnecting) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className={`flex items-center text-sm ${className}`}>
      <div className={`w-2 h-2 rounded-full mr-2 ${getStatusColor()}`}></div>
      <span className="text-muted-foreground">
        {getStatusText()}
      </span>
      {status.connectionCount > 0 && (
        <span className="ml-2 text-xs text-muted-foreground">
          (#{status.connectionCount})
        </span>
      )}
    </div>
  );
};