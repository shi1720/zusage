# Zusage

An Apertus 1.5 8B interview coach for Swiss apprenticeships. Built by Shivam Gupta for Hack Apertus, Track 2A / FHGR.

**[Try the app](https://zusage.web.app)** · **[Watch the submission demo](https://youtu.be/kNNu796CueY)**

## Submission layout

The project root is `track_2a/`, following the [official Hack Apertus template](https://github.com/HackApertus/project-template). The unused track directories are removed. All application code and submission materials remain inside this track directory.

| Required path | Zusage deliverable |
|---|---|
| [track_2a/README.md](track_2a/README.md) | Challenge, judging criteria, features and run instructions |
| [track_2a/technical_report.md](track_2a/technical_report.md) | The eight template sections, evidence and limitations |
| [track_2a/Makefile](track_2a/Makefile) | Docker launch and end-to-end selfcheck |
| [track_2a/src/](track_2a/src/) | Backend, frontend and graph source |
| [track_2a/data/](track_2a/data/) | Synthetic datasets and evaluation evidence, below 100 MB |
| [track_2a/docs/](track_2a/docs/) | Architecture, deployment, testing and [visual overview](track_2a/docs/OVERVIEW.md) |

## Run from a clean checkout

Install Docker, start its daemon and run:

```bash
make run
```

The root Makefile forwards to the track project. This builds the image, starts the app at http://localhost:8080 and runs a complete HTTP interview selfcheck. Without credentials, the interface clearly labels its deterministic offline demo. For real Apertus inference, configure `track_2a/.env` using its `.env.example`, or export `LLM_NAME`, `LLM_BASE_URL` and `LLM_API_KEY` before launching. Keep credentials private.

For weights, local hardware measurements and deployment, see the [project README](track_2a/README.md). The [six-page submission report](track_2a/Zusage_Report.pdf) records the submitted snapshot; the Markdown report tracks subsequent improvements.

Code: Apache-2.0. Original documentation/designs: CC-BY-4.0. Original datasets: CDLA-Permissive-2.0. See [license scope](LICENSES/README.md).
