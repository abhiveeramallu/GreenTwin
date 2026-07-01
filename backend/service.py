from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import GREENHOUSE_PROFILES, settings
from backend.greenhouse import (
    SIMULATION_HORIZONS_MINUTES,
    SIMULATION_STEP_MINUTES,
    build_horizon_projections,
    build_resource_summary,
    calculate_comfort_score,
    choose_optimal_strategy,
    estimate_inside_temperature,
    get_greenhouse_profile,
    simulate_temperature_series,
)
from backend.models import SimulationLog
from backend.schemas import (
    ConfigurationResponse,
    DashboardResponse,
    DashboardRequest,
    ForecastPoint,
    GreenhouseProfileResponse,
    LogsResponse,
    SimulationLogRecord,
)
from backend.weather import WeatherBundle, fetch_weather_bundle


def _model_dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "dict"):
        return model.dict()
    return model


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


class GreenTwinService:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str, float, float | None], tuple[datetime, DashboardResponse]] = {}

    def get_configuration(self) -> ConfigurationResponse:
        profiles = [
            GreenhouseProfileResponse(
                type=key,
                label=value["label"],
                k=float(value["k"]),
                s=float(value["s"]),
                w=float(value["w"]),
                description=str(value["description"]),
            )
            for key, value in GREENHOUSE_PROFILES.items()
        ]
        return ConfigurationResponse(
            project_title="Real-Time Digital Twin for Greenhouse Climate Optimization Using Weather Forecast Streams and Adaptive Cooling Control",
            default_location=settings.default_location,
            default_provider=settings.default_weather_provider,
            default_greenhouse_type=settings.default_greenhouse_type,
            default_target_temp_c=settings.default_target_temp_c,
            supported_weather_providers=["weatherapi", "openweathermap"],
            greenhouse_profiles=profiles,
        )

    def get_dashboard(self, db: Session | None, request: DashboardRequest) -> DashboardResponse:
        key = (
            request.location.strip().lower(),
            request.provider.strip().lower(),
            request.greenhouse_type.strip().lower(),
            round(request.target_temp_c, 2),
            round(request.inside_temp_c, 2) if request.inside_temp_c is not None else None,
        )
        cached = self._cache.get(key)
        now = datetime.now(timezone.utc)
        if cached and not request.refresh and now - cached[0] < timedelta(seconds=settings.default_poll_interval_seconds):
            return cached[1]

        dashboard = self._build_dashboard(db=db, request=request)
        self._cache[key] = (now, dashboard)
        return dashboard

    def get_logs(self, db: Session | None, limit: int = 25) -> LogsResponse:
        if db is None or not settings.enable_log_storage:
            return LogsResponse(items=[])
        stmt = select(SimulationLog).order_by(SimulationLog.created_at.desc()).limit(limit)
        rows = list(db.scalars(stmt))
        return LogsResponse(items=[self._serialize_log(row) for row in rows])

    def _build_dashboard(self, db: Session | None, request: DashboardRequest) -> DashboardResponse:
        weather_bundle = fetch_weather_bundle(provider=request.provider, location=request.location)
        greenhouse_profile = get_greenhouse_profile(request.greenhouse_type)
        forecast_points = self._interpolate_forecast(weather_bundle)
        current_inside_temp_c = (
            round(request.inside_temp_c, 2)
            if request.inside_temp_c is not None
            else estimate_inside_temperature(weather_bundle.current, greenhouse_profile)
        )

        uncontrolled_series = simulate_temperature_series(
            greenhouse_profile=greenhouse_profile,
            initial_inside_temp_c=current_inside_temp_c,
            forecast_points=forecast_points,
            fan_pct=0.0,
            spray_pct=0.0,
        )
        optimization, optimized_series = choose_optimal_strategy(
            greenhouse_profile=greenhouse_profile,
            initial_inside_temp_c=current_inside_temp_c,
            forecast_points=forecast_points,
            target_temp_c=request.target_temp_c,
        )
        horizons = build_horizon_projections(
            uncontrolled_series=uncontrolled_series,
            optimized_series=optimized_series,
            strategy=optimization,
            target_temp_c=request.target_temp_c,
        )
        resource_summary = build_resource_summary(optimization, optimized_series)
        comfort = calculate_comfort_score(
            optimized_series=optimized_series,
            current_weather=weather_bundle.current,
            resource_summary=resource_summary,
            target_temp_c=request.target_temp_c,
        )

        alerts = list(weather_bundle.alerts)

        final_controlled_temp_c = optimized_series[-1].inside_temp_c if optimized_series else current_inside_temp_c

        if db is not None and settings.enable_log_storage:
            log_row = SimulationLog(
                provider=weather_bundle.current.provider,
                location_name=weather_bundle.current.location_name,
                greenhouse_type=greenhouse_profile.type,
                outside_temp_c=weather_bundle.current.temp_c,
                inside_temp_c=current_inside_temp_c,
                humidity_pct=weather_bundle.current.humidity_pct,
                wind_speed_kph=weather_bundle.current.wind_speed_kph,
                cloud_cover_pct=weather_bundle.current.cloud_cover_pct,
                uv_index=weather_bundle.current.uv_index,
                target_temp_c=request.target_temp_c,
                recommended_fan_pct=optimization.recommended_fan_pct,
                recommended_spray_pct=optimization.recommended_spray_pct,
                projected_energy_kwh=optimization.projected_energy_kwh,
                projected_water_liters=optimization.projected_water_liters,
                comfort_score=comfort.score,
                comfort_band=comfort.band,
                peak_uncontrolled_temp_c=max(point.inside_temp_c for point in uncontrolled_series),
                peak_controlled_temp_c=final_controlled_temp_c,
                current_payload=_jsonable(_model_dump(weather_bundle.current)),
                simulation_payload=_jsonable(
                    {
                        "forecast_points": [_model_dump(point) for point in forecast_points],
                        "uncontrolled_series": [_model_dump(point) for point in uncontrolled_series],
                        "optimized_series": [_model_dump(point) for point in optimized_series],
                        "horizons": [_model_dump(point) for point in horizons],
                        "optimization": _model_dump(optimization),
                        "resource_summary": _model_dump(resource_summary),
                        "comfort": _model_dump(comfort),
                    }
                ),
            )
            db.add(log_row)
            db.commit()
            db.refresh(log_row)

        logs = self.get_logs(db=db, limit=12).items
        return DashboardResponse(
            project_title="Real-Time Digital Twin for Greenhouse Climate Optimization Using Weather Forecast Streams and Adaptive Cooling Control",
            generated_at=datetime.now(timezone.utc),
            mode=weather_bundle.mode,  # type: ignore[arg-type]
            weather=weather_bundle.current,
            greenhouse_profile=greenhouse_profile,
            current_inside_temp_c=current_inside_temp_c,
            target_temp_c=request.target_temp_c,
            forecast_points=forecast_points,
            uncontrolled_series=uncontrolled_series,
            optimized_series=optimized_series,
            horizons=horizons,
            optimization=optimization,
            comfort=comfort,
            resource_summary=resource_summary,
            logs=logs,
            alerts=alerts,
        )

    def _interpolate_forecast(self, weather_bundle: WeatherBundle) -> list[ForecastPoint]:
        anchors = [
            ForecastPoint(
                timestamp=weather_bundle.current.observation_time,
                outside_temp_c=weather_bundle.current.temp_c,
                humidity_pct=weather_bundle.current.humidity_pct,
                wind_speed_kph=weather_bundle.current.wind_speed_kph,
                cloud_cover_pct=weather_bundle.current.cloud_cover_pct,
                uv_index=weather_bundle.current.uv_index,
                source="current",
            )
        ]
        anchors.extend(sorted(weather_bundle.hourly_forecast, key=lambda item: item.timestamp))
        if len(anchors) == 1:
            anchors.append(
                ForecastPoint(
                    timestamp=anchors[0].timestamp + timedelta(hours=1),
                    outside_temp_c=anchors[0].outside_temp_c,
                    humidity_pct=anchors[0].humidity_pct,
                    wind_speed_kph=anchors[0].wind_speed_kph,
                    cloud_cover_pct=anchors[0].cloud_cover_pct,
                    uv_index=anchors[0].uv_index,
                    source="filled",
                )
            )

        points: list[ForecastPoint] = []
        start = anchors[0].timestamp
        for horizon in range(SIMULATION_STEP_MINUTES, max(SIMULATION_HORIZONS_MINUTES) + SIMULATION_STEP_MINUTES, SIMULATION_STEP_MINUTES):
            target = start + timedelta(minutes=horizon)
            left = anchors[-2] if len(anchors) > 1 else anchors[0]
            right = anchors[-1]
            for idx in range(1, len(anchors)):
                candidate = anchors[idx]
                if candidate.timestamp >= target:
                    left = anchors[idx - 1]
                    right = candidate
                    break

            total_seconds = max((right.timestamp - left.timestamp).total_seconds(), 1.0)
            position = clamp((target - left.timestamp).total_seconds() / total_seconds, 0.0, 1.0)
            uv_left = float(left.uv_index or 0.0)
            uv_right = float(right.uv_index or 0.0)
            points.append(
                ForecastPoint(
                    timestamp=target,
                    outside_temp_c=round(left.outside_temp_c + (right.outside_temp_c - left.outside_temp_c) * position, 2),
                    humidity_pct=round(left.humidity_pct + (right.humidity_pct - left.humidity_pct) * position, 2),
                    wind_speed_kph=round(left.wind_speed_kph + (right.wind_speed_kph - left.wind_speed_kph) * position, 2),
                    cloud_cover_pct=round(left.cloud_cover_pct + (right.cloud_cover_pct - left.cloud_cover_pct) * position, 2),
                    uv_index=round(uv_left + (uv_right - uv_left) * position, 2),
                    source=f"interpolated-{right.source}",
                )
            )
        return points

    def _serialize_log(self, row: SimulationLog) -> SimulationLogRecord:
        final_controlled_temp_c = row.peak_controlled_temp_c
        optimized_series = row.simulation_payload.get("optimized_series", []) if isinstance(row.simulation_payload, dict) else []
        if optimized_series:
            last_point = optimized_series[-1]
            if isinstance(last_point, dict) and isinstance(last_point.get("inside_temp_c"), (int, float)):
                final_controlled_temp_c = float(last_point["inside_temp_c"])

        return SimulationLogRecord(
            id=row.id,
            created_at=row.created_at,
            provider=row.provider,
            location_name=row.location_name,
            greenhouse_type=row.greenhouse_type,
            inside_temp_c=round(row.inside_temp_c, 2),
            outside_temp_c=round(row.outside_temp_c, 2),
            comfort_score=round(row.comfort_score, 1),
            comfort_band=row.comfort_band,
            recommended_fan_pct=round(row.recommended_fan_pct, 1),
            recommended_spray_pct=round(row.recommended_spray_pct, 1),
            projected_energy_kwh=round(row.projected_energy_kwh, 3),
            projected_water_liters=round(row.projected_water_liters, 3),
            peak_controlled_temp_c=round(final_controlled_temp_c, 2),
        )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
