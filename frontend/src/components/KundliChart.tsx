import { useMemo } from "react";
import type { ChartResponse, PlanetRow } from "../lib/types";

const PLANET_SHORT: Record<string, string> = {
  Sun: "Su", Moon: "Mo", Mars: "Ma", Mercury: "Me", Jupiter: "Ju",
  Venus: "Ve", Saturn: "Sa", Rahu: "Ra", Ketu: "Ke",
};

const PLANET_COLOR: Record<string, string> = {
  Sun: "#fbbf24",
  Moon: "#e2e8f0",
  Mars: "#f87171",
  Mercury: "#5eead4",
  Jupiter: "#fcd34d",
  Venus: "#f9a8d4",
  Saturn: "#93c5fd",
  Rahu: "#a3a3a3",
  Ketu: "#a3a3a3",
};

const ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];

function sortPlanets(planets: PlanetRow[]): PlanetRow[] {
  return [...planets].sort((a, b) => ORDER.indexOf(a.name) - ORDER.indexOf(b.name));
}

function PlanetStack({ x, y, planets, size }: {
  x: number; y: number; planets: PlanetRow[]; size: number;
}) {
  if (planets.length === 0) return null;
  const line = size > 0 ? size : 10;
  const startDy = planets.length > 1 ? -((planets.length - 1) * line) / 2 : 0;
  return (
    <text x={x} y={y + startDy + line * 0.35} textAnchor="middle" fontSize={line} fontWeight={700}>
      {planets.map((p, index) => (
        <tspan
          key={p.name}
          x={x}
          dy={index === 0 ? 0 : line}
          fill={PLANET_COLOR[p.name] || "#e2e8f0"}
        >
          {PLANET_SHORT[p.name] || p.name.slice(0, 2)}
          {p.retrograde ? "\u02D6" : ""}
        </tspan>
      ))}
    </text>
  );
}

function SignLabel({ x, y, sign, house, highlight }: {
  x: number; y: number; sign: string; house: number; highlight: boolean;
}) {
  return (
    <>
      <text x={x} y={y} textAnchor="middle" fontSize={9} fill={highlight ? "#fcd34d" : "#64748b"}>
        {sign.slice(0, 3)}
      </text>
      <text x={x} y={y + 10} textAnchor="middle" fontSize={8} fill="#475569">
        H{house}
      </text>
    </>
  );
}

function NorthChart({ data }: { data: ChartResponse }) {
  const { chart } = data;
  const centers: Array<[number, number]> = [
    [160, 46], [76, 36], [36, 76], [50, 160], [36, 244], [76, 284],
    [160, 284], [244, 284], [284, 244], [270, 160], [284, 76], [244, 36],
  ];
  const planetsByHouse = useMemo(() => {
    const map = new Map<number, PlanetRow[]>();
    chart.planets.forEach((p) => {
      const list = map.get(p.house) || [];
      list.push(p);
      map.set(p.house, list);
    });
    return map;
  }, [chart.planets]);

  return (
    <svg viewBox="0 0 320 320" id="kundli-svg" fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
         className="w-full max-w-[420px] mx-auto" role="img"
         aria-label={`North Indian kundli, ascendant ${chart.ascendant_sign}`}>
      <rect x="10" y="10" width="300" height="300" fill="rgba(2,6,23,0.6)" stroke="#1e293b" strokeWidth="1.5" />
      <line x1="10" y1="10" x2="310" y2="310" stroke="#1e293b" strokeWidth="1.2" />
      <line x1="310" y1="10" x2="10" y2="310" stroke="#1e293b" strokeWidth="1.2" />
      <polygon points="160,10 310,160 160,310 10,160" fill="none" stroke="#334155" strokeWidth="1.2" />
      {chart.houses.map((h, index) => {
        const [x, y] = centers[index];
        const planets = sortPlanets(planetsByHouse.get(h.house) || []);
        const isLagna = h.house === 1;
        return (
          <g key={h.house}>
            {isLagna && <circle cx={x} cy={y + 2} r={26} fill="rgba(245,158,11,0.07)" stroke="rgba(245,158,11,0.35)" strokeWidth="0.8" />}
            <SignLabel x={x} y={y - 14} sign={h.sign} house={h.house} highlight={isLagna} />
            <PlanetStack x={x} y={y + 6} planets={planets} size={planets.length > 3 ? 8 : 10} />
          </g>
        );
      })}
      <text x="160" y="166" textAnchor="middle" fontSize="9" fill="#334155">
        {chart.ascendant_degree.toFixed(1)}°
      </text>
    </svg>
  );
}

