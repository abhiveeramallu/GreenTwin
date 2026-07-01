from __future__ import annotations

from dataclasses import dataclass

from backend.config import GREENHOUSE_PROFILES
from backend.schemas import (
    ComfortScoreBreakdown,
    ForecastPoint,
    GreenhouseProfileResponse,
    HorizonProjection,
    OptimizationStrategy,
    PredictionPoint,
    ResourceSummary,
    WeatherSnapshot,
)

SIMULATION_STEP_MINUTES = 10
SIMULATION_HORIZONS_MINUTES = tuple(range(10, 241, SIMULATION_STEP_MINUTES))
FAN_COOLING_CAPACITY_C_PER_HOUR = 4.8
SPRAY_COOLING_CAPACITY_C_PER_HOUR = 6.2
FAN_POWER_KW = 0.55
SPRAY_WATER_LPH = 12.0
MAINTENANCE_BAND_C = 0.25
TARGET_SNAP_TOLERANCE_C = 0.25
CONTROL_STEP_PCT = 10


@dataclass
class StepComputation:
    next_inside_temp_c: float
    heat_gain_c: float
    solar_gain_c: float
    wind_cooling_c: float
    fan_cooling_c: float
    spray_cooling_c: float


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def get_greenhouse_profile(greenhouse_type: str) -> GreenhouseProfileResponse:
    normalized = greenhouse_type.strip().lower()
    raw = GREENHOUSE_PROFILES.get(normalized, GREENHOUSE_PROFILES["medium"])
    return GreenhouseProfileResponse(
        type=normalized if normalized in GREENHOUSE_PROFILES else "medium",
        label=raw["label"],
        k=float(raw["k"]),
        s=float(raw["s"]),
        w=float(raw["w"]),
        description=str(raw["description"]),
    )


def solar_radiation_factor(uv_index: float | None, cloud_cover_pct: float) -> float:
    uv = max(0.0, float(uv_index or 0.0))
    cloud_factor = 1.0 - clamp(cloud_cover_pct / 100.0, 0.0, 0.95)
    return uv * 3.2 * cloud_factor


def estimate_inside_temperature(current_weather: WeatherSnapshot, greenhouse_profile: GreenhouseProfileResponse) -> float:
    solar_bias = solar_radiation_factor(current_weather.uv_index, current_weather.cloud_cover_pct) * 0.08
    wind_relief = current_weather.wind_speed_kph * greenhouse_profile.w * 0.18
    base = current_weather.temp_c + 0.9 + solar_bias - wind_relief
    return round(clamp(base, 12.0, 48.0), 2)


def compute_step(
    greenhouse_profile: GreenhouseProfileResponse,
    outside_temp_c: float,
    inside_temp_c: float,
    humidity_pct: float,
    wind_speed_kph: float,
    cloud_cover_pct: float,
    uv_index: float | None,
    fan_pct: float,
    spray_pct: float,
    step_minutes: int = SIMULATION_STEP_MINUTES,
) -> StepComputation:
    time_factor = step_minutes / 60.0
    heat_gain_c = greenhouse_profile.k * (outside_temp_c - inside_temp_c) * time_factor
    solar_gain_c = greenhouse_profile.s * solar_radiation_factor(uv_index, cloud_cover_pct) * time_factor
    wind_cooling_c = greenhouse_profile.w * wind_speed_kph * time_factor

    fan_pct_normalized = clamp(fan_pct, 0.0, 100.0) / 100.0
    spray_pct_normalized = clamp(spray_pct, 0.0, 100.0) / 100.0
    spray_efficiency = clamp(1.05 - (humidity_pct / 100.0) * 0.7, 0.35, 0.95)

    fan_cooling_c = FAN_COOLING_CAPACITY_C_PER_HOUR * fan_pct_normalized * time_factor
    spray_cooling_c = SPRAY_COOLING_CAPACITY_C_PER_HOUR * spray_pct_normalized * spray_efficiency * time_factor

    next_inside_temp_c = inside_temp_c + heat_gain_c + solar_gain_c - wind_cooling_c - fan_cooling_c - spray_cooling_c
    return StepComputation(
        next_inside_temp_c=clamp(next_inside_temp_c, 5.0, 60.0),
        heat_gain_c=round(heat_gain_c, 3),
        solar_gain_c=round(solar_gain_c, 3),
        wind_cooling_c=round(wind_cooling_c, 3),
        fan_cooling_c=round(fan_cooling_c, 3),
        spray_cooling_c=round(spray_cooling_c, 3),
    )


