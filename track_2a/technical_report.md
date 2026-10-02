# Zusage technical report

Track 2A / FHGR. Built by Shivam Gupta. Source: https://github.com/shi1720/zusage. Live demo: https://zusage.web.app.

## Inspiration and approach

A first interview should not be a student's first chance to practise. Zusage pairs an Apertus interviewer with development-oriented feedback, self-assessment, immediate retries and spaced practice. It supports German, French and Italian, plus English and Swiss German interview practice, for 12 apprenticeships and three interviewer styles.

## Architecture

React/TypeScript provides a responsive multilingual interface. FastAPI, SQLModel and LangGraph coordinate interview flow and persistence; an Aegra graph and HTTP benchmark harness are included. Apertus 1.5 8B produces assessment and an interviewer reaction together in one structured call. Code validates scores, output shapes and contiguous evidence quotes. A bounded final call produces the report.

Firebase Hosting serves the live interface. Dedicated Cloud Run, PostgreSQL and Secret Manager resources support persistent sessions and data. An authenticated hourly task prepares follow-ups, sends optional Web Push and performs transcript maintenance. The same Docker app supports SQLite and a local quantized Apertus deployment.

## Product and innovation

Students assess an answer before revealing feedback, retry with a real example and compare attempts. Weak answers become Leitner-style drills. Confidence tracking and a consent-aware classroom view connect practice to teaching. Application stages, job-ad extraction, outreach drafts, prep packs, imports, nudges, analytics, momentum and a replayable tour adapt Offerloop workflows to apprenticeship learners. All live generation uses Apertus. An optional personal Apertus key is encrypted; the default server key makes the product immediately usable.

## Privacy and safety

Username accounts avoid collecting email addresses. Passwords use Argon2 and sessions use signed HttpOnly cookies. A password change invalidates prior sessions; recovery codes are hashed and single-use. Ownership checks isolate every workspace. Teachers need student consent for answer text. Identifiers are redacted before interview model calls. Distress pauses practice. Retention removes old answer text, quoted feedback and report narrative while keeping numeric progress. The hosted demo uses Google Cloud and the organiser's inference endpoint; a school can host the same model locally.

## Validation

77 backend and 9 frontend tests pass, together with Ruff and the TypeScript production build. A five-language live HTTP run completed 38 answers with 43 model calls, averaging 1.13 calls per answer, with no offline fallback in that run. Tests cover reports, real-mode gating, session isolation, teacher consent, retry safety, malformed responses, exports, imports, drafts, encrypted keys, recovery and scheduler authentication.

These tests are functional checks. Existing exploratory benchmark files are historical and are not claimed as current official judge results. Run the official LLM-as-judge benchmark once its prompts and metrics are available. Performance is weighted 50%, consistency 25% and innovation 25%.

## Runtime gate and limits

Cloud Build built the container and Cloud Run executed it. Actual consumer-GPU peak VRAM has not been measured in this environment. Apertus 8B parameter storage is roughly 16 GB at BF16 or 5 GB at 4-bit, plus runtime/cache overhead. Use make run-local and measure a physical consumer GPU before claiming the under-32-GB gate. The Docker daemon and suitable GPU were unavailable here.

Browser voice and push need browser support and permission. Some posting sites block retrieval; pasted advert text remains available. Generated messages always need human review. Future work includes educator evaluation, Profolio integration and deployment governance for a real school pilot.

## Deliverables

The six-page [technical report](Zusage_Report.pdf), source, deployment script, [testing instructions](docs/TESTING.md) and reviewed demo video form the submission. Video approval and participant eligibility must be confirmed before final submission.
