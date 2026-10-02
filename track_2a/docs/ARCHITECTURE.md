# Architecture

## Components

```mermaid
flowchart TB
    subgraph browser [Browser - React 19 + TypeScript]
      UI[Student app<br/>Today · Practice · Interview room · Gipfelbuch · Tracker · Progress]
      TC[Teacher cockpit<br/>class heatmap · weak spots · student detail]
      VOX[Voice layer<br/>optional neural/device speech · opt-in dictation]
    end

    subgraph container [Zusage container - FastAPI, single process]
      AUTH[Auth<br/>Argon2id · signed session cookie · roles]
      IVAPI[Interview API]
      JOUR[Journey API<br/>tracker · drills · dashboard]
      CLS[Classes API]
      subgraph engine [Interview engine]
        PLAN[Planner<br/>deterministic, seeded, focus-aware]
        GUARD[Guard<br/>distress screen · redaction]
        TG[LangGraph turn graph]
        BRAIN[Brain port<br/>ApertusBrain · OfflineBrain]
        VAL[Validator<br/>clamp · quote check · language ID]
      end
      LEARN[Learning layer<br/>Leitner · calibration · streaks]
      KB[(Knowledge base<br/>YAML: rubric · questions · occupations · personas)]
      DB[(SQLite / Postgres)]
    end

    LLM[Apertus 1.5 8B<br/>any OpenAI-compatible endpoint]

    VOX -->|owned interviewer text| SPEECH[Speech API]
    SPEECH -->|optional synthesis| GOOGLE[Google Chirp 3 HD EU]
    UI --> IVAPI & JOUR
    TC --> CLS
    IVAPI --> TG
    TG --> GUARD --> BRAIN --> VAL
    PLAN --> TG
    KB --> PLAN & BRAIN
    BRAIN -->|1 JSON call / answer| LLM
    IVAPI & JOUR & CLS --> DB
    JOUR --> LEARN
```

## One answer, step by step

```mermaid
sequenceDiagram
    participant S as Student
    participant A as API
    participant G as Guard
    participant B as Apertus
    participant V as Validator
    S->>A: POST /interviews/{id}/answer
    A->>G: screen(answer)
    alt distress
      G-->>A: pause → Pro Juventute 147 (no model call)
    else empty
      G-->>A: gentle reprompt (no model call)
    else ok
      G->>B: redacted answer + question + rubric anchors + company facts (1 call)
      B-->>V: {scores, evidence, strength, tip, better_answer, follow_up, bridge, flag}
      V->>V: clamp scores · verify quote · check language · fallbacks
      V-->>A: assessment + interviewer reply
      A->>A: advance plan (probe | next question | closing → report)
    end
    A-->>S: interviewer message (+ feedback in training mode)
```

## Key design decisions

| Decision | Why |
|---|---|
| **Single structured call per answer** | Coach and interviewer reason over the same evidence (no contradictions); ~1.1 calls/answer vs. the FHGR gate of 5; fewer requests than separate interviewer and assessor calls. |
| **Deterministic planner** | Questions are pre-written and reviewed in 5 languages → no language drift, no off-topic questions, no illegal questions. The model adapts *within* the skeleton (follow-ups, reactions). |
| **Planner variation + focus** | Seeded alternatives per slot (variation across sessions) and preference for questions that train the student's two weakest criteria (adaptive practice). |
| **Validator as a gate** | Clamps scores, requires the evidence quote to occur in the answer, rejects wrong-language text, falls back to hand-written phrases. Reduces specific failure modes; educator evaluation is still needed. |
| **Graceful degradation** | If Apertus fails, the turn is assessed by the offline coach and flagged `degraded`; the interview never breaks. |
| **State = one JSON document** | Engine is stateless; any worker continues any interview; the same state runs inside LangGraph/Aegra. |
| **Two LangGraph graphs, one implementation** | `turn_graph` (one invocation per answer, app-managed persistence) for the web app; `interview_graph` (interrupt-driven) for Aegra / LangGraph Server. Both call the same `core.py` functions. |
| **Offline brain = baseline** | The rule-based coach keeps the product and CI credential-free *and* serves as the baseline in the evaluation harness. |
| **Cookie sessions + Bearer** | HttpOnly cookie for browsers (no tokens in JS); the same JWT as Bearer for automated judges/harnesses. |
| **Self-hosted fonts, no CDN** | No font CDN dependency. Local inference and device speech support an isolated setup; hosted inference, optional neural speech, posting retrieval and push use external services. |

## Data model

| Table | Purpose |
|---|---|
| `user` | username (no e-mail needed), Argon2id hash, role, UI language, class, consent flag |
| `classroom` | teacher, 6-letter join code (no ambiguous characters) |
| `studentprofile` | age, school, hobbies, Schnupperlehre experience, story bank, target occupation |
| `application` | Lehrstellen tracker card with status history, interview date, job ad |
| `interview` | full engine state (JSON), report, confidence before/after, usage metrics |
| `drill` | Leitner card: question, box 1–5, due date, last/best score |

## Interfaces

- REST API - OpenAPI docs at `/docs`.
- `zusage selfcheck --url …` - end-to-end smoke test over HTTP (used by `make run`).
- `zusage simulate …` - scripted interview in the terminal.
- `zusage eval …` - evaluation harness.
- Aegra - `aegra.json` → `src/backend/aegra_graph.py:graph` (assistant id `zusage_interview`).
