# Vastu Shastra — Complete Knowledge Base

**Purpose**: the working knowledge corpus for the SweetAstro Vastu engine (planned),
compiled from the classical canon and established practice and tagged by authority.

**Confidence legend**

| Tag | Meaning |
|---|---|
| `[classical]` | Documented in the classical texts (Mayamata, Manasara, Samarangana Sutradhara, Brihat Samhita, Agni Purana, Vishvakarma Prakasha) |
| `[traditional]` | Widely practised across traditions; texts and regions vary on details |
| `[modern]` | Contemporary practice without classical textual basis (colours, crystals, pyramids, some remedies) |
| `[verify]` | Real tradition, but the exact textual formulation should be checked in a specific edition before quoting |

**Scope and honesty rules**
- Vastu is a traditional architectural and placement system, not an engineering
  discipline. Nothing here replaces a structural engineer, architect, or local code.
- The engine must never advise demolition, unsafe alteration, or expensive works as
  "necessary"; remedies are optional, proportionate and safe.
- Where schools disagree (e.g., kitchen in SE vs NW for some plots), both positions
  are recorded; the engine must present the mainstream position and note the variant.

**Source map** (from `docs/reference_library.md`, tier T6):
Mayamata (361) · Manasara (362) · Samarangana Sutradhara (363) · Vishvakarma Prakasha (364) ·
Aparajitaprccha (365) · Yukti Kalpataru (368) · Brihat Samhita architecture chapters (369) ·
Vastu-Silpa Kosha (371) · Ganapati Sthapati (372–373) · Sashikala Ananth (374) ·
Rohit Arya (375) · Niranjan Babu (377) · Kramrisch (404) · Percy Brown (403).

---

## 1. Foundations

### 1.1 The Vastu Purusha Mandala

- The site/building is planned as a sacred diagram: the **Vastu Purusha Mandala**.
  `[classical]`
- Two standard grids: **8×8 = 64 padas** (used for residential and temple planning)
  and **9×9 = 81 padas** (the most detailed; used in Mayamata/Manasara for towns,
  temples and precise room placement). `[classical]`
- The plan is presided over by **45 devatas** (deities), with **Brahma at the centre**.
  The centre cell(s) form the **Brahmasthan** — the "navel" of the building. `[classical]`
- The **Vastu Purusha** is the cosmic being pinned face-down on the site: his head
  lies in the north-east, feet in the south-west, giving the diagram its orientation.
  `[classical]` (the myth is narrated in the Matsya Purana and repeated in Mayamata's
  opening chapters).
- The diagram maps **cosmic order onto the dwelling**: each direction, deity and
  element has a proper function, and health of the building is the health of that
  order. `[classical]`

### 1.2 The 32 outer devatas (prakara devatas)

The outer ring of the mandala is held by 32 guardian deities. The inner ring holds
twelve (Aryaka, Savitra, Vivasvan, Mitra, Prithvidhara, Apah, and their counterparts).
The complete pada-by-pada grid must be taken from a specific edition — the names and
positions differ slightly between Mayamata and Manasara. `[verify]`
Established examples: **Rudra** (NE corner family), **Rajayakshma** and **Apa** near
the north, **Savitra** and **Vivasvan** along the north-west band, **Mitra** and
**Prithvidhara** toward the north-west corner. The four directional guardians sit at
the cardinal points (see §1.3). `[verify]`

### 1.3 Directions, elements, deities and planets

