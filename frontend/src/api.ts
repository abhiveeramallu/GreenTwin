import type { Configuration, Dashboard, DashboardQuery } from "./types";

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "/api/v1";

function buildUrl(path: string): string {
  if (apiBase.startsWith("http://") || apiBase.startsWith("https://")) {
    return `${apiBase}${path}`;
  }
  return `${window.location.origin}${apiBase}${path}`;
}

async function requestJson<T>(url: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Network request failed";
    throw new Error(`Cannot reach backend at ${url}. ${reason}. Start FastAPI and verify VITE_API_BASE_URL if needed.`);
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchConfiguration(): Promise<Configuration> {
  return requestJson<Configuration>(buildUrl("/config"));
}

export function fetchDashboard(query: DashboardQuery, refresh = false): Promise<Dashboard> {
  const url = new URL(buildUrl("/dashboard"));
  url.searchParams.set("location", query.location);
  url.searchParams.set("provider", query.provider);
  url.searchParams.set("greenhouse_type", query.greenhouseType);
  url.searchParams.set("target_temp_c", String(query.targetTemp));
  if (refresh) {
    url.searchParams.set("refresh", "true");
  }
  return requestJson<Dashboard>(url.toString());
}
