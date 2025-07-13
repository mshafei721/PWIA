from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import tasks

app = FastAPI(
    title="PWIA API",
    version="0.1.0",
    description="Persistent Web Intelligence Agent API"
)

# Configure CORS for Frontend development
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # Common React dev server port
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {
        "status": "healthy",
        "service": "PWIA API",
        "version": "0.1.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PWIA - Persistent Web Intelligence Agent API",
        "version": "0.1.0",
        "docs": "/docs"
    }

# Include routers
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])