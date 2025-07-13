from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import uuid

from backend.routes import tasks
from backend.websocket_manager import connection_manager
from backend.event_bus import event_bus
from backend.models import WebSocketEventType

app = FastAPI(
    title="PWIA API",
    version="0.1.0",
    description="Persistent Web Intelligence Agent API"
)

# Configure CORS for Frontend development
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # Common React dev server port
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {
        "status": "healthy",
        "service": "PWIA API",
        "version": "0.1.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PWIA - Persistent Web Intelligence Agent API",
        "version": "0.1.0",
        "docs": "/docs"
    }

# WebSocket endpoint for real-time communication
@app.websocket("/ws/tasks/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str, client_id: str = None):
    """WebSocket endpoint for real-time task monitoring and communication"""
    client_id = None
    
    try:
        # Connect to WebSocket manager
        client_id = await connection_manager.connect(websocket, task_id, client_id)
        logging.info(f"WebSocket client {client_id} connected to task {task_id}")
        
        # Emit connection event through event bus
        await event_bus.emit_task_event(
            WebSocketEventType.CONNECTION_ESTABLISHED,
            task_id,
            {"client_id": client_id, "message": "Connected successfully"}
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for incoming messages
                data = await websocket.receive_text()
                logging.debug(f"Received message from {client_id}: {data}")
                
                # Parse and handle message (basic implementation)
                # In future versions, this could handle client commands, heartbeats, etc.
                try:
                    import json
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "unknown")
                    
                    if message_type == "heartbeat":
                        # Respond to heartbeat
                        await connection_manager.send_heartbeat(client_id)
                    elif message_type == "ping":
                        # Simple ping/pong for connection testing
                        await event_bus.emit_task_event(
                            WebSocketEventType.HEARTBEAT,
                            task_id,
                            {"type": "pong", "timestamp": message_data.get("timestamp")},
                            client_id
                        )
                    else:
                        logging.warning(f"Unknown message type from {client_id}: {message_type}")
                        
                except json.JSONDecodeError:
                    logging.warning(f"Invalid JSON from client {client_id}: {data}")
                except Exception as e:
                    logging.error(f"Error processing message from {client_id}: {e}")
                    
            except WebSocketDisconnect:
                logging.info(f"Client {client_id} disconnected from task {task_id}")
                break
            except Exception as e:
                logging.error(f"WebSocket error for client {client_id}: {e}")
                break
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
    finally:
        # Clean up connection
        if client_id:
            connection_manager.disconnect(client_id)
            await event_bus.emit_task_event(
                WebSocketEventType.CONNECTION_CLOSED,
                task_id,
                {"client_id": client_id, "message": "Connection closed"}
            )

# WebSocket connection status endpoint
@app.get("/api/v1/websocket/status")
async def websocket_status():
    """Get current WebSocket connection status"""
    connections = connection_manager.get_all_connections()
    stats = event_bus.get_stats()
    
    return {
        "status": "healthy",
        "total_connections": len(connections),
        "connections_by_task": {
            task_id: connection_manager.get_task_connections(task_id)
            for task_id in set(conn.task_id for conn in connections.values())
        },
        "event_bus_stats": stats
    }

# Include routers
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])