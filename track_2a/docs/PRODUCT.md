# Zusage - product, market and business model

> **One line:** Zusage gives every Swiss school leaver an unlimited, private,
> multilingual interview coach - and gives their teacher the class-wide view to act on it.

## 1. The job to be done

| Who | Job | Today |
|---|---|---|
| **Lea, 15**, Sek A in Chur, wants to become *Fachfrau Gesundheit EFZ* | "Help me not freeze in my interview on Thursday." | Rehearses in front of the mirror, or not at all. Parents help if they know the Swiss system. |
| **Frau Meier**, class teacher, *Berufliche Orientierung* (Lehrplan 21) | "Help my 24 students practise interviews, and show me who needs me." | One role-play per student per year, if time allows. No data on who is stuck. |
| **Career counsellor (BIZ)** | "Scale individual interview prep beyond appointments." | Group workshops; individual sessions are scarce. |
| **Training company (Lehrbetrieb)** | "Get candidates who can explain why they want *this* job." | 11,500 places unfilled at start of training (Aug 2025); unclear motivation cited as a reason. |

## 2. Market facts (sources in the technical report)

- **~76,500** young people started a VET programme in 2024 (BFS); **~98,000** faced the
  post-compulsory-school choice in 2026, **63 %** considering VET (SBFI Nahtstellenbarometer).
- **~74,000** apprenticeship places offered per year; **11,500 (13 %)** still empty when
  training started in August 2025 (SRF/SBFI). Construction: 25 % unfilled.
- **~95,000** students per Sek-I grade (BFS, 288k Sek-I students 2024/25).
- Families already pay **CHF 60–100** for a Multicheck / Basic-Check aptitude test.
- Companies pay **CHF 870–1,790 per year** to list apprenticeships on yousty.
- Swiss EdTech benchmarks: **CHF 22–40 per student/year** (Lernnavi, Lernlupe, Lernpass).
- DACH extension: Germany signs **~480,000** new training contracts per year (BIBB).

## 3. Competitors and why they don't solve this

| | Swiss VET context | DE/FR/IT + dialect | Minors' data sovereign | Teacher view | Price |
|---|---|---|---|---|---|
| Yoodli, Big Interview, Huru, Final Round AI | ✗ adult white-collar | partly | ✗ US cloud | ✗ | $8–150 / month |
| yousty, gateway.one, berufsberatung.ch | ✓ content & listings | ✓ | n/a | ✗ | free / company-paid |
| Human coaching (BIZ, Pro Juventute school sessions) | ✓ | ✓ | ✓ | partly | scarce, regional |
| **Zusage** | **✓ EFZ/EBA, Schnupperlehre, Swiss companies** | **✓ + Swiss German** | **✓ Apertus on-prem** | **✓ cockpit** | **CHF 9 / student / year** |

The gap: nobody combines *Swiss VET specificity* × *privacy-safe AI for minors* ×
*classroom workflow*. Generic tools can't sell into Swiss schools (data protection,
language, curriculum fit); Swiss content portals don't have the AI.

## 4. Why now

1. **Apertus** (Sept 2025, v1.5 2026) is the first fully open, multilingual LLM built in
   Switzerland - schools and cantons can run it on their own infrastructure. Before, "AI
   coach for 15-year-olds" meant shipping minors' voices to a US cloud: a non-starter
   under the revised FADP.