| Direction | Element | Deity | Planet (jyotish) | Qualities | Modern colour convention |
|---|---|---|---|---|---|
| East | Air/Fire (rising sun) | Indra | Sun | growth, health, new beginnings, social life | white / light yellow |
| South-East | Fire | Agni | Venus | fire, energy, cooking, passion | red / orange |
| South | Fire/Earth | Yama | Mars | discipline, fame, rest, ancestors | red / coral |
| South-West | Earth | Pitru (Nairutya) | Rahu | stability, heaviness, relationships, savings | brown / earthy |
| West | Water | Varuna | Saturn | gains, movement away, dining, children | grey / white |
| North-West | Air | Vayu | Moon | movement, guests, banking, change | white / silver |
| North | Water | Kubera | Mercury | wealth, opportunity, career, clarity | blue / green |
| North-East | Water/Ether | Ishana (Shiva) | Jupiter | wisdom, spirituality, clarity, water | yellow / light blue |
| Centre | Ether | Brahma | — | void, unity; keep open and light | white / yellow |

`[classical]` for directions, elements and deities; `[traditional]` for the planet
correspondences (standard in practice, digbala-linked in jyotish, see §7.2);
`[modern]` for colour conventions.

### 1.4 Weight and openness principle

- **Heaviest/lowest in the south-west; lightest/highest in the north-east.**
  This single principle explains most room, storage, water and height rules below.
  `[classical]`

---

## 2. Site (Bhumi)

### 2.1 Selection and soil testing (bhu-pariksha)

- Dig a pit, fill it back: soil that returns loosely (voluminous) is considered
  fertile/auspicious; soil that falls short is considered weak. `[classical]`
- Soil colour and smell are graded (sweet smell, firm texture preferred). `[classical]`
- Water absorption and crop growth on the plot are traditional tests. `[traditional]`
- Avoid sites that are: waterlogged, on a cremation/burial ground, immediately south
  of a temple, at a T-junction point, or with a large tree at the exact centre.
  `[traditional]`

### 2.2 Plot shapes

| Shape | Assessment |
|---|---|
| Square | Most auspicious `[classical]` |
| Rectangle up to 1:2 | Auspicious; keep the longer axis N–S for best results `[classical]` |
| Gomukhi (narrow front, wide rear) | Auspicious `[classical]` |
| Shermukhi (wide front, narrow rear) | Generally avoided `[traditional]` |
| Triangular | Avoided `[classical]` |
| Irregular / scissors / cut corners | Defect; remedies or avoidance advised `[traditional]` |
| Circular / oval | Acceptable for specific purposes, uncommon for homes `[traditional]` |

### 2.3 Levels and slope

- **North-east lowest, south-west highest**; water should drain toward N/NE.
  `[classical]`
- A site sloping down to the north or east is favoured; down to the south or west
  is considered unfavourable. `[classical]`
- The building's floor is set slightly above the plot; the main entrance threshold
  is raised. `[traditional]`

### 2.4 Roads and surroundings

- Roads on the north and east are considered auspicious; a road on three sides is
  mixed; roads on all four (Brahmasthan site) traditionally avoided for homes.
  `[traditional]`
- T-junctions and dead-ends facing the main door are considered defects (§6).
  `[traditional]`
- Taller structures to the south/west are acceptable; tall structures to the
  north/east that block morning sun are considered a defect. `[traditional]`

### 2.5 Facing and orientation

- East and north facing plots/doors are traditionally preferred; west and south are
  acceptable when the interior layout and entrance pada are correct. `[traditional]`
- True solar orientation, not merely compass magnetic north, is used for planning;
  account for magnetic declination at the site. `[modern]` (measurement note)

---

## 3. The Mandala in Practice (zones)

### 3.1 Brahmasthan (centre)

- Keep the centre **open, light and uncluttered**: no toilet, kitchen, staircase,
  pillar, heavy storage or beam load directly over the exact centre. `[classical]`
- A skylight, courtyard or open space at the centre (traditional aangan) is ideal.
  `[classical]`

### 3.2 Zone functions

| Zone band | Direction | Function |
|---|---|---|
| Ishana | NE | puja, meditation, study, underground water, openness |
| Agni | SE | kitchen, fire, electricals |
| Yama | S | bedrooms (secondary), storage, staircase |
| Nairutya | SW | master bedroom, heavy storage, family stability |
| Varuna | W | dining, children's rooms, toilets, overhead tank |
| Vayu | NW | guests, garage, movement, toilets, granary |
| Kubera | N | wealth, treasury, office, living |
| Indra | E | entrance, living, study, health |
| Brahma | Centre | void/open |

