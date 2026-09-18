import { useState } from "react";
import { Link } from "react-router-dom";
import { postTiming } from "../lib/api";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import type { TimingResult } from "../lib/types";

const EVENTS = ["marriage", "career_change", "property", "child", "travel", "business_launch"];

function isoDate(offsetDays = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

const TIER_STYLE: Record<string, string> = {
  High: "chip chip-gold",
  Medium: "chip",
  Low: "chip",
};

export default function Muhurta() {
  const { chart } = useChart();
  const { t } = useI18n();
  const [event, setEvent] = useState("marriage");
  const [from, setFrom] = useState(isoDate(1));
  const [to, setTo] = useState(isoDate(120));
  const [result, setResult] = useState<TimingResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (!chart) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await postTiming(
        {
          name: chart.birth.name,
          dob: chart.birth.dob,
          tob: chart.birth.tob,
          place: chart.birth.place,
          tz_offset: chart.birth.tz_offset,
          lat: chart.birth.lat,
          lon: chart.birth.lon,
        },
        event,
        from,
        to,
      );
      setResult(response.result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timing computation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!chart) {
    return (
      <div className="card card-gold p-6 text-center space-y-4">
        <h1 className="font-display text-xl font-bold text-white">{t("muhurta.title")}</h1>
        <p className="text-xs text-slate-300">{t("muhurta.needChart")}</p>
        <Link to="/" className="inline-block text-xs font-semibold text-slate-950 bg-amber-500 hover:bg-amber-400 px-4 py-2 rounded-lg transition">
          {t("home.openChart")}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="card card-gold p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-bold text-white">{t("muhurta.title")}</h1>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {t("muhurta.sub")} · {chart.birth.place}
            </p>
          </div>
          <span className="chip chip-green">engine-verified windows</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <label className="block text-[11px] text-slate-400">
            {t("muhurta.event")}
            <select
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
            >
              {EVENTS.map((key) => (
                <option key={key} value={key}>
                  {t(`muhurta.event.${key}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-[11px] text-slate-400">
            {t("muhurta.from")}
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
            />
          </label>
          <label className="block text-[11px] text-slate-400">
            {t("muhurta.to")}
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
            />
          </label>
          <div className="flex items-end">
            <button
              onClick={() => void run()}
              disabled={busy}
              className="btn-gold w-full text-sm font-bold px-5 py-2.5 rounded-xl"
            >
              {busy ? t("muhurta.finding") : t("muhurta.find")}
            </button>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/60 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
      </section>

      {result && (
        <section className="space-y-4">
          <div className="card p-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-100">
                {t("muhurta.promise")}: <span className="text-amber-300">{result.promise.level}</span>
              </h2>
              <span className="chip">{result.event_label}</span>
            </div>
            <p className="text-[11px] text-slate-400">{result.promise.statement}</p>
          </div>

          {result.gated && (
            <div className="card border-rose-800/60 p-4 text-xs text-rose-200">
              {t("muhurta.gated")}
            </div>
          )}

          {!result.gated && result.windows.length === 0 && (
            <div className="card p-4 text-xs text-slate-300">{t("muhurta.noWindows")}</div>
          )}

          {result.windows.length > 0 && (
            <>
              <h2 className="text-sm font-semibold text-slate-100">
                {t("muhurta.windows")} ({result.windows.length})
              </h2>
              <div className="space-y-3">
                {result.windows.map((window) => (
                  <div key={`${window.start_date}-${window.pratyantardasha}`} className="card p-4 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-slate-100">
                        {window.start_date} → {window.end_date}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={TIER_STYLE[window.tier] || "chip"}>{window.tier}</span>
                        <span className="chip">
                          {t("muhurta.score")} {window.score}
                        </span>
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {window.mahadasha} MD / {window.antardasha} AD / {window.pratyantardasha} PD
                    </div>
                    <div className="text-[11px] text-slate-300">
                      {t("muhurta.transit")}: {window.transit_note}
                    </div>
                    <details className="text-[11px] text-slate-400">
                      <summary className="cursor-pointer hover:text-slate-200 select-none">
                        +{window.supported_by.length} / −{window.limited_by.length}
                      </summary>
                      <ul className="mt-1.5 space-y-1">
                        {window.supported_by.map((item) => (
                          <li key={item} className="text-emerald-300/90">+ {item}</li>
                        ))}
                        {window.limited_by.map((item) => (
                          <li key={item} className="text-rose-300/80">− {item}</li>
                        ))}
                      </ul>
                    </details>
                  </div>
                ))}
              </div>
            </>
          )}

          {result.method_notes.length > 0 && (
            <details className="card p-4 text-[11px] text-slate-400">
              <summary className="cursor-pointer hover:text-slate-200 select-none">Method notes</summary>
              <ul className="mt-2 space-y-1">
                {result.method_notes.map((note) => (
                  <li key={note}>- {note}</li>
                ))}
              </ul>
            </details>
          )}

          <p className="text-[10px] text-slate-500">{t("muhurta.note")}</p>
        </section>
      )}
    </div>
  );
}
