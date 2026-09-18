# Research Note — Complete Planetary Analysis ("Planetary Dossier")

**Researched**: 2026-09-13 · **Method**: audit of the existing engine
(`src/core/strength.py`, `shadbala.py`, `yogas.py`, `vargas.py`, `jaimini.py`,
`ashtakavarga.py`, `transits.py`, `dasha.py`), plus external methodology review
of classical Shadbala, avasthas, panchadha maitri, graha yuddha, and modern
structured planet-assessment practice.
**Purpose**: define the *best complete way to analyse a single planet* — using
all 16+ divisional charts, dasha, aspects, conjunctions, yogas, raja-yogas,
Shadbala and the factors still missing — and map exactly what SweetAstro must
add to reach it.

> Provenance: factors below are classical (BPHS, Phaladeepika, Saravali,
> Jataka Parijata and the standard modern treatises already catalogued in
> `docs/reference_library.md`). Nothing here makes an accuracy claim; all
> additions are deterministic computation plus documented interpretive bands.

---

## 1. What the engine already does per planet (audit)

| Layer | Implemented | Where |
|---|---|---|
| Position | sign, degree, house, nakshatra/pada/lord, retrograde, combustion flag | `chart.py` |
| Dignity | exalted, moolatrikona, own, friend, neutral, enemy, debilitated (natural friendship only) | `chart.py::_calculate_dignity` |
| Aspects | Parashara 7th + special (Mars/Jupiter/Saturn/nodes), given + received | `chart.py::_calculate_aspects` |
| Conjunctions | same-sign occupants list | `strength.py` |
| Dispositor chain | sign lord + dignity (+ nakshatra lord in nodes) | `strength.py`, `rahu_ketu.py` |
| Vargas | all 23 charts placed; selected vargas per topic; D9 dedicated | `vargas.py`, `varga_matrix.py`, `navamsa.py` |
| Varga strength | Vimshopak Bala (4 schemes), Vaiseshikamsa, vargottama | `vimshopaka.py`, `navamsa.py` |
| Yogas | Mahapurusha, Budha-Aditya, Gajakesari, Chandra-Mangal, Venus-Mars, (simplified) Rajayoga, Kala Sarpa (now arc-correct) | `yogas.py` |
| Ashtakavarga | BAV per planet, SAV per house, transit bindu notes | `ashtakavarga.py` |
| Dasha | Vimshottari MD/AD/PD/SD/PrD; Yogini and Chara as cross-checks | `dasha.py`, `yogini.py`, `chara_dasha.py` |
| Transits | gochara from Moon, vedha, Sade Sati, double-transit | `transits.py` |
| Jaimini | chara karakas, arudhas, UL analysis, argala (occupancy) | `jaimini.py`, `arudha.py`, `argala.py` |
| Strength summary | full-chain `StrengthAssessment` + recommendation + a **non-classical** 360-point analytical index | `strength.py`, `shadbala.py` |

Gaps visible immediately: no temporal/compound friendship, no avasthas, no
true Shadbala (the current module is explicitly an approximation), no Drik
Bala, no Ishta/Kashta, no graha yuddha, no gandanta/sandhi/mrityu-bhaga/
pushkara, no per-planet BAV usage in the strength decision, and Rajayoga is a
simplified proxy.

## 2. The complete classical checklist (synthesised)

A planet cannot be judged from one placement. The traditions converge on seven
question groups; each group below is what a world-class per-planet analysis
must answer.

### A. Identity — what the planet *is* in this chart
1. Natural nature (benefic/malefic/neutral), karakatwas, gender, element.
2. **Functional nature by lagna**: yogakaraka, kendra/trikona lord, dusthana
   lord, maraka (2nd/7th lord), badhaka; ownership of the topic houses.
3. **Chara karaka role** (AK…DK) from Jaimini — especially DK for marriage.
4. Dasha role: which MD/AD/PD it currently rules; whether it is the
   pratyantardasha lord, and its relation to the running chain.

