from contextlib import asynccontextmanager
import logging
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.errors import HireLoopError, RateLimitError
from src.mcp.rate_limiter import RateLimiter, client_ip_from_headers
from src.mcp.server import create_mcp_app, mcp as hireloop_mcp
from src.routers.admin import router as admin_router
from src.routers.jobs import router as jobs_router
from src.routers.meta import router as meta_router
from src.routers.resume import router as resume_router
from src.web_ui import mount_web_ui

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)


class McpRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            ip = client_ip_from_headers(
                {k: v for k, v in request.headers.items()},
                fallback=request.client.host if request.client else "127.0.0.1",
            )
            try:
                self.limiter.check(ip)
            except RateLimitError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "detail": exc.detail,
                        "error_code": exc.error_code,
                        "request_id": str(uuid.uuid4()),
                    },
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with hireloop_mcp.session_manager.run():
        yield


def create_app() -> FastAPI:
    application = FastAPI(title="HireLoop", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(McpRateLimitMiddleware)

    @application.exception_handler(HireLoopError)
    async def hireloop_error_handler(_request: Request, exc: HireLoopError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "request_id": str(uuid.uuid4()),
            },
        )

    application.include_router(admin_router)
    application.include_router(jobs_router)
    application.include_router(meta_router)
    application.include_router(resume_router)
    # Must call create_mcp_app() before lifespan uses session_manager
    application.mount("/mcp", create_mcp_app())

    @application.get("/health")
    async def health() -> dict:
        from src.services.health import build_health_payload

        return build_health_payload()

    # Static SPA last so /static does not shadow API routes
    mount_web_ui(application)

    return application


app = create_app()
