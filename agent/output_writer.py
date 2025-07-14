"""Output writer for workspace management and export functionality."""
import csv
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

from agent.utils import get_logger, ensure_directory, sanitize_filename

logger = get_logger(__name__)


class WorkspaceManager:
    """Manages workspace directory structure and file operations."""
    
    def __init__(self, workspace_root: str = "workspace"):
        """Initialize workspace manager."""
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
    def create_task_workspace(self, task_id: str) -> Path:
        """Create workspace directory for a task."""
        task_dir = self.workspace_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        subdirs = ['logs', 'outputs', 'exports']
        for subdir in subdirs:
            (task_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created workspace for task: {task_id}")
        return task_dir
    
    def get_task_workspace(self, task_id: str) -> Path:
        """Get workspace directory for a task."""
        return self.workspace_root / task_id
    
    def task_workspace_exists(self, task_id: str) -> bool:
        """Check if task workspace exists."""
        return (self.workspace_root / task_id).exists()
    
    def list_task_workspaces(self) -> List[str]:
        """List all task workspace directories."""
        return [d.name for d in self.workspace_root.iterdir() if d.is_dir()]
    
    def cleanup_task_workspace(self, task_id: str) -> bool:
        """Remove task workspace directory."""
        import shutil
        task_dir = self.workspace_root / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)
            logger.info(f"Cleaned up workspace for task: {task_id}")
            return True
        return False


class OutputWriter:
    """Handles output writing in multiple formats."""
    
    def __init__(self, workspace_manager: Optional[WorkspaceManager] = None):
        """Initialize output writer."""
        self.workspace_manager = workspace_manager or WorkspaceManager()
        
    def write_todo_md(self, task_id: str, task_data: Dict[str, Any]) -> Path:
        """Write todo.md file for a task."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        todo_path = task_dir / "todo.md"
        
        # Generate todo.md content
        content = self._generate_todo_content(task_data)
        
        with open(todo_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created todo.md for task: {task_id}")
        return todo_path
    
    def _generate_todo_content(self, task_data: Dict[str, Any]) -> str:
        """Generate todo.md content from task data."""
        task_id = task_data.get('id', 'unknown')
        title = task_data.get('title', 'Unnamed Task')
        description = task_data.get('description', '')
        subtasks = task_data.get('subtasks', [])
        
        # Calculate progress
        total_subtasks = len(subtasks)
        completed_subtasks = sum(1 for section in subtasks for subtask in section.get('subtasks', []) if subtask.get('completed', False))
        progress = (completed_subtasks / max(total_subtasks, 1)) * 100 if total_subtasks > 0 else 0
        
        content = f"""# Task Plan: {title}

## Task ID: {task_id}
## Progress: {progress:.1f}%
## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Description
{description}

### Subtasks:
"""
        
        # Add subtasks
        for i, section in enumerate(subtasks):
            section_title = section.get('title', f'Section {i+1}')
            content += f"\n#### {section_title}\n"
            
            for j, subtask in enumerate(section.get('subtasks', [])):
                status = "x" if subtask.get('completed', False) else " "
                subtask_title = subtask.get('title', f'Subtask {j+1}')
                subtask_desc = subtask.get('description', '')
                
                content += f"- [{status}] {subtask_title}\n"
                if subtask_desc:
                    content += f"  - **Description:** {subtask_desc}\n"
                
                if subtask.get('file'):
                    content += f"  - **File:** {subtask['file']}\n"
        
        # Add metadata
        content += f"""

### Planning Metadata:
- **Total Subtasks:** {total_subtasks}
- **Completed:** {completed_subtasks}
- **In Progress:** {total_subtasks - completed_subtasks}
- **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Current Status:
Status: {'Completed' if progress == 100 else 'In Progress'}
"""
        
        return content
    
    def write_json(self, task_id: str, data: Union[Dict, List], filename: str = "output.json") -> Path:
        """Write JSON output file."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        output_path = task_dir / "outputs" / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Created JSON output: {output_path}")
        return output_path
    
    def write_csv(self, task_id: str, data: List[Dict], filename: str = "output.csv") -> Path:
        """Write CSV output file."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        output_path = task_dir / "outputs" / filename
        
        if not data:
            logger.warning(f"No data to write for CSV: {filename}")
            return output_path
        
        # Get all fieldnames from the data
        fieldnames = set()
        for item in data:
            fieldnames.update(item.keys())
        
        fieldnames = sorted(fieldnames)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"Created CSV output: {output_path}")
        return output_path
    
    def write_markdown(self, task_id: str, content: str, filename: str = "output.md") -> Path:
        """Write Markdown output file."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        output_path = task_dir / "outputs" / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created Markdown output: {output_path}")
        return output_path
    
    def write_log(self, task_id: str, log_entry: Dict[str, Any]) -> Path:
        """Write log entry to task log file."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        log_path = task_dir / "logs" / "task.log"
        
        # Add timestamp if not present
        if 'timestamp' not in log_entry:
            log_entry['timestamp'] = datetime.now().isoformat()
        
        # Append to log file
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')
        
        return log_path
    
    def create_export_archive(self, task_id: str, export_format: str = "zip") -> Path:
        """Create export archive of task workspace."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        export_dir = task_dir / "exports"
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f"{task_id}_{timestamp}.{export_format}"
        archive_path = export_dir / archive_name
        
        if export_format.lower() == "zip":
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from task directory
                for file_path in task_dir.rglob('*'):
                    if file_path.is_file() and not file_path.is_relative_to(export_dir):
                        # Get relative path for archive
                        arc_name = file_path.relative_to(task_dir)
                        zipf.write(file_path, arc_name)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        logger.info(f"Created export archive: {archive_path}")
        return archive_path


