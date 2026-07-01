from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SimulationLog(Base):
    __tablename__ = "simulation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    location_name: Mapped[str] = mapped_column(String(128), index=True)
    greenhouse_type: Mapped[str] = mapped_column(String(24), index=True)
    outside_temp_c: Mapped[float] = mapped_column(Float)
    inside_temp_c: Mapped[float] = mapped_column(Float)
    humidity_pct: Mapped[float] = mapped_column(Float)
    wind_speed_kph: Mapped[float] = mapped_column(Float)
    cloud_cover_pct: Mapped[float] = mapped_column(Float)
    uv_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_temp_c: Mapped[float] = mapped_column(Float)
    recommended_fan_pct: Mapped[float] = mapped_column(Float)
    recommended_spray_pct: Mapped[float] = mapped_column(Float)
    projected_energy_kwh: Mapped[float] = mapped_column(Float)
    projected_water_liters: Mapped[float] = mapped_column(Float)
    comfort_score: Mapped[float] = mapped_column(Float)
    comfort_band: Mapped[str] = mapped_column(String(24))
    peak_uncontrolled_temp_c: Mapped[float] = mapped_column(Float)
    peak_controlled_temp_c: Mapped[float] = mapped_column(Float)
    current_payload: Mapped[dict] = mapped_column(JSON)
    simulation_payload: Mapped[dict] = mapped_column(JSON)
