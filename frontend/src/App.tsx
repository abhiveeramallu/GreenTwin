import { startTransition, useEffect, useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchConfiguration, fetchDashboard } from "./api";
import type { Configuration, Dashboard, DashboardQuery } from "./types";

type DraftForm = {
  location: string;
  provider: string;
  greenhouseType: string;
  targetTemp: string;
};

const architectureSteps = [
  { label: "Weather API", icon: "🌦️" },
  { label: "Forecast Engine", icon: "📡" },
  { label: "Digital Twin", icon: "🔬" },
  { label: "Thermal Simulation", icon: "🌡️" },
  { label: "Future Temperature", icon: "📈" },
  { label: "Optimization Engine", icon: "⚡" },
  { label: "Fan + Spray", icon: "💧" },
  { label: "Crop Comfort Score", icon: "🌿" },
];

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(digits);
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function bandTone(band: string): string {
  if (band === "Excellent") return "text-success";
  if (band === "Good") return "text-frost";
  if (band === "Moderate") return "text-caution";
  return "text-rose-700";
}

function bandBg(band: string): string {
  if (band === "Excellent") return "bg-success/10 border-success/25 text-success";
  if (band === "Good") return "bg-frost/8 border-frost/20 text-frost";
  if (band === "Moderate") return "bg-caution/10 border-caution/25 text-caution";
  return "bg-rose-50 border-rose-200 text-rose-700";
}

