# Zusage

**Your first interview should not be your first chance to practise.**

Zusage is an Apertus 1.5 8B interview coach for Swiss apprenticeships. It helps students find their own words, understand what works and build confidence before the real conversation.

## Inspiration

An apprenticeship interview can shape a young person's next chapter. Yet opportunities for repeated, individual practice are limited, and teachers cannot rehearse every interview with every student. We wanted to make practice approachable, personal and useful, while respecting Switzerland's languages and learners' privacy.

## What it does

Students choose an apprenticeship, language and interviewer, then practise a realistic conversation. In training mode, they reflect on each answer before seeing feedback across six criteria. The coach checks quotes against their actual words and suggests a concrete next step. Students can retry, compare attempts and turn weaker answers into spaced drills. Dress rehearsal keeps feedback until the end.

The surrounding workspace connects practice to real applications: a tracker, company-specific rehearsals, Apertus writing support, prep packs, imports, follow-up reminders and application insights. Teachers get a classroom view, with answer text shared only when a student opts in.

German, French and Italian meet the challenge requirements. English is the default interface, and Swiss German interview practice is also available.

## How we built it

We built a React and TypeScript interface with a shared visual system and multilingual copy. FastAPI, SQLModel and LangGraph coordinate the interview, persistence and learning loop. Apertus 1.5 8B handles assessment and adaptation in a structured response; deterministic code controls flow and validates evidence and output.

Firebase Hosting gives the app a clean URL. Cloud Run serves the API, PostgreSQL stores data, and Secret Manager protects credentials. A school can deploy the same Docker application with a local Apertus model. The app works with its default server key; an optional personal Apertus key is validated and encrypted.

## Challenges we ran into

Useful feedback needs more than fluent text. We had to prevent fabricated evidence, handle malformed model responses, preserve the interview language and keep the conversation moving when the provider is unavailable. We also worked through Firebase's cookie forwarding, durable database storage, deployment updates, mobile layouts and private demo workspaces.

Bringing application workflows into the product added another constraint: messages must use real profile facts and remain under the learner's control. Generated drafts are editable and never send automatically.

## Accomplishments that we're proud of

The live app completes interviews in all five supported interview languages. A five-language functional run completed 38 answers with 43 model calls, an average of 1.13 calls per answer, below the challenge limit. The automated suite covers account security, evidence validation, safety pauses, consent, imports, encrypted keys, recovery and reminders.

We are also proud of the learning loop: self-assessment, specific feedback, immediate retry and spaced practice. It gives students a next action, rather than leaving them with a score.

## What we learned

Structure makes a small model more dependable. Combining reviewed question flows with validated model output lets Apertus focus on the parts that need language and judgment. We also learned that trust depends on ordinary product details: recoverable errors, clear privacy controls, readable design and a working account journey.

## What's next

We want to evaluate feedback with vocational educators, run the official judging benchmark, measure peak VRAM on real consumer hardware and explore Profolio integration. A real school pilot would include an operator privacy review, accessibility testing and further dialect evaluation.

## Testing instructions

Visit https://zusage.web.app and choose **Try as student**. Follow the tour, start a short interview, answer, rate yourself and retry. Inspect the report, progress, applications, writing studio, imports and follow-up scan. Sign out and choose **Try as teacher** to inspect classroom support and consent-aware answer access.

For a new account, create a student or teacher username and password. The app works without adding an API key. Profile settings include a recovery code, account export, language preferences and an optional personal Apertus key.

The Docker and testing instructions are in the public repository: https://github.com/shi1720/zusage.