### B. Position — where it sits (D1 and the varga chain)
5. Sign, house, degree; house from its own sign (aspect geometry).
6. Nakshatra, pada, nakshatra lord and the lord's condition (the "sub-boss").
7. Dignity (all seven states) with **panchadha maitri**: natural friendship +
   **temporal friendship (tatkalika)** combined into adhimitra / mitra / sama /
   shatru / adhishatru. The engine today stops at natural friendship.
8. **Avasthas**:
   - *Baladi* (Bala/Yuva/Vriddha/Mrita — 5 states by degree, reversed in even
     signs) — the classical "age/energy" of the planet.
   - *Jagradadi* (awake/dreaming/sleeping) by dignity class.
   - *Deeptadi* (9 states: deepta, swastha, mudita, shanta, dina, duhkhita,
     vikala, khala, kopita) from dignity + combustion + retrogression.
   - (Optional advanced: *Lajjitadi* 6 states.)
9. **Sandhi / gandanta**: junction degrees (last 1° / first 1° of a sign;
   water–fire junctions), mrityu bhaga degrees, pushkara navamsa/bhaga.
10. Vargottama (D1=D9, present) and the **64th navamsa** point (sensitive).

### C. Association — who it meets
11. Conjunctions with exact orb and the compound friendship of each partner.
12. **Graha yuddha** (planetary war): two non-luminary planets within 1° —
    the victor (lower longitude, brighter/north) absorbs the loser's strength.
13. **Parivartana** (mutual exchange) between sign lords.
14. Combustion severity graded by orb (half-orb = severe already implemented).
15. Retrogression effects (Chesta Bala in true Shadbala; interpretive
    intensity rules).
16. Aspects: Parashara drishti (present), special aspects (present), and
    **Drik Bala** — the net benefic-minus-malefic aspectual strength on the
    planet (a classical Shadbala component we do not compute).
17. Argala / virodha argala on the planet's house (present, occupancy-only).

### D. Varga depth — the 16+ chart view
18. Dignity across the shodashavarga (present) + non-Parashari charts
    (present), with moolatrikona correctly excluded outside D1 (fixed).
19. **Vimshopak Bala** (present) and Vaiseshikamsa count (present).
20. Key-varga confirmation for the question's topic (present via
    `question → varga` mapping) and cross-varga consistency: the same planet
    strong in D1, D9, D10 but weak in D60 is a different statement than the
    reverse — the **weighting of vargas is fixed by scheme, not by question**.