function formatControlMode(mode: string | null | undefined): string {
  if (!mode) return "--";
  return mode
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function App() {
  const [config, setConfig] = useState<Configuration | null>(null);
  const [draft, setDraft] = useState<DraftForm>({
    location: "Coimbatore, India",
    provider: "weatherapi",
    greenhouseType: "medium",
    targetTemp: "28",
  });
  const [filters, setFilters] = useState<DashboardQuery | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      try {
        const nextConfig = await fetchConfiguration();
        if (cancelled) return;

        const defaultDraft = {
          location: nextConfig.default_location,
          provider: nextConfig.default_provider,
          greenhouseType: nextConfig.default_greenhouse_type,
          targetTemp: String(nextConfig.default_target_temp_c),
        };
        const defaultFilters: DashboardQuery = {
          location: nextConfig.default_location,
          provider: nextConfig.default_provider,
          greenhouseType: nextConfig.default_greenhouse_type,
          targetTemp: nextConfig.default_target_temp_c,
        };

        startTransition(() => {
          setConfig(nextConfig);
          setDraft(defaultDraft);
          setFilters(defaultFilters);
        });
      } catch (nextError) {
        if (cancelled) return;
        setError(nextError instanceof Error ? nextError.message : "Unable to load application configuration.");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const activeFilters = filters;
    if (!activeFilters) return;

    let cancelled = false;

    async function loadCurrentDashboard(refresh = false) {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      try {
        const nextDashboard = await fetchDashboard(activeFilters, refresh);
        if (cancelled) return;
        startTransition(() => {
          setDashboard(nextDashboard);
          setError(null);
        });
      } catch (nextError) {
        if (cancelled) return;
        setError(nextError instanceof Error ? nextError.message : "Unable to fetch the digital twin state.");
      } finally {
        if (!cancelled) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }

    void loadCurrentDashboard(false);
    const intervalId = window.setInterval(() => {
      void loadCurrentDashboard(true);
    }, 60_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [filters]);

  const chartData =
    dashboard?.optimized_series.map((point, index) => ({
      label: `${point.horizon_minutes}m`,
      timestamp: formatTimestamp(point.timestamp),
      outside: point.outside_temp_c,
      uncontrolled: dashboard.uncontrolled_series[index]?.inside_temp_c ?? point.inside_temp_c,
      controlled: point.inside_temp_c,
      fanPct: point.fan_pct,
      sprayPct: point.spray_pct,
      controlMode: point.control_mode,
      target: dashboard.target_temp_c,
      humidity: dashboard.forecast_points[index]?.humidity_pct ?? dashboard.weather.humidity_pct,
    })) ?? [];

  const comfortData = dashboard
    ? [
        { label: "Temperature", value: dashboard.comfort.temperature_component },
        { label: "Humidity", value: dashboard.comfort.humidity_component },
        { label: "Efficiency", value: dashboard.comfort.efficiency_component },
      ]
    : [];

  function applyFilters() {
    const parsedTargetTemp = Number(draft.targetTemp);
    setFilters({
      location: draft.location.trim() || "Coimbatore, India",
      provider: draft.provider,
      greenhouseType: draft.greenhouseType,
      targetTemp: Number.isFinite(parsedTargetTemp) ? parsedTargetTemp : 28,
    });
  }

  async function refreshNow() {
    const activeFilters = filters;
    if (!activeFilters) return;
    setRefreshing(true);
    try {
      const nextDashboard = await fetchDashboard(activeFilters, true);
      startTransition(() => {
        setDashboard(nextDashboard);
        setError(null);
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to refresh the dashboard.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden px-5 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">

        {/* ── Header ── */}
        <header className="glass-panel animate-float-in rounded-[28px] overflow-hidden">
          {/* Top accent stripe */}
          <div className="h-[3px] w-full bg-gradient-to-r from-lilac via-iris to-success opacity-80" />

          <div className="p-6 lg:p-8">
            <div className="grid gap-8 lg:grid-cols-[1.7fr_1fr]">
              {/* Left: branding + pipeline */}
              <div className="space-y-6">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-bone px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.32em] text-mist">
                    <span className="text-base leading-none">🌱</span>
                    GreenTwin AI
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-lilac/30 bg-lilac/8 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-iris">
                    <span className="live-dot" />
                    {dashboard?.mode === "live" ? "Live Forecast" : "Demo Forecast"}
                  </span>
                  {refreshing && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-caution/10 border border-caution/25 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-caution">
                      <svg className="h-3 w-3 animate-spin-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                      </svg>
                      Syncing
                    </span>
                  )}
                </div>

                <div className="max-w-4xl">
                  <h1 className="font-display text-[2.4rem] leading-[1.08] text-frost sm:text-[3rem] lg:text-[3.4rem]">
                    {config?.project_title ?? "Real-Time Digital Twin for Greenhouse Climate"}
                  </h1>
                  <p className="mt-3 max-w-2xl text-[14.5px] leading-[1.75] text-mist">
                    Industrial greenhouse monitoring that blends live weather intake, a physics-driven thermal simulation,
                    and adaptive fan-plus-spray optimization to hold the crop zone near 28°C.
                  </p>
                </div>

                {/* Pipeline steps */}
                <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
                  {architectureSteps.map((step, index) => (
                    <div
                      key={step.label}
                      className="group rounded-2xl border border-line bg-white/80 px-4 py-3 transition-all duration-200 hover:border-lilac/30 hover:bg-white hover:shadow-[0_4px_20px_rgba(40,27,105,0.07)]"
                      style={{ animationDelay: `${index * 60}ms` }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base leading-none">{step.icon}</span>
                        <div>
                          <div className="text-[9.5px] font-semibold uppercase tracking-[0.28em] text-mist/70">
                            Stage {index + 1}
                          </div>
                          <div className="mt-0.5 text-[13px] font-medium text-frost">{step.label}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: simulation controls */}
              <div className="rounded-[22px] border border-line/80 bg-bone/60 p-5 shadow-[0_12px_40px_rgba(40,27,105,0.05)]">
                <div className="mb-5 border-b border-line/60 pb-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-mist">Simulation Controls</p>
                  <p className="mt-1 text-[13px] leading-[1.6] text-mist">
                    Switch providers, greenhouse scale, and target assumptions.
                  </p>
                </div>
                <div className="grid gap-3.5">
                  <label className="text-sm">
                    <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.2em] text-mist">Location</span>
                    <input
                      className="form-input"
                      placeholder="e.g. Coimbatore, India"
                      value={draft.location}
                      onChange={(event) => setDraft((previous) => ({ ...previous, location: event.target.value }))}
                    />
                  </label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.2em] text-mist">Weather API</span>
                      <select
                        className="form-input"
                        value={draft.provider}
                        onChange={(event) => setDraft((previous) => ({ ...previous, provider: event.target.value }))}
                      >
                        {config?.supported_weather_providers.map((provider) => (
                          <option key={provider} value={provider}>
                            {provider === "weatherapi" ? "WeatherAPI.com" : "OpenWeatherMap"}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.2em] text-mist">Greenhouse Type</span>
                      <select
                        className="form-input"
                        value={draft.greenhouseType}
                        onChange={(event) => setDraft((previous) => ({ ...previous, greenhouseType: event.target.value }))}
                      >
                        {config?.greenhouse_profiles.map((profile) => (
                          <option key={profile.type} value={profile.type}>
                            {profile.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="text-sm">
                    <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.2em] text-mist">Target Temp (°C)</span>
                    <input
                      type="number"
                      className="form-input"
                      value={draft.targetTemp}
                      onChange={(event) => setDraft((previous) => ({ ...previous, targetTemp: event.target.value }))}
                    />
                  </label>
                  <div className="grid gap-2.5 pt-1 sm:grid-cols-2">
                    <button type="button" onClick={applyFilters} className="btn-primary">
                      Apply Simulation
                    </button>
                    <button type="button" onClick={() => void refreshNow()} className="btn-secondary">
                      {refreshing ? "Refreshing…" : "Refresh Weather"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* ── Error banner ── */}
        {error ? (
          <div className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
            <svg className="mt-0.5 h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span>{error}</span>
          </div>
        ) : null}

        {/* ── Alert banners ── */}
        {dashboard?.alerts.length ? (
          <section className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {dashboard.alerts.map((alert) => (
              <div
                key={alert}
                className="flex items-center gap-2.5 rounded-2xl border border-caution/25 bg-caution/7 px-4 py-3 text-[13px] text-caution"
              >
                <svg className="h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {alert}
              </div>
            ))}
          </section>
        ) : null}

        {/* ── Metric cards ── */}
        <section className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-6">
          <MetricCard
            label="Current Inside"
            value={`${formatNumber(dashboard?.current_inside_temp_c)}°C`}
            detail="Estimated greenhouse air state"
            icon="🏠"
            delay="stagger-1"
          />
          <MetricCard
            label="Outside Air"
            value={`${formatNumber(dashboard?.weather.temp_c)}°C`}
            detail={`${formatNumber(dashboard?.weather.cloud_cover_pct)}% cloud cover`}
            icon="☁️"
            delay="stagger-2"
          />
          <MetricCard
            label="Target Zone"
            value={`${formatNumber(dashboard?.target_temp_c)}°C`}
            detail={`${dashboard?.greenhouse_profile.label ?? "--"} greenhouse`}
            icon="🎯"
            delay="stagger-3"
          />
          <MetricCard
            label="Fan Command"
            value={`${formatNumber(dashboard?.optimization.recommended_fan_pct, 0)}%`}
            detail={`Peak 4 hrs: ${formatNumber(dashboard?.optimization.peak_fan_pct, 0)}%`}
            icon="💨"
            delay="stagger-4"
          />
          <MetricCard
            label="Spray Command"
            value={`${formatNumber(dashboard?.optimization.recommended_spray_pct, 0)}%`}
            detail={`Peak 4 hrs: ${formatNumber(dashboard?.optimization.peak_spray_pct, 0)}%`}
            icon="💧"
            delay="stagger-5"
          />
          <MetricCard
            label="Comfort Score"
            value={`${formatNumber(dashboard?.comfort.score, 0)}`}
            detail={dashboard ? dashboard.comfort.band : "Waiting for simulation"}
            accentClass={dashboard ? bandTone(dashboard.comfort.band) : "text-frost"}
            bandClass={dashboard ? bandBg(dashboard.comfort.band) : ""}
            icon="🌿"
            delay="stagger-6"
          />
        </section>

        {/* ── Charts row 1 ── */}
        <section className="grid gap-4 xl:grid-cols-[1.5fr_0.95fr]">
          <Panel
            title="Future Temperature Projection"
            kicker="Digital Twin"
            subtitle="Outside weather plus predicted inside greenhouse temperature — without cooling versus with fan-and-spray control over the next four hours."
          >
            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ left: -10, right: 8, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(26, 28, 40, 0.06)" vertical={false} />
                  <XAxis
                    dataKey="label"
                    stroke="rgba(109,114,131,0)"
                    tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="rgba(109,114,131,0)"
                    tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 16,
                      border: "1px solid rgba(123,116,160,0.16)",
                      background: "rgba(255,255,255,0.99)",
                      boxShadow: "0 24px 60px rgba(40,27,105,0.14)",
                      fontFamily: "Inter",
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontFamily: "Inter", fontSize: 12, paddingTop: 12 }}
                  />
                  <ReferenceLine y={dashboard?.target_temp_c ?? 28} stroke="#7d64ff" strokeDasharray="5 4" strokeWidth={1.5} />
                  <Line type="monotone" dataKey="outside" stroke="#a0a6b8" strokeWidth={2} dot={false} name="Outside Air" />
                  <Line type="monotone" dataKey="uncontrolled" stroke="#9b8cff" strokeWidth={2} dot={false} name="Inside (No Cooling)" strokeDasharray="4 2" />
                  <Line type="monotone" dataKey="controlled" stroke="#17181f" strokeWidth={2.5} dot={false} name="Inside (Controlled)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel
            title="Current Weather Intake"
            kicker="Forecast Engine"
            subtitle="Live atmospheric conditions feeding the thermal model."
          >
            <div className="grid gap-2.5 sm:grid-cols-2">
              <InfoTile label="Humidity" value={`${formatNumber(dashboard?.weather.humidity_pct, 0)}%`} />
              <InfoTile label="Wind Speed" value={`${formatNumber(dashboard?.weather.wind_speed_kph, 1)} kph`} />
              <InfoTile label="Pressure" value={`${formatNumber(dashboard?.weather.pressure_hpa, 0)} hPa`} />
              <InfoTile label="UV Index" value={formatNumber(dashboard?.weather.uv_index, 1)} />
              <InfoTile label="Cloud Cover" value={`${formatNumber(dashboard?.weather.cloud_cover_pct, 0)}%`} />
              <InfoTile label="Air Quality" value={formatNumber(dashboard?.weather.air_quality_index, 0)} />
            </div>
            <div className="mt-4 rounded-2xl border border-line bg-gradient-to-br from-white to-lilac/5 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-mist">Provider</p>
                  <p className="mt-1 text-lg font-semibold text-frost">{dashboard?.weather.provider ?? "--"}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-mist">Observation</p>
                  <p className="mt-1 text-[13px] text-frost">
                    {dashboard ? formatTimestamp(dashboard.weather.observation_time) : "--"}
                  </p>
                </div>
              </div>
              <div className="mt-3 space-y-1.5 border-t border-line/50 pt-3">
                <p className="text-[13px] leading-[1.6] text-mist">
                  Location:{" "}
                  <span className="font-medium text-frost">{dashboard?.weather.location_name ?? "--"}</span>
                </p>
                <p className="text-[13px] leading-[1.6] text-mist">
                  Profile:{" "}
                  <span className="font-medium text-frost">{dashboard?.greenhouse_profile.description ?? "--"}</span>
                </p>
              </div>
            </div>
          </Panel>
        </section>

        {/* ── Charts row 2 ── */}
        <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <Panel
            title="Comfort Breakdown"
            kicker="Crop Health"
            subtitle="Weighted score from target tracking, humidity fitness, and resource efficiency."
          >
            <div className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
              {/* Score card */}
              <div className="flex flex-col justify-between rounded-[22px] border border-line bg-gradient-to-br from-white via-bone to-lilac/8 p-5">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-mist">Crop Comfort Score</p>
                  <p className={`mt-3 text-[4rem] font-semibold leading-none tracking-tight ${dashboard ? bandTone(dashboard.comfort.band) : "text-frost"}`}>
                    {formatNumber(dashboard?.comfort.score, 0)}
                  </p>
                  <div className={`mt-2.5 inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${dashboard ? bandBg(dashboard.comfort.band) : "border-line text-mist bg-transparent"}`}>
                    {dashboard?.comfort.band ?? "--"}
                  </div>
                </div>
                <p className="mt-4 text-[13px] leading-[1.7] text-mist">
                  {dashboard?.optimization.rationale ?? "Running optimization…"}
                </p>
              </div>

              {/* Bar chart */}
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comfortData} margin={{ left: -16, right: 0, top: 8, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(26, 28, 40, 0.06)" vertical={false} />
                    <XAxis
                      dataKey="label"
                      stroke="rgba(109,114,131,0)"
                      tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="rgba(109,114,131,0)"
                      tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                      axisLine={false}
                      tickLine={false}
                      domain={[0, 100]}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 16,
                        border: "1px solid rgba(123,116,160,0.16)",
                        background: "rgba(255,255,255,0.99)",
                        boxShadow: "0 24px 60px rgba(40,27,105,0.14)",
                        fontFamily: "Inter",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="value" radius={[10, 10, 0, 0]}>
                      {comfortData.map((entry) => (
                        <Cell
                          key={entry.label}
                          fill={
                            entry.label === "Temperature" ? "#17181f" : entry.label === "Humidity" ? "#7d64ff" : "#338065"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Panel>

          <Panel
            title="Resource Consumption"
            kicker="Optimization"
            subtitle="Cooling pulses are only applied when the next step would drift above the target, limiting electricity and water over four hours."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <MetricRibbon label="Projected Energy" value={`${formatNumber(dashboard?.resource_summary.projected_energy_kwh, 2)} kWh`} />
              <MetricRibbon label="Projected Water" value={`${formatNumber(dashboard?.resource_summary.projected_water_liters, 2)} L`} />
              <MetricRibbon label="Electricity Index" value={formatNumber(dashboard?.resource_summary.electricity_cost_index, 2)} />
              <MetricRibbon label="Water Index" value={formatNumber(dashboard?.resource_summary.water_cost_index, 2)} />
            </div>
            <div className="mt-4 h-[210px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ left: -16, right: 0, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="humidityGlow" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#9b8cff" stopOpacity={0.55} />
                      <stop offset="95%" stopColor="#9b8cff" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(26, 28, 40, 0.06)" vertical={false} />
                  <XAxis
                    dataKey="label"
                    stroke="rgba(109,114,131,0)"
                    tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="rgba(109,114,131,0)"
                    tick={{ fill: "#6d7283", fontSize: 11, fontFamily: "Inter" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 16,
                      border: "1px solid rgba(123,116,160,0.16)",
                      background: "rgba(255,255,255,0.99)",
                      boxShadow: "0 24px 60px rgba(40,27,105,0.14)",
                      fontFamily: "Inter",
                      fontSize: 12,
                    }}
                  />
                  <Area type="monotone" dataKey="humidity" stroke="#7d64ff" fill="url(#humidityGlow)" strokeWidth={2} name="Humidity %" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </section>

        {/* ── Tables row ── */}
        <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <Panel
            title="4-Hour Control Schedule"
            kicker="Future Greenhouse Temperature"
            subtitle="Every 10-minute step compares inside greenhouse temperature without cooling against the controlled temperature produced by the fan-and-spray schedule."
          >
            <div className="overflow-x-auto rounded-xl">
              <table className="data-table min-w-[780px]">
                <thead>
                  <tr>
                    <th>Horizon</th>
                    <th>Outside</th>
                    <th>Inside (No Cooling)</th>
                    <th>Inside (Controlled)</th>
                    <th>Fan</th>
                    <th>Spray</th>
                    <th>Mode</th>
                    <th className="text-right">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard?.horizons.map((row) => (
                    <tr key={row.horizon_minutes}>
                      <td className="font-medium">{row.label}</td>
                      <td>{formatNumber(row.outside_temp_c)}°C</td>
                      <td>{formatNumber(row.uncontrolled_temp_c)}°C</td>
                      <td className="font-medium text-frost">{formatNumber(row.controlled_temp_c)}°C</td>
                      <td>
                        <span className="font-mono text-[13px]">{formatNumber(row.recommended_fan_pct, 0)}%</span>
                      </td>
                      <td>
                        <span className="font-mono text-[13px]">{formatNumber(row.recommended_spray_pct, 0)}%</span>
                      </td>
                      <td className="text-mist">{formatControlMode(row.control_mode)}</td>
                      <td className="text-right">
                        <span className={row.target_met ? "badge-met" : "badge-miss"}>
                          {row.target_met ? "✓ Met" : `${formatNumber(row.temperature_error_c)}°C`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel
            title="Thermal Coefficients"
            kicker="Digital Twin Core"
            subtitle="Each greenhouse type adjusts heat transfer, solar gain, and wind cooling differently."
          >
            <div className="space-y-3">
              {config?.greenhouse_profiles.map((profile) => {
                const active = dashboard?.greenhouse_profile.type === profile.type;
                return (
                  <div
                    key={profile.type}
                    className={`rounded-[18px] border p-4 transition-all duration-200 ${
                      active
                        ? "border-lilac/40 bg-gradient-to-br from-lilac/8 to-lilac/4 shadow-[0_0_0_1px_rgba(125,100,255,0.1)]"
                        : "border-line bg-white/80 hover:border-lilac/25 hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[15px] font-semibold text-frost">{profile.label}</p>
                      <span className={`rounded-full px-2.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.2em] ${active ? "bg-lilac/15 text-iris" : "bg-black/[0.04] text-mist"}`}>
                        {profile.type}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[13px] leading-[1.6] text-mist">{profile.description}</p>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <InfoTile label="k" value={formatNumber(profile.k, 2)} compact />
                      <InfoTile label="s" value={formatNumber(profile.s, 2)} compact />
                      <InfoTile label="w" value={formatNumber(profile.w, 2)} compact />
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </section>

        {dashboard?.logs.length ? (
          <Panel
            title="Historical Simulation Logs"
            kicker="System Memory"
            subtitle="Recent runs for reporting and validation. Starting Inside is the estimated greenhouse temperature when the run began, and Final Inside (Controlled) is the end-of-horizon controlled temperature after the cooling schedule settles."
          >
            <div className="overflow-x-auto rounded-xl">
              <table className="data-table min-w-full">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Location</th>
                    <th>Starting Inside</th>
                    <th>Final Inside (Controlled)</th>
                    <th>Fan</th>
                    <th>Spray</th>
                    <th>Comfort</th>
                    <th>Provider</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.logs.map((log) => (
                    <tr key={log.id}>
                      <td className="text-mist">{formatTimestamp(log.created_at)}</td>
                      <td className="font-medium">{log.location_name}</td>
                      <td>{formatNumber(log.inside_temp_c)}°C</td>
                      <td className="font-medium">{formatNumber(log.peak_controlled_temp_c)}°C</td>
                      <td><span className="font-mono text-[13px]">{formatNumber(log.recommended_fan_pct, 0)}%</span></td>
                      <td><span className="font-mono text-[13px]">{formatNumber(log.recommended_spray_pct, 0)}%</span></td>
                      <td>
                        <span className={`font-semibold ${bandTone(log.comfort_band)}`}>
                          {formatNumber(log.comfort_score, 0)}
                        </span>
                        <span className="ml-1.5 text-mist">/ {log.comfort_band}</span>
                      </td>
                      <td className="text-mist">{log.provider}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : null}

        {/* ── Loading state ── */}
        {loading && !dashboard ? (
          <div className="flex items-center gap-3 rounded-2xl border border-line bg-white/80 px-5 py-4 text-[13.5px] text-mist">
            <svg className="h-4 w-4 animate-spin-slow text-lilac" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            Loading digital twin simulation…
          </div>
        ) : null}

        {/* ── Footer ── */}
        <footer className="flex items-center justify-between border-t border-line/50 pt-4 pb-2">
          <p className="text-[12px] text-mist">
            GreenTwin AI — Physics-driven greenhouse climate optimization
          </p>
          <p className="text-[12px] text-mist">
            Updates every 60s · Data from {dashboard?.weather.provider ?? "Weather API"}
          </p>
        </footer>

      </div>
    </div>
  );
}

/* ── Panel ── */
type PanelProps = {
  kicker: string;
  title: string;
  subtitle: string;
  children: ReactNode;
};

function Panel({ kicker, title, subtitle, children }: PanelProps) {
  return (
    <section className="glass-panel rounded-[28px] p-5 lg:p-6">
      <div className="mb-5">
        <span className="kicker-pill">{kicker}</span>
        <h2 className="mt-3 font-display text-[1.5rem] leading-snug text-frost">{title}</h2>
        <p className="mt-1.5 max-w-3xl text-[13px] leading-[1.7] text-mist">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

/* ── MetricCard ── */
type MetricCardProps = {
  label: string;
  value: string;
  detail: string;
  accentClass?: string;
  bandClass?: string;
  icon?: string;
  delay?: string;
};

function MetricCard({ label, value, detail, accentClass = "text-frost", bandClass = "", icon, delay = "" }: MetricCardProps) {
  return (
    <article className={`glass-panel metric-sheen animate-fade-up rounded-[24px] p-5 ${delay}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-mist">{label}</p>
        {icon && <span className="text-base leading-none opacity-60">{icon}</span>}
      </div>
      <p className={`mt-4 text-[2rem] font-semibold leading-none tracking-tight ${accentClass}`}>{value}</p>
      <p className={`mt-3 text-[12.5px] leading-[1.5] ${bandClass ? bandClass + " inline-flex rounded-full px-2.5 py-0.5 border text-xs font-semibold" : "text-mist"}`}>
        {detail}
      </p>
    </article>
  );
}

/* ── InfoTile ── */
type InfoTileProps = {
  label: string;
  value: string;
  compact?: boolean;
};

function InfoTile({ label, value, compact = false }: InfoTileProps) {
  return (
    <div className={`info-tile ${compact ? "p-3" : "p-4"}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-mist">{label}</p>
      <p className={`mt-2 ${compact ? "text-[15px]" : "text-xl"} font-semibold text-frost`}>{value}</p>
    </div>
  );
}

/* ── MetricRibbon ── */
type MetricRibbonProps = {
  label: string;
  value: string;
};

function MetricRibbon({ label, value }: MetricRibbonProps) {
  return (
    <div className="info-tile bg-gradient-to-br from-white to-lilac/7 px-4 py-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-mist">{label}</p>
      <p className="mt-2 text-[1.35rem] font-semibold text-frost">{value}</p>
    </div>
  );
}

export default App;
