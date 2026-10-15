# Company Brain

A permission-aware organisational knowledge assistant built around FalkorDB. The starter focuses on the query path: cost-tiered routing, permission-scoped graph retrieval, evidence-grounded answers, and observable traces.

## Architecture

- **Tier 0 — Cache:** permission-scope keyed semantic cache; zero model calls.
- **Tier 1 — Lookup:** scoped graph retrieval and concise response.
- **Tier 2 — Contextual:** multi-hop context retrieval and synthesis.
- **Tier 3 — Investigation:** context and incident history, investigation, deterministic verification, and cited response.
- **Security boundary:** authentication and permissions are enforced in backend query construction before graph results reach any model.

The initial implementation is deliberately a small, inspectable API scaffold rather than pretending the agent components are already operational. FalkorDB, model, and embedding integrations are explicit next steps.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API docs. `POST /query` returns a demo answer, selected tier, evidence, confidence, and a model-call trace. The demo fixture does not connect to FalkorDB and is not suitable for production data.

## Local configuration

Copy `.env.example` to `.env`. Never commit `.env`, credentials, or real company data. The starter intentionally contains no provider keys.

## Repository notes

`docs/AGENT_HANDOFF.md` contains local development context and is excluded from Git. Keep it on this machine; do not force-add it.

## Roadmap

1. Add authentication and derive permission scope from trusted identity claims.
2. Add FalkorDB access with query-time visibility filtering and audit events.
3. Add semantic retrieval/cache keyed by permission scope.
4. Implement tier routing, model adapter, deterministic verification, citations, and abstention.
5. Add seeded synthetic graph fixtures and a graph/trace demo UI.
6. Add feedback and reviewed graph write-back.

## License

All rights reserved. This project is currently private and unlicensed.
