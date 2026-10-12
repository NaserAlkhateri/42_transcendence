from fastapi import FastAPI

from app.api import health
from app.api.v1.router import api_router
from app.core.errors import install_error_handlers

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sijil API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()
