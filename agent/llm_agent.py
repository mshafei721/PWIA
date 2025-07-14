"""LLM Agent integration with OpenAI Assistant API."""
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, AsyncIterator
from pydantic import BaseModel, Field, field_validator
from openai import AsyncOpenAI


class AgentConfig(BaseModel):
    """Configuration for the LLM agent."""
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = "You are a helpful web research assistant."
    max_context_messages: int = 50
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        return v
    
    @field_validator('max_tokens')
    @classmethod
    def validate_max_tokens(cls, v):
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v


class Message(BaseModel):
    """Represents a conversation message."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    """Represents a tool call request."""
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMAgent:
    """Agent that interfaces with OpenAI Assistant API."""
    
    def __init__(self, config: AgentConfig):
        """Initialize the LLM agent."""
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key)
        self.conversation_history: List[Message] = []
        self.current_thread_id: Optional[str] = None
        self.tools_enabled = True
        self.registered_tools: List[Dict[str, Any]] = []
        self.assistant_id: Optional[str] = None
    
    async def create_thread(self) -> str:
        """Create a new conversation thread."""
        thread = await self.client.beta.threads.create()
        self.current_thread_id = thread.id
        return thread.id
    
    async def send_message(self, content: str) -> str:
        """Send a message and get response (non-streaming)."""
        if not self.current_thread_id:
            await self.create_thread()
        
        # Add user message to history
        self.add_message("user", content)
        
        # Create message in thread
        await self.client.beta.threads.messages.create(
            thread_id=self.current_thread_id,
            role="user",
            content=content
        )
        
        # Create and wait for run
        run = await self.client.beta.threads.runs.create(
            thread_id=self.current_thread_id,
            assistant_id=self.assistant_id or "asst_default",
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        # Wait for completion
        while run.status in ["queued", "in_progress"]:
            await asyncio.sleep(0.5)
            run = await self.client.beta.threads.runs.retrieve(
                thread_id=self.current_thread_id,
                run_id=run.id
            )
        
        # Get response messages
        messages = await self.client.beta.threads.messages.list(
            thread_id=self.current_thread_id,
            order="desc",
            limit=1
        )
        
        if messages.data:
            response_content = messages.data[0].content
            self.add_message("assistant", response_content)
            return response_content
        
        return ""
    
    async def send_message_stream(self, content: str) -> AsyncIterator[str]:
        """Send a message and stream the response."""
        if not self.current_thread_id:
            await self.create_thread()
        
        # Add user message to history
        self.add_message("user", content)
        
        # Create message in thread
        await self.client.beta.threads.messages.create(
            thread_id=self.current_thread_id,
            role="user",
            content=content
        )
        
        # Stream the response
        stream = await self.client.beta.threads.runs.create_and_stream(
            thread_id=self.current_thread_id,
            assistant_id=self.assistant_id or "asst_default",
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            tools=self.registered_tools if self.tools_enabled else None
        )
        
        full_response = ""
        async for event in stream:
            if event.type == "thread.message.delta":
                chunk = event.data.delta.content
                full_response += chunk
                yield chunk
            elif event.type == "thread.message.completed":
                # Final complete message
                self.add_message("assistant", event.data.content)
                yield event.data.content
            elif event.type == "thread.run.requires_action":
                # Handle tool calls
                tool_calls = await self._handle_tool_calls(event)
                # Tool results would be submitted back to the run
    
    def register_tool(self, tool_definition: Dict[str, Any]):
        """Register a tool that the agent can use."""
        self.registered_tools.append(tool_definition)
    
    async def _handle_tool_calls(self, event) -> List[ToolCall]:
        """Handle tool call requests from the assistant."""
        tool_calls = []
        
        if hasattr(event.data, 'required_action'):
            for tool_call in event.data.required_action.tool_calls:
                tc = ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments)
                )
                tool_calls.append(tc)
        
        return tool_calls
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to conversation history."""
        message = Message(
            role=role,
            content=content,
            metadata=metadata
        )
        self.conversation_history.append(message)
    
    def clear_history(self):
        """Clear conversation history and reset thread."""
        self.conversation_history = []
        self.current_thread_id = None
    
    def get_context_for_api(self) -> List[Dict[str, str]]:
        """Get conversation context formatted for API."""
        # Limit context to avoid token limits
        recent_messages = self.conversation_history[-self.config.max_context_messages:]
        
        context = []
        for msg in recent_messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return context
    
    async def create_assistant(self, name: str, instructions: str) -> str:
        """Create a new assistant with specific instructions."""
        assistant = await self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=self.config.model,
            tools=self.registered_tools
        )
        self.assistant_id = assistant.id
        return assistant.id
    
    async def update_assistant_instructions(self, instructions: str):
        """Update the assistant's instructions."""
        if not self.assistant_id:
            raise ValueError("No assistant created yet")
        
        await self.client.beta.assistants.update(
            assistant_id=self.assistant_id,
            instructions=instructions
        )
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the current conversation."""
        return {
            "thread_id": self.current_thread_id,
            "message_count": len(self.conversation_history),
            "last_message": self.conversation_history[-1].content if self.conversation_history else None,
            "tools_registered": len(self.registered_tools),
            "model": self.config.model
        }