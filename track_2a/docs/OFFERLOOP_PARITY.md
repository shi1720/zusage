# Offerloop workflow comparison

Zusage retains its apprenticeship interview focus and adapts Offerloop's useful job-search workflows. All live AI generation uses Apertus 1.5 8B, including outreach, job-ad extraction and prep packs.

| Offerloop workflow | Zusage implementation |
| --- | --- |
| Today view | Due drills, upcoming interviews, quiet applications, practice goal and activation checklist |
| Posting capture | Paste advert text or public HTTPS link, Apertus extraction, confirm before saving |
| Pipeline | Six apprenticeship stages, drag-and-drop, editable status, timestamped history, soft removal and Undo |
| Outreach | Cover letter, follow-up, referral, LinkedIn message and thank-you drafts, profile/application/past-draft context, editable provenance and Gmail compose |
| Prep packs | Likely questions, answer angles, real-story STAR outlines and questions to ask |
| Scheduled nudges | Authenticated hourly scan, cumulative 5/12/22-day cadence, interview thank-you and outcome reminders, attached drafts, deduplication |
| CSV ingestion | Applications and drafts, row errors, idempotent external IDs, orphan retention and adoption; common spreadsheet/Teal/Huntr column aliases |
| Funnel analytics | Interview/offer/quiet rates, median time to interview and weekly application chart |
| Momentum and onboarding | Replayable seven-step walkthrough, profile onboarding, real-action points, activation checklist, adjustable practice goal |
| Browser push | Opt-in standard Web Push, VAPID credentials in Secret Manager, service worker, hourly delivery |
| Portability | Application/draft CSV and full account JSON export; account erasure |
| Personal API key | Live validation and encrypted personal Apertus key; server default remains available |
| Account management | Username/password registration, student/teacher roles, sign-out, display-name changes, password change, one-use recovery code |

Deliberate adaptations: username accounts avoid collecting minors' email addresses; Gemini routing and model selection are not carried over. Zusage does not meter a paid/free drafting allowance. No email is sent automatically. Rates and momentum describe user activity, not hiring predictions. Personal draft facts still need review. Some job sites block server-side retrieval; pasted advert text always remains available.
