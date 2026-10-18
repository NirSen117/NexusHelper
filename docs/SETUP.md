# NexusHelper setup checklist

## What is configured in this repository

- FastAPI backend and a Vite/React UI.
- Firebase Admin token verification code, enabled only when configured.
- FalkorDB repository and a synthetic Cypher schema/seed.
- No GCP resources or Firebase project are provisioned by this repository. No database endpoint or credentials are present.
- Gemini and Groq adapters keep API keys on the backend, verify citations, and fall back to deterministic local responses if hosted model calls fail.
- Profile and trusted membership repositories support local files for development and Firestore when `PROFILE_STORE=firestore`.

## Shared company data and desktop sign-in

NexusHelper is intended to have a web UI and installable desktop clients. Desktop sign-in should use the system browser (company identity provider/Firebase Authentication) and return to the app using a registered deep link or loopback callback. The desktop client must not contain Firebase Admin credentials, model API keys, or database credentials.

Firebase Authentication proves the user's identity; it does not by itself provide shared company authorization. Firestore is a good shared store for user profiles, organization membership references, team metadata, and audit metadata. Access decisions must be derived from administrator-managed memberships and enforced by the API. A designation and keywords entered by a user are searchable profile metadata only and must never grant access.

The current query/relationship implementation uses FalkorDB as its graph store. Firestore profile persistence is scaffolded, but is not yet the complete shared knowledge database, and the profile route is not fully connected. To share the actual knowledge graph, either keep a centrally hosted, private FalkorDB service behind the API, or deliberately migrate graph queries and relationships to a Firestore-compatible data model. Do not connect desktop clients directly to a privileged graph database. The API is the trusted boundary for authorization and graph/model access.

For a genuinely local-only mode, the API and graph may run on the user's machine, but that mode does not share company data by itself. The planned cross-company mode requires a hosted API and shared database services reachable by all authorized clients.

The UI includes a platform download page, but release installers are not published yet. Do not advertise downloadable builds until Linux (AppImage/.deb), macOS, and Windows packages are built, signed where applicable, and hosted at stable release URLs.

## Local development

1. Install Python dependencies and run `uvicorn app.main:app --reload`.
2. In `frontend/`, run `npm install`, copy `.env.example` to `.env`, then run `npm run dev`. If Firebase config is blank, click **Try demo**; the demo principal is synthetic and local-only.
3. In Firebase Console, create/select a project and register a Web App. Enable Authentication > Google (or your company identity provider). Copy the web config into `frontend/.env`.
4. Start FalkorDB locally, set `FALKORDB_*` in root `.env`, then apply `schema.cypher` to the `nexushelper` graph one statement at a time. It contains synthetic example records only.
5. For local Firebase API auth, configure Application Default Credentials and `FIREBASE_AUTH_ENABLED=true`, `FIREBASE_PROJECT_ID=<project-id>`. Set the allowed frontend origin. Local demo auth uses server-configured `X-Demo-User` identities and must never be enabled in production.

The UI's designation and keywords are profile metadata. Do not use self-entered title/department as authorization. Backend access comes from Firebase custom claims or the Firestore memberships collection. In Firestore mode create a document in `nexushelper_memberships` keyed by Firebase UID with `{ "team_ids": ["team-platform"], "is_admin": false }`. Bootstrap the first administrator through trusted Firebase custom claims (`admin: true`) or directly through a secured Firestore console process; after that, use the protected `/api/admin/users/{uid}/membership` endpoint. The server uses Application Default Credentials locally and its Cloud Run runtime service account in production.

### Model providers

Set `MODEL_PROVIDER=gemini`, `GEMINI_API_KEY`, and optionally `GROQ_API_KEY`. Gemini is tried first, Groq is the hosted open-weight fallback, and the deterministic local provider is the final fallback. `GEMINI_API_KEY` and `GROQ_API_KEY` are backend secrets only; never add them to `frontend/.env`, `VITE_*`, source control, the desktop bundle, or a browser request. You can set model names with `GEMINI_MODEL` and `GROQ_MODEL`. Straightforward lookups use deterministic grounded responses; model synthesis is reserved for contextual/investigation questions.

### Shared Firestore configuration

Set `PROFILE_STORE=firestore` and `FIRESTORE_PROJECT_ID` (or reuse `FIREBASE_PROJECT_ID`). Locally, use `gcloud auth application-default login`; in Cloud Run, grant the runtime service account `roles/datastore.user`. Do not download or commit a service-account JSON file. Firestore stores profile and trusted membership documents; the query graph itself still requires a centrally reachable FalkorDB endpoint.

## Before deploying to GCP

1. Choose or create the GCP project and link Firebase to that project. Enable billing if required by the services you choose.
2. Decide where FalkorDB will run and how it will be network-restricted. Do not expose its port publicly. Put credentials in Secret Manager and grant the backend service account access to only those secrets.
3. Deploy the API (for example Cloud Run), use a dedicated service account and Application Default Credentials, and set `APP_ENV=production`, `DEMO_AUTH_ENABLED=false`, `FIREBASE_AUTH_ENABLED=true`, `FIREBASE_PROJECT_ID`, `PROFILE_STORE=firestore`, `FALKORDB_*`, `MODEL_PROVIDER=gemini`, the model secret references, and the exact `FRONTEND_ORIGIN`.
4. Host the frontend (Firebase Hosting or another static host), set its public Firebase `VITE_*` values at build time, and configure `VITE_API_URL` to the deployed API. Only Firebase Web App config belongs in Vite; all provider and database secrets stay on the backend.
5. Configure authorized domains and the allowed sign-in provider in Firebase Authentication. Establish an admin-controlled process for assigning and revoking team claims.
6. Add backups, retention, audit logging, monitoring, and access reviews before loading company records.

GCP resources are not created automatically by the app. Provision them in the intended Google Cloud/Firebase project and verify project IDs before deploying.

The Firebase Hosting configuration and GitHub Actions workflow can deploy the frontend after a Firebase service-account secret and `FIREBASE_PROJECT_ID` repository variable are configured. The API still requires a private FalkorDB endpoint and Secret Manager entries before production deploy. Do not advertise a live shared workspace until those health checks pass.

`deploy/deploy-cloud-run.sh <project-id> [region]` deploys only to the explicitly supplied project. Before running it, create the `nexushelper-runtime` service account, grant it Firestore access and Secret Manager accessor access to the three named secrets, create/populate those secrets, and make the FalkorDB endpoint reachable from Cloud Run. This script deliberately does not infer the project from the local gcloud default.

## Desktop release builds

The Tauri 2 wrapper is in `frontend/src-tauri`. A tag matching `v*` triggers Linux AppImage/deb, macOS dmg, and Windows NSIS builds. The workflow creates a **draft** GitHub release for review; publish it only after configuring repository variables for the deployed API and public Firebase Web App settings, checking sign-in in each OS build, and reviewing unsigned-package warnings. Apple notarization and Windows code signing are not configured yet.
