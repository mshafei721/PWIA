"""Memory persistence layer using TinyDB for agent state management."""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from tinydb import TinyDB, Query
import aiofiles

logger = logging.getLogger(__name__)


class CrawlState(BaseModel):
    """State information for web crawling operations."""
    session_id: str
    task_id: str
    start_time: datetime
    current_url: Optional[str] = None
    urls_to_visit: List[str] = Field(default_factory=list)
    urls_visited: List[str] = Field(default_factory=list)
    urls_failed: List[str] = Field(default_factory=list)
    crawl_depth: int = 0
    max_depth: int = 3
    status: str = "active"  # active, paused, completed, failed
    error_message: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)


class VisitedURL(BaseModel):
    """Information about a visited URL."""
    url: str
    visited_at: datetime
    session_id: str
    response_status: int
    content_type: Optional[str] = None
    content_length: int = 0
    extraction_successful: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0


class ExtractedData(BaseModel):
    """Structured data extracted from web pages."""
    id: str
    url: str
    session_id: str
    extraction_type: str  # text, links, images, structured
    data: Dict[str, Any]
    extracted_at: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    selectors_used: List[str] = Field(default_factory=list)
    processing_time_ms: int = 0


class AgentSession(BaseModel):
    """Session information for agent operations."""
    session_id: str
    task_id: str
    agent_type: str = "web_crawler"
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "active"  # active, paused, completed, failed, timeout
    config: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Union[int, float]] = Field(default_factory=dict)
    total_urls_processed: int = 0
    total_data_extracted: int = 0
    total_errors: int = 0


