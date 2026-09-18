# Video Method Pipeline (research → evidence → labelled fallback)

**Purpose**: capture calculation methods and rules taught in YouTube videos,
verify them, and — only when the engine cannot fully answer a question — offer
them as clearly labelled modern fallback options computed on our server.

**Hard rules** (enforced by tests, not convention):

- The answer path (`src/chat/*`, `src/consumer.py`, `src/knowledge/*`) must
  never import the pipeline or read raw transcripts
  (`tests/test_video_research.py::test_answer_path_never_imports_the_research_pipeline`).
- Videos are **never** authority for a classical value. A claim that matches a
  public-domain classical text becomes a classical rule via
  `research_intake.py` + `data/rules/`; otherwise it can only ever appear as a
  labelled modern method pack (`data/methods/`).
- Nothing is served until it passes the evidence gate; packs ship
  `"enabled": false` by default.
- Views/comments are not authenticity signals. They are used only as
  disconfirming evidence (corrections, counterexamples) in research notes.

## Pipeline

```
fetch → extract (dual pass) → candidates.jsonl → gate → draft | pack
```

| Stage | Command | Output |
|---|---|---|
| Ingest | `python video_research.py fetch <url/id>` / `fetch-channel <url> --limit N` | `data/research/videos/<id>.{json,cues.jsonl,vtt}` |
| Search | `python video_research.py search "QUERY" [--limit 8] [--ingest]` | candidate videos |
| Deep search | `python video_research.py research --topic T --reason "..."` | reason-matched causes/remedies report |
| Extract | `python video_research.py extract <id>` | `data/research/candidates.jsonl` |
| Report | `python video_research.py report [--verdict quarantine]` | gate verdicts + deep links |
| Quarantine | `python video_research.py draft VC-xxxxxxxxxx` | intake draft (`source_class=web`) |
| Pack | `python video_research.py pack VC-xxxxxxxxxx --slug <slug>` | disabled skeleton in `data/methods/` |

### Extraction integrity

- Dual-pass self-consistency: only claims produced by both passes (temperature
  0.0 and 0.5) are kept.
- Quote verification: exact substring first, then token-subsequence matching
  (≥70% coverage in a local window) which tolerates auto-caption rolling
  duplicates. Quotes that do not match the transcript are dropped.
- Timestamps are clamped to the transcript chunk; locators are honest text
  positions, never invented.
- Caption kind (`manual` / `auto` / `auto-translated` / `none`) is recorded
  per video; auto-caption claims carry a "low-confidence" note in the gate.

### Evidence gate

| Verdict | Meaning | Next step |
|---|---|---|
| `classical_candidate` | public-domain library contains a matching locus | verify + promote in `research_intake.py`, then `data/rules/` |
| `modern_candidate` | ≥2 independent videos describe it consistently | fill in the pack computation + tests, then enable |
| `quarantine` | single-source claim | wait for a second source or a classical locus |

Calculations additionally require reproducing every worked example shown in
the video before they may be enabled.

### Failure handling

- yt-dlp subtitle download 429s fall back to direct caption fetch with
  retries; metadata + captions are cached so every later stage is offline.
- Batches never abort on one bad target; each failure is reported per target.
- The registry skips malformed pack files and reports them via
  `pack_problems()`.

## Fallback in answers (labelled modern option)

`src/chat/payload.py` appends a modern-method block when either:

- `capability_gap=True` (`assess_capability().verdict != "full"`) — topic-level
  fallback packs only (entries without `reason_tags`); or
- `unfavorable=True` — the promise assessment is `Weak`/`Partial`
  (`src/interpretation/promise.py`), i.e. an event reading is not in the
  native's favour. The engine's limiting factors are canonicalised to reason
  tags (`src/methods/reasons.py`) and only packs addressing **that exact
  reason** are matched (`src/methods/registry.py:method_for_topic`).

The block includes the pack label, source teacher/channel/videos, steps,
modern remedies, the addressed reason tags, and the rule "never as classical
authority, a guarantee, or a prescription".

Quoting: paraphrase-only by default. Verbatim transcript quotes require both
`SWEETASTRO_METHOD_QUOTES=1` (environment) and `"allow_quotes": true` (pack).

## Deep search (exact reason → causes and remedies)

```powershell
python video_research.py research --topic marriage --reason "Venus lord of H7 is Debilitated in H6" --limit 2
```

Builds a search-friendly query from the canonical reason tags (with a compact
fallback query when YouTube returns nothing), ingests the top hits, runs
dual-pass extraction, and ranks `cause`/`remedy` candidates whose `reason_tags`
overlap the engine's. Output stays in the normal curation path: quarantine
drafts and disabled packs only.

## Current state

- Videos ingested (auto captions): `ZrOP65MR3qg`, `eqfD7AYSSMI` (Jyotish Vedang
  by Rahul Kaushik, Hindi) · `gB6abFi0o2M` (Punneit's Astrology, English) ·
  `zaAymwJNLj0` (KRSchannel, English).
- Candidates: 15 validated claims in `data/research/candidates.jsonl`.
- Deep search live run (`marriage` / "Venus lord of H7 is Debilitated in H6"):
  2 videos ingested, 7 candidates, 4 reason-matched `cause` claims with
  timestamped deep links and classical-library hits.
- Quarantine: `RC-0001` (Saturn = first male child / father) is a draft —
  `source_class=web`, modern-only, not servable.
- Method packs: one **disabled** skeleton (`data/methods/kat-trikona-map.json`);
  placeholder computation must be replaced and tested before `"enabled": true`.
- Live answers are unchanged: no enabled pack means neither the capability-gap
  nor the unfavourable-reason fallback adds anything.
