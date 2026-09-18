import type {
  ChartRequest, ChartResponse, GeocodeHit, MatchPerson, MatchResponse, PanchangaDay, TimingResponse,
} from "./types";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("sweetastro_api_token") || "";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["X-Auth-Token"] = token;
  return headers;
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function postChart(payload: ChartRequest): Promise<ChartResponse> {
  const res = await fetch("/api/chart", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ChartResponse;
}

export async function searchPlaces(query: string, limit = 5): Promise<GeocodeHit[]> {
  const res = await fetch(
    `/api/geocode?q=${encodeURIComponent(query)}&limit=${limit}`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as GeocodeHit[];
}

export async function getPanchanga(
  dateIso: string, lat: number, lon: number, tzOffset: number,
): Promise<PanchangaDay> {
  const params = new URLSearchParams({
    date: dateIso,
    lat: String(lat),
    lon: String(lon),
    tz_offset: String(tzOffset),
  });
  const res = await fetch(`/api/panchanga?${params.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as PanchangaDay;
}

export async function postMatching(
  personA: MatchPerson,
  personB: MatchPerson,
): Promise<MatchResponse> {
  const res = await fetch("/api/matching", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ person_a: personA, person_b: personB }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as MatchResponse;
}

export async function postCalendar(
  person: { name: string; dob: string; tob: string; place: string; tz_offset: number; lat: number; lon: number },
  horizonMonths = 12,
): Promise<Blob> {
  const res = await fetch("/api/calendar", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ ...person, horizon_months: horizonMonths }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return await res.blob();
}

export async function postTiming(
  person: { name: string; dob: string; tob: string; place: string; tz_offset: number; lat: number; lon: number },
  event: string,
  rangeStart: string,
  rangeEnd: string,
): Promise<TimingResponse> {
  const res = await fetch("/api/timing", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      person,
      event,
      range_start: rangeStart,
      range_end: rangeEnd,
    }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as TimingResponse;
}
