# Technical report: Zusage

- Track: Track 2A / FHGR, AI-Powered Job Interview Coach
- Event: Online Hack Apertus
- Team: Zusage, Shivam Gupta
- Demo: [live app](https://zusage.web.app), [1:50 submission video](https://youtu.be/kNNu796CueY), [2:58 extended walkthrough](https://youtu.be/jgWSAaASskg)
- Source: [public repository](https://github.com/shi1720/zusage), default branch `aperture-redesign`

## 1. Summary

A first interview should not be a learner's first chance to practise. Zusage pairs realistic Apertus interview reactions with evidence-based developmental feedback, self-assessment, retries and spaced drills. Learners can practise 12 apprenticeships with three interviewer styles in German, French, Italian, English and experimental Swiss German. Application tracking and writing preparation connect practice to a real opportunity. A local quantized Apertus run completed eight answers with nine model calls and 5.155 GiB peak Metal allocation on a 24 GiB Apple M4 Pro. This is measured runtime evidence, not an official interview quality score.

## 2. Architecture

React and TypeScript provide the responsive multilingual interface. FastAPI and SQLModel handle authentication, workspace ownership and persistence. LangGraph coordinates an interview engine with a deterministic question planner, redaction/safety guard, Apertus generation and structured-output validation. One model call combines assessment and interviewer reaction; a bounded final call produces the report. Evidence quotes must occur in the student's answer. Self-assessment, retry comparison and Leitner-style drills turn feedback into further practice.

See the [component and sequence diagrams](docs/ARCHITECTURE.md) and [visual functionality overview](docs/OVERVIEW.md). The same backend is exposed through an Aegra graph and HTTP evaluation harness. The single Docker image serves both the frontend and API, with SQLite in a persistent volume. The hosted version uses Firebase Hosting, Cloud Run, PostgreSQL and Secret Manager. An authenticated hourly task handles optional follow-ups and transcript maintenance.

Google Chirp 3 HD Aoede optionally synthesizes interviewer text through the EU endpoint. It does not generate interview content. Local deployments default to device speech. Hosted audio uses bounded temporary memory caches and can be stopped; failure is labelled before device speech fallback. Swiss German uses approximate German pronunciation.

## 3. Use of Apertus

- Model: Apertus 1.5 8B, organiser endpoint identifier `apertus-v1.5-8b`.
- Role: interview reactions, structured assessment, final feedback and writing/preparation inference. No fine-tuning is claimed.
- Hosted inference: the organiser's OpenAI-compatible endpoint, configured server-side through `LLM_NAME`, `LLM_BASE_URL` and `LLM_API_KEY`. The private key is excluded from Git.
- Local reproduction: the same model family through a local server, or the [community 4-bit MLX conversion](https://huggingface.co/tokimoa/apertus-v1.5-8b-mlx-4bit) used for the measured Apple Silicon run.
- Prompts and validation: [interview engine source](src/backend/zusage/engine/), supported by the question bank and rubric in `data/`. No alternative coach model is selectable.

Hosted generation normally uses temperature 0.3; the recorded local MLX benchmark uses greedy decoding, temperature 0, as implemented in [local_mlx_benchmark.py](scripts/local_mlx_benchmark.py). The offline rule-based coach is a labelled, credential-free functional baseline. It is not Apertus inference. Evaluation can use a separately configured judge; exploratory judge output must not be confused with the official benchmark.

## 4. Data

`data/` contains authored synthetic occupation descriptions, interviewer personas, rubric anchors, multilingual questions, fictional learner profiles and evaluation answer banks. Original submitted datasets use CDLA-Permissive-2.0; see [license scope](../LICENSES/README.md). They are fixtures rather than observations from real learners. Repository data stays below 100 MB. Model weights, API keys, database files and private user transcripts are excluded.

Users can enter their own stories, answers and job adverts at runtime. These are private workspace data, not redistributable datasets. Teacher access to answer text requires explicit, revocable student consent. Username accounts avoid requiring email addresses, and the product provides export, deletion and transcript retention controls. Contact identifiers are redacted before interview inference. Only current, owned interviewer text can be sent for hosted speech. See [privacy and limitations](docs/PRIVACY.md).

## 5. Evaluation

We separate functional correctness, measured runtime and interview quality. Passing regression tests is not a quality benchmark score.

| Setup | Metric | Result |
|---|---|---|
| Labelled offline baseline | Deterministic, credential-free launch and interview completion | Exercised by regression tests and clean-checkout Docker CI |
| Current application | Backend/frontend regression tests | 80 backend and 13 frontend tests passed; Ruff and TypeScript production build passed |
| Hosted Apertus, five interview languages | Completed answers, model calls, fallback turns | 38 answers, 43 calls, 1.13 calls per answer, no offline fallback in that recorded run |
| Local 4-bit Apertus, Apple M4 Pro | Call budget, memory and end-to-end latency | 8 answers, 9 calls, 1.12 calls per answer, 5.155 GiB peak Metal, 3.628 GiB process RSS, 87.13 seconds, no fallback turns |
| Hosted neural speech | Real MP3 generation, replay and access validation | All five interview language routes passed; arbitrary text and invalid rates rejected |
| Official LLM-as-judge | Performance 50%, consistency 25%, innovation 25% | Not measured; no official score claimed |

[Local hardware measurements](data/eval/results/local-apertus-hardware-test.json), [hosted interview evidence](data/eval/results/hosted-interview-tests.json) and [speech evidence](data/eval/results/hosted-voice-tests.json) are retained. The [evaluation harness](src/backend/zusage/eval/harness.py) includes calibration, scripted profiles, adversarial cases and an optional blinded judge. Historical `summary.json`, `judgements.json` and related exploratory files are not current official benchmark results. Official prompts and metrics must be obtained from the organisers before reporting their score.

## 6. Limitations

The local run used Apple unified memory, not dedicated NVIDIA VRAM. Its measured accelerator allocation is below 32 GiB, but NVIDIA Docker inference has not been hardware-tested. The app Docker image runs independently of the external inference server; hosted API latency and availability depend on the provider. One recorded interview is insufficient to establish quality across all local-model scenarios.

Swiss German interview text and pronunciation remain experimental. Speech and dictation depend on device support; hosted neural speech requires Google credentials and incurs usage charges. Job sites can block retrieval, so pasted adverts remain available. Generated advice and messages need human review. Distress screening and quote validation reduce specific failure modes but do not establish suitability for every learner or replace educator oversight.

## 7. Reproducibility

From a clean checkout, install and start Docker, then run `make run` in the repository root or in `track_2a/`. The default creates `.env` from `.env.example`, builds the image, launches the labelled offline app on port 8080 and runs an HTTP interview selfcheck. Configure private Apertus credentials in `track_2a/.env` or export the template's three `LLM_*` variables for actual inference. No host Python or Node is needed for the Docker path. `make stop` stops the app; the named volume preserves local data.

The recorded hardware run used an Apple M4 Pro with 24 GiB unified RAM, 4-bit MLX weights, greedy decoding and the scripted eight-answer interview. The measured source snapshot is `c01988d`; see the exact per-call output in the linked JSON. Run the Apple Silicon commands in the [README](README.md#measure-local-apertus-on-an-apple-silicon-mac). The Linux/CPU local-server alternative is `make run-local`; it downloads Apertus GGUF weights and has not been measured on NVIDIA hardware here. Seeded question planning is implemented in the source; the hardware benchmark fixes the scenario rather than claiming stochastic reproducibility across model runtimes.

Run `make test` and `make lint` with uv/Python and Node 22 for development verification, or use the clean-checkout CI workflow. See [deployment instructions](docs/DEPLOYMENT.md) and [manual testing instructions](docs/TESTING.md). The six-page [PDF report](Zusage_Report.pdf) is the submitted snapshot; this Markdown report also documents subsequent speech improvements.

## 8. Next steps

Run the official quality benchmark when its prompts are available, add educator-led evaluation with consenting learners, verify the local Docker inference path on a physical consumer GPU, improve Swiss German pronunciation and pilot school deployment governance. Profolio integration could connect practice and real vocational guidance.

## License

Original report and documentation: Creative Commons Attribution 4.0. Code: Apache-2.0. Original datasets: CDLA-Permissive-2.0. Third-party weights, fonts and libraries retain their own licenses.

## References

- [Official project layout](https://github.com/HackApertus/project-template)
- [Official technical report template](https://github.com/HackApertus/project-template/blob/main/track_2a/technical_report.md)
- [Challenge text](docs/CHALLENGE.md)
- [Architecture and strategy](docs/ARCHITECTURE.md)
- [Submission receipt and deliverables](docs/SUBMISSION.md)
