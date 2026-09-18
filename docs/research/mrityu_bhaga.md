# Research Note — Mrityu Bhaga (critical degrees)

**Researched**: 2026-09-13 · **Purpose**: obtain a source-verified Mrityu Bhaga
table before encoding it (P3 hold-out in `docs/research/planetary_analysis.md`).
**Status**: partial table verified; full table **not yet sourced**; a
conflict was found between commonly circulated values — do not encode from
secondary web sources.

> Mrityu Bhaga is a sensitive 1-degree band, not a lifespan reading. Nothing
> here supports a death or health claim. Consumer use must remain a
> "sensitive degree" flag with the existing safety language.

---

## 1. What the sources agree on

- **Structure (Jataka Parijata, Adhyaya 1, Shloka 57; Sarvartha Chintamani)**:
  one integer N is listed per body per sign, and the band is the Nth degree —
  `(N-1)°00′` up to `N°00′`. Example given in the source summary: Sun at
  `19°20′` Aries is in the 20th degree, i.e. Aries Mrityu Bhaga for the Sun.
  (Hindu Calculator, Mrityu Bhaga page — describes JP/Sarvartha Chintamani;
  Phaladeepika lists a different Moon row.)
- **Scope**: JP lists rows for Lagna, the seven grahas, Rahu, Ketu and
  Mandi (Gulika). Lagna/Gulika require exact birth time and the Gulika
  computation; both must be gated by the existing time-reliability system.
- **Tradition split**: JP and Sarvartha Chintamani share one Moon row;
  Phaladeepika (and Brihat Prajapatya) give another. The other bodies match
  across JP/Sarvartha per the secondary summaries.

## 2. Verified fragments (with sources)

| Body | Value | Source (secondary) |
|---|---|---|
| Moon — full row, Aries→Pisces | 8, 25, 22, 22, 21, 1, 4, 23, 18, 20, 20, 10 | Sarvartha Chintamani = Jataka Parijata (Rakesh Soni compilation; quoted in search summary) |
| Sun — Aries | 20th degree | Hindu Calculator worked example (JP table) |
| Sun — Capricorn | 2° | AstroSaxena, *Concept of Mrityu Bhaga* |
| Saturn — Cancer | 9° | AstroSaxena |
| Jupiter — Cancer | 27° | AstroSaxena |
| Rahu — Aquarius | 18th degree | IndiaDivine forum thread (JP convention) |
| Phaladeepika variant — Moon Aquarius | 5° | IndiaDivine forum thread |

## 3. Conflicts found (why the full table is not encoded)

1. **Moon — Capricorn**: the JP/Sarvartha row (§2) gives **20**, but
   AstroSaxena's article quotes **25** for the same position. One of the two
   is miscopied; without the printed source this cannot be resolved.
2. **Mercury row**: one commercial site (Veda Lumina) publishes a full
   12-sign Mercury row (15, 14, 13, 12, 8, 18, 20, 10, 21, 22, 7, 5). The
   first four values descend in lockstep (15,14,13,12), which no classical
   table does; the page also reads as machine-generated and cites no verse.
   **Rejected as unreliable.**
3. **Fixed-degree lists** ("Sun 11–12° in any sign", etc.) circulating on
   SEO pages are a different, later convention that ignores the per-sign
   structure. Not JP; not used.
4. The `hinducalculator.com` page confirms the per-sign structure but does
   not print the numeric table in the fetchable text.

## 4. What is needed to finish (one book check)

Verified editions already catalogued in `docs/reference_library.md`:

- **Jataka Parijata** — trans. V. Subrahmanya Sastri (3 vols, entry 124) or
  trans. G.S. Kapoor (entry 125): Adhyaya 1, Shloka 57.
- **Sarvartha Chintamani** — trans. G.S. Kapoor (entry 126) and the English
  rendering by B. Suryanarain Rao (entry 211), for the second Moon row and
  cross-check.
- **Phaladeepika** — trans. G.S. Kapoor (entry 121) or S.S. Sareen (entry
  122), for the variant Moon row (declare the convention if used).

Procedure once a printed table is in hand: transcribe one row at a time,
compare against the verified fragments in §2, and only then encode.

## 5. Implementation plan (ready to execute)

1. `src/core/sensitive_points.py`: add
   `MRITYU_BHAGA: Dict[str, Dict[int, int]]` (body → sign index → N) with a
   per-row provenance comment naming the book/edition/verse.
2. `is_mrityu_bhaga(body, sign_index, deg, orb=0.0)`: band is
   `(N-1)° ≤ deg < N°`; optional orb widens symmetrically and must be
   declared in output.
3. Include Lagna and Gulika rows only when the birth-time reliability gate
   passes (Gulika additionally needs the Saturn-kala computation).
4. Surface it as a **flag with cancellation checks** already available in
   the engine (own/exaltation, Vargottama, benefic aspect, Pushkara), never
   as a verdict — and never in health-topic answers without the existing
   professional-referral language.
5. Tests: every encoded row checked against §2's fragments; boundary tests
   at `(N-1)°00′`, `N°00′`, and `N°00′ + orb`.

Until then, the engine ships **no** Mrityu Bhaga data — by design.