const SOUTH_LAYOUT: Array<{ signIndex: number; col: number; row: number }> = [
  { signIndex: 12, col: 0, row: 0 }, { signIndex: 1, col: 1, row: 0 },
  { signIndex: 2, col: 2, row: 0 }, { signIndex: 3, col: 3, row: 0 },
  { signIndex: 11, col: 0, row: 1 }, { signIndex: 4, col: 3, row: 1 },
  { signIndex: 10, col: 0, row: 2 }, { signIndex: 5, col: 3, row: 2 },
  { signIndex: 9, col: 0, row: 3 }, { signIndex: 8, col: 1, row: 3 },
  { signIndex: 7, col: 2, row: 3 }, { signIndex: 6, col: 3, row: 3 },
];

function SouthChart({ data }: { data: ChartResponse }) {
  const { chart } = data;
  const cell = 75;
  const origin = 10;
  const planetsBySign = useMemo(() => {
    const map = new Map<number, PlanetRow[]>();
    chart.planets.forEach((p) => {
      const list = map.get(p.sign_index) || [];
      list.push(p);
      map.set(p.sign_index, list);
    });
    return map;
  }, [chart.planets]);

  return (
    <svg viewBox="0 0 320 320" id="kundli-svg" fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
         className="w-full max-w-[420px] mx-auto" role="img"
         aria-label={`South Indian kundli, ascendant ${chart.ascendant_sign}`}>
      <rect x={origin} y={origin} width={cell * 4} height={cell * 4} fill="rgba(2,6,23,0.6)" stroke="#1e293b" strokeWidth="1.5" />
      {SOUTH_LAYOUT.map(({ signIndex, col, row }) => {
        const x = origin + col * cell;
        const y = origin + row * cell;
        const house = ((signIndex - chart.ascendant_sign_index + 12) % 12) + 1;
        const isLagna = house === 1;
        const planets = sortPlanets(planetsBySign.get(signIndex) || []);
        return (
          <g key={signIndex}>
            <rect x={x} y={y} width={cell} height={cell} fill={isLagna ? "rgba(245,158,11,0.06)" : "transparent"}
                  stroke="#1e293b" strokeWidth="1" />
            <SignLabel x={x + 12} y={y + 14} sign={chart.houses[house - 1].sign} house={house} highlight={isLagna} />
            <PlanetStack x={x + cell / 2} y={y + cell / 2 + 6} planets={planets}
                         size={planets.length > 3 ? 8 : 10} />
          </g>
        );
      })}
      <rect x={origin + cell} y={origin + cell} width={cell * 2} height={cell * 2}
            fill="rgba(11,18,32,0.95)" stroke="#1e293b" strokeWidth="1" />
      <text x={origin + cell * 2} y={origin + cell * 2 - 8} textAnchor="middle" fontSize="12" fill="#fcd34d"
            fontWeight={700} fontFamily="Cinzel, serif">
        Rashi
      </text>
      <text x={origin + cell * 2} y={origin + cell * 2 + 10} textAnchor="middle" fontSize="9" fill="#64748b">
        Lagna {chart.ascendant_sign}
      </text>
      <text x={origin + cell * 2} y={origin + cell * 2 + 24} textAnchor="middle" fontSize="8" fill="#475569">
        {chart.ascendant_degree.toFixed(1)}° · Lahiri {data.chart.ayanamsha.toFixed(3)}°
      </text>
    </svg>
  );
}

export default function KundliChart({ data, style }: { data: ChartResponse; style: "north" | "south" }) {
  return style === "south" ? <SouthChart data={data} /> : <NorthChart data={data} />;
}