def simulate_temperature_series(
    greenhouse_profile: GreenhouseProfileResponse,
    initial_inside_temp_c: float,
    forecast_points: list[ForecastPoint],
    fan_pct: float,
    spray_pct: float,
) -> list[PredictionPoint]:
    series: list[PredictionPoint] = []
    inside_temp_c = initial_inside_temp_c

    for index, point in enumerate(forecast_points, start=1):
        computation = compute_step(
            greenhouse_profile=greenhouse_profile,
            outside_temp_c=point.outside_temp_c,
            inside_temp_c=inside_temp_c,
            humidity_pct=point.humidity_pct,
            wind_speed_kph=point.wind_speed_kph,
            cloud_cover_pct=point.cloud_cover_pct,
            uv_index=point.uv_index,
            fan_pct=fan_pct,
            spray_pct=spray_pct,
        )
        inside_temp_c = computation.next_inside_temp_c
        series.append(
            PredictionPoint(
                timestamp=point.timestamp,
                horizon_minutes=index * SIMULATION_STEP_MINUTES,
                outside_temp_c=round(point.outside_temp_c, 2),
                inside_temp_c=round(inside_temp_c, 2),
                fan_pct=round(fan_pct, 1),
                spray_pct=round(spray_pct, 1),
                control_mode="passive" if fan_pct == 0 and spray_pct == 0 else "fixed_control",
                heat_gain_c=computation.heat_gain_c,
                solar_gain_c=computation.solar_gain_c,
                wind_cooling_c=computation.wind_cooling_c,
                fan_cooling_c=computation.fan_cooling_c,
                spray_cooling_c=computation.spray_cooling_c,
            )
        )

    return series


def _step_resource_usage(fan_pct: float, spray_pct: float, step_minutes: int = SIMULATION_STEP_MINUTES) -> tuple[float, float]:
    step_hours = step_minutes / 60.0
    energy_kwh = FAN_POWER_KW * (fan_pct / 100.0) * step_hours
    water_liters = SPRAY_WATER_LPH * (spray_pct / 100.0) * step_hours
    return energy_kwh, water_liters


def _control_mode_for(fan_pct: float, spray_pct: float) -> str:
    if fan_pct <= 0 and spray_pct <= 0:
        return "idle_hold"
    if spray_pct <= 0:
        return "fan_pulse"
    if fan_pct <= 0:
        return "spray_pulse"
    return "fan_and_spray_pulse"


def simulate_maintenance_series(
    greenhouse_profile: GreenhouseProfileResponse,
    initial_inside_temp_c: float,
    forecast_points: list[ForecastPoint],
    target_temp_c: float,
) -> list[PredictionPoint]:
    series: list[PredictionPoint] = []
    inside_temp_c = initial_inside_temp_c

    for index, point in enumerate(forecast_points, start=1):
        passive = compute_step(
            greenhouse_profile=greenhouse_profile,
            outside_temp_c=point.outside_temp_c,
            inside_temp_c=inside_temp_c,
            humidity_pct=point.humidity_pct,
            wind_speed_kph=point.wind_speed_kph,
            cloud_cover_pct=point.cloud_cover_pct,
            uv_index=point.uv_index,
            fan_pct=0.0,
            spray_pct=0.0,
        )

        best_fan_pct = 0.0
        best_spray_pct = 0.0
        best_computation = passive
        best_cost = float("inf")

        for fan_pct in range(0, 101, CONTROL_STEP_PCT):
            for spray_pct in range(0, 101, CONTROL_STEP_PCT):
                computation = compute_step(
                    greenhouse_profile=greenhouse_profile,
                    outside_temp_c=point.outside_temp_c,
                    inside_temp_c=inside_temp_c,
                    humidity_pct=point.humidity_pct,
                    wind_speed_kph=point.wind_speed_kph,
                    cloud_cover_pct=point.cloud_cover_pct,
                    uv_index=point.uv_index,
                    fan_pct=float(fan_pct),
                    spray_pct=float(spray_pct),
                )
                energy_kwh, water_liters = _step_resource_usage(float(fan_pct), float(spray_pct))
                below_target = max(0.0, target_temp_c - computation.next_inside_temp_c)
                above_target = max(0.0, computation.next_inside_temp_c - target_temp_c)
                overshoot_penalty = below_target * 900.0 + max(0.0, below_target - 0.05) * 3200.0
                residual_heat_penalty = above_target * 260.0
                switching_penalty = (float(fan_pct) + float(spray_pct)) * 0.028
                utility_penalty = (energy_kwh * 12.0) + (water_liters * 2.8)
                spray_bias = 0.0 if fan_pct > 0 else spray_pct * 0.02
                target_snap_bonus = 30.0 if abs(computation.next_inside_temp_c - target_temp_c) <= TARGET_SNAP_TOLERANCE_C else 0.0
                cost = overshoot_penalty + residual_heat_penalty + switching_penalty + utility_penalty + spray_bias - target_snap_bonus

                if cost < best_cost:
                    best_cost = cost
                    best_fan_pct = float(fan_pct)
                    best_spray_pct = float(spray_pct)
                    best_computation = computation

        next_inside_temp_c = best_computation.next_inside_temp_c
        if abs(next_inside_temp_c - target_temp_c) <= TARGET_SNAP_TOLERANCE_C:
            next_inside_temp_c = target_temp_c

        inside_temp_c = next_inside_temp_c
        series.append(
            PredictionPoint(
                timestamp=point.timestamp,
                horizon_minutes=index * SIMULATION_STEP_MINUTES,
                outside_temp_c=round(point.outside_temp_c, 2),
                inside_temp_c=round(next_inside_temp_c, 2),
                fan_pct=round(best_fan_pct, 1),
                spray_pct=round(best_spray_pct, 1),
                control_mode=_control_mode_for(best_fan_pct, best_spray_pct),
                heat_gain_c=best_computation.heat_gain_c,
                solar_gain_c=best_computation.solar_gain_c,
                wind_cooling_c=best_computation.wind_cooling_c,
                fan_cooling_c=best_computation.fan_cooling_c,
                spray_cooling_c=best_computation.spray_cooling_c,
            )
        )

    return series


