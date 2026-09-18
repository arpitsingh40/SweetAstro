import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { postChart, searchPlaces } from "../lib/api";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import type { GeocodeHit } from "../lib/types";

export default function Home() {
  const { chart, setChart } = useChart();
  const { t } = useI18n();
  const navigate = useNavigate();

  const [name, setName] = useState(chart?.birth.name || "");
  const [dob, setDob] = useState(chart?.birth.dob || "");
  const [tob, setTob] = useState((chart?.birth.tob || "").slice(0, 5));
  const [unknownTime, setUnknownTime] = useState(false);
  const [place, setPlace] = useState(chart?.birth.place || "");
  const [lat, setLat] = useState<number | null>(chart?.birth.lat ?? null);
  const [lon, setLon] = useState<number | null>(chart?.birth.lon ?? null);
  const [tz, setTz] = useState(chart?.birth.tz_offset ?? 5.5);
  const [hits, setHits] = useState<GeocodeHit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const searchTimer = useRef<number | null>(null);

  useEffect(() => {
    if (place.trim().length < 3 || (lat != null && lon != null)) {
      setHits([]);
      return;
    }
    if (searchTimer.current) window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(async () => {
      try {
        setHits(await searchPlaces(place.trim()));
      } catch {
        setHits([]);
      }
    }, 450);
    return () => {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
    };
  }, [place, lat, lon]);

  function pickHit(hit: GeocodeHit) {
    setLat(hit.lat);
    setLon(hit.lon);
    setPlace(hit.display_name);
    setHits([]);
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!dob) {
      setError(t("home.error.dob"));
      return;
    }
    if (!place.trim()) {
      setError(t("home.error.place"));
      return;
    }
    if (!unknownTime && !tob) {
      setError(t("home.error.time"));
      return;
    }
    setBusy(true);
    try {
      const result = await postChart({
        name: name.trim() || "Native",
        dob,
        tob: unknownTime ? "12:00:00" : `${tob}:00`,
        place: place.trim(),
        tz_offset: tz,
        lat: lat ?? 28.6139,
        lon: lon ?? 77.209,
        geocode_provider: "nominatim",
        time_reliable: !unknownTime,
      });
      setChart(result);
      navigate("/chart");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chart computation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="text-center space-y-5 pt-6 sm:pt-12 animate-fade-up">
        <div className="relative w-20 h-20 mx-auto">
          <div className="absolute inset-0 rounded-3xl bg-amber-400/25 blur-2xl" aria-hidden="true" />
          <div className="relative w-20 h-20 rounded-3xl bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-4xl shadow-2xl shadow-amber-500/30 animate-floaty ring-1 ring-amber-200/50">
            🪐
          </div>
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold">
          <span className="text-gradient-gold">
            {chart
              ? `${t("home.title.back")}${chart.birth.name !== "Native" ? `, ${chart.birth.name}` : ""}`
              : t("home.title.new")}
          </span>
        </h1>
        <p className="text-sm text-slate-400 max-w-xl mx-auto leading-relaxed">{t("home.sub")}</p>
        <div className="flex flex-wrap justify-center gap-x-3 gap-y-1.5 text-[11px] text-slate-400">
          <span className="chip chip-green">{t("home.chip.math")}</span>
          <span className="chip chip-gold">{t("home.chip.source")}</span>
          <span className="chip">{t("home.chip.precision")}</span>
        </div>
      </section>

      {chart && (
        <section className="card card-gold p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-100 truncate">
              {chart.birth.name} · {chart.chart.ascendant_sign} lagna · {chart.birth.dob}
            </div>
            <div className="text-[11px] text-slate-400 truncate">
              {chart.dasha.mahadasha} MD / {chart.dasha.antardasha} AD · {chart.birth.place}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate("/chart")}
              className="btn-gold text-xs font-bold px-4 py-2 rounded-lg"
            >
              {t("home.openChart")}
            </button>
            <button
              onClick={() => {
                setChart(null);
                setLat(null);
                setLon(null);
              }}
              className="btn-ghost text-xs font-medium px-4 py-2 rounded-lg"
            >
              {t("common.newPerson")}
            </button>
          </div>
        </section>
      )}

      <section className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">
            {chart ? t("home.form.title2") : t("home.form.title")}
          </h2>
          <span className="chip">≈ 60 s</span>
        </div>

        <form onSubmit={onSubmit} className="space-y-4" aria-label="Birth details form">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block text-[11px] text-slate-400">
              {t("home.form.name")}
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("home.form.namePh")}
                className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
              />
            </label>
            <label className="block text-[11px] text-slate-400">
              {t("home.form.dob")}
              <input
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                required
                className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
              />
            </label>
            <label className={`block text-[11px] ${unknownTime ? "text-slate-600" : "text-slate-400"}`}>
              {t("home.form.tob")}
              <input
                type="time"
                value={tob}
                disabled={unknownTime}
                onChange={(e) => setTob(e.target.value)}
                className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60 disabled:opacity-40"
              />
            </label>
            <label className="block text-[11px] text-slate-400">
              {t("home.form.tz")}
              <input
                type="number"
                step="0.25"
                value={tz}
                onChange={(e) => setTz(parseFloat(e.target.value || "5.5"))}
                className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
              />
            </label>
          </div>

          <label className="flex items-center gap-2 text-[11px] text-slate-400">
            <input
              type="checkbox"
              checked={unknownTime}
              onChange={(e) => setUnknownTime(e.target.checked)}
              className="accent-amber-500"
            />
            {t("home.form.unknown")}
          </label>

          <div className="relative">
            <label className="block text-[11px] text-slate-400">
              {t("home.form.place")}
              <input
                value={place}
                onChange={(e) => {
                  setPlace(e.target.value);
                  setLat(null);
                  setLon(null);
                }}
                placeholder={t("home.form.placePh")}
                required
                className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
              />
            </label>
            {lat != null && lon != null && (
              <p className="text-[10px] text-emerald-300/80 mt-1">
                {t("home.form.resolved")}: {lat.toFixed(4)}, {lon.toFixed(4)}
              </p>
            )}
            {hits.length > 0 && (
              <div className="absolute z-20 mt-1 w-full card border-slate-700 p-1 max-h-56 overflow-y-auto">
                {hits.map((hit) => (
                  <button
                    key={`${hit.lat},${hit.lon},${hit.display_name}`}
                    type="button"
                    onClick={() => pickHit(hit)}
                    className="w-full text-left text-[11px] px-3 py-2 rounded-lg hover:bg-slate-800/80 text-slate-200 transition"
                  >
                    {hit.display_name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {error && (
            <p role="alert" className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/60 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="btn-gold w-full sm:w-auto text-sm font-bold px-6 py-2.5 rounded-xl"
          >
            {busy ? t("home.form.submitting") : t("home.form.submit")}
          </button>
        </form>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px] text-slate-400">
        {(["trust1", "trust2", "trust3"] as const).map((key, index) => (
          <div key={key} className="card card-hover p-4 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-amber-500/12 border border-amber-500/30 text-amber-300 text-[11px] font-bold flex items-center justify-center">
                {index + 1}
              </span>
              <div className="text-slate-100 font-semibold text-xs">{t(`home.${key}.title`)}</div>
            </div>
            <p className="leading-relaxed">{t(`home.${key}.body`)}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