`[classical]` for the directional associations; `[traditional]` where practice
varies (e.g., dining W/E; study E/N/NE; toilets NW/W).

### 3.3 Entrance padas

- Specific padas of each direction are named for the presiding devatas; entrance
  through auspicious padas (e.g., those of Jayanta, Mahendra, Surya, Satya, Bhrisha
  in the north/east bands) is preferred. `[verify]` — exact grid per edition.
- Main door padas traditionally **avoided**: those of Yama, Roga, Papayakshma,
  Asura and Shosha. `[verify]`

---

## 4. Built Spaces — Placement Matrix

### 4.1 Rooms

| Space | Best | Acceptable | Avoid | Tier |
|---|---|---|---|---|
| Puja / meditation | NE | E, N | S, SW, centre; never under a staircase | classical |
| Kitchen (fire) | SE | E, S (partial) | NE, SW, centre; not facing the main door | classical |
| Master bedroom | SW | S, W | NE, SE, centre | classical |
| Children's bedroom | W | NW, E, N | SW (authority clash), SE | traditional |
| Guest room | NW | W, N | NE (turns into a permanent room) | traditional |
| Living / family room | E, NE, N | W, centre-adjacent | SW (heavy) | traditional |
| Dining | W | E, N | S (Yama), SW? (avoid directly under SW) | traditional |
| Study / office | NE, E, N | W | S, SW, under stairs | traditional |
| Parents' / elders' room | SW or W | S | NE | traditional |
| Store room | SW | S, W | NE, N (wealth zones) | traditional |
| Staircase | S, SW, W | — | NE, centre, E, N | traditional |
| Toilets / bathrooms | NW, W | SE (secondary WC only, modern) | NE, E, N, centre, SW, puja wall | traditional |
| Washing / utility | NW, W | SE | NE | traditional |
| Garage | NW, SE | W | NE, centre | traditional |

### 4.2 Water and tanks

- **Underground water tank / well / borewell**: NE, N, E — most favoured NE.
  `[classical]`
- **Overhead water tank**: SW, W, S — never over the NE or centre. `[traditional]`
- Drinking water source away from toilets; water flow out of the site toward N/NE.
  `[traditional]`

### 4.3 Pillars, beams and staircases

- Pillars should not obstruct the centre; beams should not run directly over the
  bed head or the puja space. `[traditional]`
- Staircases rise clockwise (as seen from above) in S/SW/W; avoid a staircase
  directly in front of the main door. `[traditional]`

### 4.4 Main door and gates

- Main door preferred in N, E, NE; the door should open inward, be solid, and be
  free of obstruction (no pole, tree, toilet or staircase facing it). `[traditional]`
- Avoid a main door exactly aligned with a back door or another large opening
  (energy/movement loss); offset them. `[traditional]`
- Compound gate: aligned not directly in line with the main door; a gate on N/E
  is preferred; gate smaller than compound wall height? — practice varies; keep the
  gate proportionate and unobstructed. `[verify]`

### 4.5 Compound wall and structure heights

- Compound wall higher/thicker on the S and W sides, lower/lighter on N and E.
  `[classical]`
- Building height: leaving more open space on N and E sides (setbacks) is favoured.
  `[traditional]`
- South-west corner of both plot and building kept the "heaviest". `[classical]`

### 4.6 Interiors and elements

