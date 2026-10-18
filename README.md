# NexusHelper

A permission-aware organisational knowledge assistant built around FalkorDB. The starter focuses on the query path: cost-tiered routing, permission-scoped graph retrieval, evidence-grounded answers, and observable traces.

## Architecture

- **Tier 0 — Cache:** permission-scope keyed semantic cache; zero model calls.
- **Tier 1 — Lookup:** scoped graph retrieval and concise response.
- **Tier 2 — Contextual:** multi-hop context retrieval and synthesis.
- **Tier 3 — Investigation:** context and incident history, investigation, deterministic verification, and cited response.
- **Security boundary:** authentication and permissions are enforced in backend query construction before graph results reach any model.

The starter uses deterministic query routing, a permission-scoped graph repository, citation verification, Groq synthesis with optional Gemini fallback, and explicit abstention when evidence is missing. Company records, verified memberships, and invitations use shared Firestore. Every company receives a separate FalkorDB graph. The company creator becomes its first owner and can invite teammates by verified email, with optional temporary team access.

## Quick start

Requires Python 3.11+.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal, run the UI:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Without Firebase Web settings, click **Try demo** in the UI. Local demo mode uses the synthetic Alice/Platform identity and the synthetic graph; it is for development/demo only. For a real shared workspace, provision Firebase Authentication, Firestore, a private FalkorDB service, and configure production API secrets as described in [docs/SETUP.md](docs/SETUP.md).

Open `http://127.0.0.1:8000/docs` for the API docs. `POST /api/query` returns a selected tier, evidence, and a model-call trace. Without a trusted identity and FalkorDB connection, the API abstains. Never put user-controlled permission scopes into production requests.

For local graph development, start FalkorDB with `docker run --rm -p 6379:6379 falkordb/falkordb:latest`, set connection values in `.env`, then apply statements in `schema.cypher` one at a time using FalkorDB Browser or `redis-cli GRAPH.QUERY`. The schema contains synthetic demo data; do not expose it to real users.

See [docs/SETUP.md](docs/SETUP.md) for Firebase, database, and GCP provisioning steps.

NexusHelper is planned as both a browser app and installable desktop app. The UI has a platform downloads page, but installers are not published yet. Company-wide sharing requires a hosted API and shared database; a local-only install cannot share records with other employees by itself. See the shared-data and desktop-auth notes in the setup guide.

## Local configuration

Copy `.env.example` to `.env`. Never commit `.env`, credentials, or real company data. The starter intentionally contains no provider keys.

## Companies and teams

Sign in with a verified Firebase identity, then create a company or accept a one-time invitation. The creator becomes a company owner. Owners invite people by email, assign team IDs, and can set access to expire after 1–90 days. Leaving the expiry blank grants continuing membership. Company data is isolated in a dedicated FalkorDB graph; Firestore stores company, invitation, and membership records. User-entered designation and keywords are profile details, never access grants.

## Roadmap

1. Provision the intended Firebase/GCP project, enable sign-in and Firestore, and configure runtime credentials.
2. Provision a private FalkorDB service and connect it to the API through a private endpoint.
3. Configure Gemini and Groq secrets, then validate grounded responses and team-scoped access with synthetic data.
4. Configure company ownership, team membership, operational monitoring, backups, and retention.
5. Publish signed web and desktop releases after end-to-end sign-in and authorization review.

## License

All rights reserved. This project is currently private and unlicensed.