def choose_optimal_strategy(
    greenhouse_profile: GreenhouseProfileResponse,
    initial_inside_temp_c: float,
    forecast_points: list[ForecastPoint],
    target_temp_c: float,
) -> tuple[OptimizationStrategy, list[PredictionPoint]]:
    baseline = simulate_temperature_series(
        greenhouse_profile=greenhouse_profile,
        initial_inside_temp_c=initial_inside_temp_c,
        forecast_points=forecast_points,
        fan_pct=0.0,
        spray_pct=0.0,
    )

    if baseline and max(point.inside_temp_c for point in baseline) <= target_temp_c + MAINTENANCE_BAND_C:
        strategy = OptimizationStrategy(
            target_temp_c=target_temp_c,
            recommended_fan_pct=0.0,
            recommended_spray_pct=0.0,
            peak_fan_pct=0.0,
            peak_spray_pct=0.0,
            maintenance_band_c=MAINTENANCE_BAND_C,
            horizon_minutes=len(forecast_points) * SIMULATION_STEP_MINUTES,
            projected_energy_kwh=0.0,
            projected_water_liters=0.0,
            electricity_cost_index=0.0,
            water_cost_index=0.0,
            total_cost_score=0.0,
            rationale="Passive conditions already keep the greenhouse within the comfort target.",
        )
        return strategy, baseline

    best_series = simulate_maintenance_series(
        greenhouse_profile=greenhouse_profile,
        initial_inside_temp_c=initial_inside_temp_c,
        forecast_points=forecast_points,
        target_temp_c=target_temp_c,
    )

    total_energy_kwh = 0.0
    total_water_liters = 0.0
    fan_runtime_minutes = 0
    spray_runtime_minutes = 0
    for point in best_series:
        step_energy_kwh, step_water_liters = _step_resource_usage(point.fan_pct, point.spray_pct)
        total_energy_kwh += step_energy_kwh
        total_water_liters += step_water_liters
        if point.fan_pct > 0:
            fan_runtime_minutes += SIMULATION_STEP_MINUTES
        if point.spray_pct > 0:
            spray_runtime_minutes += SIMULATION_STEP_MINUTES

    peak_error = max(max(0.0, point.inside_temp_c - target_temp_c) for point in best_series)
    mean_abs_error = sum(abs(point.inside_temp_c - target_temp_c) for point in best_series) / max(len(best_series), 1)
    electricity_cost_index = round(total_energy_kwh * 11.5, 3)
    water_cost_index = round(total_water_liters * 2.4, 3)
    total_cost_score = round((peak_error * 160.0) + (mean_abs_error * 40.0) + electricity_cost_index + water_cost_index, 3)

    reached_target = any(point.inside_temp_c <= target_temp_c + MAINTENANCE_BAND_C for point in best_series)
    uses_spray = any(point.spray_pct > 0 for point in best_series)
    if reached_target and uses_spray:
        rationale = "The controller reaches the setpoint and then uses duty-cycled fan and spray pulses inside each 10-minute interval to hold near 28C for the next 4 hours."
    elif reached_target:
        rationale = "The controller reaches the setpoint and then uses duty-cycled fan pulses to keep the greenhouse close to 28C for the next 4 hours."
    elif uses_spray:
        rationale = "Even full pulsed fan-plus-spray cooling cannot fully reach 28C under this forecast, but it minimizes overshoot and prevents runaway heat."
    else:
        rationale = "Fan-only pulsed cooling is enough to move toward the target while avoiding unnecessary overcooling."

    strategy = OptimizationStrategy(
        target_temp_c=target_temp_c,
        recommended_fan_pct=round(best_series[0].fan_pct if best_series else 0.0, 1),
        recommended_spray_pct=round(best_series[0].spray_pct if best_series else 0.0, 1),
        peak_fan_pct=max((point.fan_pct for point in best_series), default=0.0),
        peak_spray_pct=max((point.spray_pct for point in best_series), default=0.0),
        maintenance_band_c=MAINTENANCE_BAND_C,
        horizon_minutes=len(best_series) * SIMULATION_STEP_MINUTES,
        projected_energy_kwh=round(total_energy_kwh, 3),
        projected_water_liters=round(total_water_liters, 3),
        electricity_cost_index=electricity_cost_index,
        water_cost_index=water_cost_index,
        total_cost_score=total_cost_score,
        rationale=rationale,
    )
    return strategy, best_series


