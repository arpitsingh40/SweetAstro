import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { getPanchanga } from "../lib/api";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import { DashaCard, UpcomingCard } from "../components/Cards";
import type { PanchangaDay } from "../lib/types";

function isoToday(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function clock(iso: string): string {
  return iso && iso.length >= 16 ? iso.slice(11, 16) : "—";
}

export default function Today() {
  const { chart } = useChart();
  const { t } = useI18n();
  const [day, setDay] = useState<PanchangaDay | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!chart) return;
    let cancelled = false;
    getPanchanga(isoToday(), chart.birth.lat, chart.birth.lon, chart.birth.tz_offset)
      .then((result) => {
        if (!cancelled) setDay(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Panchanga unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, [chart]);

  const [digest, setDigest] = useState<string[]>([]);

  useEffect(() => {
    if (!chart) return;
    const key = `sweetastro_visit_${chart.birth.dob || "unknown"}`;
    let previous: { md?: string; ad?: string } | null = null;
    try {
      previous = JSON.parse(localStorage.getItem(key) || "null");
    } catch {
      previous = null;
    }
    const notes: string[] = [];
    if (previous && (previous.md !== chart.dasha.mahadasha || previous.ad !== chart.dasha.antardasha)) {
      notes.push(`${chart.dasha.mahadasha} MD / ${chart.dasha.antardasha} AD`);
    }
    const nowMs = Date.now();
    const soon = (chart.upcoming || []).find((period) => {
      const days = (new Date(period.start).getTime() - nowMs) / 86400000;
      return days >= 0 && days <= 60;
    });
    if (soon) {
      notes.push(`${soon.level} ${soon.lord} · ${soon.start.slice(0, 10)}`);
    } else {
      notes.push(t("today.noBoundary"));
    }
    setDigest(notes.slice(0, 3));
    localStorage.setItem(key, JSON.stringify({
      md: chart.dasha.mahadasha,
      ad: chart.dasha.antardasha,
    }));
  }, [chart, t]);

  if (!chart) return <Navigate to="/" replace />;

  const rows: Array<[string, string]> = day
    ? [
        [t("today.vara"), day.vara],
        [t("today.tithi"), day.tithi],
        [t("today.nakshatra"), `${day.nakshatra} P${day.nakshatra_pada}`],
        [t("today.yoga"), day.yoga],
        [t("today.karana"), day.karana],
        [t("today.moonSun"), `${day.moon_sign} / ${day.sun_sign}`],
        [t("today.sun"), `${clock(day.sunrise)} / ${clock(day.sunset)}`],
      ]
    : [];

  return (
    <div className="space-y-6">
      <section className="card card-gold p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-bold text-white">
              {t("today.title")} · {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
            </h1>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {chart.birth.place} · {t("today.localNote")} (UTC {chart.birth.tz_offset >= 0 ? "+" : ""}
              {chart.birth.tz_offset}h)
            </p>
          </div>
          <span className="chip chip-green">deterministic drik ganita</span>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100">{t("today.panchanga")}</h2>
            {day && <span className="chip">{day.date}</span>}
          </div>
          {error && (
            <p role="alert" className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/60 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          {!day && !error && <p className="text-xs text-slate-400">{t("today.computing")}</p>}
          {day && (
            <dl className="text-[11px] space-y-1.5">
              {rows.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="text-slate-200 text-right">{value}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="text-[10px] text-slate-500">{t("today.panchangaNote")}</p>
        </div>

        <div className="space-y-4">
          <DashaCard dasha={chart.dasha} />
          <UpcomingCard periods={chart.upcoming || []} />
        </div>
      </section>

      {digest.length > 0 && (
        <section className="card p-4 space-y-1.5">
          <h2 className="text-sm font-semibold text-slate-100">{t("today.digest")}</h2>
          {digest.map((note) => (
            <p key={note} className="text-[11px] text-slate-300">{note}</p>
          ))}
        </section>
      )}

      <section className="flex flex-wrap gap-2">
        <Link
          to="/chart"
          className="text-xs font-semibold text-slate-950 bg-amber-500 hover:bg-amber-400 px-3.5 py-2 rounded-lg transition"
        >
          {t("today.openChart")}
        </Link>
        <Link
          to="/chat"
          className="text-xs font-medium text-slate-300 border border-slate-700 hover:border-amber-500/50 px-3.5 py-2 rounded-lg transition"
        >
          {t("today.ask")}
        </Link>
      </section>
    </div>
  );
}
