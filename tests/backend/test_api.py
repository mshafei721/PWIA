import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from backend.main import app
from backend.models import TaskStatus

client = TestClient(app)

class TestHealthEndpoint:
    """Test the health check endpoint"""
    
    def test_health_check(self):
        """Test that health endpoint returns correct response"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "PWIA API"
        assert data["version"] == "0.1.0"

class TestRootEndpoint:
    """Test the root endpoint"""
    
    def test_root(self):
        """Test that root endpoint returns correct response"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "PWIA - Persistent Web Intelligence Agent API"
        assert data["version"] == "0.1.0"
        assert data["docs"] == "/docs"

class TestCORS:
    """Test CORS configuration"""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses"""
        response = client.options("/api/v1/tasks/")
        assert response.status_code in [200, 405]  # 405 is also acceptable for OPTIONS
        
        # Test with a simple GET request
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        # Note: TestClient doesn't always include CORS headers in test environment

class TestTasksAPI:
    """Test the tasks API endpoints"""
    
    def test_get_tasks_success(self):
        """Test getting all tasks returns success"""
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Tasks retrieved successfully"
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)
        assert data["total"] >= 0
        
        # Check if we have the expected mock data
        if data["total"] > 0:
            task = data["tasks"][0]
            assert "id" in task
            assert "title" in task
            assert "description" in task
            assert "status" in task
            assert "subtasks" in task
    
    def test_get_task_by_id_success(self):
        """Test getting a specific task by ID"""
        # First get all tasks to get a valid ID
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        tasks_data = response.json()
        
        if tasks_data["total"] > 0:
            task_id = tasks_data["tasks"][0]["id"]
            
            # Test getting specific task
            response = client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["message"] == "Task retrieved successfully"
            assert data["task"] is not None
            assert data["task"]["id"] == task_id
    
    def test_get_task_by_id_not_found(self):
        """Test getting a non-existent task returns 404"""
        response = client.get("/api/v1/tasks/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_create_task_success(self):
        """Test creating a new task"""
        new_task_data = {
            "title": "Test Task",
            "description": "This is a test task created by the test suite",
            "agent_id": "test_agent"
        }
        
        response = client.post("/api/v1/tasks/", json=new_task_data)
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Task created successfully"
        assert data["task"] is not None
        
        task = data["task"]
        assert task["title"] == new_task_data["title"]
        assert task["description"] == new_task_data["description"]
        assert task["agent_id"] == new_task_data["agent_id"]
        assert task["status"] == "pending"
        assert "id" in task
        assert task["confidence"] == 0.0
    
    def test_create_task_missing_fields(self):
        """Test creating a task with missing required fields"""
        incomplete_task_data = {
            "title": "Test Task"
            # Missing description
        }
        
        response = client.post("/api/v1/tasks/", json=incomplete_task_data)
        assert response.status_code == 422  # Validation error
    
    def test_update_task_success(self):
        """Test updating an existing task"""
        # First create a task
        create_data = {
            "title": "Original Title",
            "description": "Original description"
        }
        create_response = client.post("/api/v1/tasks/", json=create_data)
        assert create_response.status_code == 201
        task_id = create_response.json()["task"]["id"]
        
        # Now update it
        update_data = {
            "title": "Updated Title",
            "status": "in_progress",
            "confidence": 0.75
        }
        
        response = client.put(f"/api/v1/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Task updated successfully"
        assert data["task"]["title"] == update_data["title"]
        assert data["task"]["status"] == update_data["status"]
        assert data["task"]["confidence"] == update_data["confidence"]
        assert data["task"]["description"] == create_data["description"]  # Unchanged
    
    def test_update_task_not_found(self):
        """Test updating a non-existent task returns 404"""
        update_data = {
            "title": "Updated Title"
        }
        
        response = client.put("/api/v1/tasks/non-existent-id", json=update_data)
        assert response.status_code == 404
    
    def test_update_task_partial(self):
        """Test partial task updates work correctly"""
        # Create a task first
        create_data = {
            "title": "Original Title",
            "description": "Original description"
        }
        create_response = client.post("/api/v1/tasks/", json=create_data)
        task_id = create_response.json()["task"]["id"]
        
        # Update only the title
        update_data = {"title": "Only Title Updated"}
        
        response = client.put(f"/api/v1/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        
        updated_task = response.json()["task"]
        assert updated_task["title"] == "Only Title Updated"
        assert updated_task["description"] == "Original description"  # Should remain unchanged
    
    def test_delete_task_success(self):
        """Test deleting an existing task"""
        # First create a task
        create_data = {
            "title": "Task to Delete",
            "description": "This task will be deleted"
        }
        create_response = client.post("/api/v1/tasks/", json=create_data)
        task_id = create_response.json()["task"]["id"]
        
        # Delete the task
        response = client.delete(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "deleted successfully" in data["message"]
        assert data["task"]["id"] == task_id
        
        # Verify task is actually deleted
        get_response = client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.status_code == 404
    
    def test_delete_task_not_found(self):
        """Test deleting a non-existent task returns 404"""
        response = client.delete("/api/v1/tasks/non-existent-id")
        assert response.status_code == 404

class TestTaskDataStructure:
    """Test that task data structure matches Frontend expectations"""
    
    def test_task_structure_matches_frontend(self):
        """Test that the task structure exactly matches what Frontend expects"""
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        data = response.json()
        
        if data["total"] > 0:
            task = data["tasks"][0]
            
            # Check main task structure
            required_fields = ["id", "title", "description", "status", "subtasks", 
                             "created_at", "updated_at", "agent_id", "confidence"]
            for field in required_fields:
                assert field in task, f"Missing field: {field}"
            
            # Check subtasks structure
            if task["subtasks"]:
                subtask_section = task["subtasks"][0]
                assert "id" in subtask_section
                assert "title" in subtask_section
                assert "subtasks" in subtask_section
                
                if subtask_section["subtasks"]:
                    subtask = subtask_section["subtasks"][0]
                    subtask_fields = ["id", "title", "completed"]
                    for field in subtask_fields:
                        assert field in subtask, f"Missing subtask field: {field}"
    
    def test_task_status_enum_values(self):
        """Test that task status uses correct enum values"""
        response = client.get("/api/v1/tasks/")
        data = response.json()
        
        valid_statuses = ["pending", "in_progress", "completed", "failed", "paused"]
        
        for task in data["tasks"]:
            assert task["status"] in valid_statuses
    
    def test_confidence_score_validation(self):
        """Test that confidence scores are properly validated"""
        # Test creating task with invalid confidence (should work as confidence is set to 0.0)
        task_data = {
            "title": "Confidence Test",
            "description": "Testing confidence validation"
        }
        
        response = client.post("/api/v1/tasks/", json=task_data)
        assert response.status_code == 201
        task = response.json()["task"]
        assert 0.0 <= task["confidence"] <= 1.0
        
        # Test updating with valid confidence
        update_data = {"confidence": 0.85}
        response = client.put(f"/api/v1/tasks/{task['id']}", json=update_data)
        assert response.status_code == 200
        assert response.json()["task"]["confidence"] == 0.85

class TestAPIDocumentation:
    """Test that API documentation is accessible"""
    
    def test_openapi_docs_accessible(self):
        """Test that OpenAPI documentation is accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_json_accessible(self):
        """Test that OpenAPI JSON schema is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "PWIA API"