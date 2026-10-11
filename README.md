<div align="center">

# DESNWORLD

**A general-purpose AI scenario exploration engine — possibilities, not predictions.**

Ask a question, and DESNWORLD grows a scenario tree: a baseline future, three meaningfully
different alternative branches, the triggers that would select each one, the assumptions and
evidence behind them, and a comparison report explaining how the scenarios differ.

</div>

---

## What DESNWORLD does

DESNWORLD helps users **explore possible futures** for a question. Every run produces:

- a **baseline scenario** with documented assumptions;
- **exactly three meaningfully different alternative branches**;
- the **triggers** — concrete events or conditions — that would push the future toward each branch;
- **uncertainties, missing evidence, and possible consequences**, stated honestly;
- a side-by-side **comparison report**;
- the option to **explore any branch further** and generate sub-branches.

The first module is **educational stock-market scenario analysis**. The engine is domain-aware
(general, stock market education, business, technology) and designed to grow into business
strategy, product launches, technology trends and other complex decisions.

DESNWORLD explores possibilities. It does **not** pretend to predict the future with certainty,
does **not** present model output as reliable price predictions, and does **not** provide
personalized buy/sell instructions or guaranteed returns.

## Repository layout

```
DESNWORLD/
├── engine/                    Python package `desnworld` — the scenario engine
│   ├── desnworld/
│   │   ├── schema.py          Versioned scenario-report schema (v1) + validators
│   │   ├── input_validation.py  Question / domain / horizon / evidence validation
│   │   ├── prompts.py         One model, separate prompts per pipeline stage
│   │   ├── providers.py       OpenAI-compatible provider + deterministic mock
│   │   ├── engine.py          Pipeline: validate → baseline → 3 branches → …
│   │   ├── llm_client.py      OpenAI-compatible client (adapted from MiroFish)
│   │   ├── report.py          JSON/Markdown report serialization
│   │   ├── cli.py             CLI used by GitHub Actions and local runs
│   │   └── server.py          Optional local dev API (stdlib, no framework)
│   └── tests/                 pytest suite (129 tests)
├── frontend/                  Vue 3 + Vite static SPA (GitHub Pages compatible)
│   └── src/                   Scenario tree, detail panel, comparison view, …
├── .github/workflows/
│   ├── generate-scenarios.yml workflow_dispatch remote generation → artifact
│   ├── ci.yml                 Engine tests + frontend production build
│   └── deploy-pages.yml       GitHub Pages deployment
├── LICENSE                    AGPL-3.0 (upstream MiroFish licence, preserved)
└── NOTICE.md                  Upstream attribution and derivation notes
```

## The AI scenario engine

One configurable external AI model (any OpenAI-compatible Chat Completions endpoint) performs
multiple tasks through **separate prompts**:

| # | Stage | Prompt | Output |
|---|-------|--------|--------|
| 1 | Validate the user's question | — (pure code) | normalized request |
| 2 | Collect/accept evidence | — (pure code) | evidence ledger |
| 3 | Establish baseline + assumptions | `baseline_prompt` | `baseline` scenario |
| 4 | Generate exactly 3 alternatives | `alternatives_prompt` | `alternatives[]` |
| 5 | Explain distinguishing triggers | `alternatives_prompt` | `triggers[]` per branch |
| 6 | Uncertainties, missing evidence, consequences | `uncertainties_prompt` | `uncertainties[]`, `missing_information[]`, `limitations[]` |
| 7 | Validate structured response | — (schema v1 + provenance rules) | bounded repair loop |
| 8 | Comparison report | `comparison_prompt` | `comparison` |
| 9 | Explore a branch → sub-branches | `sub_branch_prompt` | `children[]` (up to 2 levels deep) |

**Honesty rules enforced in code, not just in prompts:**

