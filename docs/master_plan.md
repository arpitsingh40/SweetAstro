# SweetAstro — Final Master Plan

> Adopted 2026-09-18. Reconciled against the actual repository before adoption:
> the existing core engine stays, and `vedic-calc` remains an optional
> reference only. Execution status is tracked in the code and tests, not in
> this document.

## 1. The company/product thesis

**SweetAstro is not going to be "another AI astrologer."**

The product:

> **A question-first astrology intelligence platform that understands a person's real-life problem, dynamically selects the relevant astrological methods, calculates deterministic evidence, analyzes timing, explains the result, remembers context, and learns from outcomes.**

The user never needs to understand D1, D9, KP, BNN, etc.

They simply ask:

> **"What should I know about this situation?"**

---

## 2. The final architecture

```text
                         SWEETASTRO
                             │
                             ▼
                    CONVERSATION ENGINE
                             │
                             ▼
                    CORE ISSUE ENGINE
                             │
                             ▼
                  ASTROLOGY STRATEGIST
                             │
                             ▼
                 CALCULATION PLANNER
                             │
                             ▼
                  SWEETASTRO CORE
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   CHART ENGINE          TIME ENGINE        RELATION GRAPH
        │                    │                    │
        ▼                    ▼                    ▼
     D1–D60                DASHAS              PLANETS
     HOUSES                TRANSITS            LORDS
     ASPECTS               TIMING              NAKSHATRAS
     STRENGTH              DIRECTIONS          CHAINS
        └────────────────────┼────────────────────┘
                             ▼
                      METHOD ENGINES
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
      PARASHARI             KP                BNN/KAT
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                         JAIMINI
                             │
                             ▼
                    WESTERN METHODS
                             │
                             ▼
                      RULE ENGINE
                             │
                             ▼
                    EVIDENCE GRAPH
                             │
                             ▼
                     TIMING ENGINE
                             │
                             ▼
                  SENSITIVITY ENGINE
                             │
                             ▼
                    DECISION ENGINE
                             │
                             ▼
                         LLM
                             │
                             ▼
                          USER
                             │
                             ▼
                     LIFE MEMORY
                             │
                             ▼
                    OUTCOME DATABASE
                             │
                             ▼
                    BACKTESTING LAB
```

---

## 3. Don't replace the current engine

This is a firm decision.

The existing SweetAstro core is already substantially developed. The
repository contains a deterministic Swiss-Ephemeris-based calculation layer,
extensive varga support, Vimshottari/timing functionality, Jaimini-related
calculations, structured rules, sensitivity analysis and a
prediction/backtesting framework.

Therefore:

### Keep

- current core
- current tests
- current prediction engine
- current rules
- current backtesting
- current marriage engine

### Upgrade

- architecture
- calculation abstraction
- methodology coverage
- KP
- BNN
- KAT
- Western methods
- dynamic strategist

`vedic-calc` should remain an **optional reference/cross-check**, not the
foundation of SweetAstro. Its current GitHub repository is small,
AGPL-licensed, and relatively new; there is no compelling reason to replace
the existing core with it.

---

## 4. Phase 1 — SweetAstro Core v2

This is the **next engineering milestone**.

### A. Multi-ayanamsha

Current:

```text
Lahiri
```

Target:

```text
AyanamshaProvider
├── Lahiri
├── Krishnamurti
├── Raman
├── Fagan-Bradley
└── extensible
```

This is particularly important before implementing KP.

**Status:** implemented in `src/core/ayanamsha.py` (Step 1), with the provider
wired through `calculate_d1_chart`.

### B. Universal chart model

Create one canonical representation:

```json
{
  "birth": {},
  "zodiac": {},
  "planets": {},
  "houses": {},
  "nakshatras": {},
  "vargas": {},
  "strength": {},
  "metadata": {}
}
```

Every method consumes this normalized structure.

### C. House/Cusp engine

Support:

```text
Whole Sign
Bhava Chalit
Placidus
Equal
Sripati
Regiomontanus
...
```

Each methodology explicitly requests its required system.

### D. Universal aspect engine

Support both:

### Vedic

- Parashari aspects
- Mars/Jupiter/Saturn special aspects

### Western

- conjunction
- opposition
- square
- trine
- sextile
- etc.

### Uranian

- hard-aspect dial relationships
- midpoint structures

### E. Universal dasha interface

Normalize:

```text
Vimshottari
Yogini
Chara
Ashtottari
Narayana
```

into one API.

---

## 5. Phase 2 — Planetary Relationship Graph

This is one of the most important pieces.

Build:

```text
PLANET
 │
 ├── sign
 ├── house
 ├── sign lord
 ├── house lord
 ├── dispositor
 ├── nakshatra lord
 ├── conjunction
 ├── aspect
 ├── dignity
 ├── combustion
 └── retrogression
```

