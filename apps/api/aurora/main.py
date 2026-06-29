"""FastAPI application factory.

Wires configuration, structured logging, the request-id middleware, CORS, the consistent error
model, the versioned router, and (in dev) demo seeding so the API is runnable end to end.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_router
from .core.config import Settings, get_settings
from .core.errors import register_exception_handlers
from .core.logging import configure_logging, get_logger, new_request_id, set_request_id
from .repositories.memory import get_store
from .seed.demo import seed_demo


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_runtime()
    configure_logging(settings.log_level)
    logger = get_logger("aurora.app")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.seed_demo_on_startup:
            logins = seed_demo(get_store(), settings.demo_password)
            logger.info(
                "Seeded demo tenant 'nimbus' with %d users (password: %s)",
                len(logins),
                settings.demo_password,
            )
        yield

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or new_request_id()
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