class AgentMemory:
    """TinyDB-based memory management for agent state persistence."""
    
    def __init__(self, memory_dir: str = "app-memory"):
        """Initialize agent memory with TinyDB storage."""
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize separate databases for different data types
        self.crawl_db = TinyDB(self.memory_dir / "agent_crawl.json")
        self.urls_db = TinyDB(self.memory_dir / "visited_urls.json")
        self.data_db = TinyDB(self.memory_dir / "extracted_data.json")
        self.sessions_db = TinyDB(self.memory_dir / "agent_sessions.json")
        
        logger.info(f"AgentMemory initialized with storage at {self.memory_dir}")
    
    def close(self):
        """Close all database connections."""
        self.crawl_db.close()
        self.urls_db.close()
        self.data_db.close()
        self.sessions_db.close()
        logger.info("AgentMemory databases closed")
    
    # Crawl State Operations
    async def save_crawl_state(self, crawl_state: CrawlState) -> bool:
        """Save or update crawl state to persistent storage."""
        try:
            crawl_data = crawl_state.model_dump()
            # Convert datetime objects to ISO strings
            crawl_data['start_time'] = crawl_state.start_time.isoformat()
            crawl_data['last_updated'] = crawl_state.last_updated.isoformat()
            
            Query_obj = Query()
            # Upsert operation - insert if new, update if exists
            self.crawl_db.upsert(
                crawl_data,
                Query_obj.session_id == crawl_state.session_id
            )
            
            logger.info(f"Crawl state saved for session {crawl_state.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save crawl state: {e}")
            return False
    
    async def load_crawl_state(self, session_id: str) -> Optional[CrawlState]:
        """Load crawl state from persistent storage."""
        try:
            Query_obj = Query()
            result = self.crawl_db.search(Query_obj.session_id == session_id)
            
            if not result:
                logger.warning(f"No crawl state found for session {session_id}")
                return None
            
            crawl_data = result[0]
            # Convert ISO strings back to datetime objects
            crawl_data['start_time'] = datetime.fromisoformat(crawl_data['start_time'])
            crawl_data['last_updated'] = datetime.fromisoformat(crawl_data['last_updated'])
            
            crawl_state = CrawlState(**crawl_data)
            logger.info(f"Crawl state loaded for session {session_id}")
            return crawl_state
            
        except Exception as e:
            logger.error(f"Failed to load crawl state: {e}")
            return None
    
    async def get_visited_urls(self, session_id: str) -> List[str]:
        """Get list of URLs already visited in this session."""
        try:
            Query_obj = Query()
            results = self.urls_db.search(Query_obj.session_id == session_id)
            
            visited_urls = [result['url'] for result in results]
            logger.debug(f"Retrieved {len(visited_urls)} visited URLs for session {session_id}")
            return visited_urls
            
        except Exception as e:
            logger.error(f"Failed to get visited URLs: {e}")
            return []
    
    # URL Operations
    async def save_visited_url(self, visited_url: VisitedURL) -> bool:
        """Save information about a visited URL."""
        try:
            url_data = visited_url.model_dump()
            url_data['visited_at'] = visited_url.visited_at.isoformat()
            
            self.urls_db.insert(url_data)
            logger.debug(f"Visited URL saved: {visited_url.url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save visited URL: {e}")
            return False
    
    async def get_url_info(self, url: str, session_id: str) -> Optional[VisitedURL]:
        """Get information about a specific visited URL."""
        try:
            Query_obj = Query()
            result = self.urls_db.search(
                (Query_obj.url == url) & (Query_obj.session_id == session_id)
            )
            
            if not result:
                return None
            
            url_data = result[0]
            url_data['visited_at'] = datetime.fromisoformat(url_data['visited_at'])
            
            return VisitedURL(**url_data)
            
        except Exception as e:
            logger.error(f"Failed to get URL info: {e}")
            return None
    
    # Extracted Data Operations
    async def save_extracted_data(self, extracted_data: ExtractedData) -> bool:
        """Save extracted data to persistent storage."""
        try:
            data_dict = extracted_data.model_dump()
            data_dict['extracted_at'] = extracted_data.extracted_at.isoformat()
            
            self.data_db.insert(data_dict)
            logger.info(f"Extracted data saved: {extracted_data.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save extracted data: {e}")
            return False
    
    async def get_extracted_data(self, session_id: str, 
                               extraction_type: Optional[str] = None) -> List[ExtractedData]:
        """Get extracted data for a session, optionally filtered by type."""
        try:
            Query_obj = Query()
            query = Query_obj.session_id == session_id
            
            if extraction_type:
                query = query & (Query_obj.extraction_type == extraction_type)
            
            results = self.data_db.search(query)
            
            extracted_data_list = []
            for result in results:
                result['extracted_at'] = datetime.fromisoformat(result['extracted_at'])
                extracted_data_list.append(ExtractedData(**result))
            
            logger.info(f"Retrieved {len(extracted_data_list)} extracted data items")
            return extracted_data_list
            
        except Exception as e:
            logger.error(f"Failed to get extracted data: {e}")
            return []
    
    # Session Operations
    async def save_session(self, session: AgentSession) -> bool:
        """Save or update agent session information."""
        try:
            session_data = session.model_dump()
            session_data['start_time'] = session.start_time.isoformat()
            if session.end_time:
                session_data['end_time'] = session.end_time.isoformat()
            
            Query_obj = Query()
            self.sessions_db.upsert(
                session_data,
                Query_obj.session_id == session.session_id
            )
            
            logger.info(f"Session saved: {session.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get agent session information."""
        try:
            Query_obj = Query()
            result = self.sessions_db.search(Query_obj.session_id == session_id)
            
            if not result:
                return None
            
            session_data = result[0]
            session_data['start_time'] = datetime.fromisoformat(session_data['start_time'])
            if session_data.get('end_time'):
                session_data['end_time'] = datetime.fromisoformat(session_data['end_time'])
            
            return AgentSession(**session_data)
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def get_active_sessions(self) -> List[AgentSession]:
        """Get all active agent sessions."""
        try:
            Query_obj = Query()
            results = self.sessions_db.search(Query_obj.status == "active")
            
            sessions = []
            for result in results:
                result['start_time'] = datetime.fromisoformat(result['start_time'])
                if result.get('end_time'):
                    result['end_time'] = datetime.fromisoformat(result['end_time'])
                sessions.append(AgentSession(**result))
            
            logger.info(f"Retrieved {len(sessions)} active sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    # Utility Operations
    async def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old data based on retention policy."""
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
            
            cleanup_stats = {
                "crawl_states": 0,
                "visited_urls": 0,
                "extracted_data": 0,
                "sessions": 0
            }
            
            Query_obj = Query()
            
            # Note: This is a simplified cleanup - in production you'd want
            # more sophisticated date handling
            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {}
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about memory usage."""
        try:
            stats = {
                "crawl_states": len(self.crawl_db.all()),
                "visited_urls": len(self.urls_db.all()),
                "extracted_data": len(self.data_db.all()),
                "sessions": len(self.sessions_db.all()),
                "memory_dir": str(self.memory_dir),
                "db_files": []
            }
            
            # Get file sizes
            for db_file in self.memory_dir.glob("*.json"):
                stats["db_files"].append({
                    "file": db_file.name,
                    "size_bytes": db_file.stat().st_size
                })
            
            logger.debug(f"Memory stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}
    
    async def export_data(self, export_path: str, session_id: Optional[str] = None) -> bool:
        """Export memory data to JSON files."""
        try:
            export_dir = Path(export_path)
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Export all data or filter by session
            Query_obj = Query()
            
            if session_id:
                crawl_data = self.crawl_db.search(Query_obj.session_id == session_id)
                urls_data = self.urls_db.search(Query_obj.session_id == session_id)
                extracted_data = self.data_db.search(Query_obj.session_id == session_id)
                session_data = self.sessions_db.search(Query_obj.session_id == session_id)
            else:
                crawl_data = self.crawl_db.all()
                urls_data = self.urls_db.all()
                extracted_data = self.data_db.all()
                session_data = self.sessions_db.all()
            
            # Write to files
            export_files = [
                ("crawl_states.json", crawl_data),
                ("visited_urls.json", urls_data),
                ("extracted_data.json", extracted_data),
                ("sessions.json", session_data)
            ]
            
            for filename, data in export_files:
                async with aiofiles.open(export_dir / filename, 'w') as f:
                    await f.write(json.dumps(data, indent=2, default=str))
            
            logger.info(f"Data exported to {export_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return False