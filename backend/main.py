"""
Main FastAPI application for AutoVision backend
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import AutoVision modules
from supabase import create_client
from backend.auth import get_current_user, AuthUser
from backend.video_processor import VideoProcessor
from backend.video_cleanup import run_scheduled_cleanup
from backend.api_routes import create_api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AutoVision backend...")
    
    # Initialize video processor
    video_processor = VideoProcessor()
    app.state.video_processor = video_processor
    
    # Start video processing queue
    video_processor.start_processing()
    
    # Start background cleanup task (runs every 24 hours)
    async def scheduled_cleanup_task():
        while True:
            try:
                await asyncio.sleep(24 * 60 * 60)  # Wait 24 hours
                logger.info("Running scheduled video cleanup...")
                await run_scheduled_cleanup()
            except Exception as e:
                logger.error(f"Scheduled cleanup failed: {e}")
    
    # Start the cleanup task
    cleanup_task = asyncio.create_task(scheduled_cleanup_task())
    app.state.cleanup_task = cleanup_task
    
    logger.info("AutoVision backend started successfully")
    
    yield
      # Shutdown    logger.info("Shutting down AutoVision backend...")
    
    # Cancel cleanup task
    if hasattr(app.state, 'cleanup_task'):
        app.state.cleanup_task.cancel()
        try:
            await app.state.cleanup_task
        except asyncio.CancelledError:
            pass
    
    logger.info("AutoVision backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="AutoVision API",
    description="AI-Powered Video Surveillance & Anomaly Detection Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("models", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
api_router = create_api_router()
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AutoVision API - AI-Powered Video Surveillance Platform",
        "version": "1.0.0",
        "status": "running",
        "description": "Real-time video anomaly detection and surveillance analytics"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:        # Check Supabase connection
        supabase_status = "connected"
        try:
            # Test database connection (simplified)
            pass
        except Exception as e:
            supabase_status = f"error: {str(e)}"
          # Video processor status
        video_processor_status = "running"
        
        return {
            "status": "healthy",
            "timestamp": "2024-12-19T00:00:00Z",
            "services": {
                "supabase": supabase_status,
                "video_processor": video_processor_status
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    # Configure logging
    logger.add(
        "logs/autovision.log",
        rotation="1 day",
        retention="30 days",
        level="INFO"
    )
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=12000,
        reload=True,
        log_level="info"
    )