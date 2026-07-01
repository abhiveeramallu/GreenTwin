from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.config import settings
from backend.schemas import ForecastPoint, WeatherSnapshot


@dataclass
class WeatherBundle:
    mode: str
    current: WeatherSnapshot
    hourly_forecast: list[ForecastPoint]
    alerts: list[str]


def _read_json(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    with urlopen(f"{base_url}?{query}", timeout=settings.weather_timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _mock_bundle(location: str, provider: str, reason: str) -> WeatherBundle:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    hour_angle = ((now.hour * 60) + now.minute) / 1440 * math.pi * 2
    base_temp = 31.0 + math.sin(hour_angle - 0.6) * 4.5
    humidity = 62.0 - math.cos(hour_angle) * 8.0
    cloud_cover = max(8.0, min(78.0, 28.0 + math.sin(hour_angle + 0.7) * 22.0))
    wind_speed = max(4.0, 12.0 + math.cos(hour_angle - 0.2) * 4.0)
    uv_index = max(0.0, min(10.0, math.sin(hour_angle - math.pi / 2) * 9.0))

    current = WeatherSnapshot(
        provider=provider,
        location_name=location,
        observation_time=now,
        temp_c=round(base_temp, 2),
        humidity_pct=round(humidity, 2),
        wind_speed_kph=round(wind_speed, 2),
        pressure_hpa=1009.0,
        cloud_cover_pct=round(cloud_cover, 2),
        uv_index=round(uv_index, 2),
        air_quality_index=2.0,
    )

    forecast: list[ForecastPoint] = []
    for hour in range(1, 7):
        ts = now + timedelta(hours=hour)
        wave = math.sin(hour_angle + hour * 0.35)
        future_uv = max(0.0, min(10.0, uv_index - hour * 0.7))
        forecast.append(
            ForecastPoint(
                timestamp=ts,
                outside_temp_c=round(base_temp + wave * 1.4 - hour * 0.15, 2),
                humidity_pct=round(max(40.0, min(88.0, humidity + hour * 1.5 - wave * 2.0)), 2),
                wind_speed_kph=round(max(3.0, wind_speed + hour * 0.35), 2),
                cloud_cover_pct=round(max(5.0, min(95.0, cloud_cover + hour * 3.2 - wave * 8.0)), 2),
                uv_index=round(future_uv, 2),
                source="mock",
            )
        )

    return WeatherBundle(
        mode="demo",
        current=current,
        hourly_forecast=forecast,
        alerts=[reason],
    )


def _fetch_weatherapi(location: str) -> WeatherBundle:
    if not settings.weatherapi_key:
        return _mock_bundle(location, "weatherapi", "WeatherAPI key missing. Serving simulated forecast data.")

    try:
        payload = _read_json(
            "https://api.weatherapi.com/v1/forecast.json",
            {
                "key": settings.weatherapi_key,
                "q": location,
                "days": 2,
                "aqi": "yes",
                "alerts": "no",
            },
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return _mock_bundle(location, "weatherapi", f"WeatherAPI request failed ({exc}). Serving simulated data.")

    current_payload = payload.get("current", {})
    location_payload = payload.get("location", {})
    now = datetime.fromtimestamp(int(current_payload.get("last_updated_epoch", 0)), tz=timezone.utc)
    current = WeatherSnapshot(
        provider="weatherapi",
        location_name=str(location_payload.get("name") or location),
        observation_time=now,
        temp_c=float(current_payload.get("temp_c", 0.0)),
        humidity_pct=float(current_payload.get("humidity", 0.0)),
        wind_speed_kph=float(current_payload.get("wind_kph", 0.0)),
        pressure_hpa=float(current_payload.get("pressure_mb", 0.0)),
        cloud_cover_pct=float(current_payload.get("cloud", 0.0)),
        uv_index=float(current_payload.get("uv", 0.0)),
        air_quality_index=float(
            (current_payload.get("air_quality") or {}).get("us-epa-index", 0.0) or 0.0
        ),
    )

    hourly_forecast: list[ForecastPoint] = []
    for day in payload.get("forecast", {}).get("forecastday", []):
        for hour in day.get("hour", []):
            timestamp = datetime.fromtimestamp(int(hour.get("time_epoch", 0)), tz=timezone.utc)
            if timestamp <= now:
                continue
            hourly_forecast.append(
                ForecastPoint(
                    timestamp=timestamp,
                    outside_temp_c=float(hour.get("temp_c", 0.0)),
                    humidity_pct=float(hour.get("humidity", 0.0)),
                    wind_speed_kph=float(hour.get("wind_kph", 0.0)),
                    cloud_cover_pct=float(hour.get("cloud", 0.0)),
                    uv_index=float(hour.get("uv", 0.0)),
                    source="weatherapi",
                )
            )

    return WeatherBundle(mode="live", current=current, hourly_forecast=hourly_forecast[:12], alerts=[])


def _fetch_openweathermap(location: str) -> WeatherBundle:
    if not settings.openweathermap_key:
        return _mock_bundle(location, "openweathermap", "OpenWeatherMap key missing. Serving simulated forecast data.")

    try:
        current_payload = _read_json(
            "https://api.openweathermap.org/data/2.5/weather",
            {
                "appid": settings.openweathermap_key,
                "q": location,
                "units": "metric",
            },
        )
        forecast_payload = _read_json(
            "https://api.openweathermap.org/data/2.5/forecast",
            {
                "appid": settings.openweathermap_key,
                "q": location,
                "units": "metric",
            },
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return _mock_bundle(
            location,
            "openweathermap",
            f"OpenWeatherMap request failed ({exc}). Serving simulated data.",
        )

    now = datetime.fromtimestamp(int(current_payload.get("dt", 0)), tz=timezone.utc)
    current = WeatherSnapshot(
        provider="openweathermap",
        location_name=str(current_payload.get("name") or location),
        observation_time=now,
        temp_c=float((current_payload.get("main") or {}).get("temp", 0.0)),
        humidity_pct=float((current_payload.get("main") or {}).get("humidity", 0.0)),
        wind_speed_kph=round(float((current_payload.get("wind") or {}).get("speed", 0.0)) * 3.6, 2),
        pressure_hpa=float((current_payload.get("main") or {}).get("pressure", 0.0)),
        cloud_cover_pct=float((current_payload.get("clouds") or {}).get("all", 0.0)),
        uv_index=None,
        air_quality_index=None,
    )

    hourly_forecast: list[ForecastPoint] = []
    for item in forecast_payload.get("list", []):
        timestamp = datetime.fromtimestamp(int(item.get("dt", 0)), tz=timezone.utc)
        if timestamp <= now:
            continue
        hourly_forecast.append(
            ForecastPoint(
                timestamp=timestamp,
                outside_temp_c=float((item.get("main") or {}).get("temp", 0.0)),
                humidity_pct=float((item.get("main") or {}).get("humidity", 0.0)),
                wind_speed_kph=round(float((item.get("wind") or {}).get("speed", 0.0)) * 3.6, 2),
                cloud_cover_pct=float((item.get("clouds") or {}).get("all", 0.0)),
                uv_index=None,
                source="openweathermap",
            )
        )

    alerts = [
        "OpenWeatherMap current + 5-day forecast mode does not include UV index in this starter integration."
    ]
    return WeatherBundle(mode="live", current=current, hourly_forecast=hourly_forecast[:12], alerts=alerts)


def fetch_weather_bundle(provider: str, location: str) -> WeatherBundle:
    normalized = provider.strip().lower()
    if normalized == "openweathermap":
        return _fetch_openweathermap(location)
    return _fetch_weatherapi(location)