21. Pushkara navamsa / pushkara bhaga placement (auspicious boost).
22. **Rashi-Tulya-Navamsha / Navamsha-Tulya-Rashi** repeat confirmations
    (V.P. Goel's research line; needs a verified source before encoding).

### E. Strength — how strong it actually is
23. **True Shadbala** (six components, in virupas; 60 virupas = 1 rupa):
    - *Sthana Bala*: uchcha (exaltation angle), saptavargaja, ojhayugma
      (odd/even sign), kendradi, drekkana.
    - *Dig Bala*: directional (present as approximation).
    - *Kala Bala*: natonnata (day/night), paksha (Moon's phase for
      benefics/malefics), tribhaga, varsha–masa–dina–hora, ayana, yuddha.
    - *Chesta Bala*: motional (retrograde/speed — needs real speed; fallback
      now correct).
    - *Naisargika Bala*: fixed natural order (Sun strongest → Saturn weakest).
    - *Drik Bala*: net aspectual strength (see 16).
    Then the classical minimum ratios per planet and the rupa total.
24. **Ishta Phala / Kashta Phala**: benefic yield vs harm potential derived
    from uchcha + chesta — the classical "will this planet do good or damage".
25. **Bhava Bala** of the house it occupies (bhavadhipati, bhava-dig,
    bhava-drishti) — the planet carries its house's strength.
26. **Ashtakavarga personal bindus**: the planet's own BAV in its sign/house
    (present in data, not yet used in the strength verdict).
27. The engine's analytical 360-point index (present) must be **renamed and
    demoted** to what it is — a transparent composite score — never labelled
    "Shadbala".

### F. Time — what it will do and when
28. Current dasha depth (MD → PrD) and upcoming sub-periods (present).
29. Cross-dasha agreement (Vimshottari vs Yogini vs Chara) for the planet's
    period (engines present; only Chara is wired into event timing).
30. Transit interaction: gochara position from Moon/lagna, vedha, Sade Sati,
    double transit, and the planet's own BAV at the transit sign (present).
31. Is the planet a *promise* factor (natal) vs *trigger* factor (dasha/
    transit) for the asked topic — the promise/timing separation (present in
    the pipeline, not in the per-planet dossier).

### G. Synthesis — what it means
32. Yoga participation: which named yogas it forms/joins, raja/dhana yoga
    classification, and cancellation checks (Neecha Bhanga, Dosha
    cancellations). Rajayoga detection must be rebuilt on lord-based
    kendra-trikona connections, not the current dispositor proxy.
33. Classical conflict resolution: strength hierarchy when factors disagree
    (dignity + avastha + shadbala > single aspect; yogas override dignity).
    This must be an explicit, documented rubric — never a naive sum.
34. Result statement + remedy/gemstone suitability + limits (what cannot be
    judged without a reliable birth time).

## 3. Gap analysis vs the checklist

| # | Factor | Status | Effort |
|---|---|---|---|
| 7 | Tatkalika + panchadha maitri | missing | S |
| 8 | Baladi / Jagradadi / Deeptadi avasthas | missing | S–M |
| 9 | Sandhi, gandanta, mrityu bhaga, pushkara | missing | S |
| 10 | 64th navamsa | missing | S |
| 12 | Graha yuddha | missing | S |
| 13 | Parivartana exchanges | missing | S |
| 16 | Drik Bala | missing | M |
| 21 | Pushkara navamsa/bhaga | missing | S |
| 23 | True Shadbala (six components) | approximation only | L |
| 24 | Ishta / Kashta phala | missing | M |
| 25 | Bhava Bala | missing | M |
| 26 | BAV in the strength verdict | data present, unused | S |
| 32 | Correct Rajayoga (lord-based) + Neecha Bhanga | simplified | M |
| 33 | Explicit factor-resolution rubric | informal | M |
| 34 | Per-planet result statement in deep mode | partial | S |

## 4. Best-way architecture (proposal)

Add one deterministic module, `src/core/planet_dossier.py`, that assembles a
`PlanetaryDossier` per graha from the engines above — no new astronomy, only
composition plus the missing classical computations:

```
PlanetaryDossier
├── identity: nature, functional roles, maraka/badhaka flags, karaka role
├── position: sign/house/nakshatra chain, dignity, panchadha maitri, avasthas,
│             sandhi/gandanta/mrityu-bhaga/pushkara flags
├── association: conjunctions (orb + friendship), graha yuddha, exchanges,
│                combustion severity, drik bala, argala
├── vargas: per-varga dignity (23), vimshopaka, vaiseshikamsa, vargottama
├── strength: true shadbala components (rupas), ishta/kashta, bhava bala,
│             bav bindus, analytical index (clearly named as such)
├── time: current dasha depth, cross-dasha agreement, transit status + BAV
├── synthesis: yoga participation, resolved verdict, remedies suitability,
│              confidence + limits
└── provenance: every field source-labelled; interpretive fields flagged
```

Rules for correctness:
- Exact classical formulas for each Shadbala component, each with a unit test
  against hand-computed values or a frozen reference chart.
- Avasthas and friendship are pure arithmetic — fully testable.
- The synthesis step uses a **documented priority rubric** (dignity + avastha
  + shadbala core, then yoga overrides, then dasha/transit modulation) with
  the weights written down and exposed in output — not an opaque score.
- Deep mode (`answer_shape="report"`) renders the dossier for all seven
  physical grahas; nodes keep their full chain. Lookup mode can print a
  single planet's dossier on request.
- Birth-time gating: varga/avastha-derived fields degrade with the existing
  reliability system; sandhi/gandanta need minute-level time.

## 5. Validation plan

1. Unit-test every formula (maitri table, avastha boundaries at 6° steps,
   yuddha orb, shadbala components) against hand-computed values.
2. Freeze one reference chart's full dossier as a regression fixture.
3. Keep the existing analyst checks: `score_chat_answer` rubric + golden
   payload cases; add a golden case asserting the dossier block appears only
   in deep mode and covers all nine grahas.
4. No accuracy claim: dossiers are interpretive composition; the accuracy
   protocol continues to govern any prediction statement.

## 6. Prioritised roadmap

**P0 — DONE (2026-09-13)** — `src/core/planet_factors.py`:
tatkalika + panchadha maitri; Baladi/Jagradadi/Deeptadi avasthas; sandhi and
gandanta flags; graha yuddha (lower-longitude convention); parivartana
(Maha/Dainya/Khala); own BAV bindus in the strength verdict; factors carried
on `StrengthAssessment` and rendered in the payload (`· factors:` line).
Mrityu bhaga and Pushkara navamsa/bhaga moved to P2 — their tables have
competing published traditions and need a verified edition before encoding.
The analytical 360-point index remains labelled "SweetAstro analytical
model, not classical Shadbala" everywhere it surfaces.

**P1 — DONE (2026-09-13)** — `src/core/classical_shadbala.py`:
true Shadbala components (Uchcha, Saptavargaja with panchadha maitri, Ojhayugma,
Kendradi, Drekkana, Dig, Natonnata, Paksha, Tribhaga, Dina, Hora, Ayana,
Chesta, Naisargika, Drik), rupa totals vs Rashmi minimums with ratio bands,
and Ishta = √(Uchcha×Chesta) / Kashta = √((60−Uchcha)×(60−Chesta)).
`yogas.py`: Rajayoga rebuilt on lord-based kendra–trikona connections
(conjunction / mutual aspect / exchange) + Neecha Bhanga detection.
Deep mode now carries the classical strength for every physical graha and
Pushkara flags (rendered in the payload factors line).
Declared omissions (never guessed): Varsha/Masa Bala (needs a chosen
solar-year convention) and true mean-longitude Chesta Kendra (speed-ratio
convention used instead, documented in the module).

**P3 — DONE (2026-09-13, where sources allow)** — `src/core/strength_extras.py`:
Varsha Bala (15 virupas, weekday lord of the Mesha Sankranti) and Masa Bala
(30 virupas, weekday lord of the sidereal solar-month ingress) — both
ingresses computed with the engine's own solar-return math, convention
declared; wired into Kala Bala in deep mode. Bhava Bala: Bhavadhipati Bala
(lord's classical Shadbala) + Bhava Drishti Bala (net aspect on the house)
for all 12 houses; Bhava Digbala remains omitted (needs a declared bhava-madhya
source). Dasha cross-system agreement (Vimshottari vs Yogini vs Chara) as an
independent, never-stacked cross-check.
Still blocked (no reliable source obtained): **Mrityu Bhaga** — deep research
in `docs/research/mrityu_bhaga.md` verified the structure, the full Moon row,
and several spot values, but found a conflict (Moon Capricorn 20 vs 25) and a
rejected fabricated-looking row; encoding waits on a printed JP/Sarvartha
Chintamani edition. True mean-longitude Chesta Kendra (mean elements) and
Goel-style varga-linking (licensed book required) remain deferred.

## 7. Open questions

1. Kala Bala includes several sub-components with variant formulas
   (hora/varsha–masa–dina, tribhaga, ayana). Which published edition do we
   adopt? Verify against a verified T2 edition before encoding.
2. Ishta/Kashta has two common derivations (uchcha+chesta vs shadbala-based);
   pick one and label it.
3. Bhava Bala requires bhava madhya (house cusps) — our houses are whole-sign.
   Decide whether to compute bhava-sandhi variants or limit Bhava Bala to
   whole-sign adaptation.
4. Avastha interpretation weights are traditional, not empirically calibrated;
   keep them labelled interpretive until (if ever) outcome data supports more.
