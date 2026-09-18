# Method packs (modern, fallback-only)

A method pack is a **modern, non-classical** technique curated from the video
research pipeline (`video_research.py`, `src/research_pipeline/`). Packs are
surfaced only as a labelled fallback when `assess_capability` reports the
engine cannot fully answer a question (`verdict != "full"`), and only when the
pack is explicitly enabled. They can never appear in — or modify — the
classical provenance ledger.

## Schema

```json
{
  "version": "0.1.0",
  "slug": "kebab-case-id",
  "method": "short human title",
  "source": {
    "teacher": "name",
    "channel": "YouTube channel",
    "basis": "what the method is based on",
    "confidence": "modern",
    "research_note": "docs/research/....md",
    "label": "Shown in answers (modern — teacher)"
  },
  "enabled": false,
  "allow_quotes": false,
  "source_videos": [{"id": "...", "title": "...", "locator": "HH:MM:SS-HH:MM:SS"}],
  "safety_rules": ["Unvalidated modern method; optional; no guarantees."],
  "topic_map": {
    "career": {
      "label": "Human-readable label",
      "formula": "deterministic computation the server applies",
      "steps": ["step 1", "step 2"],
      "remedies": ["modern, optional remedy for the exact reason"],
      "reason_tags": ["venus_debilitated", "venus_house_7"],
      "quote": "verbatim transcript excerpt (optional)",
      "locator": "HH:MM:SS-HH:MM:SS",
      "adapted": false,
      "note": "mapping note when adapted"
    }
  }
}
```

`reason_tags` are canonical snake_case tags (`src/methods/reasons.py`). They
are matched against the engine's promise limiting factors, so a pack is only
shown for the exact unfavourable reason it addresses:

- entry **with** `reason_tags` → only matched when the engine's reason tags
  overlap (e.g. "Venus (lord of H7) is Debilitated in H6" → `venus_debilitated`);
- entry **without** tags → topic-level fallback (capability-gap answers);
- tagged entries never appear without a matching reason.

Rules enforced by `src/methods/registry.py` (`pack_problems()`):

- `confidence` must be `modern`;
- `safety_rules` must be non-empty;
- required fields: `slug`, `method`, `source`, `enabled`, `topic_map`;
- a malformed file is skipped, never fatal.

## Lifecycle

1. `python video_research.py extract <video_id>` — dual-pass extraction.
2. `python video_research.py report` — evidence gate verdicts
   (`classical_candidate` / `modern_candidate` / `quarantine`).
3. For an exact unfavourable reading, run the targeted deep search first:
   `python video_research.py research --topic marriage --reason "Venus lord of H7 is Debilitated in H6"`
   which ranks reason-matched `cause`/`remedy` candidates.
4. `python video_research.py pack VC-xxxxxxxxxx --slug my-method` — writes a
   **disabled** skeleton here with provenance, reason tags and remedies.
5. Replace the placeholder `formula`/`steps` with the deterministic
   server-side computation and add tests; reproduce every worked example from
   the video before enabling.
6. Set `"enabled": true` only after the gate says `modern_candidate`
   (two independent sources) or the claim was re-grounded as a classical rule
   (then it belongs in `data/rules/`, not here).

## Quoting mode

Default: paraphrase + attribution only. To allow verbatim transcript quotes in
answers (personal use), set `SWEETASTRO_METHOD_QUOTES=1` **and**
`"allow_quotes": true` in the pack. Without both, quotes are never emitted.
