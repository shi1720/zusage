# Privacy, safety and compliance

Zusage's users are mostly **minors (14–17)**. The design follows the Swiss Federal Act on
Data Protection (revFADP / revDSG), GDPR principles, and child-safety practice.

## Data minimisation (FADP Art. 6)

- Students register with a **username only** - no e-mail, no birth date, no address.
- The profile asks only for what improves the interview (age, school level, hobbies,
  Schnupperlehre experience, story bank) and says explicitly that no contact data is needed.
- **Redaction before the model:** phone numbers, e-mail addresses, Swiss AHV numbers and
  IBANs are masked in answers *before* they are stored or sent to the LLM
  ([`guard.py`](../src/backend/zusage/engine/guard.py)).
- **Retention:** answer texts are purged after 180 days (`ZUSAGE_TRANSCRIPT_RETENTION_DAYS`);
  numeric scores are kept for progress tracking; quoted feedback and report narrative are also removed.

## Data subject rights

- **Access / portability:** *Profile → Download my data* (JSON of everything stored).
- **Erasure:** *Profile → Delete my account* hard-deletes the account and every row it owns.

## Teacher access is consent-based

Teachers see aggregates (scores, practice counts, confidence, application stages) for
their class. **Answer texts are visible only if the student switches on "Let my teacher
read my interview answers"**, revocable at any time. Leaving a class revokes consent.

## Sovereignty

- The model is **Apertus**, an open model built in Switzerland, served from an endpoint
  the operator chooses: CSCS, a cantonal data centre, a school server, or fully local
  (`make run-local`). Fonts are bundled. Optional posting retrieval and Web Push contact the selected public posting site and browser push provider.
- The hosted demo sends redacted interview context to the organiser's Apertus endpoint and stores data on Google Cloud. A local deployment can keep processing on the school server. Operator agreements and retention policies need review before using real student data.
- Optional browser dictation uses the browser's speech service (in Chrome this streams
  audio to the browser vendor) - it is **off by default** and labelled; typing is always
  available. Text-to-speech uses on-device voices.

## Safety for minors

| Risk | Control |
|---|---|
| Acute distress disclosed in an answer | Deterministic multilingual keyword screen runs **before** any model call → interview pauses, shows Pro Juventute **147** (free, 24/7, confidential). The model's `flag` field is a second layer. |
| Inappropriate content | Model flag + polite redirection; never a sarcastic or shaming response. |
| Harsh or discouraging feedback | Prompt follows wise-feedback and Hattie & Timperley; no grades, only "not yet / getting there / good / strong"; score colours avoid red. |
| Illegal interview questions (OR Art. 328b: religion, origin, pregnancy, health, politics, sexual orientation) | Planned questions are pre-written; the prompt forbids these topics; the evaluation harness checks every interviewer turn. |
| Hallucinated facts about the company | The interviewer may only use a closed list of company facts; otherwise it says it will find out. |
| Hallucinated feedback | The evidence quote must occur in the student's answer, or it is dropped. |
| Prompt injection via answers or pasted job ads | Fenced as data in the prompt; outputs validated; the model has no tools. |

## Security

Argon2id password hashing · HttpOnly SameSite cookies (`Secure` behind HTTPS via
`ZUSAGE_COOKIE_SECURE=true`) · login rate limiting · per-user authorisation checks on
every resource · non-root container user · persisted session secret (0600).

## EU AI Act note

An interview *training* tool for learners is not a recruitment decision system. Zusage
makes no hiring decisions and shares nothing with employers. If used in education for
assessment purposes, the transparency of the rubric, the human-readable evidence and
teacher oversight support the obligations for education-related AI.
