import type { PlanetRow } from "../lib/types";

const DIGNITY_STYLE: Record<string, string> = {
  Exalted: "text-emerald-300",
  Moolatrikona: "text-emerald-300",
  Own: "text-emerald-200",
  Friend: "text-teal-300",
  Neutral: "text-slate-300",
  Enemy: "text-amber-300",
  Debilitated: "text-rose-300",
};

export default function PlanetTable({ planets }: { planets: PlanetRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[420px]">
        <thead>
          <tr className="text-slate-500 uppercase tracking-wide text-[10px]">
            <th className="text-left py-2 pr-3">Graha</th>
            <th className="text-left py-2 pr-3">Position</th>
            <th className="text-left py-2 pr-3">House</th>
            <th className="text-left py-2 pr-3">Dignity</th>
            <th className="text-left py-2">Nakshatra</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70">
          {planets.map((p) => (
            <tr key={p.name} className="text-slate-200">
              <td className="py-2 pr-3 font-semibold whitespace-nowrap">
                {p.name}
                {p.retrograde && <span className="text-amber-300 ml-1" title="Retrograde">R</span>}
                {p.combust && <span className="text-rose-300 ml-1" title="Combust">C</span>}
              </td>
              <td className="py-2 pr-3 whitespace-nowrap">
                {p.sign} {p.degree.toFixed(2)}°
              </td>
              <td className="py-2 pr-3">{p.house}H</td>
              <td className={`py-2 pr-3 ${DIGNITY_STYLE[p.dignity] || "text-slate-300"}`}>{p.dignity}</td>
              <td className="py-2 whitespace-nowrap">
                {p.nakshatra} <span className="text-slate-500">P{p.nakshatra_pada}</span>
                <span className="text-slate-500"> · {p.nakshatra_lord}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
