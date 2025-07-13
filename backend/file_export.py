"""
File Export Module for PWIA Backend
Provides export functionality for CSV, Markdown, and ZIP formats
"""

import csv
import zipfile
import tempfile
import json
from io import StringIO, BytesIO
from pathlib import Path
from typing import List, Dict, Any, Union
from datetime import datetime

from .models import Task, SubTask, TaskSection


class FileExporter:
    """Handles exporting task data to various formats"""
    
    def __init__(self):
        self.supported_formats = ['csv', 'markdown', 'md', 'zip', 'json']
    
    def export_task(self, task: Task, format: str) -> Union[str, bytes]:
        """
        Export a single task to the specified format
        
        Args:
            task: Task object to export
            format: Export format ('csv', 'markdown', 'md', 'zip', 'json')
            
        Returns:
            String content for text formats, bytes for binary formats
        """
        format = format.lower()
        
        if format not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.supported_formats}")
        
        if format == 'csv':
            return self._export_task_csv(task)
        elif format in ['markdown', 'md']:
            return self._export_task_markdown(task)
        elif format == 'zip':
            return self._export_task_zip(task)
        elif format == 'json':
            return self._export_task_json(task)
    
    def export_tasks(self, tasks: List[Task], format: str) -> Union[str, bytes]:
        """
        Export multiple tasks to the specified format
        
        Args:
            tasks: List of Task objects to export
            format: Export format ('csv', 'markdown', 'md', 'zip', 'json')
            
        Returns:
            String content for text formats, bytes for binary formats
        """
        format = format.lower()
        
        if format not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.supported_formats}")
        
        if format == 'csv':
            return self._export_tasks_csv(tasks)
        elif format in ['markdown', 'md']:
            return self._export_tasks_markdown(tasks)
        elif format == 'zip':
            return self._export_tasks_zip(tasks)
        elif format == 'json':
            return self._export_tasks_json(tasks)
    
    def _export_task_csv(self, task: Task) -> str:
        """Export single task to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Task ID', 'Task Title', 'Task Description', 'Section ID', 
                        'Section Title', 'Subtask ID', 'Subtask Title', 'Subtask Description',
                        'Completed', 'File', 'Created At', 'Updated At'])
        
        # Write task data
        for section in task.subtasks:
            for subtask in section.subtasks:
                writer.writerow([
                    task.id,
                    task.title,
                    task.description,
                    section.id,
                    section.title,
                    subtask.id,
                    subtask.title,
                    subtask.description or '',
                    subtask.completed,
                    subtask.file or '',
                    task.created_at or '',
                    task.updated_at or ''
                ])
        
        return output.getvalue()
    
    def _export_tasks_csv(self, tasks: List[Task]) -> str:
        """Export multiple tasks to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Task ID', 'Task Title', 'Task Description', 'Section ID', 
                        'Section Title', 'Subtask ID', 'Subtask Title', 'Subtask Description',
                        'Completed', 'File', 'Created At', 'Updated At'])
        
        # Write all tasks data
        for task in tasks:
            for section in task.subtasks:
                for subtask in section.subtasks:
                    writer.writerow([
                        task.id,
                        task.title,
                        task.description,
                        section.id,
                        section.title,
                        subtask.id,
                        subtask.title,
                        subtask.description or '',
                        subtask.completed,
                        subtask.file or '',
                        task.created_at or '',
                        task.updated_at or ''
                    ])
        
        return output.getvalue()
    
    def _export_task_markdown(self, task: Task) -> str:
        """Export single task to Markdown format"""
        lines = []
        lines.append(f"# {task.title}")
        lines.append("")
        lines.append(f"**Description:** {task.description}")
        lines.append("")
        
        if task.created_at:
            lines.append(f"**Created:** {task.created_at}")
        if task.updated_at:
            lines.append(f"**Updated:** {task.updated_at}")
        if task.status:
            lines.append(f"**Status:** {task.status}")
        lines.append("")
        
        # Export sections and subtasks
        for section in task.subtasks:
            lines.append(f"## {section.title}")
            lines.append("")
            
            for subtask in section.subtasks:
                # Create checkbox based on completion status
                checkbox = "- [x]" if subtask.completed else "- [ ]"
                lines.append(f"{checkbox} **{subtask.title}**")
                
                if subtask.description:
                    lines.append(f"  - Description: {subtask.description}")
                if subtask.file:
                    lines.append(f"  - File: `{subtask.file}`")
                lines.append("")
        
        return "\n".join(lines)
    
    def _export_tasks_markdown(self, tasks: List[Task]) -> str:
        """Export multiple tasks to Markdown format"""
        lines = []
        lines.append("# PWIA Tasks Export")
        lines.append("")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"Total tasks: {len(tasks)}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for i, task in enumerate(tasks, 1):
            lines.append(f"## Task {i}: {task.title}")
            lines.append("")
            lines.append(f"**ID:** {task.id}")
            lines.append(f"**Description:** {task.description}")
            lines.append("")
            
            if task.created_at:
                lines.append(f"**Created:** {task.created_at}")
            if task.updated_at:
                lines.append(f"**Updated:** {task.updated_at}")
            if task.status:
                lines.append(f"**Status:** {task.status}")
            lines.append("")
            
            # Export sections and subtasks
            for section in task.subtasks:
                lines.append(f"### {section.title}")
                lines.append("")
                
                for subtask in section.subtasks:
                    checkbox = "- [x]" if subtask.completed else "- [ ]"
                    lines.append(f"{checkbox} **{subtask.title}**")
                    
                    if subtask.description:
                        lines.append(f"  - Description: {subtask.description}")
                    if subtask.file:
                        lines.append(f"  - File: `{subtask.file}`")
                    lines.append("")
            
            if i < len(tasks):
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)
    
    def _export_task_json(self, task: Task) -> str:
        """Export single task to JSON format"""
        return task.model_dump_json(indent=2)
    
    def _export_tasks_json(self, tasks: List[Task]) -> str:
        """Export multiple tasks to JSON format"""
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "tasks": [task.model_dump() for task in tasks]
        }
        return json.dumps(export_data, indent=2)
    
    def _export_task_zip(self, task: Task) -> bytes:
        """Export single task to ZIP format with multiple file formats"""
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add task in multiple formats
            filename_base = f"task_{task.id}_{task.title.replace(' ', '_').lower()}"
            
            # Add JSON version
            json_content = self._export_task_json(task)
            zip_file.writestr(f"{filename_base}.json", json_content)
            
            # Add Markdown version
            md_content = self._export_task_markdown(task)
            zip_file.writestr(f"{filename_base}.md", md_content)
            
            # Add CSV version
            csv_content = self._export_task_csv(task)
            zip_file.writestr(f"{filename_base}.csv", csv_content)
            
            # Add metadata file
            metadata = {
                "task_id": task.id,
                "task_title": task.title,
                "export_timestamp": datetime.now().isoformat(),
                "formats_included": ["json", "markdown", "csv"],
                "total_sections": len(task.subtasks),
                "total_subtasks": sum(len(section.subtasks) for section in task.subtasks)
            }
            zip_file.writestr("export_metadata.json", json.dumps(metadata, indent=2))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    def _export_tasks_zip(self, tasks: List[Task]) -> bytes:
        """Export multiple tasks to ZIP format"""
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add combined export files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Add combined JSON
            json_content = self._export_tasks_json(tasks)
            zip_file.writestr(f"pwia_tasks_export_{timestamp}.json", json_content)
            
            # Add combined Markdown
            md_content = self._export_tasks_markdown(tasks)
            zip_file.writestr(f"pwia_tasks_export_{timestamp}.md", md_content)
            
            # Add combined CSV
            csv_content = self._export_tasks_csv(tasks)
            zip_file.writestr(f"pwia_tasks_export_{timestamp}.csv", csv_content)
            
            # Add individual task files
            individual_dir = "individual_tasks/"
            for task in tasks:
                task_filename_base = f"task_{task.id}_{task.title.replace(' ', '_').lower()}"
                
                # Individual JSON
                task_json = self._export_task_json(task)
                zip_file.writestr(f"{individual_dir}{task_filename_base}.json", task_json)
                
                # Individual Markdown
                task_md = self._export_task_markdown(task)
                zip_file.writestr(f"{individual_dir}{task_filename_base}.md", task_md)
            
            # Add export metadata
            metadata = {
                "export_timestamp": datetime.now().isoformat(),
                "total_tasks": len(tasks),
                "formats_included": ["json", "markdown", "csv"],
                "structure": {
                    "combined_files": ["json", "markdown", "csv"],
                    "individual_files": ["json", "markdown"]
                },
                "tasks_summary": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "sections": len(task.subtasks),
                        "subtasks": sum(len(section.subtasks) for section in task.subtasks)
                    }
                    for task in tasks
                ]
            }
            zip_file.writestr("export_metadata.json", json.dumps(metadata, indent=2))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()


# Singleton instance for use in API endpoints
file_exporter = FileExporter()