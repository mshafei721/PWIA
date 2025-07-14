"""Tests for memory foundation using TinyDB for agent state persistence."""
import pytest
import tempfile
import os
from pathlib import Path
from tinydb import TinyDB, Query
import asyncio
import aiofiles


class TestMemoryFoundation:
    """Test TinyDB database operations for agent memory persistence."""
    
    def test_tinydb_basic_operations(self):
        """Test basic TinyDB create/read/write/delete operations."""
        # Create in-memory database
        db = TinyDB(':memory:')
        # Ensure clean state
        db.truncate()
        
        # Test CREATE operation
        doc_id = db.insert({'type': 'test', 'data': 'initial', 'version': 1})
        assert doc_id is not None, "Failed to create document"
        
        # Test READ operation
        Query_obj = Query()
        result = db.search(Query_obj.type == 'test')
        assert len(result) == 1, "Failed to read document"
        assert result[0]['data'] == 'initial', "Read data doesn't match"
        assert result[0]['version'] == 1, "Read version doesn't match"
        
        # Test UPDATE operation
        db.update({'data': 'updated', 'version': 2}, Query_obj.type == 'test')
        updated_result = db.search(Query_obj.type == 'test')
        assert len(updated_result) == 1, "Update created duplicate documents"
        assert updated_result[0]['data'] == 'updated', "Update failed"
        assert updated_result[0]['version'] == 2, "Version not updated"
        
        # Test DELETE operation
        db.remove(Query_obj.type == 'test')
        deleted_result = db.search(Query_obj.type == 'test')
        assert len(deleted_result) == 0, "Delete operation failed"
        
        # Verify database is empty
        all_docs = db.all()
        assert len(all_docs) == 0, "Database not properly cleaned up"

    def test_tinydb_file_persistence(self):
        """Test TinyDB file-based persistence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_db.json"
            
            # Create database with file persistence
            db = TinyDB(str(db_path))
            
            # Insert test data
            test_data = {'session_id': 'test-123', 'urls_visited': 5, 'status': 'active'}
            doc_id = db.insert(test_data)
            
            # Close database
            db.close()
            
            # Verify file exists
            assert db_path.exists(), "Database file not created"
            
            # Reopen database and verify persistence
            db2 = TinyDB(str(db_path))
            Query_obj = Query()
            result = db2.search(Query_obj.session_id == 'test-123')
            
            assert len(result) == 1, "Data not persisted to file"
            assert result[0]['urls_visited'] == 5, "Persisted data corrupted"
            assert result[0]['status'] == 'active', "Persisted status corrupted"
            
            db2.close()

    def test_tinydb_multiple_tables(self):
        """Test TinyDB multiple table functionality."""
        db = TinyDB(':memory:')
        
        # Create different tables
        sessions_table = db.table('sessions')
        urls_table = db.table('urls')
        data_table = db.table('extracted_data')
        
        # Ensure all tables are clean
        sessions_table.truncate()
        urls_table.truncate()
        data_table.truncate()
        
        # Insert data into different tables
        session_id = sessions_table.insert({
            'id': 'session-001',
            'start_time': '2025-01-14T10:00:00',
            'status': 'active'
        })
        
        url_id = urls_table.insert({
            'url': 'https://example.com',
            'visited_at': '2025-01-14T10:01:00',
            'session_id': 'session-001'
        })
        
        data_id = data_table.insert({
            'content': 'Sample extracted text',
            'url': 'https://example.com',
            'extraction_type': 'text'
        })
        
        # Verify table isolation
        assert len(sessions_table.all()) == 1, "Sessions table incorrect"
        assert len(urls_table.all()) == 1, "URLs table incorrect"
        assert len(data_table.all()) == 1, "Data table incorrect"
        
        # Verify cross-table queries work
        Query_obj = Query()
        session_urls = urls_table.search(Query_obj.session_id == 'session-001')
        assert len(session_urls) == 1, "Cross-table query failed"
        assert session_urls[0]['url'] == 'https://example.com', "Cross-table data mismatch"

    def test_tinydb_concurrent_access_simulation(self):
        """Test TinyDB behavior under simulated concurrent access."""
        db = TinyDB(':memory:')
        db.truncate()  # Ensure clean state
        Query_obj = Query()
        
        # Simulate concurrent writes
        for i in range(10):
            db.insert({'worker_id': f'worker-{i}', 'task': f'task-{i}', 'timestamp': i})
        
        # Verify all writes succeeded
        all_records = db.all()
        assert len(all_records) == 10, "Concurrent writes failed"
        
        # Verify data integrity
        worker_ids = {record['worker_id'] for record in all_records}
        assert len(worker_ids) == 10, "Duplicate worker IDs found"
        
        # Test concurrent reads
        for i in range(10):
            result = db.search(Query_obj.worker_id == f'worker-{i}')
            assert len(result) == 1, f"Worker {i} data not found"
            assert result[0]['task'] == f'task-{i}', f"Worker {i} task data corrupted"

    def test_tinydb_query_performance(self):
        """Test TinyDB query performance with larger datasets."""
        db = TinyDB(':memory:')
        db.truncate()  # Ensure clean state
        
        # Insert test dataset
        test_data = []
        for i in range(100):
            test_data.append({
                'id': i,
                'type': 'url' if i % 2 == 0 else 'data',
                'priority': i % 5,
                'processed': i < 50
            })
        
        # Batch insert
        db.insert_multiple(test_data)
        
        # Test various query patterns
        Query_obj = Query()
        
        # Count queries
        all_count = len(db.all())
        assert all_count == 100, "Batch insert failed"
        
        # Filtered queries
        url_count = len(db.search(Query_obj.type == 'url'))
        assert url_count == 50, "Type filter query failed"
        
        high_priority = len(db.search(Query_obj.priority == 4))
        assert high_priority == 20, "Priority filter query failed"
        
        processed_count = len(db.search(Query_obj.processed == True))
        assert processed_count == 50, "Boolean filter query failed"
        
        # Complex queries
        complex_query = db.search(
            (Query_obj.type == 'url') & 
            (Query_obj.priority >= 3) & 
            (Query_obj.processed == False)
        )
        expected_complex = len([
            item for item in test_data 
            if item['type'] == 'url' and item['priority'] >= 3 and not item['processed']
        ])
        assert len(complex_query) == expected_complex, "Complex query failed"

    @pytest.mark.asyncio
    async def test_async_file_operations(self):
        """Test async file operations for integration with aiofiles."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file with aiofiles
            test_file = Path(temp_dir) / "async_test.json"
            
            test_content = '{"test": "async_content", "timestamp": "2025-01-14"}'
            
            # Write file asynchronously
            async with aiofiles.open(test_file, 'w') as f:
                await f.write(test_content)
            
            # Verify file exists
            assert test_file.exists(), "Async file write failed"
            
            # Read file asynchronously
            async with aiofiles.open(test_file, 'r') as f:
                content = await f.read()
            
            assert content == test_content, "Async file read failed"
            
            # Parse and verify JSON content
            import json
            parsed = json.loads(content)
            assert parsed['test'] == 'async_content', "JSON parsing failed"
            assert parsed['timestamp'] == '2025-01-14', "JSON data integrity failed"

    def test_tinydb_error_handling(self):
        """Test TinyDB error handling scenarios."""
        db = TinyDB(':memory:')
        db.truncate()  # Ensure clean state
        Query_obj = Query()
        
        # Test querying empty database
        result = db.search(Query_obj.nonexistent == 'value')
        assert result == [], "Empty query should return empty list"
        
        # Test inserting invalid data - TinyDB validates input
        with pytest.raises(ValueError):
            db.insert(None)  # Should raise ValueError
        
        # Test complex nested data
        nested_data = {
            'session': {
                'id': 'nested-001',
                'config': {
                    'retries': 3,
                    'timeout': 30
                },
                'urls': ['http://example.com', 'http://test.com']
            }
        }
        
        nested_id = db.insert(nested_data)
        assert nested_id is not None, "Nested data insert failed"
        
        # Query nested data
        nested_result = db.search(Query_obj.session.id == 'nested-001')
        assert len(nested_result) == 1, "Nested query failed"
        assert nested_result[0]['session']['config']['retries'] == 3, "Nested data access failed"

    def test_tinydb_upsert_operations(self):
        """Test TinyDB upsert (insert or update) operations."""
        db = TinyDB(':memory:')
        Query_obj = Query()
        
        # Initial upsert (should insert)
        db.upsert({'key': 'test', 'value': 1, 'updated_count': 0}, Query_obj.key == 'test')
        
        result = db.search(Query_obj.key == 'test')
        assert len(result) == 1, "Upsert insert failed"
        assert result[0]['value'] == 1, "Upsert insert value incorrect"
        
        # Second upsert (should update)
        db.upsert({'key': 'test', 'value': 2, 'updated_count': 1}, Query_obj.key == 'test')
        
        result = db.search(Query_obj.key == 'test')
        assert len(result) == 1, "Upsert update created duplicate"
        assert result[0]['value'] == 2, "Upsert update value incorrect"
        assert result[0]['updated_count'] == 1, "Upsert update count incorrect"
        
        # Third upsert (should update again)
        db.upsert({'key': 'test', 'value': 3, 'updated_count': 2}, Query_obj.key == 'test')
        
        result = db.search(Query_obj.key == 'test')
        assert len(result) == 1, "Final upsert created duplicate"
        assert result[0]['value'] == 3, "Final upsert value incorrect"
        assert result[0]['updated_count'] == 2, "Final upsert count incorrect"