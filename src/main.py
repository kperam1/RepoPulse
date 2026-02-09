from fastapi import FastAPI
from src.api.routes import router as api_router

app = FastAPI(
    title="RepoPulse API",
    description="A metrics and monitoring tool for GitHub repositories.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(api_router)
