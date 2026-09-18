export interface PlanetRow {
  name: string;
  sign: string;
  sign_index: number;
  house: number;
  degree: number;
  retrograde: boolean;
  combust: boolean;
  dignity: string;
  nakshatra: string;
  nakshatra_pada: number;
  nakshatra_lord: string;
}

export interface HouseRow {
  house: number;
  sign: string;
  sign_index: number;
  lord: string;
  occupants: string[];
}

export interface DashaState {
  mahadasha: string;
  antardasha: string;
  pratyantardasha: string;
  md_start: string;
  md_end: string;
  ad_start: string;
  ad_end: string;
  pd_start: string;
  pd_end: string;
}

export interface PanchangaRow {
  vara: string;
  tithi: string;
  paksha: string;
  nakshatra: string;
  nakshatra_pada: number;
  yoga: string;
  karana: string;
}

export interface UpcomingPeriod {
  lord: string;
  level: string;
  start: string;
  end: string;
}

export interface TimelinePeriod extends UpcomingPeriod {
  current: boolean;
}

export interface PanchangaDay {
  date: string;
  vara: string;
  tithi: string;
  nakshatra: string;
  nakshatra_pada: number;
  yoga: string;
  karana: string;
  moon_sign: string;
  sun_sign: string;
  sunrise: string;
  sunset: string;
}

export interface ChartResponse {
  birth: {
    name: string;
    dob: string;
    tob: string;
    place: string;
    tz_offset: number;
    lat: number;
    lon: number;
    geo_note: string;
  };
  chart: {
    ascendant_sign: string;
    ascendant_sign_index: number;
    ascendant_degree: number;
    ayanamsha: number;
    planets: PlanetRow[];
    houses: HouseRow[];
  };
  dasha: DashaState;
  panchanga: PanchangaRow | null;
  upcoming: UpcomingPeriod[];
  timeline: TimelinePeriod[];
  current_ads: TimelinePeriod[];
  birth_time_reliable: boolean;
  calculation: string;
}

export interface ChartRequest {
  name: string;
  dob: string;
  tob: string;
  place: string;
  tz_offset: number;
  lat: number;
  lon: number;
  geocode_provider?: string;
  time_reliable?: boolean;
}

export interface GeocodeHit {
  display_name: string;
  lat: number;
  lon: number;
  source: string;
}

export interface TimingWindow {
  mahadasha: string;
  antardasha: string;
  pratyantardasha: string;
  start_date: string;
  end_date: string;
  score: number;
  tier: string;
  supported_by: string[];
  limited_by: string[];
  transit_note: string;
}

export interface TimingResult {
  event: string;
  event_label: string;
  gated: boolean;
  promise: { level: string; statement: string; score: number };
  windows: TimingWindow[];
  method_notes: string[];
  disclaimer: string;
}

export interface TimingResponse {
  result: TimingResult;
  markdown: string;
  location: { lat: number; lon: number; note: string };
}

export interface MatchLocation {
  place: string;
  lat: number;
  lon: number;
  note: string;
}

export interface MatchPerson {
  name: string;
  dob: string;
  tob: string;
  place: string;
  tz_offset: number;
  lat: number;
  lon: number;
  geocode_provider?: string;
}

export interface MatchKuta {
  kuta: string;
  points: number;
  max_points: number;
  detail: string;
}

export interface MangalReading {
  active: boolean;
  houses: Record<string, number>;
  cancellations: string[];
  note: string;
}

export interface MatchResult {
  total: number;
  max_total: number;
  verdict: string;
  kutas: MatchKuta[];
  mangal_a: MangalReading;
  mangal_b: MangalReading;
  notes: string[];
}

export interface MatchResponse {
  result: MatchResult;
  markdown: string;
  locations: { a: MatchLocation; b: MatchLocation };
}