Then:

```text
Planet A
   ↓
Planet B
   ↓
Planet C
   ↓
Life significance
```

This becomes the infrastructure for:

**BNN + KAT + other relationship-based methodologies.**

---

## 6. Phase 3 — KP

Build KP as a separate method.

```text
KP
├── Cusps
├── Nakshatra Lords
├── Sub Lords
├── 249 divisions
├── Significators
├── Ruling Planets
├── Event Houses
└── Timing
```

KP should answer structured questions like:

> Is there support for this event?

> Which houses signify it?

> What periods activate those significators?

Don't let the LLM determine KP results.

---

## 7. Phase 4 — BNN

Build:

```text
BNN
├── planetary significators
├── planetary chains
├── conjunction relationships
├── nakshatra relationships
├── event mapping
└── timing
```

BNN consumes the **same chart graph** generated by Core v2.

---

## 8. Phase 5 — KAT

Make KAT a separate methodology:

```text
KAT
├── planetary patterns
├── predictive rules
├── alignment
├── timing
└── remedies
```

Maintain explicit provenance:

```json
{
  "method": "KAT",
  "source": "...",
  "rule_id": "...",
  "tradition": "KAT",
  "version": "1.0"
}
```

Don't silently blend KAT with BNN.

And don't reproduce copyrighted book/course content without authorization.

---

## 9. Phase 6 — Jaimini

Expand:

```text
Chara Karakas
Atmakaraka
Amatyakaraka
Darakaraka
Arudha
Upapada
Jaimini aspects
Chara Dasha
```

Use it as an independent methodology.

---

## 10. Phase 7 — Western methodology layer

Don't build everything simultaneously.

First:

### Hellenistic

- Annual Profections
- Zodiacal Releasing

### Western timing

- Solar Arc
- Secondary Progressions
- Primary Directions

### Pattern methods

- Midpoints
- Cosmobiology
- Uranian

Each is a **pluggable method**.

---

## 11. Phase 8 — Dynamic Astrology Strategist

This is the actual heart of SweetAstro.

User:

> "Should I take a loan and expand my business?"

Strategist produces:

```json
{
  "domain": [
    "business",
    "wealth",
    "debt",
    "timing"
  ],

  "methods": [
    "parashari",
    "kp",
    "bnn",
    "jaimini"
  ],

  "calculations": [
    "D1",
    "D2",
    "D10",
    "dasha",
    "transit",
    "ashtakavarga"
  ]
}
```

The system calculates **only what is relevant**.

---

## 12. Phase 9 — Evidence Graph

Every conclusion must have traceable evidence.

```text
CLAIM
 ↓
RULE
 ↓
CALCULATION
 ↓
METHOD
 ↓
SOURCE
```

Example:

```text
Business expansion supported
        ↓
KP rule #KP-104
        ↓
10th/11th significators
        ↓
KP
        ↓
source/version
```

Also record:

```text
contradicting evidence
uncertainty
birth-time sensitivity
method disagreement
```

---

## 13. Phase 10 — Timing Engine

Build a unified timing engine:

```text
Natal Promise
       ↓
Dasha
       ↓
Sub-period
       ↓
Transit
       ↓
Ashtakavarga
       ↓
KP timing
       ↓
Jaimini timing
       ↓
Varshaphala
       ↓
Western timing
       ↓
CONVERGENCE
```

Output **windows**, not fake precision.

Example:

> **Strongest period: April–June 2028.**

---

## 14. Phase 11 — Sensitivity

The existing birth-time perturbation work should remain.

Test:

```text
-10m
-8m
-6m
...
exact
...
+8m
+10m
```

Then:

```text
Prediction stability
Method stability
House stability
Timing stability
```

This becomes part of the confidence explanation.

---

## 15. Phase 12 — Decision Engine

This is where SweetAstro becomes more than a horoscope product.

Example:

> "Should I expand?"

Return:

```text
ASTROLOGICAL ANALYSIS
        +
TIMING
        +
CONTRADICTIONS
        +
UNCERTAINTY
        +
PRACTICAL FACTORS
```

Not:

> "Yes, definitely."

Instead:

> "The selected astrological methods show support for expansion during X
> period, while debt-related indicators are mixed. Before acting, evaluate
> cash flow, debt service and demand."

That is much more useful.

---

## 16. Phase 13 — Life Threads

Store user context:

```text
Business
 ├── goal
 ├── current status
 ├── decisions
 ├── previous analysis
 └── outcomes
```

Then the conversation becomes continuous.

---

## 17. Phase 14 — Outcome database

This is potentially the strongest long-term asset.