| Element | Guidance | Tier |
|---|---|---|
| Colours | Per-direction palette (§1.3); light tones in N/NE, deeper in S/SW | modern |
| Mirrors | On N/E walls favoured for expansion; avoid facing the bed or reflecting the main door | modern |
| Plants | Tulsi (NE), money plant (N/SE indoors per practice); avoid large thorny plants at the entrance; avoid heavy trees at centre/SW | traditional |
| Water features | Small fountains/pools in N/NE; not in S/SW or bedrooms | modern |
| Metals | Copper/brass in NE/E; iron/heavy metal in S/SW/W; wind chimes NW (modern practice) | modern |
| Deity images | NE puja room; avoid bedrooms; keep out of toilets | traditional |
| Couches/beds | Head toward S or E; avoid head to N (tradition) and feet to the door | traditional |
| Safes/valuables | N or SW, opening toward N/E; do not place under a beam | traditional |

---

## 5. Measurement Canons (Ayadi)

### 5.1 Units

- Traditional units: **angula** (finger, ~1.9 cm), **hasta** (cubit, 24 angulas),
  **danda** (4 hastas). Building measures in Mayamata/Manasara are given in hastas.
  `[classical]`

### 5.2 The six Ayadi limbs (for plot/building dimensions)

Classical measurement verdicts are computed from the perimeter/dimensions:
**Aya** (income/auspiciousness), **Vyaya** (expenditure), **Yoni** (eight yonis),
**Nakshatra** (stellar size), **Vara** (weekday), **Amsa/Tithi** (part).
Each has specific arithmetic formulas in Mayamata and Manasara. `[verify]` —
formulas must be extracted from a specific edition before implementing; a wrong
formula would silently mislabel a dimension as auspicious or not.

### 5.3 Proportions

- Height-to-width proportion, room size progression, and door proportions follow
  chapter-level tables in the classical texts; general principle: proportions
  should be harmonic and consistent, not arbitrary. `[classical]`

---

## 6. Doshas and Remedies

### 6.1 Common defects (checklist)

| ID | Defect | Basis |
|---|---|---|
| V-D01 | Toilet/extended toilet in NE | traditional |
| V-D02 | Kitchen in NE or SW | traditional |
| V-D03 | Master bedroom in NE or SE | traditional |
| V-D04 | Water tank overhead in NE | traditional |
| V-D05 | Underground tank in SW | classical |
| V-D06 | Slope/water flow toward S/W | classical |
| V-D07 | Main door pada of Yama/Roga/Asura | verify |
| V-D08 | Toilet/kitchen/bed/pillar at Brahmasthan | classical |
| V-D09 | Staircase in NE / facing main door | traditional |
| V-D10 | Cut/extension missing in NE (truncated Ishana) | traditional |
| V-D11 | South-west extension beyond plot proportions | traditional |
| V-D12 | Large tree at centre / heavy tree in NE | traditional |
| V-D13 | T-junction or dead-end directly facing entrance | traditional |
| V-D14 | Beam/load over bed or puja place | traditional |
| V-D15 | More open space on S/W than N/E setbacks | traditional |
| V-D16 | Toilet sharing wall with puja room | traditional |

### 6.2 Non-structural remedies (traditional/optional)

- Correct the use of a room rather than demolish (change NE room to puja, move
  toilet use to NW/W, etc.). `[traditional]`
- Balance by lightness: keep N/NE open, light colours, low furniture; add weight
  in S/SW (storage, heavy materials). `[traditional]`
- Colours and materials per direction; mirrors/plants/water features as soft
  remedies. `[modern]`
- Metal strips, salts, pyramids, yantra placements — **modern practice**; may be
  offered as optional with zero-cost alternatives first. `[modern]`
- Structural changes (additions, extensions, cutting) are **engineering matters**:
  the engine must refer the user to a qualified professional, never advise
  demolition as a remedy. (Engine safety rule — matches the remedy ethics gate.)

### 6.3 What the engine must not do

- No guarantee that a remedy fixes outcomes; no fear-based selling; no advice that
  risks safety, heritage value, tenants' rights, or local building law.
- No fabricated verse citations; measurement formulas only after edition check.

---

## 7. Integration with Jyotish and Muhurta

### 7.1 Construction and occupation muhurta

