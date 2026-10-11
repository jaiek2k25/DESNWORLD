# NOTICE

## Upstream project

DESNWORLD reuses source code and design patterns from **MiroFish**

- Project: https://github.com/666ghj/MiroFish
- Copyright (c) MiroFish authors and contributors (666ghj and others)
- Licence: GNU Affero General Public License v3.0 (AGPL-3.0)

DESNWORLD is a modified and redistributed work derived in part from MiroFish and
is therefore also licensed under **AGPL-3.0**. The full licence text is in
[`LICENSE`](./LICENSE).

## Files derived from MiroFish

The following files are adapted from MiroFish source files (originally located
under `backend/app/utils/` and `backend/app/config.py` in the upstream project).
They were modified for the DESNWORLD scenario-exploration engine (renamed
modules, English documentation, DESNWORLD configuration keys, and scenario
pipeline integration):

| DESNWORLD file | Derived from |
| --- | --- |
| `engine/desnworld/llm_client.py` | `backend/app/utils/llm_client.py` |
| `engine/desnworld/openai_chat_compat.py` | `backend/app/utils/openai_chat_compat.py` |
| `engine/desnworld/retry.py` | `backend/app/utils/retry.py` |
| `engine/desnworld/config.py` | `backend/app/config.py` (pattern) |

Every derived file carries an attribution header naming the upstream project.

## Changes relative to MiroFish

MiroFish is a multi-agent swarm-simulation engine (OASIS social simulation, Zep
memory graphs, GraphRAG environment building, ReportAgent). DESNWORLD is a
general-purpose **scenario exploration** engine: it replaces the swarm
simulation layer with a structured scenario pipeline (baseline + three
alternative branches, triggers, uncertainties, comparison report, sub-branch
expansion) with a versioned JSON schema. The simulation, memory-graph and
platform-integration layers of MiroFish are intentionally **not** redistributed
in this repository.

New work in this repository (scenario schema, branching engine, prompts, web
interface, GitHub Actions workflows, tests) is original DESNWORLD code, licensed
under the same AGPL-3.0 terms.

## Attribution in outputs

Generated DESNWORLD scenario reports record the generator name and engine
version in the `generator` block of the JSON report.
