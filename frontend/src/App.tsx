import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { ChartProvider, useChart } from "./lib/chart-context";
import { I18nProvider, useI18n } from "./lib/i18n";
import type { Lang } from "./lib/i18n";
import Home from "./pages/Home";
import Chart from "./pages/Chart";
import Today from "./pages/Today";
import Timeline from "./pages/Timeline";
import Chat from "./pages/Chat";
import Muhurta from "./pages/Muhurta";
import Match from "./pages/Match";

function NavItem({ to, label, end = false }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        "px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-medium transition " +
        (isActive
          ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
          : "text-slate-300 border border-transparent hover:border-slate-700 hover:text-white")
      }
    >
      {label}
    </NavLink>
  );
}

function LanguageSelect() {
  const { lang, setLang, t } = useI18n();
  return (
    <select
      value={lang}
      onChange={(e) => setLang(e.target.value as Lang)}
      aria-label="Language"
      className="text-[11px] bg-ink-950 border border-slate-700 text-slate-300 rounded-lg px-1.5 py-1.5 focus:outline-none focus:border-amber-500/50"
    >
      <option value="en">{t("lang.en")}</option>
      <option value="hi">{t("lang.hi")}</option>
      <option value="hinglish">{t("lang.hinglish")}</option>
    </select>
  );
}

function Shell() {
  const { chart } = useChart();
  const { t } = useI18n();
  return (
    <div className="min-h-full flex flex-col">
      <div className="bg-cosmos" aria-hidden="true" />
      <div className="bg-stars" aria-hidden="true" />
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-ink-950/75 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <Link to="/" className="flex items-center gap-3 min-w-0 group">
            <span className="relative w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-slate-950 text-lg shrink-0 shadow-lg shadow-amber-500/25 transition group-hover:scale-105">
              🪐
              <span className="absolute inset-0 rounded-2xl ring-1 ring-amber-200/40" />
            </span>
            <span className="min-w-0">
              <span className="block font-display text-[17px] font-bold text-gradient-gold leading-tight truncate">
                SweetAstro
              </span>
              <span className="block text-[10px] text-slate-400 truncate">{t("app.tagline")}</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 sm:gap-1.5" aria-label="Primary">
            <NavItem to="/today" label={t("nav.today")} />
            <NavItem to="/chart" label={t("nav.chart")} />
            <NavItem to="/timeline" label={t("nav.timeline")} />
            <NavItem to="/muhurta" label={t("nav.muhurta")} />
            <NavItem to="/match" label={t("nav.match")} />
            <NavItem to="/" label={t("nav.add")} end />
            <LanguageSelect />
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                "btn-gold px-3.5 py-1.5 rounded-lg text-xs font-bold " + (isActive ? "ring-1 ring-amber-200/60" : "")
              }
            >
              {t("nav.chat")}
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-4xl mx-auto px-4 py-6 pb-16">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/today" element={<Today />} />
            <Route path="/chart" element={<Chart />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/muhurta" element={<Muhurta />} />
            <Route path="/match" element={<Match />} />
            <Route path="*" element={<Home />} />
          </Routes>
          {!chart && <div className="h-2" />}
        </div>
      </main>

      <footer className="border-t border-slate-800 py-4">
        <p className="max-w-4xl mx-auto px-4 text-[10px] text-slate-500 text-center">
          {t("common.disclaimer")}
        </p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <ChartProvider>
        <BrowserRouter basename="/app">
          <Shell />
        </BrowserRouter>
      </ChartProvider>
    </I18nProvider>
  );
}