| Stage | Traditional timing |
|---|---|
| Bhoomi puja (ground-breaking) | Auspicious lagna/day; avoid Rikta tithis, Bhadra; typically NE corner first `[traditional]` |
| Shilanyasa (first stone/foundation) | Auspicious muhurta; south-west block first, per construction sequence `[traditional]` |
| Door installation (main door) | Auspicious muhurta; door frames set with the auspicious lagna `[traditional]` |
| Griha pravesh (first entry) | Our muhurta engine's `griha_pravesh` rules (Rohini/Mrigashira/Uttara/Chitra/Anuradha/Uttara Ashadha/Uttara Bhadrapada/Revati; fixed lagnas; Rahu/Bhadra avoided) `[traditional]` |
| Occupation without ceremony | Avoid Amavasya, eclipse days, and the family's inauspicious taras `[traditional]` |

The chat engine already computes `griha_pravesh` windows (§ Panchanga & Muhurta
section of the README); bhoomi-puja/shilanyasa rule lists still need
edition-verified additions.

### 7.2 Planetary directions (digbala correspondence)

Sun–East · Moon–North-West · Mars–South · Mercury–North · Jupiter–North-East ·
Venus–South-East · Saturn–West · Rahu–South-West · Ketu–North-East.
`[traditional]` — used to link chart indications to spatial correction
(e.g., Jupiter remedies in the NE puja space; Saturn discipline in the west).

### 7.3 Chart-linked placement (optional practice)

Some traditions assign rooms by the native's lagna and planetary strengths
(e.g., master bedroom for a strong Venus/Saturn chart). This is a **practitioner
practice**, not a single classical rule set; the engine may present it as an
optional overlay with clear labelling. `[traditional]` / `[verify]`

---

## 8. Commercial and Office Spaces

| Space | Guidance | Tier |
|---|---|---|
| Owner/manager seating | SW, facing N or E | traditional |
| Accounts/treasury | N or SW, safe opening N/E | traditional |
| Staff seating | N, E, W (facing N/E) | traditional |
| Reception | NE or N-E | traditional |
| Toilets | NW or W (never NE) | traditional |
| Pantry/kitchenette | SE (fire) | traditional |
| Storage/heavy goods | SW, S | traditional |
| Machinery/heat | SE or S | traditional |

---

## 9. Source-to-Section Map

| Section | Primary sources |
|---|---|
| 1 Foundations, mandala, devatas | Mayamata (361), Manasara (362), Kramrisch (404), Matsya Purana |
| 2 Site and soil | Mayamata, Manasara, Brihat Samhita (369) |
| 3 Zone functions | Mayamata, Manasara, Vishvakarma Prakasha (364), Rajavallabha (367) |
| 4 Placement matrix | Mayamata, Manasara, Yukti Kalpataru (368); modern practice: Ananth (374), Arya (375), Babu (377) |
| 5 Measurements/Ayadi | Mayamata, Manasara, Aparajitaprccha (365) |
| 6 Doshas/remedies | Samarangana Sutradhara (363) for defects; remedies largely traditional/modern practice |
| 7 Jyotish/muhurta links | Muhurta Chintamani, Nirnaya Sindhu; Uttara Kalamrita (29) for karakatwas |
| 8 Commercial | modern practice (Ananth, Babu, Mahavastu literature) |

## 10. Engine Mapping (planned)

The structured version of this document lives in `data/rules/vastu_rules.json`
(directions, zones, room placements, water, stairs, door, defects with remedies,
construction muhurta). The planned Vastu engine will:

1. Take a layout (facing, plot shape, room positions by direction, water/stair
   locations, defects observed) — from user description or a guided checklist.
2. Score each element against the tables with provenance tiers shown.
3. Return: compliant items, defects with severity, optional remedies (safe,
   zero-cost first), and unresolved items requiring a professional.
4. Never fabricate measurements or verse citations; measurement (Ayadi) formulas
   are disabled until edition-verified.
