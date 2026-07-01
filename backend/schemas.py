from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WeatherSnapshot(BaseModel):
    provider: str
    location_name: str
    observation_time: datetime
    temp_c: float
    humidity_pct: float
    wind_speed_kph: float
    pressure_hpa: float | None = None
    cloud_cover_pct: float
    uv_index: float | None = None
    air_quality_index: float | None = None


class ForecastPoint(BaseModel):
    timestamp: datetime
    outside_temp_c: float
    humidity_pct: float
    wind_speed_kph: float
    cloud_cover_pct: float
    uv_index: float | None = None
    source: str = "forecast"


class GreenhouseProfileResponse(BaseModel):
    type: str
    label: str
    k: float
    s: float
    w: float
    description: str


class PredictionPoint(BaseModel):
    timestamp: datetime
    horizon_minutes: int
    outside_temp_c: float
    inside_temp_c: float
    fan_pct: float = 0.0
    spray_pct: float = 0.0
    control_mode: str = "passive"
    heat_gain_c: float
    solar_gain_c: float
    wind_cooling_c: float
    fan_cooling_c: float
    spray_cooling_c: float


class HorizonProjection(BaseModel):
    horizon_minutes: int
    label: str
    outside_temp_c: float
    uncontrolled_temp_c: float
    controlled_temp_c: float
    recommended_fan_pct: float
    recommended_spray_pct: float
    control_mode: str
    target_met: bool
    temperature_error_c: float


class OptimizationStrategy(BaseModel):
    target_temp_c: float
    recommended_fan_pct: float
    recommended_spray_pct: float
    peak_fan_pct: float
    peak_spray_pct: float
    maintenance_band_c: float
    horizon_minutes: int
    projected_energy_kwh: float
    projected_water_liters: float
    electricity_cost_index: float
    water_cost_index: float
    total_cost_score: float
    rationale: str


class ComfortScoreBreakdown(BaseModel):
    score: float
    band: Literal["Excellent", "Good", "Moderate", "Poor"]
    temperature_component: float
    humidity_component: float
    efficiency_component: float


class ResourceSummary(BaseModel):
    projected_energy_kwh: float
    projected_water_liters: float
    electricity_cost_index: float
    water_cost_index: float
    fan_runtime_minutes: int
    spray_runtime_minutes: int


class SimulationLogRecord(BaseModel):
    id: int
    created_at: datetime
    provider: str
    location_name: str
    greenhouse_type: str
    inside_temp_c: float
    outside_temp_c: float
    comfort_score: float
    comfort_band: str
    recommended_fan_pct: float
    recommended_spray_pct: float
    projected_energy_kwh: float
    projected_water_liters: float
    peak_controlled_temp_c: float


class DashboardResponse(BaseModel):
    project_title: str
    generated_at: datetime
    mode: Literal["live", "demo"]
    weather: WeatherSnapshot
    greenhouse_profile: GreenhouseProfileResponse
    current_inside_temp_c: float
    target_temp_c: float
    forecast_points: list[ForecastPoint]
    uncontrolled_series: list[PredictionPoint]
    optimized_series: list[PredictionPoint]
    horizons: list[HorizonProjection]
    optimization: OptimizationStrategy
    comfort: ComfortScoreBreakdown
    resource_summary: ResourceSummary
    logs: list[SimulationLogRecord]
    alerts: list[str] = Field(default_factory=list)


class DashboardRequest(BaseModel):
    location: str = "Coimbatore, India"
    provider: str = "weatherapi"
    greenhouse_type: str = "medium"
    target_temp_c: float = 28.0
    inside_temp_c: float | None = None
    refresh: bool = False


class ConfigurationResponse(BaseModel):
    project_title: str
    default_location: str
    default_provider: str
    default_greenhouse_type: str
    default_target_temp_c: float
    supported_weather_providers: list[str]
    greenhouse_profiles: list[GreenhouseProfileResponse]


class LogsResponse(BaseModel):
    items: list[SimulationLogRecord]