def build_horizon_projections(
    uncontrolled_series: list[PredictionPoint],
    optimized_series: list[PredictionPoint],
    strategy: OptimizationStrategy,
    target_temp_c: float,
) -> list[HorizonProjection]:
    index_by_horizon = {point.horizon_minutes: point for point in uncontrolled_series}
    optimized_index_by_horizon = {point.horizon_minutes: point for point in optimized_series}
    projections: list[HorizonProjection] = []

    for horizon in SIMULATION_HORIZONS_MINUTES:
        uncontrolled = index_by_horizon.get(horizon)
        controlled = optimized_index_by_horizon.get(horizon)
        if uncontrolled is None or controlled is None:
            continue
        projections.append(
            HorizonProjection(
                horizon_minutes=horizon,
                label=f"{horizon} min",
                outside_temp_c=controlled.outside_temp_c,
                uncontrolled_temp_c=uncontrolled.inside_temp_c,
                controlled_temp_c=controlled.inside_temp_c,
                recommended_fan_pct=controlled.fan_pct,
                recommended_spray_pct=controlled.spray_pct,
                control_mode=controlled.control_mode,
                target_met=abs(controlled.inside_temp_c - target_temp_c) <= strategy.maintenance_band_c,
                temperature_error_c=round(controlled.inside_temp_c - target_temp_c, 2),
            )
        )
    return projections


def build_resource_summary(strategy: OptimizationStrategy, optimized_series: list[PredictionPoint]) -> ResourceSummary:
    return ResourceSummary(
        projected_energy_kwh=strategy.projected_energy_kwh,
        projected_water_liters=strategy.projected_water_liters,
        electricity_cost_index=strategy.electricity_cost_index,
        water_cost_index=strategy.water_cost_index,
        fan_runtime_minutes=sum(SIMULATION_STEP_MINUTES for point in optimized_series if point.fan_pct > 0),
        spray_runtime_minutes=sum(SIMULATION_STEP_MINUTES for point in optimized_series if point.spray_pct > 0),
    )


def calculate_comfort_score(
    optimized_series: list[PredictionPoint],
    current_weather: WeatherSnapshot,
    resource_summary: ResourceSummary,
    target_temp_c: float,
) -> ComfortScoreBreakdown:
    if not optimized_series:
        return ComfortScoreBreakdown(
            score=0.0,
            band="Poor",
            temperature_component=0.0,
            humidity_component=0.0,
            efficiency_component=0.0,
        )

    mean_abs_temp_error = sum(abs(point.inside_temp_c - target_temp_c) for point in optimized_series) / len(optimized_series)
    humidity_distance = abs(current_weather.humidity_pct - 65.0)
    temperature_component = clamp(100.0 - mean_abs_temp_error * 18.0, 0.0, 100.0)
    humidity_component = clamp(100.0 - humidity_distance * 2.2, 0.0, 100.0)
    efficiency_component = clamp(
        100.0
        - (resource_summary.projected_energy_kwh * 30.0)
        - (resource_summary.projected_water_liters * 3.2),
        0.0,
        100.0,
    )
    score = round(temperature_component * 0.5 + humidity_component * 0.25 + efficiency_component * 0.25, 1)
    if score >= 90.0:
        band = "Excellent"
    elif score >= 70.0:
        band = "Good"
    elif score >= 50.0:
        band = "Moderate"
    else:
        band = "Poor"
    return ComfortScoreBreakdown(
        score=score,
        band=band,
        temperature_component=round(temperature_component, 1),
        humidity_component=round(humidity_component, 1),
        efficiency_component=round(efficiency_component, 1),
    )
