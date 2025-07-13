#!/usr/bin/env python3
"""
Progress update simulation for testing WebSocket integration
Simulates backend sending progress updates to connected clients
"""

import asyncio
import json
import logging
from backend.event_bus import event_bus
from backend.models import WebSocketEventType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simulate_task_progress():
    """Simulate task progress updates"""
    task_id = "test_001"
    
    logger.info("🚀 Starting task progress simulation...")
    
    # Simulate task started
    await event_bus.emit_task_event(
        WebSocketEventType.TASK_STARTED,
        task_id,
        {
            "status": "started",
            "message": "Task simulation started"
        }
    )
    
    # Simulate progress updates
    progress_steps = [
        (0.1, "Initializing task..."),
        (0.25, "Loading resources..."),
        (0.5, "Processing data..."),
        (0.75, "Generating results..."),
        (0.9, "Finalizing output..."),
        (1.0, "Task completed successfully!")
    ]
    
    for progress, message in progress_steps:
        logger.info(f"📊 Progress: {int(progress * 100)}% - {message}")
        
        await event_bus.emit_progress_update(
            task_id=task_id,
            progress=progress,
            message=message,
            confidence=0.8
        )
        
        # Wait between updates to simulate real work
        await asyncio.sleep(2)
    
    # Simulate task completion
    await event_bus.emit_task_event(
        WebSocketEventType.TASK_COMPLETED,
        task_id,
        {
            "status": "completed",
            "message": "Task simulation completed successfully",
            "results": {
                "files_processed": 10,
                "duration": "20 seconds"
            }
        }
    )
    
    logger.info("✅ Task progress simulation completed!")

async def main():
    """Main simulation function"""
    logger.info("🎭 Starting progress simulation for WebSocket testing...")
    
    # Run simulation
    await simulate_task_progress()
    
    logger.info("🎉 Progress simulation finished!")

if __name__ == "__main__":
    asyncio.run(main())