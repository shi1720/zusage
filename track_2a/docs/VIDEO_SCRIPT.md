# Zusage - demo video script (2:30, trims to 2:00)

**Speaker:** Shivam Gupta · **Format:** screen recording + voice-over · **Resolution:** 1920×1080,
browser zoom 110 %, UI language German (switch languages where noted).

**Before recording**
1. `cd track_2a && make run` with the Apertus key in `.env` (sidebar badge shows *Coach: Apertus*).
2. Open http://localhost:8080 in a clean Chrome window (no bookmarks bar), macOS dark menu bar hidden.
3. Turn on system voice output; in Chrome's speech settings pick a Swiss German voice if available.
4. Practise the answers below once so typing is smooth (or paste them).
5. Keep a second tab with the teacher login ready (private window → "Als Lehrperson testen").

Lines in **bold** are what you say, word for word. *Italics* = what is on screen / what you do.
Approximate timings in brackets. Speak calmly - about 140 words per minute.

---

### 1 · Hook - the problem [0:00–0:18]

*Landing page, hero visible. Slowly scroll so "Bis zur Zusage." fills the frame.*

**"This is Lea. She's fifteen, she lives in Chur, and on Thursday she has her first job
interview - for an apprenticeship as a healthcare assistant.**

**Like most of the seventy-six thousand teenagers who start an apprenticeship in
Switzerland every year, she has never practised. Her teacher has twenty-four students
and no time for mock interviews. And last August, eleven thousand five hundred
apprenticeships stayed empty."**

### 2 · The product [0:18–0:30]

*Click "Als Schüler:in testen". The Today page appears with the yellow card "In 4 Tagen - Gespräch bei Pflegezentrum Calanda".*

**"So we built Zusage - an interview coach for Swiss apprentices, running on Apertus,
Switzerland's open language model. Zusage knows Lea has a real interview coming up -
so let's rehearse exactly that one."**

*Click "Dieses Gespräch proben". On the setup page: Deutsch, Frau Caduff, Training, Kurz. Pick the 🙂 confidence face. Click "Gespräch starten".*

### 3 · The interview [0:30–1:15]

*Interview room. Turn voice on (speaker icon) - Frau Caduff greets Lea out loud.*

**"Frau Caduff is a vocational trainer at the real company from Lea's tracker. She speaks -
and Lea answers like she would in the room."**

*Type (or paste) a deliberately weak answer:* `Weil ich gern mit Menschen arbeite.`
*Press Ctrl+Enter.*

**"Before Lea sees any feedback, Zusage asks her: how did that go? Predicting first trains
her inner judge."**

*Click 💪 "Stark". Feedback appears on the right.*

**"The coach disagrees - kindly. It quotes her own words, says what already works, and
gives one concrete next step: name a real moment from your trial apprenticeship. And the
interviewer reacts like a real person - with a follow-up question."**

*Point the cursor at the highlighted quote, then at "Als Nächstes".*

**"So Lea tries again."** *Click "Diese Antwort nochmals versuchen" and paste:*
`In der Schnupperlehre im Pflegeheim habe ich einer älteren Frau beim Essen geholfen. Sie hat sich so gefreut – da wusste ich: Das will ich machen.`

*Send. The score rows show green "+1.5"-style deltas.*

**"Same question, better answer - and she can see exactly how much better. That's
deliberate practice, not a chatbot."**

### 4 · The Gipfelbuch [1:15–1:35]

*Click "Beenden", pick 😎 for confidence after, click "Mein Gipfelbuch öffnen".*

**"At the end, Lea gets her Gipfelbuch - her summit log. Her interview drawn as a hiking
trail, her profile on the six criteria from Swiss vocational training, compared to last
time - and two next steps, written to encourage, never to shame. Her weakest answers
come back as two-minute drills - tomorrow, in three days, in a week. Spaced practice,
like learning vocabulary."**

*Scroll slowly: elevation profile → radar → "Deine nächste Etappe".*

### 5 · Multilingual [1:35–1:50]

*Go to "Übungsgespräch", choose Italiano → start → show Signora Bernasconi's greeting. Then quickly show the language list with "Schwiizerdütsch".*

**"Switzerland has four languages, so Zusage does too: German, French, Italian -
and Swiss German. Same coach, same rubric, same quality."**

### 6 · The teacher [1:50–2:10]

*Switch to the teacher tab: the class cockpit for "3. Sek A".*

**"Here's Lea's teacher. One screen: who practised this week, where the whole class
struggles - with a ready-made lesson idea - and who needs a nudge. Lea's actual answers
stay private unless she decides to share them."**

*Hover the heatmap, point at "Wo die Klasse Mühe hat", then at Luca's "wenig Selbstvertrauen" badge.*

### 7 · Under the hood & close [2:10–2:30]

*Show the small grey line under the coach panel ("1 model call per answer"), then the terminal with `make run` ending in "✓ selfcheck passed".*

**"Under the hood: one Apertus call per answer - more than four times under the challenge budget -
with every piece of feedback checked against what the student actually said. It runs on
a single consumer GPU, or fully offline on a school server. No student data leaves
Switzerland.**

**Zusage: practise until you get the yes. Bis zur Zusage."**

*End card: logo, "Bis zur Zusage · Jusqu'au oui · Fino al sì", github.com/shi1720/zusage.*

---

## 2-minute cut

Drop section 5 (multilingual) and shorten section 4 to its first two sentences.

## Recording tips

- Record each section separately (QuickTime or OBS), then join - easier retakes.
- Record the voice-over separately in a quiet room; leave 0.5 s of silence between sections.
- Before section 3, warm up the model with one answer in another tab so the first live call is fast.
- If a model answer looks different from the script, adapt one sentence - the structure still works.
