from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from backend.greenhouse import (
    build_horizon_projections,
    calculate_comfort_score,
    choose_optimal_strategy,
    get_greenhouse_profile,
    simulate_temperature_series,
)
from backend.schemas import ForecastPoint, ResourceSummary, WeatherSnapshot


class DigitalTwinTests(unittest.TestCase):
    def setUp(self) -> None:
        start = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)
        self.forecast_points = [
            ForecastPoint(
                timestamp=start + timedelta(minutes=index * 10),
                outside_temp_c=36.0 + index * 0.3,
                humidity_pct=58.0 + index * 0.2,
                wind_speed_kph=10.0 + index * 0.1,
                cloud_cover_pct=24.0 + index * 0.3,
                uv_index=7.5 - index * 0.15,
                source="test",
            )
            for index in range(1, 25)
        ]

    def test_optimizer_reduces_peak_temperature(self) -> None:
        profile = get_greenhouse_profile("medium")
        baseline = simulate_temperature_series(profile, 33.0, self.forecast_points, fan_pct=0.0, spray_pct=0.0)
        strategy, optimized = choose_optimal_strategy(profile, 33.0, self.forecast_points, target_temp_c=28.0)

        self.assertGreater(max(point.inside_temp_c for point in baseline), max(point.inside_temp_c for point in optimized))
        self.assertGreaterEqual(strategy.recommended_fan_pct, 0.0)
        self.assertGreaterEqual(strategy.recommended_spray_pct, 0.0)
        self.assertEqual(strategy.horizon_minutes, 240)

        horizons = build_horizon_projections(baseline, optimized, strategy, target_temp_c=28.0)
        self.assertTrue(any(horizon.target_met for horizon in horizons))
        self.assertEqual(horizons[-1].horizon_minutes, 240)

    def test_optimizer_holds_near_target_after_reaching_it(self) -> None:
        profile = get_greenhouse_profile("medium")
        _, optimized = choose_optimal_strategy(profile, 33.0, self.forecast_points, target_temp_c=28.0)

        hit_index = next(index for index, point in enumerate(optimized) if point.inside_temp_c <= 28.25)
        maintained_segment = optimized[hit_index:]

        self.assertTrue(all(point.inside_temp_c >= 27.75 for point in maintained_segment))
        self.assertTrue(all(point.inside_temp_c <= 28.25 for point in maintained_segment))
        self.assertTrue(any(point.fan_pct > 0 or point.spray_pct > 0 for point in maintained_segment))
        self.assertTrue(any(point.fan_pct < 100 or point.spray_pct < 100 for point in maintained_segment))

    def test_comfort_score_stays_bounded(self) -> None:
        profile = get_greenhouse_profile("medium")
        _, optimized = choose_optimal_strategy(profile, 32.0, self.forecast_points, target_temp_c=28.0)
        current_weather = WeatherSnapshot(
            provider="test",
            location_name="Test Greenhouse",
            observation_time=datetime.now(timezone.utc),
            temp_c=34.0,
            humidity_pct=63.0,
            wind_speed_kph=12.0,
            pressure_hpa=1010.0,
            cloud_cover_pct=20.0,
            uv_index=7.0,
            air_quality_index=2.0,
        )
        resources = ResourceSummary(
            projected_energy_kwh=0.42,
            projected_water_liters=2.4,
            electricity_cost_index=4.8,
            water_cost_index=5.8,
            fan_runtime_minutes=120,
            spray_runtime_minutes=120,
        )
        comfort = calculate_comfort_score(optimized, current_weather, resources, target_temp_c=28.0)
        self.assertGreaterEqual(comfort.score, 0.0)
        self.assertLessEqual(comfort.score, 100.0)
        self.assertIn(comfort.band, {"Excellent", "Good", "Moderate", "Poor"})


if __name__ == "__main__":
    unittest.main()
