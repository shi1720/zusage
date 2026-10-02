# Zusage functionality overview

[Live app](https://zusage.web.app) · [Submission video with captions](https://youtu.be/kNNu796CueY) · [Extended walkthrough](https://youtu.be/jgWSAaASskg)

## Learner journey

```mermaid
flowchart LR
    A[Demo or private account] --> B[Choose apprenticeship and language]
    B --> C[Interview with Apertus]
    C --> D[Self-assess and reveal feedback]
    D --> E[Retry with a real example]
    E --> F[Report and spaced practice]
    F --> C
    A --> G[Track applications and prepare writing]
    F --> H[Teacher progress with consent]
```

## Start and prepare

English is the default interface, with German, French and Italian options. Demo accounts let judges explore immediately. Learners track an opportunity and choose a tailored practice session.

![Welcome and demo entry](screenshots/01-landing.png)
![Application tracker](screenshots/04-tracker.png)
![Interview setup](screenshots/03-practice.png)

## Practise and improve

Apertus reacts to the learner's answer and provides evidence-based feedback. Training mode supports self-assessment and retries; dress rehearsal holds feedback until the end. The optional neural voice offers pacing, replay and stop controls.

![Interview and natural voice controls](screenshots/16-natural-voice.png)
![Structured answer feedback](screenshots/09-interview-feedback.png)
![Final report](screenshots/10-report.png)

## Continue learning and teaching

Progress and drills make practice repeatable. Teachers see class-level progress; answer text requires explicit student consent. The layout adapts to a phone screen.

![Learner progress](screenshots/05-progress.png)
![Teacher dashboard](screenshots/11-teacher.png)
![Mobile interview and speech controls](screenshots/17-mobile-natural-voice.png)

Screenshots show fictional demonstration accounts. Older screenshots record the submission build; voice screenshots show the subsequent speech improvement. See [architecture](ARCHITECTURE.md), [test steps](TESTING.md) and [privacy](PRIVACY.md).
