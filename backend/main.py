from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Base, SessionLocal, engine, get_db
from backend.schemas import ConfigurationResponse, DashboardRequest, DashboardResponse, LogsResponse
from backend.service import GreenTwinService

service = GreenTwinService()


async def _poll_default_dashboard() -> None:
    while True:
        try:
            if SessionLocal is None:
                service.get_dashboard(
                    db=None,
                    request=DashboardRequest(
                        location=settings.default_location,
                        provider=settings.default_weather_provider,
                        greenhouse_type=settings.default_greenhouse_type,
                        target_temp_c=settings.default_target_temp_c,
                        refresh=True,
                    ),
                )
            else:
                with SessionLocal() as db:
                    service.get_dashboard(
                        db=db,
                        request=DashboardRequest(
                            location=settings.default_location,
                            provider=settings.default_weather_provider,
                            greenhouse_type=settings.default_greenhouse_type,
                            target_temp_c=settings.default_target_temp_c,
                            refresh=True,
                        ),
                    )
        except Exception:
            # Keep background polling alive even if one weather or database call fails.
            pass
        await asyncio.sleep(settings.default_poll_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if engine is not None:
        Base.metadata.create_all(bind=engine)
    poll_task: asyncio.Task[None] | None = None
    if settings.enable_background_polling:
        poll_task = asyncio.create_task(_poll_default_dashboard())
    try:
        yield
    finally:
        if poll_task is not None:
            poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await poll_task


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    summary="Real-time greenhouse digital twin with live weather, thermal simulation, and adaptive cooling optimization.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "GreenTwin AI backend is running.", "docs": "/docs", "health": "/health"}


@app.get(f"{settings.api_prefix}/config", response_model=ConfigurationResponse)
def get_config() -> ConfigurationResponse:
    return service.get_configuration()


@app.get(f"{settings.api_prefix}/dashboard", response_model=DashboardResponse)
def get_dashboard(
    location: str = Query(default=settings.default_location),
    provider: str = Query(default=settings.default_weather_provider),
    greenhouse_type: str = Query(default=settings.default_greenhouse_type),
    target_temp_c: float = Query(default=settings.default_target_temp_c),
    inside_temp_c: float | None = Query(default=None),
    refresh: bool = Query(default=False),
    db: Session | None = Depends(get_db),
) -> DashboardResponse:
    return service.get_dashboard(
        db=db,
        request=DashboardRequest(
            location=location,
            provider=provider,
            greenhouse_type=greenhouse_type,
            target_temp_c=target_temp_c,
            inside_temp_c=inside_temp_c,
            refresh=refresh,
        ),
    )


@app.post(f"{settings.api_prefix}/simulate", response_model=DashboardResponse)
def simulate_dashboard(payload: DashboardRequest, db: Session | None = Depends(get_db)) -> DashboardResponse:
    return service.get_dashboard(db=db, request=payload)


@app.get(f"{settings.api_prefix}/logs", response_model=LogsResponse)
def get_logs(limit: int = Query(default=25, ge=1, le=100), db: Session | None = Depends(get_db)) -> LogsResponse:
    return service.get_logs(db=db, limit=limit)
