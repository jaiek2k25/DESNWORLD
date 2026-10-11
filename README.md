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
├── frontend/                  Vue 3 + Vite web app (GitHub Pages compatible)
│   ├── src/engine/            In-browser pipeline: schema v1, prompts, providers,
│   │                          repair loop — same reports as the Python engine
│   └── src/components/        Scenario tree, overview, comparison, full report, …
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
#    e.g. NVIDIA NIM (https://build.nvidia.com):
#      LLM_API_KEY=nvapi-...
#      LLM_BASE_URL=https://integrate.api.nvidia.com/v1
#      LLM_MODEL_NAME=meta/llama-3.3-70b-instruct

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
python -m pytest engine/tests          # 129 engine tests
cd frontend && npm install && npm test # 75 browser-engine + UI tests
npm run build
```

## Run everything in the website

The web app is a complete DESNWORLD workstation: compose a question, run the full pipeline, and
inspect every result — **Overview**, **Scenario tree**, **Compare** side-by-side, and the **Full
report** (assumptions matrix, triggers, consequences & indicators, uncertainties, missing
information, limitations, evidence ledger) — with local run history and JSON/Markdown export.
Branch expansion (3 sub-branches per node, two levels deep) is one click.

Pick a **Run mode** in the UI:

| Mode | What it does | Credentials |
|------|--------------|-------------|
| **Demo engine** | Deterministic offline pipeline in your browser — the whole workflow, instantly | none |
| **Your AI model** | The real pipeline runs in your browser against any OpenAI-compatible endpoint (`/chat/completions`) | an API key **you** supply at runtime — never embedded in this codebase; stored in memory, or localStorage only if you opt in |
| **DESNWORLD API** | Pipeline runs on a DESNWORLD server (`python -m desnworld.server`, same-origin `/api` or a URL) | keys stay on the server |

Every mode produces the same schema-v1 report (browser and Python engine outputs are
interchangeable — reports generated in the browser pass the Python validator and vice versa).
Provenance rules are enforced identically in both runtimes: fabricated sources are rejected,
unbacked claims are downgraded to AI assumptions, and `data_status` always states honestly what
was and was not checked.

**Browser-side AI notes:** your key is sent only to the endpoint you configure (Authorization
header). The endpoint must allow browser CORS — OpenAI, OpenRouter, Groq and Together generally
do; if yours does not, use API mode or the GitHub Actions workflow. Site operators embed **no**
keys and **no** GitHub tokens; the workflow-dispatch path is never exposed to browsers.

### Local development server (optional)

```bash
# terminal 1 — the local dev API (stdlib only; uses mock output if LLM_API_KEY is unset)
python -m desnworld.server             # http://127.0.0.1:8787

# terminal 2 — the web app (proxies /api to :8787)
cd frontend && npm run dev             # http://localhost:5173
```

## GitHub-first deployment (no personal server required)

### Required GitHub Actions secrets

| Secret | Required | Purpose | NVIDIA NIM example |
|--------|----------|---------|--------------------|
| `LLM_API_KEY` | **yes** (real runs) | API key for an OpenAI-compatible Chat Completions endpoint | `nvapi-…` |
| `LLM_BASE_URL` | no | Endpoint base URL (default `https://api.openai.com/v1`) | `https://integrate.api.nvidia.com/v1` |
| `LLM_MODEL_NAME` | no | Model id (default `gpt-4o-mini`) | `meta/llama-3.3-70b-instruct` |

Set them under **Settings → Secrets and variables → Actions**. Keys live only in server-side
workflow steps — **no tokens or API keys are ever embedded in frontend code**.

### Where the same AI provider can be configured

DESNWORLD supports one AI provider configuration in three places, depending on how you run:

1. **Local engine / dev server** — `.env` at the repo root (`LLM_API_KEY`, `LLM_BASE_URL`,
   `LLM_MODEL_NAME`). Git-ignored; never commit it.
