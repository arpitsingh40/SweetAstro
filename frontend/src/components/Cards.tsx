import { useI18n } from "../lib/i18n";
import type { DashaState, PanchangaRow, UpcomingPeriod } from "../lib/types";

function shortDate(iso: string): string {
  return iso ? iso.slice(0, 10) : "—";
}

export function DashaCard({ dasha }: { dasha: DashaState }) {
  const { t } = useI18n();
  return (
    <div className="card card-gold p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gold-300">{t("chart.dasha")}</h3>
        <span className="chip chip-gold">{t("common.engineVerified")}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          [t("dasha.mahadasha"), dasha.mahadasha],
          [t("dasha.antardasha"), dasha.antardasha],
          [t("dasha.pratyantar"), dasha.pratyantardasha],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-ink-900/60 px-2 py-2.5">
            <div className="text-[9px] uppercase tracking-wide text-slate-500">{label}</div>
            <div className="text-sm font-semibold text-slate-100 mt-0.5">{value}</div>
          </div>
        ))}
      </div>
      <dl className="text-[11px] text-slate-400 space-y-1">
        <div className="flex justify-between gap-3">
          <dt>{t("dasha.mdPeriod")}</dt>
          <dd className="text-slate-200">{shortDate(dasha.md_start)} → {shortDate(dasha.md_end)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t("dasha.adPeriod")}</dt>
          <dd className="text-slate-200">{shortDate(dasha.ad_start)} → {shortDate(dasha.ad_end)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t("dasha.pdPeriod")}</dt>
          <dd className="text-slate-200">{shortDate(dasha.pd_start)} → {shortDate(dasha.pd_end)}</dd>
        </div>
      </dl>
    </div>
  );
}
export function PanchangaCard({ panchanga }: { panchanga: PanchangaRow | null }) {
  const { t } = useI18n();
  if (!panchanga) return null;
  const rows = [
    [t("today.vara"), panchanga.vara],
    [t("today.tithi"), `${panchanga.paksha} ${panchanga.tithi}`],
    [t("today.nakshatra"), `${panchanga.nakshatra} P${panchanga.nakshatra_pada}`],
    [t("today.yoga"), panchanga.yoga],
    [t("today.karana"), panchanga.karana],
  ];
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">{t("chart.birthPanchanga")}</h3>
        <span className="chip">drik ganita</span>
      </div>
      <dl className="text-[11px] space-y-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-slate-200 text-right">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function UpcomingCard({ periods }: { periods: UpcomingPeriod[] }) {
  const { t } = useI18n();
  if (periods.length === 0) return null;
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">{t("chart.coming")}</h3>
        <span className="chip">Vimshottari</span>
      </div>
      <ul className="space-y-2">
        {periods.map((period) => (
          <li key={`${period.level}-${period.lord}-${period.start}`}
              className="flex items-center justify-between gap-3 text-[11px]">
            <span className="flex items-center gap-2 min-w-0">
              <span className={`chip ${period.level === "MD" ? "chip-gold" : ""}`}>{period.level}</span>
              <span className="text-slate-200 font-medium truncate">{period.lord}</span>
            </span>
            <span className="text-slate-400 whitespace-nowrap">
              {period.start.slice(0, 10)} → {period.end.slice(0, 10)}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-[10px] text-slate-500">{t("dasha.periodNote")}</p>
    </div>
  );
}
