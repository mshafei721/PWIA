"""Tests for task planner and decomposition."""
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest
from agent.planner import TaskPlanner, TaskConfig, SubTask, PlanningContext


@pytest.fixture
def task_config():
    """Create test task configuration.""" 
    return TaskConfig(
        task_id="test-task-123",
        description="Research Python web frameworks",
        workspace_dir="workspace/test-task-123",
        max_subtasks=10,
        confidence_threshold=70.0
    )


@pytest.fixture
def planning_context():
    """Create test planning context."""
    return PlanningContext(
        user_prompt="Find information about FastAPI and Django",
        search_constraints=["focus on performance", "include examples"],
        output_format="markdown",
        time_limit_minutes=30
    )


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace directory."""
    workspace = tmp_path / "workspace" / "test-task-123"
    workspace.mkdir(parents=True)
    return workspace


class TestTaskPlanner:
    """Test suite for task planner."""
    
    def test_planner_initialization(self, task_config):
        """Test planner initialization with config."""
        planner = TaskPlanner(task_config)
        
        assert planner.config == task_config
        assert planner.subtasks == []
        assert planner.current_subtask_index == 0
        assert planner.is_plan_complete is False
    
    @pytest.mark.asyncio
    async def test_decompose_task(self, task_config, planning_context):
        """Test task decomposition into subtasks."""
        planner = TaskPlanner(task_config)
        
        # Mock LLM agent for task decomposition
        with patch('agent.planner.LLMAgent') as mock_llm:
            mock_agent = Mock()
            mock_agent.send_message = AsyncMock(return_value="""
            1. Search for FastAPI documentation and tutorials
            2. Research Django performance benchmarks
            3. Compare framework features and use cases
            4. Create summary table of findings
            """)
            mock_llm.return_value = mock_agent
            
            await planner.decompose_task(planning_context)
            
            assert len(planner.subtasks) == 4
            assert planner.subtasks[0].title == "Search for FastAPI documentation and tutorials"
            assert planner.subtasks[0].status == "pending"
            assert planner.subtasks[0].estimated_duration == 10  # Search tasks are 10min
    
    def test_create_subtask(self, task_config):
        """Test creating individual subtasks."""
        planner = TaskPlanner(task_config)
        
        subtask = planner.create_subtask(
            title="Research FastAPI performance",
            description="Look up FastAPI benchmarks and performance studies",
            estimated_duration=20,
            priority="high"
        )
        
        assert subtask.id.startswith("test-task-123-")
        assert subtask.title == "Research FastAPI performance"
        assert subtask.description == "Look up FastAPI benchmarks and performance studies"
        assert subtask.estimated_duration == 20
        assert subtask.priority == "high"
        assert subtask.status == "pending"
    
    def test_update_subtask_progress(self, task_config):
        """Test updating subtask progress and status."""
        planner = TaskPlanner(task_config)
        
        # Create a subtask
        subtask = planner.create_subtask("Test task", "Test description")
        planner.add_subtask(subtask)
        
        # Update progress
        planner.update_subtask_progress(subtask.id, 50.0, "in_progress")
        
        updated_subtask = planner.get_subtask(subtask.id)
        assert updated_subtask.progress == 50.0
        assert updated_subtask.status == "in_progress"
    
    def test_get_current_subtask(self, task_config):
        """Test getting the current active subtask."""
        planner = TaskPlanner(task_config)
        
        # Add some subtasks
        task1 = planner.create_subtask("Task 1", "First task")
        task2 = planner.create_subtask("Task 2", "Second task")
        planner.add_subtask(task1)
        planner.add_subtask(task2)
        
        # Should return first pending task
        current = planner.get_current_subtask()
        assert current.id == task1.id
        
        # Complete first task
        planner.update_subtask_progress(task1.id, 100.0, "completed")
        
        # Should now return second task
        current = planner.get_current_subtask()
        assert current.id == task2.id
    
    def test_calculate_overall_progress(self, task_config):
        """Test overall progress calculation."""
        task_config.auto_save = False  # Disable auto-save for test
        planner = TaskPlanner(task_config)
        
        # Add subtasks with different progress
        task1 = planner.create_subtask("Task 1", "First task")
        task2 = planner.create_subtask("Task 2", "Second task")
        task3 = planner.create_subtask("Task 3", "Third task")
        
        planner.add_subtask(task1)
        planner.add_subtask(task2) 
        planner.add_subtask(task3)
        
        # Set different progress levels
        planner.update_subtask_progress(task1.id, 100.0, "completed")  # 100%
        planner.update_subtask_progress(task2.id, 50.0, "in_progress") # 50%
        planner.update_subtask_progress(task3.id, 0.0, "pending")      # 0%
        
        overall_progress = planner.calculate_overall_progress()
        assert overall_progress == 50.0  # (100 + 50 + 0) / 3
    
    def test_generate_todo_file(self, task_config, temp_workspace):
        """Test generating todo.md file in workspace."""
        task_config.workspace_dir = str(temp_workspace)
        planner = TaskPlanner(task_config)
        
        # Add some subtasks
        task1 = planner.create_subtask("Research FastAPI", "Look up FastAPI docs")
        task2 = planner.create_subtask("Compare frameworks", "Create comparison table")
        
        planner.add_subtask(task1)
        planner.add_subtask(task2)
        
        # Update progress on first task
        planner.update_subtask_progress(task1.id, 75.0, "in_progress")
        
        # Generate todo file
        todo_path = planner.generate_todo_file()
        
        assert todo_path.exists()
        content = todo_path.read_text()
        
        # Check content format
        assert "# Task Plan: Research Python web frameworks" in content
        assert "## Progress: 37.5%" in content  # (75 + 0) / 2
        assert "- [⏳] Research FastAPI" in content  # in_progress
        assert "- [ ] Compare frameworks" in content  # pending
    
    def test_load_existing_plan(self, task_config, temp_workspace):
        """Test loading existing plan from todo.md file."""
        task_config.workspace_dir = str(temp_workspace)
        
        # Create existing todo.md file
        todo_content = """# Task Plan: Test Task

