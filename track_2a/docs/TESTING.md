# Testing Zusage

Open https://zusage.web.app. New visitors see English; German, French and Italian are available in the language switch. The interface preference and the interview language can differ.

1. Choose Try as student. Dismiss or follow the replayable tutorial. This is a private copy of a fictional class.
2. Open Practice interview. Choose an occupation, one of five languages, interviewer, training mode and a short interview. Start with a simple answer.
3. Rate your answer before viewing feedback. Verify the quotes match your actual words. Retry with a specific real example and inspect the comparison.
4. Complete the interview or use Finish. Check the final report, confidence check, progress page and due practice cards.
5. Add an apprenticeship, paste a job advert, change stages, set an interview date, inspect history and launch its tailored rehearsal. Remove it and use Undo.
6. In Writing studio, choose an application and generate a cover letter or prep pack. Edit and save it, copy it, and open the Gmail compose draft. Nothing sends automatically.
7. In Follow-ups, run Scan now. Inspect generated reminders and drafts. Repeat the scan and verify no duplicates; mark a reminder done.
8. In Import & export, load sample applications and import twice. Verify one card per external ID. Import sample drafts and inspect linkage. Download both CSVs.
9. Check Application insights, momentum and the weekly practice goal. Replay the tour from the sidebar.
10. In Profile, update stories and language, export account data and inspect privacy controls. Registered accounts can create a recovery code, change a password and configure an optional Apertus key.
11. Sign out and choose Try as teacher. Inspect the fictional class. Compare a student who shares answers with one who has not consented. Register a teacher to create a new class and share its join code.
12. Test a narrow phone viewport. Navigation moves into Menu; tracker columns stack, forms fit, and the interview composer remains accessible.

## Automated checks

```bash
make test
make lint
cd track_2a
uv run --project src/backend python scripts/e2e.py --url https://zusage.web.app --out hosted-e2e.json
```

The live suite completes interviews in all five languages and checks session isolation, budget, end reports, progress, closed-session rejection, account export and teacher consent. Backend tests cover malformed provider responses, redaction, safety pause/retry, retention, typed profile validation, CSV idempotency, draft isolation, recovery, credential encryption, scheduler authentication and analytics.

Consumer GPU memory and the official LLM-as-judge benchmark must be measured separately. Browser dictation and Web Push depend on browser permission and support. Never use real student or contact data in the public demo.
