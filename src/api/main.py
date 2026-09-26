"""
TAJ FROID ERP - Main FastAPI Application
Enterprise-grade API with comprehensive error handling and middleware
Supports REST API and WebSocket for real-time updates across desktop, web, and mobile
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from contextlib import asynccontextmanager
import asyncio

from src.core.config import settings
from src.core.database import init_db
from src.api.routes import router as api_router


# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info(f"Starting TAJ FROID ERP v1.0.0")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Port: {settings.api_port}, WebSocket Port: {settings.ws_port}")
    
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="TAJ FROID ERP",
    version="1.0.0",
    description="Enterprise Resource Planning API with real-time WebSocket support for multi-channel sales tracking",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# CORS Middleware
#
# SECURITY: this was `allow_origins=["*"]` together with
# `allow_credentials=True`, which lets any website a logged-in user visits
# call this API with their session. Origins are now explicit, and the
# wildcard is only honoured outside production - and never together with
# credentials, which is the combination that actually matters.
_is_production = settings.environment.lower() in ("production", "prod")
_configured_origins = list(getattr(settings.api, "cors_origins", []) or [])

if _is_production:
    _origins = [o for o in _configured_origins if o != "*"]
    if not _origins:
        # Fail closed rather than exposing the API to every origin.
        raise RuntimeError(
            "CORS_ORIGINS must list explicit origins in production; "
            "'*' is not permitted."
        )
else:
    _origins = _configured_origins or ["*"]

# Credentials are only allowed for explicit origins; a wildcard with
# credentials is rejected by browsers and must not be relied upon.
_allow_credentials = "*" not in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        } if settings.environment == "development" else {"detail": "Internal server error"}
    )


# Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


# Health Check Endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "websocket_enabled": True
    }


# Root Endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "TAJ FROID ERP",
        "version": "1.0.0",
        "description": "Multi-channel ERP with real-time WebSocket support",
        "features": [
            "Dual pricing (website fixed price, store variable price)",
            "Real-time stock updates via WebSocket",
            "Multi-channel sales tracking (website, store, mobile app)",
            "Comprehensive analytics dashboard",
            "Mobile app ready for owner"
        ],
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/{client_type}"
    }


# Register API routes
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.environment == "development")
    )
