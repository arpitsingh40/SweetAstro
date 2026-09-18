import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import KundliChart from "../components/KundliChart";
import PlanetTable from "../components/PlanetTable";
import { DashaCard, PanchangaCard, UpcomingCard } from "../components/Cards";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import { downloadSvgAsPng } from "../lib/export";

type ChartStyle = "north" | "south";

export default function Chart() {
  const { chart } = useChart();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [style, setStyle] = useState<ChartStyle>(
    () => (localStorage.getItem("sweetastro_chart_style") as ChartStyle) || "north",
  );

  if (!chart) return <Navigate to="/" replace />;

  const selectStyle = (next: ChartStyle) => {
    setStyle(next);
    localStorage.setItem("sweetastro_chart_style", next);
  };

  const moon = chart.chart.planets.find((p) => p.name === "Moon");
  const lagna = chart.chart.ascendant_sign;

  return (
    <div className="space-y-6">
      <section className="card card-gold p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="font-display text-xl font-bold text-white truncate">
              {chart.birth.name} · {lagna} Lagna
            </h1>
            <p className="text-[11px] text-slate-400 mt-0.5 truncate">
              {chart.birth.dob} {chart.birth.tob ? `· ${chart.birth.tob}` : ""} · {chart.birth.place}
              {" · "}UTC {chart.birth.tz_offset >= 0 ? "+" : ""}{chart.birth.tz_offset}h
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="chip chip-green" title="Verified against Swiss Ephemeris">
              {t("common.engineVerified")}
            </span>
            <span className="chip chip-gold">Lahiri {chart.chart.ayanamsha.toFixed(3)}°</span>
            {moon && (
              <span className="chip">
                {t("chart.moon")} {moon.sign} · {moon.nakshatra} P{moon.nakshatra_pada}
              </span>
            )}
          </div>
        </div>
        {!chart.birth_time_reliable && (
          <p
            role="status"
            className="mt-3 text-[11px] text-amber-200 bg-amber-950/40 border border-amber-800/60 rounded-lg px-3 py-2"
          >
            {t("chart.timeUncertain")}
          </p>
        )}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={() => window.print()}
            className="btn-gold text-xs font-bold px-4 py-2 rounded-lg"
          >
            {t("common.print")}
          </button>
          <button
            onClick={async () => {
              const svg = document.getElementById("kundli-svg") as SVGSVGElement | null;
              if (!svg) return;
              const slug = chart.birth.name.trim().replace(/\s+/g, "-").toLowerCase() || "kundli";
              try {
                await downloadSvgAsPng(svg, `${slug}-kundli.png`);
              } catch {
                window.print();
              }
            }}
            className="btn-ghost text-xs font-medium px-4 py-2 rounded-lg"
          >
            {t("common.savePng")}
          </button>
          <button
            onClick={() => navigate("/")}
            className="btn-ghost text-xs font-medium px-4 py-2 rounded-lg"
          >
            {t("common.newPerson")}
          </button>
          <button
            onClick={() => navigate("/chat")}
            className="btn-ghost text-xs font-medium px-4 py-2 rounded-lg"
          >
            {t("common.askEngine")}
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100">{t("chart.kundli")}</h2>
            <div className="flex rounded-lg border border-slate-700 overflow-hidden text-[11px]">
              {(["north", "south"] as ChartStyle[]).map((option) => (
                <button
                  key={option}
                  onClick={() => selectStyle(option)}
                  className={
                    "px-3 py-1.5 transition " +
                    (style === option
                      ? "bg-amber-500 text-slate-950 font-semibold"
                      : "text-slate-300 hover:bg-slate-800/70")
                  }
                >
                  {option === "north" ? t("chart.north") : t("chart.south")}
                </button>
              ))}
            </div>
          </div>
          <KundliChart data={chart} style={style} />
          <p className="text-[10px] text-slate-500 text-center">{t("chart.kundliNote")}</p>
        </div>

        <div className="space-y-4">
          <DashaCard dasha={chart.dasha} />
          <PanchangaCard panchanga={chart.panchanga} />
          <UpcomingCard periods={chart.upcoming || []} />
        </div>
      </section>

      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">{t("chart.grahas")}</h2>
          <span className="chip">{t("chart.grahasNote")}</span>
        </div>
        <PlanetTable planets={chart.chart.planets} />
        <p className="text-[10px] text-slate-500">{chart.calculation}</p>
      </section>
    </div>
  );
}
