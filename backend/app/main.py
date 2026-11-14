from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.api.v1.health import router as root_health_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import logger, setup_logging
from app.db.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Application shutting down.")

app = FastAPI(
    title="AI Data Analyst API",
    version="0.1.0",
    description="Agentic data analysis backend with safe tool execution and statistical rigor.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501", "http://127.0.0.1:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handlers
register_error_handlers(app)

# Root-level health check (for load balancers & docker)
app.include_router(root_health_router)

# Version 1 API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.API_PORT, reload=True)
