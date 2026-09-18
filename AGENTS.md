# SweetAstro — Agent Notes

Project: chat-based Vedic astrology answer engine (`C:\Users\Dell -\Documents\Code\SweetAstro`).
Package is imported as `SweetAstro.src...` (the parent directory `Documents\Code` must be on
`sys.path`; `conftest.py` handles this under pytest).

## Answer protocol (user directive — apply to every request)

1. **Before starting:** state what the user expects and how to provide the best result.
2. **After the final answer:** check whether the result is genuinely best for the user;
   if not, revise before delivering.

## Fast development loop (use this, not deploy, while iterating)

| Change | Command | Time |
|---|---|---|
| UI only, legacy pages (`src/api/static/*.html`) | **no restart** — pages are read from disk per request; just refresh the browser | 0 s |
| UI only, new app (`frontend/src`) | `.\dev.ps1 dev-all` once → Vite HMR at http://localhost:5174/static/app/; or `.\dev.ps1 ui-watch` to keep `/app` fresh | instant / ~1 s |
| Frontend toolchain, first time | `.\dev.ps1 ui-install` | ~30 s |
| Backend code | `.\dev.ps1 dev` once → server auto-reloads on every save (skips network preflight) | ~3 s |
| One backend change without reload | `.\dev.ps1 restart` | ~2 s |
| One test file | `.\dev.ps1 test-one -Path tests/test_x.py` | ~3 s |
| Last-failed tests only | `.\dev.ps1 test-quick` | ~4 s |
| Full suite before ship | `.\dev.ps1 test` | ~7 s |
| Ship | `.\dev.ps1 deploy` (preflight → web build only if changed → fast tests → restart → health) | ~15 s |

Notes:
- `dev.ps1` ends with `[Environment]::Exit()`, so anything chained after it in the same
  shell will not run. Call it as the final command of a shell invocation.
- Test subsetting: `slow`-marked tests (120-day panchanga scan) are excluded from
  `test-fast`/`test-quick`; `pytest.ini` also prunes unused plugins to cut startup.
- Measured loop on this machine: `test-one` ~3 s · `test-quick` ~4 s ·
  `test-fast` ~10 s · full `test` ~13 s · `deploy` ~8 s when the web build is
  skipped (`deploy` auto-skips the UI build when nothing under `frontend/` changed).
- First `test`/`deploy` run after `npm install` or a fresh UI build can be much
  slower (Windows Defender/indexer scanning new files). Subsequent runs are fast;
  no code change is needed. Reducing build churn (latin-only font subsets) keeps it that way.
- `pytest.exe` (user Scripts dir) is used automatically when present — faster than `python -m pytest`.
- Network-dependent preflight cannot run offline: use `SWEETASTRO_SKIP_NET_CHECK=1`
  (already set by `.\dev.ps1 dev`).
- Verify endpoints by HTTP after backend changes: `GET /api/health`, pages `/`, `/match`,
  `/dashboard`.

## Testing conventions

- All tests live in `tests/`, run with `python -m pytest` (or via `dev.ps1`).
- Deterministic engine calls are real in tests; LLM calls are mocked with fake clients.
- New behavior must ship with tests; audit rounds live in `tests/test_audit_round*.py`.
- Accuracy claims: governed by `docs/accuracy_protocol.md`; never claim timing accuracy
  without a passed, pre-registered run.

## Key entry points

- Chat orchestrator: `src/chat/orchestrator.py` · prompts `src/chat/prompt.py`
- Web app (React SPA at `/app`): `frontend/` · `POST /api/chart` · golden tests `tests/test_app_ui.py`
- Consumer engine: `src/consumer.py` · answer format `src/llm/consumer_answer_engine.py`
- Event timing: `src/prediction/event_timing.py` · matching: `src/core/matching.py`
- Rules: `src/rules/evaluator.py` + `data/rules/*.json`
- Research intake (sourced claims, quarantined): `research_intake.py` · `src/knowledge/intake.py`
- Public-domain library (full text + citations): `library.py` · `src/knowledge/library.py` · `data/library/catalog.json`
- Video method pipeline (dev-only research→fallback): `video_research.py` · `src/research_pipeline/` · packs `src/methods/` + `data/methods/` · doc `docs/research/video_method_pipeline.md`
- Accuracy: `accuracy_backtest.py`, `src/evaluation/`, manifest `data/accuracy_manifest.json`
