# NexusHelper setup checklist

## What is configured in this repository

- FastAPI backend and a Vite/React UI.
- Firebase ID token verification, enabled only when configured.
- FalkorDB repository and a synthetic Cypher schema/seed.
- GCP/Firebase resources are provisioned separately; credentials and endpoints are supplied through environment variables or Secret Manager.
- Gemini and Groq adapters keep API keys on the backend, verify citations, and fall back to deterministic local responses if hosted model calls fail.
- Profile and trusted membership repositories support local files for development and Firestore when `PROFILE_STORE=firestore`.

## Shared company data and desktop sign-in

NexusHelper is intended to have a web UI and installable desktop clients. Desktop sign-in should use the system browser (company identity provider/Firebase Authentication) and return to the app using a registered deep link or loopback callback. The desktop client must not contain Firebase server credentials, model API keys, or database credentials.

Firebase Authentication proves the user's identity; it does not by itself provide shared company authorization. Firestore is a good shared store for user profiles, organization membership references, team metadata, and audit metadata. Access decisions must be derived from company-owned memberships and enforced by the API. A designation and keywords entered by a user are searchable profile metadata only and must never grant access.

The current implementation uses FalkorDB for a separate graph per company. Firestore stores profiles, companies, invitations, and memberships; the backend routes each company to its graph. Keep FalkorDB reachable only by the backend and do not connect desktop clients directly to it. The API is the trusted boundary for authorization, graph queries, and model access. New company graphs are empty until records are ingested; import connectors are not yet implemented.

For a genuinely local-only mode, the API and graph may run on the user's machine, but that mode does not share company data by itself. The planned cross-company mode requires a hosted API and shared database services reachable by all authorized clients.

The UI includes a platform download page, but release installers are not published yet. Do not advertise downloadable builds until Linux (AppImage/.deb), macOS, and Windows packages are built, signed where applicable, and hosted at stable release URLs.

## Local development

1. Install Python dependencies and run `uvicorn app.main:app --reload`.
2. In `frontend/`, run `npm install`, copy `.env.example` to `.env`, then run `npm run dev`. If Firebase config is blank, click **Try demo**; the demo principal is synthetic and local-only.
3. In Firebase Console, create/select a project and register a Web App. Enable Authentication > Google (or your company identity provider). Copy the web config into `frontend/.env`.
4. For a local graph-backed demo, start FalkorDB locally and set `FALKORDB_*` in root `.env`; run `./.venv/bin/python scripts/setup_local_falkordb.py` to load the fictional seed into an empty local graph. Alternatively, leave the example settings to use the synthetic in-memory demo graph.
5. For local Firebase API auth, configure Application Default Credentials and `FIREBASE_AUTH_ENABLED=true`, `FIREBASE_PROJECT_ID=<project-id>`. Set the allowed frontend origin. Local demo auth uses server-configured `X-Demo-User` identities and must never be enabled in production.

The designation and keyword fields are searchable profile details; they do not change access. In Firestore mode, users create a company or join through an invitation sent to their verified email. The company creator becomes its first owner and can invite teammates with selected team IDs and an optional 1–90 day expiry. Membership records are stored in `nexushelper_memberships`; each company maps to its own FalkorDB graph. The API uses Application Default Credentials locally and its Cloud Run runtime identity in production.

### Model providers

Set `MODEL_PROVIDER=groq` and `GROQ_API_KEY` to use Groq as the primary hosted model; `GEMINI_API_KEY` enables the optional Gemini fallback. The deterministic local provider is the final fallback. The current query path invokes the configured model for lookup, contextual, and investigation questions, using the retrieved graph facts as grounding context. `GEMINI_API_KEY` and `GROQ_API_KEY` are backend secrets only; never add them to `frontend/.env`, `VITE_*`, source control, the desktop bundle, or a browser request. You can set model names with `GEMINI_MODEL` and `GROQ_MODEL`.

### Shared Firestore configuration

Set `PROFILE_STORE=firestore` and `FIRESTORE_PROJECT_ID` (or reuse `FIREBASE_PROJECT_ID`). Locally, use `gcloud auth application-default login`; in Cloud Run, grant the runtime service account `roles/datastore.user`. Do not download or commit a service-account JSON file. Firestore stores profile and trusted membership documents; the query graph itself still requires a centrally reachable FalkorDB endpoint.

## Before deploying to GCP

1. Choose or create the GCP project and link Firebase to that project. Enable billing if required by the services you choose.
2. Decide where FalkorDB will run and how it will be network-restricted. Do not expose its port publicly. Put credentials in Secret Manager and grant the backend service account access to only those secrets.
3. Deploy the API (for example Cloud Run), use a dedicated service account and Application Default Credentials, and set `APP_ENV=production`, `DEMO_AUTH_ENABLED=false`, `FIREBASE_AUTH_ENABLED=true`, `FIREBASE_PROJECT_ID`, `PROFILE_STORE=firestore`, `FALKORDB_*`, `MODEL_PROVIDER=groq`, the model secret references, and the exact `FRONTEND_ORIGIN`.
4. Host the frontend (Firebase Hosting or another static host), set its public Firebase `VITE_*` values at build time, and configure `VITE_API_URL` to the deployed API. Only Firebase Web App config belongs in Vite; all provider and database secrets stay on the backend.
5. Configure authorized domains and the allowed sign-in provider in Firebase Authentication. Verify company creation, invitation acceptance, ownership transfer, and temporary team expiry.
6. Add backups, retention, audit logging, monitoring, and access reviews before loading company records.

GCP resources are not created automatically by the app. Provision them in the intended Google Cloud/Firebase project and verify project IDs before deploying.

The Firebase Hosting configuration and GitHub Actions workflow can deploy the frontend after a Firebase service-account secret and `FIREBASE_PROJECT_ID` repository variable are configured. The live frontend and API endpoints are listed in the repository README. A successful API health check does not confirm that sign-in, model generation, or FalkorDB queries are healthy; verify those paths separately before relying on company data.

`deploy/deploy-cloud-run.sh <project-id> [region]` deploys only to the explicitly supplied project. Before running it, create the `nexushelper-runtime` service account, grant it Firestore access for the companies, invitations, memberships, and profiles collections and Secret Manager accessor access to the named secrets, create/populate those secrets, and make the FalkorDB endpoint reachable from Cloud Run. This script deliberately does not infer the project from the local gcloud default.

## Desktop release builds

The Tauri 2 wrapper is in `frontend/src-tauri`. A tag matching `v*` triggers Linux AppImage/deb, macOS dmg, and Windows NSIS builds. The workflow creates a **draft** GitHub release for review; publish it only after configuring repository variables for the deployed API and public Firebase Web App settings, checking sign-in in each OS build, and reviewing unsigned-package warnings. Apple notarization and Windows code signing are not configured yet.
