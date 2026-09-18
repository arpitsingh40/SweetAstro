import { useEffect, useRef, useState } from "react";
import { postMatching, searchPlaces } from "../lib/api";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import type { GeocodeHit, MatchResponse } from "../lib/types";

interface PersonForm {
  name: string;
  dob: string;
  tob: string;
  unknownTime: boolean;
  place: string;
  tz: number;
  lat: number | null;
  lon: number | null;
}

function emptyPerson(name = ""): PersonForm {
  return { name, dob: "", tob: "", unknownTime: false, place: "", tz: 5.5, lat: null, lon: null };
}

function PersonCard({
  title,
  value,
  onChange,
}: {
  title: string;
  value: PersonForm;
  onChange: (next: PersonForm) => void;
}) {
  const { t } = useI18n();
  const [hits, setHits] = useState<GeocodeHit[]>([]);
  const searchTimer = useRef<number | null>(null);
  const set = (patch: Partial<PersonForm>) => onChange({ ...value, ...patch });

  useEffect(() => {
    if (value.place.trim().length < 3 || (value.lat != null && value.lon != null)) {
      setHits([]);
      return;
    }
    if (searchTimer.current) window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(async () => {
      try {
        setHits(await searchPlaces(value.place.trim()));
      } catch {
        setHits([]);
      }
    }, 450);
    return () => {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
    };
  }, [value.place, value.lat, value.lon]);

  return (
    <div className="card p-4 space-y-3">
      <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="block text-[11px] text-slate-400">
          {t("match.name")}
          <input
            value={value.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder={t("match.namePh")}
            className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
          />
        </label>
        <label className="block text-[11px] text-slate-400">
          {t("match.dob")}
          <input
            type="date"
            value={value.dob}
            onChange={(e) => set({ dob: e.target.value })}
            required
            className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
          />
        </label>
        <label className={`block text-[11px] ${value.unknownTime ? "text-slate-600" : "text-slate-400"}`}>
          {t("match.tob")}
          <input
            type="time"
            value={value.tob}
            disabled={value.unknownTime}
            onChange={(e) => set({ tob: e.target.value })}
            className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60 disabled:opacity-40"
          />
        </label>
        <label className="block text-[11px] text-slate-400">
          {t("match.tz")}
          <input
            type="number"
            step="0.25"
            value={value.tz}
            onChange={(e) => set({ tz: parseFloat(e.target.value || "5.5") })}
            className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-[11px] text-slate-400">
        <input
          type="checkbox"
          checked={value.unknownTime}
          onChange={(e) => set({ unknownTime: e.target.checked })}
          className="accent-amber-500"
        />
        {t("match.unknown")}
      </label>
      <div className="relative">
        <label className="block text-[11px] text-slate-400">
          {t("match.place")}
          <input
            value={value.place}
            onChange={(e) => set({ place: e.target.value, lat: null, lon: null })}
            placeholder={t("match.placePh")}
            required
            className="mt-1 w-full bg-ink-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/60"
          />
        </label>
        {value.lat != null && value.lon != null && (
          <p className="text-[10px] text-emerald-300/80 mt-1">
            {t("home.form.resolved")}: {value.lat.toFixed(4)}, {value.lon.toFixed(4)}
          </p>
        )}
        {hits.length > 0 && (
          <div className="absolute z-20 mt-1 w-full card border-slate-700 p-1 max-h-56 overflow-y-auto">
            {hits.map((hit) => (
              <button
                key={`${hit.lat},${hit.lon},${hit.display_name}`}
                type="button"
                onClick={() => set({ place: hit.display_name, lat: hit.lat, lon: hit.lon })}
                className="w-full text-left text-[11px] px-3 py-2 rounded-lg hover:bg-slate-800/80 text-slate-200 transition"
              >
                {hit.display_name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function personFrom(form: PersonForm, fallbackName: string) {
  return {
    name: form.name.trim() || fallbackName,
    dob: form.dob,
    tob: form.unknownTime || !form.tob ? "12:00:00" : `${form.tob}:00`,
    place: form.place.trim(),
    tz_offset: form.tz,
    lat: form.lat ?? 28.6139,
    lon: form.lon ?? 77.209,
    geocode_provider: "nominatim",
  };
}

export default function Match() {
  const { chart } = useChart();
  const { t } = useI18n();
  const [a, setA] = useState<PersonForm>(emptyPerson());
  const [b, setB] = useState<PersonForm>(emptyPerson());
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [labels, setLabels] = useState({ a: "", b: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!chart) return;
    setA({
      name: chart.birth.name === "Native" ? "" : chart.birth.name,
      dob: chart.birth.dob || "",
      tob: (chart.birth.tob || "").slice(0, 5),
      unknownTime: false,
      place: chart.birth.place || "",
      tz: chart.birth.tz_offset ?? 5.5,
      lat: chart.birth.lat ?? null,
      lon: chart.birth.lon ?? null,
    });
  }, [chart]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!a.dob || !b.dob || !a.place.trim() || !b.place.trim()) {
      setError(t("match.error"));
      return;
    }
    setBusy(true);
    try {
      const personA = personFrom(a, "Person A");
      const personB = personFrom(b, "Person B");
      setLabels({ a: personA.name, b: personB.name });
      const response = await postMatching(personA, personB);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("match.failed"));
    } finally {
      setBusy(false);
    }
  }

  const total = result?.result.total ?? 0;
  const max = result?.result.max_total ?? 36;

  return (
    <div className="space-y-6">
      <section className="card card-gold p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-bold text-white">{t("match.title")}</h1>
            <p className="text-[11px] text-slate-400 mt-0.5">{t("match.sub")}</p>
          </div>
          <span className="chip chip-green">ashtakoota 36-point · deterministic</span>
        </div>
      </section>

      <form onSubmit={onSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PersonCard title={t("match.personA")} value={a} onChange={setA} />
        <PersonCard title={t("match.personB")} value={b} onChange={setB} />
        <div className="lg:col-span-2 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={busy}
            className="btn-gold text-sm font-bold px-6 py-2.5 rounded-xl"
          >
            {busy ? t("match.running") : t("match.run")}
          </button>
          {error && (
            <p role="alert" className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/60 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>
      </form>

      {result && (
        <section className="space-y-4">
          <div className="card p-4 sm:p-5 flex flex-wrap items-center gap-4">
            <div className="relative w-24 h-24 rounded-full border-4 border-amber-500/50 flex items-center justify-center">
              <div className="text-center">
                <div className="font-display text-2xl font-bold text-gradient-gold">{total}</div>
                <div className="text-[10px] text-slate-400">/ {max}</div>
              </div>
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-100">{t("match.verdict")}</div>
              <p className="text-xs text-slate-300 mt-1">{result.result.verdict}</p>
            </div>
          </div>

          <div className="card p-4 sm:p-5 space-y-3">
            <h2 className="text-sm font-semibold text-slate-100">{t("match.kutas")}</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs min-w-[420px]">
                <thead>
                  <tr className="text-slate-500 uppercase tracking-wide text-[10px]">
                    <th className="text-left py-2 pr-3">{t("match.kuta")}</th>
                    <th className="text-left py-2 pr-3">{t("match.points")}</th>
                    <th className="text-left py-2">{t("match.detail")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {result.result.kutas.map((kuta) => (
                    <tr key={kuta.kuta} className="text-slate-200">
                      <td className="py-2 pr-3 font-semibold whitespace-nowrap">{kuta.kuta}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">
                        <span className="chip">{kuta.points}/{kuta.max_points}</span>
                      </td>
                      <td className="py-2 text-slate-400">{kuta.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {([["a", result.result.mangal_a], ["b", result.result.mangal_b]] as const).map(
              ([side, mangal]) => (
                <div key={side} className="card p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-slate-100">
                      {t("match.mangal")} · {side === "a" ? labels.a || t("match.personA") : labels.b || t("match.personB")}
                    </h3>
                    <span className={`chip ${mangal.active ? "chip-gold" : "chip-green"}`}>
                      {mangal.active ? t("match.mangalActive") : t("match.mangalNone")}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{mangal.note}</p>
                  {mangal.cancellations.length > 0 && (
                    <p className="text-[11px] text-emerald-300/80">
                      {t("match.cancellations")}: {mangal.cancellations.join("; ")}
                    </p>
                  )}
                </div>
              ),
            )}
          </div>

          {result.result.notes.length > 0 && (
            <div className="card p-4 space-y-1">
              <h3 className="text-xs font-semibold text-slate-100">{t("match.notes")}</h3>
              {result.result.notes.map((note) => (
                <p key={note} className="text-[11px] text-slate-400">{note}</p>
              ))}
            </div>
          )}

          <p className="text-[10px] text-slate-500 text-center">{t("match.note")}</p>
        </section>
      )}
    </div>
  );
}