2. An 8B model is now good enough for structured coaching **when the system around it is
   engineered** (Zusage's validator and single-call design make the 8B reliable) - and
   cheap enough to give away per student.
3. The Lehrstellen market has flipped to a *matching* problem: places stay empty while
   students struggle - companies have a direct financial interest in better-prepared
   candidates.

## 5. Business model

**Free for students, paid by institutions.** A 15-year-old will never pay for this -
and shouldn't have to.

| Revenue line | Buyer | Price | Rationale |
|---|---|---|---|
| **School licence** | Sek-I schools / municipalities | CHF 9 per student per year (min. CHF 290/school) | Below Swiss EdTech norms (CHF 22–40); bought from existing teaching-material budgets |
| **Cantonal licence** | Canton (education dept. or BIZ) | CHF 5 per student, all schools | Volume deal; includes on-prem hosting on cantonal infrastructure |
| **Occupation pack sponsorship** | Industry associations, large Lehrbetriebe | CHF 900–2,500 per occupation per year | Company supplies real facts & questions → students rehearse *their* interview; comparable to a yousty listing, with far better reach into the target cohort |
| **Platform integration** | Profolio (FHGR / S&B), yousty, career portals | revenue share / white label | Zusage as the interview module inside existing career-choice platforms |

**Unit economics.** A full interview ≈ 11 Apertus calls × ~1,900 tokens ≈ 21k tokens.
- Self-hosted 8B on one consumer-class GPU (~CHF 1/hour, dozens of concurrent sessions)
  → **< CHF 0.01 per interview**.
- Hosted Apertus at public price points (e.g. 70B at CHF 0.70/2.50 per M tokens) → ~CHF 0.03.
- A student doing 10 interviews + 20 drills per year costs **< CHF 0.30** in compute
  against CHF 5–9 revenue → **> 95 % gross margin**. The single-call design is what
  makes this margin possible: a typical multi-agent design (5 calls/answer) costs ~4×.

**Sizing (Switzerland only).** 95,000 students per cohort × CHF 5–9 → **CHF 0.5–0.9M ARR**
at full coverage of one grade, plus 10th-year bridge programmes, plus sponsorship
(12 core occupations × several associations). DACH (Germany ~480k contracts/year, Austria)
multiplies the market by ~6× with the same product (German UI exists).

## 6. Moat

1. **Swiss VET knowledge graph** - occupations, EFZ/EBA, Schnupperlehre, company fact
   bases, rubric anchors, multilingual question bank incl. Swiss German. Grows with every
   occupation pack and is curated by counsellors.
2. **Trust & compliance** - sovereign by architecture (Apertus, on-prem, no e-mail, redaction,
   retention, consent-gated teacher access). Hard for US tools to retrofit, required to sell
   to Swiss schools.
3. **Distribution through the classroom** - teachers adopt it for the cockpit; students
   come with their class. Integration into Profolio (FHGR) puts it where career choice is
   already taught.
4. **Evaluation flywheel** - opt-in, anonymised rubric judgements (teacher overrides,
   self-ratings) form a Swiss-specific calibration set that improves the coach and could
   later fine-tune an Apertus adapter. Competitors start from zero.

## 7. Go-to-market

1. **Pilot (Q1 2027):** 3 schools in Graubünden with FHGR, integrated in Profolio;
   measure confidence gain, score gain, teacher time saved.
2. **Canton deal (2027):** one canton's BIZ licence, hosted on cantonal infrastructure
   (`make run-local` architecture).
3. **Sponsorship (2027–28):** occupation packs with 2–3 industry associations that suffer
   most from empty places (construction, gastronomy, electrical installation).
4. **DACH (2028):** German market via career-choice platforms.

## 8. Roadmap

- Voice-first interviews: on-prem Whisper (STT, Swiss-German-tuned) + Piper (TTS) behind
  the existing engine interface.
- Teacher overrides of coach scores → calibration data (flywheel).
- 30+ occupations (all EFZ/EBA with > 500 contracts/year), Romansh UI.
- Video-free body-language tips (posture, greeting) via short checklists - no camera, by design.
- Gymnasium and *Lehrabschluss → first job* interviews (same engine, new knowledge packs).

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| 8B model gives wrong or harsh feedback to a minor | Deterministic validator, quote verification, wise-feedback prompt, no grades, fallbacks; teacher can see aggregates |
| Student discloses distress | Keyword pre-screen (no model needed) → pause + Pro Juventute 147; second layer from the model |
| Schools' procurement cycles are slow | Free pilot tier via FHGR/Profolio; canton-level deals |
| Over-reliance on scripted answers ("gaming the coach") | Scores reward *concrete, personal* examples; story bank uses the student's own experiences |
| Dialect understanding varies | Swiss German interviews flagged beta; planned questions pre-written in dialect; feedback in Standard German |

## 10. OfferLoop lineage

Zusage is a new product, but it stands on **OfferLoop** - Shivam Gupta's job-search CRM.
Its architecture (FastAPI + React single container, adapter seams with a deterministic
offline mode, pipeline board with status history and undo) was forked and re-cut:
OfferLoop's **follow-up cadence engine** (nudge recruiters after 5/7/10 quiet days)
became Zusage's **spaced-repetition scheduler** (re-practise weak answers after
1/3/7/14/30 days), and its application pipeline became the **Lehrstellen tracker**.
OfferLoop's Gemini/Firebase stack was replaced with Apertus, local auth and SQLite for
sovereign deployment. OfferLoop itself is unchanged.