- Every claim is tagged `sourced_fact`, `user_supplied_fact`, or `ai_assumption`.
- A `sourced_fact` must carry a real `source_uri` or point to user-supplied evidence — otherwise
  the engine deterministically downgrades it to `ai_assumption` (and the validator rejects
  fabricated provenance outright).
- `data_status.live_market_data_checked` records whether any live data was actually queried.
  The prototype ships **without** a market-data adapter and reports this limitation instead of
  inventing numbers.
- Malformed model output is never "repaired" into invented content: truncated JSON is rejected,
  and at most one bounded repair prompt is attempted per stage before a structured error.

Reports are versioned JSON documents (`schema_version: 1.0.0`, MAJOR-compat policy documented in
`engine/desnworld/schema.py`) that round-trip through the CLI, the workflow artifact, and the web
interface.

## Quick start (local development)

Prerequisites: Python 3.10+, Node.js 18+.

```bash
# 1. Install the engine (and its dev dependencies)
python -m venv .venv && source .venv/bin/activate
pip install -e "./engine[dev]"

# 2. Configure credentials for real generation (any OpenAI-compatible endpoint)
cp .env.example .env       # then edit LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME

# 3. Run a scenario (use --mock for an offline demo without any key)
python -m desnworld.cli \
  --question "How might AI regulation affect semiconductor stocks over the next year?" \
  --domain stock_market_education --horizon 12 \
  --output report.json --markdown

# 4. Optionally expand a branch into 3 sub-branches
python -m desnworld.cli --expand alt-1 --from-report report.json --output report.json

# 5. Validate any report against schema v1
python -m desnworld.cli --validate-only report.json
```

Run the tests and the frontend build:

```bash
python -m pytest engine/tests          # 129 tests
cd frontend && npm install && npm run build
```

### Local web interface + dev API

```bash
# terminal 1 — the local dev API (stdlib only; uses mock output if LLM_API_KEY is unset)
python -m desnworld.server             # http://127.0.0.1:8787

# terminal 2 — the web interface
cd frontend && npm run dev             # http://localhost:5173 (proxies /api to :8787)
```

In the UI, open **configure endpoint** and use `http://127.0.0.1:8787`, then **Generate
Scenarios**. Without any endpoint the interface still works fully for exploring, comparing,
importing and downloading reports, plus a bundled demo report.

## GitHub-first deployment (no personal server required)

### Required GitHub Actions secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `LLM_API_KEY` | **yes** (real runs) | API key for an OpenAI-compatible Chat Completions endpoint |
| `LLM_BASE_URL` | no | Endpoint base URL (default `https://api.openai.com/v1`) |
| `LLM_MODEL_NAME` | no | Model id (default `gpt-4o-mini`) |

Set them under **Settings → Secrets and variables → Actions**. Keys live only in server-side
workflow steps — **no tokens or API keys are ever embedded in frontend code**.

### Run your first DESNWORLD simulation (GitHub Actions)

1. Push this repository to GitHub (or use this fork) and open the **Actions** tab.
2. Select the **Generate Scenarios** workflow → **Run workflow**.
3. Fill in the inputs, for example:
   - `question`: `How might shifts in interest-rate expectations affect broad equity markets over the next year?`
   - `domain`: `stock_market_education`
   - `horizon_months`: `12`
   - `evidence` (optional): one fact per line, e.g. `Historical example (educational): the 2022 rate-hiking cycle coincided with broad equity drawdowns before a partial recovery.`
   - `expand_scenario_id` (optional): `alt-1`
   - `use_mock`: leave `false` for a real AI run, or `true` for an offline smoke test
4. When the run finishes, download the **`desnworld-report`** artifact (`desnworld-report.json`).
5. Open the deployed web interface (or `frontend` locally) → **Import JSON** → explore the tree,
   switch to **Compare**, and **Download JSON** whenever you want a copy.

The web interface's **Generate Scenarios** button can also copy ready-to-paste workflow inputs to
the clipboard for this exact flow.

### GitHub Pages (the interface)

