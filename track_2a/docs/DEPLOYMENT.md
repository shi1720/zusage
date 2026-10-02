# Deployment

The working deployment is https://zusage.web.app. Dedicated resources live in GCP project `gen-lang-client-0444960702`; other project services are not modified.

## Firebase and Cloud Run

```bash
cd track_2a
./scripts/deploy.sh
```

Prerequisites: authenticated `gcloud` and Firebase CLI, enabled Cloud Run/Build/SQL/Artifact Registry/Secret Manager/Scheduler/Firebase APIs, the Firebase Hosting site, Artifact Registry repository `zusage`, Cloud SQL instance `zusage-db`, PostgreSQL database/user `zusage`, and the runtime account `zusage-runtime@PROJECT.iam.gserviceaccount.com`.

The runtime account needs Cloud SQL Client and access only to these dedicated secrets:

- `zusage-apertus-key`: organiser-issued Apertus key.
- `zusage-session-key`: stable random signing/encryption secret. Back this up; rotation requires users to enter personal keys again.
- `zusage-database-url`: `postgresql+psycopg://USER:PASSWORD@/zusage?host=/cloudsql/PROJECT:europe-west1:zusage-db`.
- `zusage-harness-key`: private benchmark harness token.
- `zusage-task-key`: random scheduler authentication token.
- `zusage-push-private` and `zusage-push-public`: matching VAPID P-256 keys (base64url DER private and uncompressed public).

Create an hourly HTTP Cloud Scheduler job for the Cloud Run `/api/workspace/scheduled-scan` URL, with `X-Zusage-Task-Key` holding the scheduler token. Never commit secret values or scheduler headers. The endpoint rejects unauthenticated requests, skips fictional/demo accounts, prepares drafts and handles optional push. It also purges old transcript text.

Set `GCP_PROJECT`, `GCP_REGION` and `FIREBASE_SITE` to use another provisioned deployment. Firebase routes `/api/**` and `/v1/**` to Cloud Run; `__session` is deliberately the authentication cookie name because Hosting forwards that cookie. PostgreSQL persists data across deployments.

## School server or local Apertus

```bash
cp .env.example .env
make run
# Or a local quantized Apertus server:
make run-local
```

Configure Apertus 1.5 8B through `LLM_NAME`, `LLM_BASE_URL` and `LLM_API_KEY`. The operator can host that same model locally; users cannot select another model/provider. SQLite defaults to a Docker volume; PostgreSQL is available for a larger deployment. Disable demo seed accounts, set secure cookies and use HTTPS before a real school rollout.

A complete local interview was measured on an Apple M4 Pro with 24 GiB unified memory using a community 4-bit Apertus 1.5 8B MLX conversion: 8 answers, 9 calls (1.12 per answer), no fallback turns, 5.155 GiB peak Metal allocation, 3.628 GiB peak process RSS and 87.13 seconds total. Apple Metal uses shared memory rather than dedicated NVIDIA VRAM. See `data/eval/results/local-apertus-hardware-test.json` for the measured run. The Docker image was built and verified on Cloud Run; NVIDIA Docker inference has not been hardware-tested.

## Recovery and cost

Cloud SQL has automated backups. Firebase static releases can be rolled back; Cloud Run retains service revisions. Do not rotate secrets casually. Cloud Run is limited to two instances, but Cloud SQL has a standing cost and model usage consumes organiser quota. Delete only dedicated Zusage resources when retiring the demo.
