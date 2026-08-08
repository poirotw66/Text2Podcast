"""
FastAPI application entry point
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="Podcast Generation API",
    description="API for generating podcasts from text content",
    version="1.0.0"
)

# CORS middleware
# allow_origins=["*"] together with allow_credentials=True is a combination browsers
# reject outright (and that FastAPI/Starlette will refuse to serve credentialed
# responses for), so it was both insecure-looking and non-functional. Origins are now
# driven by CORS_ALLOW_ORIGINS (comma-separated), defaulting to the two local dev
# frontends. Credentials are only enabled when the origin list isn't a wildcard.
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:5173")
_cors_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
_cors_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Podcast Generation API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