class ExportManager:
    """Manages export operations for different data formats."""
    
    def __init__(self, workspace_manager: Optional[WorkspaceManager] = None):
        """Initialize export manager."""
        self.workspace_manager = workspace_manager or WorkspaceManager()
        self.output_writer = OutputWriter(workspace_manager)
    
    def export_crawl_results(
        self, 
        task_id: str, 
        results: List[Dict[str, Any]], 
        format: str = "json"
    ) -> Path:
        """Export crawl results in specified format."""
        if not self.workspace_manager.task_workspace_exists(task_id):
            self.workspace_manager.create_task_workspace(task_id)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format.lower() == "json":
            filename = f"crawl_results_{timestamp}.json"
            return self.output_writer.write_json(task_id, results, filename)
        
        elif format.lower() == "csv":
            # Flatten results for CSV export
            flattened_results = []
            for result in results:
                flattened = {
                    'url': result.get('url', ''),
                    'title': result.get('title', ''),
                    'status': result.get('status', ''),
                    'timestamp': result.get('timestamp', ''),
                    'data_extracted': len(result.get('data', [])),
                    'errors': len(result.get('errors', []))
                }
                flattened_results.append(flattened)
            
            filename = f"crawl_results_{timestamp}.csv"
            return self.output_writer.write_csv(task_id, flattened_results, filename)
        
        elif format.lower() == "markdown":
            # Generate markdown report
            markdown_content = self._generate_crawl_markdown(results)
            filename = f"crawl_results_{timestamp}.md"
            return self.output_writer.write_markdown(task_id, markdown_content, filename)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _generate_crawl_markdown(self, results: List[Dict[str, Any]]) -> str:
        """Generate markdown report from crawl results."""
        content = f"""# Crawl Results Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- **Total URLs Processed:** {len(results)}
- **Successful Extractions:** {sum(1 for r in results if r.get('status') == 'success')}
- **Failed Extractions:** {sum(1 for r in results if r.get('status') == 'failed')}

## Results Details

"""
        
        for i, result in enumerate(results, 1):
            url = result.get('url', 'Unknown URL')
            title = result.get('title', 'No Title')
            status = result.get('status', 'unknown')
            data_count = len(result.get('data', []))
            
            content += f"""### {i}. {title}
- **URL:** {url}
- **Status:** {status}
- **Data Extracted:** {data_count} items
- **Timestamp:** {result.get('timestamp', 'N/A')}

"""
            
            if result.get('errors'):
                content += "**Errors:**\n"
                for error in result.get('errors', []):
                    content += f"- {error}\n"
                content += "\n"
        
        return content
    
    def export_task_workspace(self, task_id: str) -> Path:
        """Export entire task workspace as ZIP archive."""
        return self.output_writer.create_export_archive(task_id)
    
    def get_export_info(self, task_id: str) -> Dict[str, Any]:
        """Get information about available exports for a task."""
        task_dir = self.workspace_manager.get_task_workspace(task_id)
        export_dir = task_dir / "exports"
        
        if not export_dir.exists():
            return {"available_exports": [], "total_size": 0}
        
        exports = []
        total_size = 0
        
        for export_file in export_dir.glob("*"):
            if export_file.is_file():
                file_size = export_file.stat().st_size
                total_size += file_size
                
                exports.append({
                    "filename": export_file.name,
                    "size": file_size,
                    "created": datetime.fromtimestamp(export_file.stat().st_ctime).isoformat(),
                    "format": export_file.suffix.lstrip('.')
                })
        
        return {
            "available_exports": exports,
            "total_size": total_size,
            "export_directory": str(export_dir)
        }


# Convenience functions for common operations

def create_task_workspace(task_id: str) -> Path:
    """Create workspace for a task."""
    manager = WorkspaceManager()
    return manager.create_task_workspace(task_id)


def write_task_output(task_id: str, data: Any, format: str = "json", filename: Optional[str] = None) -> Path:
    """Write task output in specified format."""
    writer = OutputWriter()
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"output_{timestamp}.{format}"
    
    if format.lower() == "json":
        return writer.write_json(task_id, data, filename)
    elif format.lower() == "csv":
        return writer.write_csv(task_id, data, filename)
    elif format.lower() == "markdown":
        return writer.write_markdown(task_id, data, filename)
    else:
        raise ValueError(f"Unsupported format: {format}")


def export_task_results(task_id: str, results: List[Dict], format: str = "json") -> Path:
    """Export task results in specified format."""
    exporter = ExportManager()
    return exporter.export_crawl_results(task_id, results, format)


def log_task_event(task_id: str, event_type: str, event_data: Dict[str, Any]) -> Path:
    """Log an event for a task."""
    writer = OutputWriter()
    
    log_entry = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        **event_data
    }
    
    return writer.write_log(task_id, log_entry)