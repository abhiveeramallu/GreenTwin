export type WeatherSnapshot = {
  provider: string;
  location_name: string;
  observation_time: string;
  temp_c: number;
  humidity_pct: number;
  wind_speed_kph: number;
  pressure_hpa: number | null;
  cloud_cover_pct: number;
  uv_index: number | null;
  air_quality_index: number | null;
};

export type ForecastPoint = {
  timestamp: string;
  outside_temp_c: number;
  humidity_pct: number;
  wind_speed_kph: number;
  cloud_cover_pct: number;
  uv_index: number | null;
  source: string;
};

export type GreenhouseProfile = {
  type: string;
  label: string;
  k: number;
  s: number;
  w: number;
  description: string;
};

export type PredictionPoint = {
  timestamp: string;
  horizon_minutes: number;
  outside_temp_c: number;
  inside_temp_c: number;
  fan_pct: number;
  spray_pct: number;
  control_mode: string;
  heat_gain_c: number;
  solar_gain_c: number;
  wind_cooling_c: number;
  fan_cooling_c: number;
  spray_cooling_c: number;
};

export type HorizonProjection = {
  horizon_minutes: number;
  label: string;
  outside_temp_c: number;
  uncontrolled_temp_c: number;
  controlled_temp_c: number;
  recommended_fan_pct: number;
  recommended_spray_pct: number;
  control_mode: string;
  target_met: boolean;
  temperature_error_c: number;
};

export type OptimizationStrategy = {
  target_temp_c: number;
  recommended_fan_pct: number;
  recommended_spray_pct: number;
  peak_fan_pct: number;
  peak_spray_pct: number;
  maintenance_band_c: number;
  horizon_minutes: number;
  projected_energy_kwh: number;
  projected_water_liters: number;
  electricity_cost_index: number;
  water_cost_index: number;
  total_cost_score: number;
  rationale: string;
};

export type ComfortScoreBreakdown = {
  score: number;
  band: "Excellent" | "Good" | "Moderate" | "Poor";
  temperature_component: number;
  humidity_component: number;
  efficiency_component: number;
};

export type ResourceSummary = {
  projected_energy_kwh: number;
  projected_water_liters: number;
  electricity_cost_index: number;
  water_cost_index: number;
  fan_runtime_minutes: number;
  spray_runtime_minutes: number;
};

export type SimulationLogRecord = {
  id: number;
  created_at: string;
  provider: string;
  location_name: string;
  greenhouse_type: string;
  inside_temp_c: number;
  outside_temp_c: number;
  comfort_score: number;
  comfort_band: string;
  recommended_fan_pct: number;
  recommended_spray_pct: number;
  projected_energy_kwh: number;
  projected_water_liters: number;
  peak_controlled_temp_c: number;
};

export type Dashboard = {
  project_title: string;
  generated_at: string;
  mode: "live" | "demo";
  weather: WeatherSnapshot;
  greenhouse_profile: GreenhouseProfile;
  current_inside_temp_c: number;
  target_temp_c: number;
  forecast_points: ForecastPoint[];
  uncontrolled_series: PredictionPoint[];
  optimized_series: PredictionPoint[];
  horizons: HorizonProjection[];
  optimization: OptimizationStrategy;
  comfort: ComfortScoreBreakdown;
  resource_summary: ResourceSummary;
  logs: SimulationLogRecord[];
  alerts: string[];
};

export type Configuration = {
  project_title: string;
  default_location: string;
  default_provider: string;
  default_greenhouse_type: string;
  default_target_temp_c: number;
  supported_weather_providers: string[];
  greenhouse_profiles: GreenhouseProfile[];
};

export type DashboardQuery = {
  location: string;
  provider: string;
  greenhouseType: string;
  targetTemp: number;
};
