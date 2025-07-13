#!/usr/bin/env python3
"""
Complete WebSocket flow test
Tests WebSocket connection + progress updates together
"""

import asyncio
import websockets
import json
import logging
from backend.event_bus import event_bus
from backend.models import WebSocketEventType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def websocket_client_listener():
    """WebSocket client that listens for messages"""
    uri = "ws://localhost:8000/ws/tasks/test_001"
    
    try:
        logger.info(f"🔌 Client connecting to {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Client connected!")
            
            # Listen for messages
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    event_type = data.get("event_type")
                    if event_type == "progress_update":
                        progress_data = data.get("data", {})
                        progress = progress_data.get("progress", 0)
                        message_text = progress_data.get("message", "")
                        logger.info(f"📊 Client received progress: {int(progress * 100)}% - {message_text}")
                    elif event_type == "task_started":
                        logger.info("🚀 Client received: Task started")
                    elif event_type == "task_completed":
                        logger.info("✅ Client received: Task completed")
                        break
                    elif event_type == "connection_established":
                        logger.info("🔗 Client received: Connection established")
                    else:
                        logger.info(f"📨 Client received: {event_type}")
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"❌ Client error: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"❌ Client connection failed: {e}")

async def progress_simulator():
    """Simulate progress updates"""
    task_id = "test_001"
    
    # Wait a bit for client to connect
    await asyncio.sleep(2)
    
    logger.info("🎭 Starting progress simulation...")
    
    # Task started
    await event_bus.emit_task_event(
        WebSocketEventType.TASK_STARTED,
        task_id,
        {"status": "started", "message": "Full flow test started"}
    )
    
    # Progress updates
    for i, (progress, message) in enumerate([
        (0.2, "Connecting to data source..."),
        (0.4, "Downloading files..."),
        (0.6, "Processing content..."),
        (0.8, "Generating report..."),
        (1.0, "Task completed!")
    ]):
        await asyncio.sleep(1)
        logger.info(f"📡 Server sending progress: {int(progress * 100)}% - {message}")
        
        await event_bus.emit_progress_update(
            task_id=task_id,
            progress=progress,
            message=message,
            confidence=0.9
        )
    
    # Task completed
    await event_bus.emit_task_event(
        WebSocketEventType.TASK_COMPLETED,
        task_id,
        {"status": "completed", "message": "Full flow test completed"}
    )
    
    logger.info("✅ Progress simulation finished!")

async def main():
    """Main test function"""
    logger.info("🧪 Starting full WebSocket flow test...")
    
    # Run client and simulator concurrently
    await asyncio.gather(
        websocket_client_listener(),
        progress_simulator()
    )
    
    logger.info("🎉 Full WebSocket flow test completed!")

if __name__ == "__main__":
    asyncio.run(main())