```text
QUESTION
   ↓
ANALYSIS
   ↓
PREDICTION
   ↓
USER ACTION
   ↓
REAL OUTCOME
   ↓
EVALUATION
```

This allows SweetAstro to learn **which methods and rule combinations
actually perform well on collected evaluation data**.

---

## 18. Phase 15 — Backtesting

Keep the existing system.

Expand it to:

```text
Parashari
        ↓
Parashari + Jaimini
        ↓
Parashari + KP
        ↓
Parashari + BNN
        ↓
Parashari + KP + BNN
        ↓
+ KAT
        ↓
+ Western timing
```

Measure:

- event accuracy
- timing error
- top-1/top-3
- calibration
- stability
- coverage
- contradiction rate

Don't assume a technique works because it's famous.

**Test it.**

---

## 19. First five domains

Don't build 50.

### Launch domains

**1. Marriage**

**2. Career**

**3. Business**

**4. Money**

**5. Property**

The existing marriage engine becomes the first mature benchmark.

---

## 20. The killer UX

The user should see almost none of the complexity.

### User

> "My business is doing okay, but I'm considering a ₹30 lakh loan to expand. Is this the right time?"

### SweetAstro

```text
Understanding your question...

Business expansion
+
Debt
+
Cash flow
+
12-month timing
```

Then the system works.

The final answer might contain:

### What your chart indicates

### Why

### Timing

### Risks/contradictions

### What to consider practically

### Follow-up question

The complexity stays behind the interface.

---

## 21. Business model

Don't rely only on:

> ₹1,999/month unlimited.

Test several models.

### Free

3 questions.

### Paid

- deeper analysis
- longer conversations
- Life Threads
- advanced timing
- multiple methods
- reports
- history

### Later

- professional astrologer tools
- API
- developer platform
- research platform
- white-label engine
- enterprise integrations

The **open-source core** can attract developers while the hosted service
monetizes convenience, infrastructure, advanced features and personalization.

---

## 22. The billion-dollar strategy

This needs to be approached as a hypothesis, not a prediction.

The potential path is:

```text
OPEN SOURCE CORE
        ↓
DEVELOPERS
        ↓
COMMUNITY
        ↓
FREE USERS
        ↓
QUESTION-FIRST PRODUCT
        ↓
RETENTION
        ↓
PAID USERS
        ↓
PERSONALIZED LIFE INTELLIGENCE
        ↓
GLOBAL MARKET
```

The huge opportunity isn't:

> "Sell astrology reports."

It's potentially:

> **Build a global personalized decision/introspection platform around astrology.**

But that only becomes a large business if actual users demonstrate sustained
demand.

---

## 23. What NOT to do

### Don't

- ❌ Replace the current engine with `vedic-calc`.
- ❌ Build every astrology technique before testing demand.
- ❌ Let the LLM calculate astrology.
- ❌ Put all rules inside prompts.
- ❌ Give exact dates when the underlying methods don't justify them.
- ❌ Mix BNN/KAT/Parashari rules without provenance.
- ❌ Assume more methods = more accuracy.
- ❌ Spend the entire budget on infrastructure.
- ❌ Wait for a "perfect" engine before launching.

---

## 24. The execution order

```text
STEP 1
Multi-ayanamsha abstraction
        ↓
STEP 2
Universal chart model
        ↓
STEP 3
House/cusp engine
        ↓
STEP 4
Universal aspect engine
        ↓
STEP 5
Universal dasha interface
        ↓
STEP 6
Planetary relationship graph
        ↓
STEP 7
KP
        ↓
STEP 8
BNN
        ↓
STEP 9
KAT
        ↓
STEP 10
Jaimini expansion
        ↓
STEP 11
Dynamic Strategist
        ↓
STEP 12
Evidence Graph
        ↓
STEP 13
Unified Timing
        ↓
STEP 14
Backtesting
        ↓
STEP 15
20–50 user beta
        ↓
STEP 16
Improve based on evidence
        ↓
STEP 17
Public launch
        ↓
STEP 18
Scale
```

---

## 25. The single most important principle

**Don't try to make SweetAstro the astrology library with the most features.**

Make it the system that is best at answering:

> **"I have this real-life question. What astrological analysis is actually
> relevant, what evidence does it produce, when is it activated, how stable
> is the result, and what should I understand about it?"**

That is the differentiation.

---

## Final decision

### Keep SweetAstro's existing core.

### Don't migrate to `vedic-calc`.

### Build **SweetAstro Core v2** around:

**Multi-ayanamsha → House/Cusp → Relationship Graph → KP → BNN → KAT →
Jaimini → Dynamic Strategist → Evidence → Timing → Backtesting.**

Then launch with **5 domains**, not 50.

And the business loop is:

> **Build → test with users → measure retention → backtest → improve →
> monetize → scale.**
