"""
Daily News Podcast API

A comprehensive REST API built with FastAPI and Supabase for:
- User authentication (Google OAuth)
- Subscription and billing management (Stripe, Toss)
- Scheduled podcast generation
- Real-time news to podcast conversion

Usage:
    # Run the API server
    python -m podcastfy.api.main
    
    # Or with uvicorn
    uvicorn podcastfy.api.main:app --host 0.0.0.0 --port 8000

    # Run the scheduler worker
    python -m podcastfy.api.scheduler.worker
"""

from .main import app, run_server

__version__ = "2.0.0"
__all__ = ["app", "run_server"]
