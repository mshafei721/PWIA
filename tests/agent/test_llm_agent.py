"""Tests for LLM agent integration."""
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
from agent.llm_agent import LLMAgent, AgentConfig, Message, ToolCall


@pytest.fixture
def agent_config():
    """Create test agent configuration."""
    return AgentConfig(
        api_key="test-api-key",
        model="gpt-4-turbo-preview",
        temperature=0.7,
        max_tokens=2000,
        system_prompt="You are a helpful web research assistant."
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    with patch('agent.llm_agent.AsyncOpenAI') as mock:
        client = Mock()
        mock.return_value = client
        yield client


class TestLLMAgent:
    """Test suite for LLM agent."""
    
    def test_agent_initialization(self, agent_config):
        """Test agent initialization with config."""
        agent = LLMAgent(agent_config)
        
        assert agent.config == agent_config
        assert agent.conversation_history == []
        assert agent.current_thread_id is None
        assert agent.tools_enabled is True
    
    @pytest.mark.asyncio
    async def test_create_thread(self, agent_config, mock_openai_client):
        """Test creating a new conversation thread."""
        agent = LLMAgent(agent_config)
        
        # Mock thread creation
        mock_thread = Mock(id="thread-123")
        mock_openai_client.beta.threads.create = AsyncMock(return_value=mock_thread)
        
        thread_id = await agent.create_thread()
        
        assert thread_id == "thread-123"
        assert agent.current_thread_id == "thread-123"
        mock_openai_client.beta.threads.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message(self, agent_config, mock_openai_client):
        """Test sending a message and receiving response."""
        agent = LLMAgent(agent_config)
        agent.current_thread_id = "thread-123"
        
        # Mock message creation
        mock_openai_client.beta.threads.messages.create = AsyncMock()
        
        # Mock run creation and completion
        mock_run = Mock(id="run-456", status="completed")
        mock_openai_client.beta.threads.runs.create = AsyncMock(return_value=mock_run)
        mock_openai_client.beta.threads.runs.retrieve = AsyncMock(return_value=mock_run)
        
        # Mock response messages
        mock_response = Mock(content="This is the AI response")
        mock_messages = Mock(data=[mock_response])
        mock_openai_client.beta.threads.messages.list = AsyncMock(return_value=mock_messages)
        
        response = await agent.send_message("Hello, AI!")
        
        assert response == "This is the AI response"
        assert len(agent.conversation_history) == 2  # User message + AI response
    
    @pytest.mark.asyncio
    async def test_streaming_response(self, agent_config, mock_openai_client):
        """Test streaming response handling."""
        agent = LLMAgent(agent_config)
        agent.current_thread_id = "thread-123"
        
        # Mock the messages.create call
        mock_openai_client.beta.threads.messages.create = AsyncMock()
        
        # Mock streaming events
        events = [
            Mock(type="thread.message.delta", data=Mock(delta=Mock(content="Hello"))),
            Mock(type="thread.message.delta", data=Mock(delta=Mock(content=" world"))),
            Mock(type="thread.message.completed", data=Mock(content="Hello world"))
        ]
        
        # Create async iterator for streaming
        async def mock_stream():
            for event in events:
                yield event
        
        mock_openai_client.beta.threads.runs.create_and_stream = AsyncMock(return_value=mock_stream())
        
        chunks = []
        async for chunk in agent.send_message_stream("Hi there!"):
            chunks.append(chunk)
        
        assert chunks == ["Hello", " world", "Hello world"]
    
    @pytest.mark.asyncio
    async def test_tool_calling(self, agent_config, mock_openai_client):
        """Test tool calling functionality."""
        agent = LLMAgent(agent_config)
        agent.current_thread_id = "thread-123"
        
        # Define test tool
        test_tool = {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
        
        agent.register_tool(test_tool)
        
        # Mock tool call in response with proper string values
        mock_tool_call = Mock()
        mock_tool_call.id = "call-123"
        mock_tool_call.function.name = "search_web"
        mock_tool_call.function.arguments = '{"query": "Python programming"}'
        
        tool_call_event = Mock()
        tool_call_event.type = "thread.run.requires_action"
        tool_call_event.data = Mock()
        tool_call_event.data.required_action = Mock()
        tool_call_event.data.required_action.tool_calls = [mock_tool_call]
        
        # Test tool call handling
        tool_calls = await agent._handle_tool_calls(tool_call_event)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "search_web"
        assert tool_calls[0].arguments == {"query": "Python programming"}
    
    def test_conversation_history(self, agent_config):
        """Test conversation history management."""
        agent = LLMAgent(agent_config)
        
        # Add messages
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there!")
        
        assert len(agent.conversation_history) == 2
        assert agent.conversation_history[0].role == "user"
        assert agent.conversation_history[0].content == "Hello"
        assert agent.conversation_history[1].role == "assistant"
        assert agent.conversation_history[1].content == "Hi there!"
    
    def test_clear_history(self, agent_config):
        """Test clearing conversation history."""
        agent = LLMAgent(agent_config)
        
        # Add messages
        agent.add_message("user", "Test")
        agent.add_message("assistant", "Response")
        
        # Clear history
        agent.clear_history()
        
        assert len(agent.conversation_history) == 0
        assert agent.current_thread_id is None
    
    @pytest.mark.asyncio
    async def test_error_handling(self, agent_config, mock_openai_client):
        """Test error handling in API calls."""
        agent = LLMAgent(agent_config)
        
        # Mock API error
        mock_openai_client.beta.threads.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        with pytest.raises(Exception, match="API Error"):
            await agent.create_thread()
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid temperature
        with pytest.raises(ValueError):
            AgentConfig(
                api_key="test",
                temperature=2.0  # Should be between 0 and 1
            )
        
        # Invalid max_tokens
        with pytest.raises(ValueError):
            AgentConfig(
                api_key="test",
                max_tokens=-100
            )
    
    @pytest.mark.asyncio
    async def test_context_management(self, agent_config, mock_openai_client):
        """Test context window management."""
        agent = LLMAgent(agent_config)
        
        # Add many messages to test truncation
        for i in range(100):
            agent.add_message("user", f"Message {i}")
            agent.add_message("assistant", f"Response {i}")
        
        # Should maintain reasonable history size
        context = agent.get_context_for_api()
        assert len(context) <= agent.config.max_context_messages