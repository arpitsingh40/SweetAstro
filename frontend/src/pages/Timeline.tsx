import { useState } from "react";
import { Navigate } from "react-router-dom";
import { postCalendar } from "../lib/api";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import type { TimelinePeriod } from "../lib/types";

const LORD_COLOR: Record<string, string> = {
  Ketu: "#94a3b8",
  Venus: "#f9a8d4",
  Sun: "#fbbf24",
  Moon: "#e2e8f0",
  Mars: "#f87171",
  Rahu: "#64748b",
  Jupiter: "#fcd34d",
  Saturn: "#93c5fd",
  Mercury: "#5eead4",
};

function ageAt(dobIso: string, iso: string): number {
  const dob = new Date(`${dobIso}T00:00:00`);
  const at = new Date(iso);
  let age = at.getFullYear() - dob.getFullYear();
  const monthDiff = at.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && at.getDate() < dob.getDate())) age -= 1;
  return Math.max(0, age);
}

function PeriodTable({ periods, dob }: { periods: TimelinePeriod[]; dob: string }) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[420px]">
        <thead>
          <tr className="text-slate-500 uppercase tracking-wide text-[10px]">
            <th className="text-left py-2 pr-3">{t("table.level")}</th>
            <th className="text-left py-2 pr-3">{t("table.lord")}</th>
            <th className="text-left py-2 pr-3">{t("table.from")}</th>
            <th className="text-left py-2 pr-3">{t("table.to")}</th>
            <th className="text-left py-2">{t("table.age")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70">
          {periods.map((period) => (
            <tr
              key={`${period.level}-${period.lord}-${period.start}`}
              className={period.current ? "text-amber-200" : "text-slate-200"}
            >
              <td className="py-2 pr-3">
                <span className={`chip ${period.level === "MD" ? "chip-gold" : ""}`}>
                  {period.level}
                </span>
              </td>
              <td className="py-2 pr-3 font-semibold whitespace-nowrap">
                <span
                  className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
                  style={{ background: LORD_COLOR[period.lord] || "#94a3b8" }}
                />
                {period.lord}
                {period.current && <span className="ml-2 chip chip-gold">now</span>}
              </td>
              <td className="py-2 pr-3 whitespace-nowrap">{period.start.slice(0, 10)}</td>
              <td className="py-2 pr-3 whitespace-nowrap">{period.end.slice(0, 10)}</td>
              <td className="py-2 whitespace-nowrap">
                {ageAt(dob, period.start)}–{ageAt(dob, period.end)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Timeline() {
  const { chart } = useChart();
  const { t } = useI18n();
  const [calendarBusy, setCalendarBusy] = useState(false);
  if (!chart) return <Navigate to="/" replace />;

  async function downloadCalendar() {
    if (!chart) return;
    setCalendarBusy(true);
    try {
      const blob = await postCalendar({
        name: chart.birth.name,
        dob: chart.birth.dob,
        tob: chart.birth.tob || "12:00:00",
        place: chart.birth.place,
        tz_offset: chart.birth.tz_offset,
        lat: chart.birth.lat,
        lon: chart.birth.lon,
      }, 12);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "sweetastro-dasha.ics";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } finally {
      setCalendarBusy(false);
    }
  }

  const periods = chart.timeline || [];
  const startMs = periods.length ? new Date(periods[0].start).getTime() : 0;
  const endMs = periods.length ? new Date(periods[periods.length - 1].end).getTime() : 1;
  const spanMs = Math.max(1, endMs - startMs);

  return (
    <div className="space-y-6">
      <section className="card card-gold p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-bold text-white">{t("timeline.title")}</h1>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {t("timeline.sub")} {chart.birth.name} · {chart.birth.dob}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip chip-green">{t("timeline.verified")}</span>
            <button
              onClick={downloadCalendar}
              disabled={calendarBusy}
              className="btn-ghost text-[11px] font-medium px-3 py-1.5 rounded-lg"
            >
              {calendarBusy ? t("common.loading") : t("timeline.calendar")}
            </button>
          </div>
        </div>

        <div className="flex h-6 w-full overflow-hidden rounded-full border border-slate-800">
          {periods.map((period) => {
            const width = ((new Date(period.end).getTime() - new Date(period.start).getTime()) / spanMs) * 100;
            return (
              <div
                key={`bar-${period.lord}-${period.start}`}
                title={`${period.lord} ${period.start.slice(0, 10)} → ${period.end.slice(0, 10)}`}
                className={"h-full " + (period.current ? "ring-2 ring-amber-300 ring-inset" : "")}
                style={{
                  width: `${width}%`,
                  background: LORD_COLOR[period.lord] || "#94a3b8",
                  opacity: period.current ? 1 : 0.55,
                }}
              />
            );
          })}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
          {periods.map((period) => (
            <span key={`legend-${period.lord}-${period.start}`} className="inline-flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ background: LORD_COLOR[period.lord] || "#94a3b8" }}
              />
              {period.lord}
              {period.current ? ` (${t("common.now")})` : ""}
            </span>
          ))}
        </div>
      </section>

      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">{t("timeline.mahadashas")}</h2>
          <span className="chip">9 · 120y</span>
        </div>
        <PeriodTable periods={periods} dob={chart.birth.dob} />
      </section>

      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">
            {t("timeline.antardashas")} {chart.dasha.mahadasha}
          </h2>
          <span className="chip chip-gold">{t("timeline.currentMd")}</span>
        </div>
        <PeriodTable periods={chart.current_ads || []} dob={chart.birth.dob} />
      </section>

      <p className="text-[10px] text-slate-500">{t("timeline.note")}</p>
    </div>
  );
}