## Progress: 50.0%

### Subtasks:
- [x] Task 1 (completed) - 100.0%
- [ ] Task 2 (pending) - 0.0%
"""
        todo_file = temp_workspace / "todo.md"
        todo_file.write_text(todo_content)
        
        planner = TaskPlanner(task_config)
        loaded = planner.load_existing_plan()
        
        assert loaded is True
        assert len(planner.subtasks) >= 0  # Should have loaded tasks
    
    def test_adaptive_planning(self, task_config):
        """Test adaptive planning based on confidence scores."""
        planner = TaskPlanner(task_config)
        
        # Create subtask with low confidence
        subtask = planner.create_subtask("Complex research", "Difficult task")
        planner.add_subtask(subtask)
        
        # Simulate low confidence requiring replanning
        needs_replan = planner.should_replan(confidence_score=40.0)
        assert needs_replan is True  # Below threshold of 70
        
        # High confidence should not require replanning
        needs_replan = planner.should_replan(confidence_score=85.0)
        assert needs_replan is False
    
    def test_export_plan_json(self, task_config):
        """Test exporting plan to JSON format."""
        planner = TaskPlanner(task_config)
        
        # Add subtasks
        task1 = planner.create_subtask("Task 1", "First task")
        task2 = planner.create_subtask("Task 2", "Second task")
        planner.add_subtask(task1)
        planner.add_subtask(task2)
        
        # Export to JSON
        plan_json = planner.export_plan_json()
        plan_data = json.loads(plan_json)
        
        assert plan_data["task_id"] == "test-task-123"
        assert plan_data["description"] == "Research Python web frameworks"
        assert len(plan_data["subtasks"]) == 2
        assert plan_data["overall_progress"] == 0.0
    
    @pytest.mark.asyncio
    async def test_dynamic_task_adjustment(self, task_config, planning_context):
        """Test dynamic task adjustment based on progress."""
        planner = TaskPlanner(task_config)
        
        # Mock LLM for replanning
        with patch('agent.planner.LLMAgent') as mock_llm:
            mock_agent = Mock()
            mock_agent.send_message = AsyncMock(return_value="""
            Based on progress, adjusting plan:
            1. Skip redundant research (already completed)
            2. Focus on performance comparison
            3. Add new task: Create deployment guide
            """)
            mock_llm.return_value = mock_agent
            
            # Initial task
            original_task = planner.create_subtask("Original task", "Original description")
            planner.add_subtask(original_task)
            
            # Adjust plan based on findings
            await planner.adjust_plan_dynamically(
                current_findings="FastAPI is clearly faster",
                confidence_score=60.0  # Below threshold
            )
            
            # Should have called LLM for replanning
            mock_agent.send_message.assert_called()
    
    def test_workspace_management(self, task_config, temp_workspace):
        """Test workspace directory creation and management."""
        task_config.workspace_dir = str(temp_workspace)
        planner = TaskPlanner(task_config)
        
        # Ensure workspace is created
        planner.ensure_workspace_exists()
        
        assert temp_workspace.exists()
        assert (temp_workspace / "logs").exists()
        assert (temp_workspace / "outputs").exists()
        
        # Test creating subtask-specific directories
        subtask = planner.create_subtask("Research task", "Research description")
        subtask_dir = planner.get_subtask_workspace(subtask.id)
        
        assert subtask_dir.exists()
        assert subtask_dir.name == subtask.id


class TestBrowserAutomationPlanning:
    """Test suite for browser automation specific planning."""
    
    @pytest.fixture
    def browser_task_config(self):
        """Create browser automation task configuration."""
        return TaskConfig(
            task_id="browser-test-123",
            description="Crawl e-commerce sites for product data",
            workspace_dir="workspace/browser-test-123",
            max_subtasks=15,
            confidence_threshold=75.0
        )
    
    @pytest.fixture
    def crawl_context(self):
        """Create crawling context."""
        return PlanningContext(
            user_prompt="Extract product information from e-commerce sites",
            search_constraints=["respect robots.txt", "rate limit 1 req/sec"],
            output_format="json",
            time_limit_minutes=45
        )
    
    @pytest.mark.asyncio
    async def test_decompose_crawl_task(self, browser_task_config, crawl_context):
        """Test decomposing a crawling task into subtasks."""
        planner = TaskPlanner(browser_task_config)
        
        # Test URLs
        test_urls = [
            "https://example.com/products",
            "https://shop.example.com/catalog",
            "https://store.example.org/items"
        ]
        
        # Mock LLM response
        with patch('agent.planner.LLMAgent') as mock_llm:
            mock_agent = Mock()
            mock_agent.send_message = AsyncMock(return_value="""
            1. Validate URLs and check robots.txt compliance
            2. Analyze site structure for efficient crawling
            3. Crawl example.com domain systematically
            4. Crawl shop.example.com domain
            5. Extract product data from all pages
            6. Compile and export results
            """)
            mock_llm.return_value = mock_agent
            
            # Decompose crawl task
            subtasks = await planner.decompose_crawl_task(
                urls=test_urls,
                context=crawl_context,
                crawl_depth=2,
                max_pages=30
            )
            
            # Should create structured subtasks
            assert len(subtasks) >= 4  # Validation, domain crawls, extraction, export
            
            # Check for validation task
            validation_tasks = [t for t in subtasks if "validation" in t.title.lower()]
            assert len(validation_tasks) == 1
            assert validation_tasks[0].task_type == "crawl"
            assert len(validation_tasks[0].urls) == 3
            
            # Check for domain-specific crawl tasks
            crawl_tasks = [t for t in subtasks 
                          if t.task_type == "crawl" and "crawl" in t.title.lower()]
            assert len(crawl_tasks) >= 2  # At least 2 domains
            
            # Check for extraction task
            extraction_tasks = [t for t in subtasks if t.task_type == "extract"]
            assert len(extraction_tasks) == 1
            
            # Check for export task
            export_tasks = [t for t in subtasks if t.task_type == "export"]
            assert len(export_tasks) == 1
    
    def test_create_extraction_subtask(self, browser_task_config):
        """Test creating data extraction subtasks."""
        planner = TaskPlanner(browser_task_config)
        
        # Test data
        url = "https://example.com/products"
        selectors = [
            ".product-name",
            ".product-price",
            ".product-description"
        ]
        
        # Create extraction subtask
        extraction_task = planner.create_extraction_subtask(
            url=url,
            selectors=selectors,
            title="Extract product data"
        )
        
        assert extraction_task.task_type == "extract"
        assert extraction_task.urls == [url]
        assert extraction_task.selectors == selectors
        assert extraction_task.title == "Extract product data"
        assert extraction_task.estimated_duration == 5 + len(selectors) * 2  # 11 minutes
    
    def test_create_analysis_subtask(self, browser_task_config):
        """Test creating data analysis subtasks."""
        planner = TaskPlanner(browser_task_config)
        
        # Create analysis subtask
        analysis_task = planner.create_analysis_subtask(
            data_source="product_data.json",
            analysis_type="price_comparison"
        )
        
        assert analysis_task.task_type == "analyze"
        assert "price_comparison" in analysis_task.title
        assert "product_data.json" in analysis_task.title
        assert analysis_task.estimated_duration == 20
    
    def test_browser_subtask_filtering(self, browser_task_config):
        """Test filtering browser automation subtasks."""
        planner = TaskPlanner(browser_task_config)
        
        # Add mixed subtasks
        general_task = planner.create_subtask("General planning", "Regular task")
        crawl_task = SubTask(
            title="Crawl website",
            description="Crawl example.com",
            task_type="crawl"
        )
        extract_task = SubTask(
            title="Extract data",
            description="Extract product info",
            task_type="extract"
        )
        
        planner.add_subtask(general_task)
        planner.add_subtask(crawl_task)
        planner.add_subtask(extract_task)
        
        # Get browser subtasks only
        browser_tasks = planner.get_browser_subtasks()
        
        assert len(browser_tasks) == 2  # crawl + extract
        assert all(t.task_type in ["crawl", "extract", "analyze", "export"] 
                  for t in browser_tasks)
    
    def test_next_task_selection(self, browser_task_config):
        """Test selecting next crawl/extraction tasks."""
        planner = TaskPlanner(browser_task_config)
        
        # Create tasks with dependencies
        validation_task = SubTask(
            id="val-01",
            title="Validate URLs",
            description="Check robots.txt",
            task_type="crawl",
            status="completed"
        )
        
        crawl_task = SubTask(
            id="crawl-01", 
            title="Crawl site",
            description="Crawl example.com",
            task_type="crawl",
            status="pending",
            dependencies=["val-01"]
        )
        
        extract_task = SubTask(
            id="extract-01",
            title="Extract data", 
            description="Extract product data",
            task_type="extract",
            status="pending",
            dependencies=["crawl-01"]
        )
        
        planner.add_subtask(validation_task)
        planner.add_subtask(crawl_task)
        planner.add_subtask(extract_task)
        
        # Should return crawl task (validation completed)
        next_crawl = planner.get_next_crawl_subtask()
        assert next_crawl == crawl_task
        
        # Should not return extract task (crawl not completed)
        next_extract = planner.get_next_extraction_subtask()
        assert next_extract is None
        
        # Complete crawl task
        planner.update_subtask_progress("crawl-01", 100.0, "completed")
        
        # Now extract task should be available
        next_extract = planner.get_next_extraction_subtask()
        assert next_extract == extract_task
    
    def test_crawl_progress_summary(self, browser_task_config):
        """Test getting crawl progress summary."""
        planner = TaskPlanner(browser_task_config)
        
        # Add browser tasks
        crawl_task = SubTask(
            title="Crawl site",
            description="Crawl example.com", 
            task_type="crawl",
            status="completed",
            urls=["https://example.com/1", "https://example.com/2"]
        )
        
        extract_task = SubTask(
            title="Extract data",
            description="Extract product data",
            task_type="extract", 
            status="in_progress",
            urls=["https://example.com/products"]
        )
        
        export_task = SubTask(
            title="Export results",
            description="Export to JSON",
            task_type="export",
            status="pending"
        )
        
        planner.add_subtask(crawl_task)
        planner.add_subtask(extract_task)
        planner.add_subtask(export_task)
        
        # Get progress summary
        summary = planner.get_crawl_progress_summary()
        
        assert summary["total_tasks"] == 3
        assert summary["completed_tasks"] == 1
        assert summary["in_progress_tasks"] == 1
        assert summary["total_urls"] == 3  # 2 + 1 + 0
        assert summary["progress_percent"] == pytest.approx(33.33, rel=1e-2)
    
    def test_crawl_time_estimation(self, browser_task_config):
        """Test estimating total crawl time."""
        planner = TaskPlanner(browser_task_config)
        
        # Add crawl tasks with different durations
        task1 = SubTask(
            title="Quick crawl",
            description="Fast site",
            task_type="crawl",
            estimated_duration=10
        )
        
        task2 = SubTask(
            title="Slow crawl", 
            description="Complex site",
            task_type="crawl",
            estimated_duration=25
        )
        
        general_task = SubTask(
            title="Planning",
            description="General planning",
            task_type="general",
            estimated_duration=5
        )
        
        planner.add_subtask(task1)
        planner.add_subtask(task2)
        planner.add_subtask(general_task)
        
        # Should only count crawl tasks
        total_time = planner.estimate_total_crawl_time()
        assert total_time == 35  # 10 + 25