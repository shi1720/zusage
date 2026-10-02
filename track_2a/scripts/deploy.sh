#!/usr/bin/env bash
# Deploy the tested container and frontend to an existing, provisioned GCP project.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="${GCP_PROJECT:-gen-lang-client-0444960702}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE="zusage"
SITE="${FIREBASE_SITE:-zusage}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/zusage/app:$(git rev-parse --short HEAD)"
ACCOUNT="zusage-runtime@$PROJECT.iam.gserviceaccount.com"
command -v gcloud >/dev/null
command -v node >/dev/null
(cd src/backend && uv run --extra dev pytest -q && uv run --extra dev ruff check zusage tests)
(cd src/frontend && npm ci --no-audit --no-fund && npm run build && npm test)
gcloud builds submit . --tag "$IMAGE" --project "$PROJECT" --quiet
gcloud run deploy "$SERVICE" --image "$IMAGE" --project "$PROJECT" --region "$REGION" \
  --service-account "$ACCOUNT" --allow-unauthenticated --port 8080 \
  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 2 --concurrency 8 --timeout 60 \
  --add-cloudsql-instances "$PROJECT:$REGION:zusage-db" \
  --set-env-vars "LLM_NAME=apertus-v1.5-8b,LLM_BASE_URL=https://hackapertus.livemap.sh/v1,ZUSAGE_COOKIE_SECURE=true,ZUSAGE_SEED_DEMO=true,ZUSAGE_ISOLATE_DEMO=true,ZUSAGE_LLM_TIMEOUT_S=12,ZUSAGE_LLM_MAX_RETRIES=0,ZUSAGE_TTS_ENABLED=true,ZUSAGE_TTS_PROJECT=$PROJECT" \
  --set-secrets 'LLM_API_KEY=zusage-apertus-key:latest,ZUSAGE_SECRET_KEY=zusage-session-key:latest,ZUSAGE_DATABASE_URL=zusage-database-url:latest,ZUSAGE_HARNESS_KEY=zusage-harness-key:latest,ZUSAGE_TASK_KEY=zusage-task-key:latest,ZUSAGE_PUSH_PRIVATE_KEY=zusage-push-private:latest,ZUSAGE_PUSH_PUBLIC_KEY=zusage-push-public:latest' \
  --quiet
# The config targets only the named Hosting site, not any other project sites.
FIREBASE_CONFIG=$(mktemp)
trap 'rm -f "$FIREBASE_CONFIG"' EXIT
python3 - "$SITE" "$REGION" "$FIREBASE_CONFIG" <<'PY'
import json,sys
from pathlib import Path
site,region,path=sys.argv[1:]
config=json.loads(Path('firebase.json').read_text())
config['hosting']['site']=site
for rewrite in config['hosting']['rewrites']:
    if 'run' in rewrite:
        rewrite['run']['region']=region
# Firebase resolves public paths relative to its config, so use an absolute path.
from pathlib import Path
config['hosting']['public']=str(Path('src/frontend/dist').resolve())
Path(path).write_text(json.dumps(config))
PY
npx --yes firebase-tools@15.32.1 deploy --only hosting --project "$PROJECT" --config "$FIREBASE_CONFIG" --non-interactive
# Wait for Hosting rewrites to propagate before the end-to-end check.
python3 - "$SITE" <<'PYREADY'
import sys,time,json,urllib.request
url=f"https://{sys.argv[1]}.web.app/api/config"
for attempt in range(30):
    try:
        with urllib.request.urlopen(url,timeout=10) as response:
            assert json.load(response)["mode"] in ("live","offline")
        break
    except Exception:
        if attempt == 29: raise
        time.sleep(2)
PYREADY
uv run --project src/backend zusage selfcheck --url "https://$SITE.web.app"
printf '\nZusage is live at https://%s.web.app\n' "$SITE"