The `Deploy to GitHub Pages` workflow builds `frontend/` and publishes it on every push to
`main` (enable Pages under **Settings → Pages → Source: GitHub Actions**). The build uses
relative asset paths, so it works at `https://<user>.github.io/DESNWORLD/` without configuration.

### Deployment architecture and limitations

**GitHub Pages is a static host, not a backend.** It serves the interface and demo data; it
cannot call AI models. Interactive, on-demand generation in the browser therefore requires one
of:

1. **GitHub Actions** (implemented): manual `workflow_dispatch` runs the pipeline remotely with
   secrets, uploads the JSON report as a downloadable artifact — no server at all. This is the
   recommended prototype path.
2. **A secure backend or job service** (documented, not shipped): deploy `engine/desnworld/server.py`
   (or any service wrapping `ScenarioEngine`) behind HTTPS with authentication and restricted
   CORS, and point the interface's **configure endpoint** field at it. For public use this is
   required: never expose a private workflow through a browser-side token — a static page cannot
   hold a GitHub token or AI API key securely.

The local dev server (`python -m desnworld.server`) is a convenience for development only: it
binds to localhost with open CORS and must not be exposed publicly as-is.

### Limitations of this prototype

- **No live market data.** No market-data adapter is enabled; reports state this in
  `data_status` instead of fabricating figures. If you configure licensed data sources of your
  own, their content enters the analysis only as user-supplied evidence.
- **AI output is speculative.** Scenarios are structured possibilities generated by a language
  model, not forecasts. Stances are qualitative ("more likely / plausible / less likely"), never
  computed probabilities.
- **Educational scope for markets.** No personalized investment advice, no target prices, no
  guaranteed returns.
- **Manual generation trigger.** On-demand, in-browser generation needs the secure backend
  described above; the Actions path is intentionally manual (`workflow_dispatch`).
- **Schema v1 is young.** Reports carry `schema_version`; consumers accept MAJOR 1 with MINOR ≤
  their own. Breaking changes will bump MAJOR.
- **Cost control.** Real runs make 4+ model calls per report (one per stage, plus repairs and
  expansions). Use `use_mock: true` to smoke-test the workflow for free.

## Engineering notes

- **Tests** (`engine/tests/`): input validation, schema validation (including provenance and
  tree-shape rules), scenario branching and sub-branch expansion, repair loops, and error
  handling (missing credentials, malformed JSON, rate limits, timeouts, CLI exit codes).
- **Frontend build**: `cd frontend && npm run build` produces `frontend/dist` (static, relative
  paths). The app has no runtime dependencies beyond Vue and never holds credentials.
- **Credentials**: `.env` is git-ignored; only `.env.example` is committed. Never commit real
  keys or generated sensitive data.

## Relationship to MiroFish & licence

DESNWORLD is built on code and patterns derived from
[MiroFish](https://github.com/666ghj/MiroFish) (a multi-agent swarm-intelligence simulation
engine), redistributed under the **GNU Affero General Public License v3.0** — the original
MiroFish licence, preserved in [`LICENSE`](./LICENSE).

The MiroFish LLM utility layer (`llm_client.py`, `openai_chat_compat.py`, `retry.py`, config
pattern) is adapted in `engine/desnworld/` with attribution headers. The swarm-simulation stack
(OASIS platforms, Zep memory graphs, GraphRAG environment building) is intentionally not
redistributed; DESNWORLD replaces it with the scenario pipeline described above. See
[`NOTICE.md`](./NOTICE.md) for the full derivation record.

## Recommended next milestone

Deploy a minimal authenticated scenario service (FastAPI/Flask or a serverless job queue) that
wraps `ScenarioEngine`, add a market-data adapter behind the existing `data_status` contract with
licensed sources, and wire the interface's Generate action to it — keeping the GitHub Actions
path as a batch fallback. After that: richer branching depth controls, report diffing between
runs, and i18n.