2. **GitHub Actions** — the three repository secrets above (`Generate Scenarios` workflow).
3. **Browser ("Your AI model" mode)** — Run settings in the web app: pick the **NVIDIA NIM**
   (or OpenAI / OpenRouter) preset, paste your own key. The key is kept in your browser only.

All three accept the same OpenAI-compatible providers (NVIDIA NIM, OpenAI, OpenRouter, …).

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

The website's **Run settings → "Prefer a batch run?"** panel documents this flow; the artifact's
`desnworld-report.json` imports cleanly with **Import JSON**.

### GitHub Pages (the interface)

The `Deploy to GitHub Pages` workflow builds `frontend/` and publishes it on every push to
`main` (enable Pages under **Settings → Pages → Source: GitHub Actions**). The build uses
relative asset paths, so it works at `https://<user>.github.io/DESNWORLD/` without configuration.

### Deployment architecture and limitations

**GitHub Pages is a static host, not a backend.** With the in-browser engine it no longer *needs*
one: the **Demo engine** and **Your AI model** modes run the entire pipeline client-side, and the
same static bundle works at `https://<user>.github.io/DESNWORLD/` with zero configuration. What
this architecture means:

- **Real AI runs in the browser use the user's own key.** The site ships no secrets. Users who
  want AI-generated scenarios bring an OpenAI-compatible endpoint and key at runtime. The key
  never touches your servers (there are none) and is never committed or embedded.
- **Browser-side calls need CORS.** If a provider blocks browser requests, the user can run the
  **DESNWORLD API** mode against `python -m desnworld.server` (or any service wrapping
  `ScenarioEngine`) deployed behind HTTPS with authentication and restricted CORS — or use the
  **GitHub Actions** batch path and import the artifact.
- **The GitHub Actions workflow stays a batch fallback** (`workflow_dispatch` with secrets) — and
  is never invoked from the browser. Do not expose a private workflow through a browser-side
  token; a static page cannot hold a GitHub token or AI API key securely.

The local dev server binds to localhost with open CORS and must not be exposed publicly as-is.

### Limitations of this prototype

- **No live market data.** No market-data adapter is enabled; reports state this in
  `data_status` instead of fabricating figures. If you configure licensed data sources of your
  own, their content enters the analysis only as user-supplied evidence.
- **AI output is speculative.** Scenarios are structured possibilities generated by a language
  model, not forecasts. Stances are qualitative ("more likely / plausible / less likely"), never
  computed probabilities. The Demo engine is illustrative output, labelled as such.
- **Educational scope for markets.** No personalized investment advice, no target prices, no
  guaranteed returns.
- **Browser key custody is the user's responsibility.** With "remember key" enabled the key
  lives in that browser's localStorage; anyone with access to the device can read it. Keys can
  also leak via browser extensions — power users should prefer API mode with a server-side key.
- **CORS varies by provider.** Endpoints that block browser calls require API mode or Actions.
- **Schema v1 is young.** Reports carry `schema_version`; consumers accept MAJOR 1 with MINOR ≤
  their own. Breaking changes will bump MAJOR.
- **Cost control.** Real runs make 4+ model calls per report (one per stage, plus repairs and
  expansions). Use the Demo engine to learn the workflow for free.

## Engineering notes

- **Tests**: `engine/tests/` — 129 pytest cases (input validation, schema validation including
  provenance and tree-shape rules, branching/expansion, repair loops, error handling);
  `frontend/tests/` — 75 vitest cases covering the in-browser engine (same four areas plus JSON
  extraction, provider error mapping, and UI smoke tests that mount the real components).
- **Frontend build**: `cd frontend && npm run build` produces `frontend/dist` (static, relative
  paths). Runtime dependencies: Vue only. The app holds no secrets; user keys are runtime-only.
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

Ship an optional hosted scenario service (FastAPI or serverless job queue wrapping
`ScenarioEngine`) with per-user authentication and quota, so users who do not want to bring
their own key can run real AI scenarios without a browser-side key — keeping the BYO-key,
Demo-engine, and GitHub Actions paths as fallbacks. Then: a licensed market-data adapter behind
the existing `data_status` contract, report diffing between runs, and i18n.
