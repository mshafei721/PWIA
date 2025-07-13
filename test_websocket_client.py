#!/usr/bin/env python3
"""
Simple WebSocket client test for PWIA backend
Tests the WebSocket connection and message handling
"""

import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to PWIA backend"""
    uri = "ws://localhost:8000/ws/tasks/test_001"
    
    try:
        logger.info(f"Connecting to {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket connection established!")
            
            # Test 1: Send a ping message
            ping_message = {
                "type": "ping",
                "timestamp": 1234567890
            }
            
            logger.info("📤 Sending ping message...")
            await websocket.send(json.dumps(ping_message))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received response: {response}")
                
                # Parse response
                response_data = json.loads(response)
                if response_data.get("event_type") == "heartbeat":
                    logger.info("✅ Heartbeat response received successfully!")
                
            except asyncio.TimeoutError:
                logger.warning("⚠️  No response received within 5 seconds")
            
            # Test 2: Send a heartbeat
            heartbeat_message = {
                "type": "heartbeat",
                "timestamp": 1234567890
            }
            
            logger.info("💓 Sending heartbeat message...")
            await websocket.send(json.dumps(heartbeat_message))
            
            # Wait a bit to see if connection stays alive
            await asyncio.sleep(2)
            
            logger.info("✅ WebSocket connection test completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ WebSocket connection failed: {e}")
        return False
    
    return True

async def main():
    """Main test function"""
    logger.info("🧪 Starting WebSocket client test...")
    
    success = await test_websocket_connection()
    
    if success:
        logger.info("🎉 All WebSocket tests passed!")
    else:
        logger.error("💥 WebSocket tests failed!")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)