"""
Daily News Podcast API - Main Application

A comprehensive REST API for:
- User authentication (Google OAuth via Supabase)
- Subscription and billing management
- Scheduled podcast generation
- Real-time news to podcast conversion

Version: 2.0.0
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .models.common import HealthResponse, ErrorResponse
from .routers import (
    auth_router,
    users_router,
    subscriptions_router,
    credits_router,
    schedules_router,
    podcasts_router,
    payments_router,
)
from .utils.logger import get_logger
from .utils.exceptions import APIException

logger = get_logger(__name__)


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("Starting Daily News Podcast API v2.0.0")
    
    # Startup tasks
    # - Initialize database connections (handled by Supabase client)
    # - Start background scheduler (optional, can run separately)
    
    yield
    
    # Shutdown tasks
    logger.info("Shutting down Daily News Podcast API")


# ============================================================================
# Application Setup
# ============================================================================

# Check if docs should be enabled
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"
API_PREFIX = os.getenv("API_PREFIX", "/api/v2")

app = FastAPI(
    title="Daily News Podcast API",
    description="""
## 실시간 뉴스를 검색하고 팟캐스트로 변환하는 API

### 주요 기능
- **인증**: Google OAuth를 통한 사용자 인증
- **구독 관리**: Free, Basic, Pro 플랜 지원
- **크레딧 시스템**: 온디맨드 생성 및 배치 토큰
- **스케줄링**: 자동 팟캐스트 생성 및 이메일 전송
- **결제**: Stripe 및 토스페이먼츠 지원

### API 버전
- **v2**: 새로운 Supabase 기반 백엔드 (현재)
- **v1**: 레거시 API (하위 호환)

### 인증
대부분의 엔드포인트는 JWT Bearer 토큰이 필요합니다:
```
Authorization: Bearer <your_jwt_token>
```
""",
    version="2.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
    lifespan=lifespan,
)


# ============================================================================
# Middleware
# ============================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {process_time:.2f}ms"
    )
    
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                **exc.details,
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        }
    )


# ============================================================================
# Routers
# ============================================================================

# Include all routers with API prefix
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(subscriptions_router, prefix=API_PREFIX)
app.include_router(credits_router, prefix=API_PREFIX)
app.include_router(schedules_router, prefix=API_PREFIX)
app.include_router(podcasts_router, prefix=API_PREFIX)
app.include_router(payments_router, prefix=API_PREFIX)


# ============================================================================
# Root Endpoints
# ============================================================================

@app.get("/", response_model=HealthResponse, tags=["Health"])
async def root():
    """API root endpoint with health status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="2.0.0",
        services={
            "database": "supabase",
            "auth": "supabase_auth",
            "storage": "local",
        }
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="2.0.0",
    )


@app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["Health"])
async def api_health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="2.0.0",
    )


# ============================================================================
# Entry Point
# ============================================================================

def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
):
    """Run the API server."""
    import uvicorn
    
    uvicorn.run(
        "podcastfy.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    run_server(host=host, port=port, reload=reload)
