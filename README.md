# Zusage

**Your next chapter starts here.** An Apertus 1.5 8B interview coach for Swiss apprenticeships, built by Shivam Gupta for Hack Apertus 2026, Track 2A / FHGR.

**[Try Zusage](https://zusage.web.app)** - choose a private student or teacher demo, with no registration or API key required.

Zusage helps young people practise realistic interviews, reflect on their own answers, retry with better examples and turn feedback into spaced practice. German, French and Italian meet the challenge requirements. English is the default interface; Swiss German interview practice is also available.

## What you can do

- Practise 12 apprenticeships with three interviewer styles, in training or dress rehearsal mode.
- Get six-criterion feedback with verified quotes, self-assessment, retry comparisons and a final report.
- Build a real story bank, practise due drills and track confidence and progress.
- Track applications, interview dates, company-specific rehearsals and stage history.
- Use Apertus for cover letters, follow-ups, referral requests, LinkedIn messages, thank-you notes and interview prep packs. Review and edit before opening Gmail.
- Capture pasted job adverts or supported public HTTPS posting links, then confirm extracted details.
- Import applications and drafts from CSV, including common Teal/Huntr columns. Repeat imports update existing records and preserve unlinked drafts for later adoption.
- View follow-up reminders, application funnel statistics, weekly goals, momentum and a replayable guided tour.
- Create student or teacher accounts, change your password, save a single-use recovery code, export data and delete your account.
- Use the configured Apertus key immediately, or save an optional personal Apertus key encrypted on the server. There is no model or provider selector.
- Teachers see class progress. Student answer text requires explicit, revocable consent.

## Run and test

```bash
cp track_2a/.env.example track_2a/.env
# Set the Apertus endpoint/key in the ignored .env file.
make run
make test
make lint
```

The container serves the app at `http://localhost:8080`. `make run-local` from `track_2a` starts a local quantized Apertus 8B server. Fonts are bundled. A complete local interview was measured on an Apple M4 Pro with 24 GiB unified memory using a community 4-bit Apertus 1.5 8B MLX conversion: 8 answers, 9 calls (1.12 per answer), no fallback turns, 5.155 GiB peak Metal allocation, 3.628 GiB peak process RSS and 87.13 seconds total. Apple Metal uses shared memory rather than dedicated NVIDIA VRAM. See `data/eval/results/local-apertus-hardware-test.json` for the measured run. The Docker image was built and verified on Cloud Run; NVIDIA Docker inference has not been hardware-tested.

```bash
cd track_2a
uv run --project src/backend python scripts/e2e.py --url https://zusage.web.app
./scripts/deploy.sh
```

The deployment script validates the source, builds the container, deploys only the dedicated Zusage Cloud Run service and Firebase site, waits for routing and runs a live interview selfcheck. It expects the dedicated database, runtime service account and secrets to be provisioned first.

## Measure local Apertus on an Apple Silicon Mac

The optional Metal benchmark runs a complete interview through the same coach engine using real local Apertus weights. It measures peak Metal allocation and process memory, model calls, fallback turns and latency. It does not use the hosted inference endpoint. Run from `track_2a`:

```bash
uv venv .mlx-bench --python 3.12
uv pip install --python .mlx-bench/bin/python ./src/backend mlx-lm
.mlx-bench/bin/hf download tokimoa/apertus-v1.5-8b-mlx-4bit \
  --local-dir models/apertus-mlx --include '*.json' '*.safetensors' '*.txt' '*.model' '*.jinja'
.mlx-bench/bin/python scripts/local_mlx_benchmark.py \
  --model models/apertus-mlx --data data --out local-benchmark.json
```

This uses a [community 4-bit MLX conversion](https://huggingface.co/tokimoa/apertus-v1.5-8b-mlx-4bit) of Apertus 1.5 8B. Apple GPUs share system memory, so Metal allocation differs from dedicated NVIDIA VRAM. The recorded M4 Pro run used 5.155 GiB peak Metal allocation and 1.12 calls per answer. The Docker path remains the application deployment route.

## Deployment and verification

Firebase Hosting serves the frontend at **https://zusage.web.app**. Cloud Run in `europe-west1` serves the API; Cloud SQL PostgreSQL persists data. Secret Manager holds server credentials. An authenticated hourly Cloud Scheduler job prepares follow-ups for registered accounts and sends optional Web Push notifications. Demo visitors are excluded from background scans.

Current automated validation: 77 backend tests and 9 frontend tests, plus live HTTP interviews across German, French, Italian, English and Swiss German. The five-language run completed 38 candidate answers with 43 model calls, averaging 1.13 calls per answer, with no offline fallback in that run. This verifies functionality, not an official judge benchmark or a guarantee of future model availability.

See [deployment](track_2a/docs/DEPLOYMENT.md), [testing instructions](track_2a/docs/TESTING.md), [privacy](track_2a/docs/PRIVACY.md), [feature comparison](track_2a/docs/OFFERLOOP_PARITY.md) and [technical report](track_2a/technical_report.md).

Apache-2.0. Offerloop-inspired workflow design is adapted for apprenticeship learners. The application coach remains Apertus 1.5 8B.

## Licenses

Code is Apache-2.0, original documentation and designs are CC-BY-4.0, and original submitted datasets are CDLA-Permissive-2.0. Third-party components retain their own licenses. See the repository LICENSES directory.

## Interview speech

The hosted app offers Google Cloud Chirp 3 HD (Aoede) natural speech in English, German, French and Italian, with comfortable/slower/faster pacing and replay/stop controls. Swiss German uses the German voice and is labelled as approximate dialect pronunciation. Apertus 1.5 8B still generates every interview question and response; speech synthesis does not replace the coach model. Voice starts only when enabled or Read aloud is pressed. Only owned, current interviewer text can be synthesized; contact identifiers are redacted. Audio uses bounded temporary memory caches. Provider failures are labelled and fall back to device speech. Local deployments default to browser/device speech.

To enable natural speech on a GCP deployment, enable the Cloud Text-to-Speech API, give the runtime service account Service Usage Consumer on the project, and set ZUSAGE_TTS_ENABLED=true and ZUSAGE_TTS_PROJECT to that project ID. Application Default Credentials are used; no speech key is shipped to the browser. The EU synthesis endpoint is used. Google Cloud speech usage is billed to the deployment project.
