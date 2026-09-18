# Public-Domain Library (full-text corpus)

The indexes in `01_classical_canon.md`–`03_applied_systems.md` are a **metadata**
corpus: titles, one-line summaries, categories, confidence status. This file
documents the companion **full-text** corpus: verbatim, citable passages from
public-domain editions, stored locally and retrieved deterministically.

- Catalog: `data/library/catalog.json`
- Source texts: `data/library/sources/<slug>.txt` (downloaded, not hand-edited)
- Passage indexes: `data/library/index/<slug>.jsonl` (generated)
- Engine module: `src/knowledge/library.py`
- CLI: `python library.py fetch|build|search|stats|verify`
- Tests: `tests/test_library.py`

## Corpus (all verified public domain)

| slug | work | edition used | basis |
|---|---|---|---|
| `brihat_jataka` | Brihat Jataka (Varahamihira) | N. Chidambaram Iyer, 1885 | pre-1930 imprint; archive `NOT_IN_COPYRIGHT` |
| `jaimini_sutras` | Jaimini Sutras (Upadesa Sutras) | B. Suryanarain Rao translation | translator d. 1937 (India life+60); translation first published pre-1930 |
| `brihat_samhita` | Brihat Samhita (Varahamihira) | H. Kern, 1865 | pre-1930 imprint |
| `phaladeepika` | Phaladeepika (Mantreswara) | V. Subrahmanya Sastri, 1937 | DLI rights statement: "In Public Domain" |
| `bphs_subodhini` | BPHS with Subodhini commentary | Khemraj Shrikrishnadas, 1923 (Sanskrit + Hindi) | pre-1930 imprint; CC0 scan release |
| `saravali_manuscript` | Saravali (Kalyana Varma) | Gurukul Kangri manuscript scan (Sanskrit, partial) | CC0 release |
| `tetrabiblos` | Ptolemy's Tetrabiblos | J. M. Ashmand trans., 1900 printing | pre-1930; Project Gutenberg PD-in-USA |
| `lilly_introduction` | An Introduction to Astrology (Lilly/Zadkiel) | H. G. Bohn, 1852 | pre-1930; archive `NOT_IN_COPYRIGHT` |
| `sepharial_horoscope` | How to Make and Read Your Own Horoscope (Sepharial) | Project Gutenberg eBook | author d. 1929; PD-in-USA |
| `baughan_influence` | The Influence of the Stars (Rosa Baughan) | Project Gutenberg eBook | PD-in-USA |

Modern copyrighted translations (R. Santhanam, B.V. Raman, G.C. Sharma,
Benjamin Dykes, etc.) are **intentionally excluded** even where the underlying
Sanskrit is ancient. The catalog `license_note` states this rule and
`validate_catalog()` enforces that every entry records rights + a PD basis.

## Workflow

```powershell
python library.py fetch      # download missing texts (archive.org / Gutenberg)
python library.py build      # segment into data/library/index/*.jsonl
python library.py search "marriage seventh house venus delay" --topic marriage
python library.py stats
python library.py verify     # catalog integrity + index coverage
```

`fetch` resolves the `*_djvu.txt` file inside each archive item via the
archive.org metadata API; Gutenberg volumes come from the plain-text cache.
`fetch` is idempotent and never overwrites an existing source file. The
download step needs network; `build`, `search`, `stats` and `verify` are fully
offline. Network failures surface as `LibraryError` and never corrupt state.

## Retrieval design

- **Deterministic keyword scoring** (no embeddings, no network): query tokens
  are expanded with a small fixed synonym map (`seventh`↔`7th`, `dasha`↔`dasa`,
  `saturn`↔`sani`, …), weighted with inverse document frequency, and scored
  against each passage. Ties break on book slug, then passage order.
- **Honest locators**: passages are labelled `leaf N` (scan pages split on form
  feeds) or `passage N` / `ch. IV, passage N` (continuous transcription).
  Locators are text-partition labels, never fabricated printed pages or verse
  numbers. Citations carry the book, translator, edition year, e.g.
  `Phaladeepika (trans. V. Subrahmanya Sastri, 1937), leaf 42`.
- **No invention**: an empty or missing index yields an empty result. The
  answer path falls back to the metadata index alone.
- **OCR hygiene**: page-number lines and garble-dominated lines (replacement
  characters, mostly-symbol strings) are dropped at build time. Devanagari
  volumes are indexed for completeness but cannot match English keyword
  searches — use them for human verification by locator.

## Answer-path integration

`src/chat/orchestrator.py` appends up to three `search_library()` passages
(min score 2.0) to the payload's source references, under a line telling the
model these are verbatim public-domain passages quotable only with book,
edition and locator. The payload's existing no-fabrication header still
applies. If the index was never built, nothing is added and behaviour is
unchanged (`tests/test_library.py` covers both paths).

## Adding a volume

1. Confirm the edition is public domain and can be redistributed; record the
   exact basis (imprint year, archive rights statement, or CC0 release).
2. Add a catalog entry (`slug`, `title`, `short_title`, `format` =
   `gutenberg`/`archive`, `remote_id`, `rights`, `pd_basis`, `categories`).
3. `python library.py verify` must pass; run `fetch` + `build`.
4. Spot-check retrieval quality and citations for two or three queries.
5. `.\dev.ps1 test-one -Path tests/test_library.py` and the full suite.

Promotion of doctrinal *claims* extracted from these volumes into engine rules
still goes through `research_intake.py` — a passage in this library is
evidence, not an automatic rule change.
