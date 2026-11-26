# Project state

The single place to find out where Adle stands and what to do next. Update it at the end of every
work session (see `AGENTS.md` → "Keeping the next agent oriented").

- **Last updated:** 2026-11-25
- **Branch:** `main`, the only one (ADR-043, since 2026-11-21; `dev` was folded into it).
  On GitHub: `github.com/XelXen/Adle`, public, since 2026-11-21
- **Last commit:** see `git log -1`
- **Active milestone:** M8 — release hardening, done as far as this machine can take it:
  failure handling (ADR-018), packaging (ADR-019), the licence inventory, the audits, the
  performance report, and the release checklist. Since then: a second AI provider, NVIDIA
  NIM, beside AIHubMix (ADR-021), through which **a real model has written lessons for the
  first time**; and, at the owner's request on 2026-11-20: a new look (ADR-022) in Geist
  (ADR-025), both providers used together (ADR-023), questions asked during a lesson
  (ADR-024), and a break while a lesson is written (ADR-026). Then, after the owner looked
  at the app and asked for a review of it: neutral colours with a near-black dark theme
  (ADR-027), every sentence rewritten short and plain (ADR-028), the findings of two reviews
  fixed (ADR-029), and a title bar of the app's own (ADR-030). And then the largest thing
  that was left from the plan: **a lesson opens as soon as its words are written**, and its
  pictures arrive while the learner studies (ADR-031). Sitting a lesson written that way
  showed a formula without its minus sign, and so: a picture is drawn at a size that suits
  the frame it is shown in (ADR-032). And on the same day, at the owner's word: Adle is under
  the GNU GPL, version 3 (ADR-033); it has installers for Windows, macOS and Linux, built,
  tried out and published by GitHub (ADR-034); and its first version, 0.1.0-alpha.1, was
  published from the tag `v0.1.0-alpha.1` the same evening:
  `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.1`. After looking at it the owner
  asked for eight things, and each was built that day (ADR-035 to ADR-042), the last of
  them a natural voice on the learner's own computer (ADR-042); and for one branch, with a
  release made by a commit (ADR-043). **0.1.0-alpha.2 carries all of it**: published from
  the release commit `622b396` on 2026-11-22,
  `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.2`. Since then, at the owner's word,
  what a learner reads is in American English (ADR-044); and, asked why pictures fail and
  are so few, why a PDF's syllabus is not covered, and for every slowdown to go: **most
  pictures are figures** that Adle draws from the lesson's data, four to seven a lesson
  with no request of their own (ADR-045); **a PDF's whole syllabus** from its outline or
  numbered headings (ADR-046); and **a lesson's answer mended rather than asked for
  again**, with a natural voice that begins as soon as the words are stored (ADR-047).
  Then, at the owner's word to do it all and to make sensible choices: **a lesson begins
  at its first part** while the rest is written, and its model thinks at "medium"
  (ADR-048), and the figures take the shapes a model writes, a probability shaded under a
  cumulative curve drawn as its rise among them (ADR-045's addenda). Each was measured on
  the owner's own chapter with the real provider ("The real providers" below). **All of it
  is in 0.1.0-alpha.3**, published from the release commit `3eddd4a` on 2026-11-22,
  `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.3`. Then, after the owner watched real
  lessons and asked for pictures that carry the idea: **a lesson is a slideshow**, every
  part that teaches a slide Adle draws from what the lesson scripts, a step at each phrase
  its narration marks, and a lesson begun about twelve seconds after it is asked for
  (ADR-049). **That is in 0.1.0-alpha.4**, published from the release commit `fd2c524` on
  2026-11-22, `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.4`. Then, at the owner's
  word after watching it ("first show example visually and then relate the theory to it";
  the richer voices so slow that the computer's voice read instead): **the case first, and
  the rule out of it** (ADR-050), and **a lesson in a natural voice made with its voice**,
  ready once its first part can be heard and never switching voices by itself (ADR-051).
  **That is in 0.1.0-alpha.5**, published from the release commit `2f3c894` on
  2026-11-22, `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.5`. Then, at the owner's
  word ("still time them because we dont know how weak the hardware would be"): **every
  voice is timed where it runs**, at setup, by every line and by every lesson, and a voice
  slower than speech gives a lesson a head start before it is ready (ADR-052); and, after
  looking at a concept and at making a course: **a course made straight from its files**,
  named by Adle and set up if asked (its concepts added, its first lesson begun), "Start
  from your materials" no longer offered, and a concept shown as what it is, then the
  learner's learning of it, then where it is in their files (ADR-053). **Both are in
  0.1.0-alpha.6**, published from the release commit `015506d` on 2026-11-23,
  `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.6`. Then, after looking at a
  lesson's bar of controls ("make it compact- too much text"; "allow to revert back if
  mistakenly clicked on this didn't help"): **one compact row of controls**, Read aloud,
  Transcript and "This didn't help" as icon toggles, and **"This didn't help" taken back**
  by Undo or by pressing it again (ADR-054); and, asked whether overlaps and pictures
  past the edge could be found ("idk how you'll check"): **a picture's words kept clear
  of each other and of the edge**, checked at every step of every example, and **a
  slide's step no longer than its words** (ADR-055), and then no line run through a
  word either (ADR-056). **All of it is in 0.1.0-alpha.7**, published from the release
  commit `9b7a633` on 2026-11-23, `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.7`.
  Then, at the owner's word about the voice ("voice never pronounces it as that"; "the
  expressive voice doesn't sound very nice"; "get rid of rich"; "allow samples"; record
  "if the voice is changed in settings"): **mathematics typed with the keyboard said as it
  is meant**, **Rich removed**, **the Expressive voice described by the learner** (with
  presets) and each lesson adding only its delivery, designed saying a passage made for it,
  **a sample of any voice before it is chosen**, and **a new voice recording the lessons
  opened last at once** (ADR-057); and, found as that release was checked, **an axis
  counted as a line** and **a moving label looking for room again only once its point has
  moved** (ADR-058). **All of it is in 0.1.0-alpha.8**, published from the release
  commit `2c01ef2` on 2026-11-24, `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.8`.
  Then, at the owner's word about notes ("what if PDF is a scanned copy of a notebook? or
  handwritten notes"; a textbook chapter whose page 4 "could not be read and [was]
  skipped"; "tests are way too long"): **a page with a detailed drawing read on a second
  try** (`587fb31`), **pages that are pictures read by the AI at the learner's word**
  (ADR-060, the owner having let the rule against uploading go "if it's really
  required"), and **a check that runs what a change can reach** (ADR-059). **All of it
  is in 0.1.0-alpha.9**, published from the release commit `76565a4` on 2026-11-24,
  `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.9`. Then the owner asked for five
  things at once (2026-11-24; all five are listed under "Next actions"), and the first is
  **a lesson is formed by rules, and each subject has its
  own** (ADR-061): seven rules of every lesson and thirteen kinds of subject written down
  once (`lessons/axioms.py`), a course with a subject (guessed from its name, named by the
  AI with its plan, or chosen by the learner), a writer given its subject's needs and its
  subject's example, slides that draw a timeline, a vessel, a molecule and code, and the
  rules readable from the course, one press away. And the second: **the Expressive
  voice put together from parts** (ADR-062): who speaks, age, pitch, pace, tone,
  feeling, delivery, accent and style, each chosen from a list, the description written
  by the core, voices to start from as choices of parts, and the learner's own words
  still the most exact way. And the third: **a course saved as a file, and brought in
  from one** (ADR-063): a template with nothing of the learner in it, or everything, to
  move a course; what either holds changed under "Advanced"; a file brought in always
  a new course, made by the ordinary roads, with what the learner knows worked out
  again from their answers. And the fourth: **settings saved as a file, and brought in
  from one** (ADR-064): the look, how lessons are taught, the voice, which provider is
  used, and the keys, each part chosen by the learner, the keys only ever locked with a
  password they choose; on another computer, a voice it does not have is set up only at
  the learner's word, else the nearest that runs there, else the computer's own, and a
  provider not offered there leaves the choice as it was. And the fifth: **a film of a
  whole course** (ADR-065): a chapter for each concept, each a ManimGX animation the AI
  writes, checked by a policy of its own and then by the engine at every moment, sent
  back three times at most with what was found, read in the natural voice, put together
  and made into a video, in a lane of its own; the film maker downloaded only at the
  learner's word. **All five are in 0.1.0-alpha.10**, published from the release commit
  `d8e2778` on 2026-11-25, `github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.10`. What is
  left of them is under "Next actions". Then, at the owner's yes the same day: **a film's
  pictures are looked over** by a model that sees them, once a chapter, and what it sees is
  mended with what the engine found (ADR-066); and a chapter sent back is shown back whole.
  And, asked the same day ("allow answer a question to change the lecture slides ... it
  forgot to draw hydrogen bonds"): **a question can have its part's picture drawn again**,
  used at the learner's press and put back as easily (ADR-067). And at the owner's word:
  **each provider's own limits, and several requests at once at NVIDIA** (ADR-068), a
  film's chapters and a file's pages asked for side by side; and **a soft shadow under a
  word that lands on another, or under a line** (ADR-069). Then, the owner asking for a
  teacher with character, slides as clean as a film's, deeper lessons, two more themes, and
  "this is finally 0.2.0": **a lesson's pictures stay Wanim scenes** (ADR-070); **a teacher
  the learner chooses**, or the Expressive voice's person (ADR-071); **deeper lessons** with
  summaries along the way (ADR-072); **a crowded slide drawn again beside the writing**, and
  a lesson's pictures drawn side by side (ADR-073); and **Pastel and Pastel dark** (ADR-074).
  **All of it is in 0.2.0**, the first version that is not an alpha, published as the latest
  release from the release commit `cb2f00c` on 2026-11-25,
  `github.com/XelXen/Adle/releases/tag/v0.2.0`. Then, at the owner's yes, three lessons
  written for real in the app through NVIDIA, and what they showed fixed (ADR-075): the
  teacher heard, slides that keep their pictures apart. **That is in 0.2.1**, published as
  the latest release from the release commit `f451016` the same day,
  `github.com/XelXen/Adle/releases/tag/v0.2.1`. Then, at the owner's word: each chapter of
  a film at work says what it is doing on a line of its own (ADR-076), a film writes five
  chapters at once at NVIDIA and leaves one request free for the learner (ADR-077), and a
  slip of the keys in a typed answer is answered again (ADR-078). **That is in 0.2.2**,
  published as the latest release from the release commit `ba24189` on 2026-11-26,
  `github.com/XelXen/Adle/releases/tag/v0.2.2`
- **Commits:** a commit is GPG-signed if the owner answers the passphrase prompt (a
  `pinentry` window on the desktop) within a few minutes. If not, it is made unsigned, as
  the owner asked on 2026-11-21. `git log --format='%h %G? %s'` shows which is which.
- **Pushing and releasing:** push `main` when a commit is ready; GitHub then runs everything
  on its own machines (`TESTING.md`, section 5) and publishes nothing. A version is published
  by a commit `release: <version>`, once every check has passed for it: an alpha as a
  pre-release, a stable version as the latest (`CONTRIBUTING.md` → Releasing, ADR-043).

## Milestone status

| Milestone | Status | Evidence / what is missing |
|---|---|---|
| M0 — Foundation | **Done** | Workspace, pinned toolchain, lint/type/test gates, docs, ADR process, CI workflow written. CI has run on GitHub with every push since 2026-11-21. |
| M1 — Desktop shell and Sprout | **Done** | App launches without a key; welcome, library, settings; key add/remove without exposure; themes; a11y gates. |
| M2 — Persistence and ingestion | **Done** | Database with safe migrations, backup and restore; import of PDF, DOCX, Markdown, text with provenance; duplicate detection; FTS5 search; course and materials screens. Vector search deliberately not built (ADR-007). |
| M3 — Curriculum and learner model | **Done** | Concept graph validated on every write (loops, references, order, layers); curriculum screen (list and map; add, edit, reorder, remove; objectives; prerequisites with reasons; links to materials; outline from headings); learner preferences; knowledge as an append-only record folded through BKT into four states with reasons; review scheduling; retrieval with provenance (ADR-009). **Deferred to the lesson work:** working memory and the interaction event log. Answer evidence is exercised through the service in tests; in the app only self-rating can create evidence until questions exist. |
| M4 — Wanim and Lesson IR | **Done** | Player frame, adapter, static scene policy, skill, threat model (ADR-004). Lesson IR 1.0 with a generated JSON Schema; one validating gateway; scenes re-checked on every read; answer keys kept in the core with deterministic scoring; the lesson player; the first lesson of the sample course (ADR-010). The same journeys pass against the packaged build. |
| M5 — Generation, audio, timeline | **Done** | Provider client, quota, and gateway; curriculum proposals and lessons as cancellable jobs compiled into the Lesson IR (ADR-012); the interface for both with every failure state; narration aloud through the computer's own voices (ADR-013). Two providers, chosen by the learner, each with its own key and count; a provider's next model stands in when its first is not available, and that is always said (ADR-021). Every path is tested against stand-ins. **A real model has written lessons** (Kimi K3.1 Pro and Mistral Large 4 through NVIDIA NIM, 2026-11-20); see "The real providers". |
| M6 — Assessment and adaptation | **Done** | Hypotheses about mistakes computed from the record (tentative, supported, rejected, resolved), checked with questions that would show them, and dismissible by the learner; slips counted as partly right; repeats counted in full only after a gap; questions kept for practice in the Lesson IR; a next-step policy with a reason for every step; the Learn tab, practice and review, "what next" after a lesson, "This did not help"; teaching strategy chosen or rotated (ADR-014). Not built by decision: model grading of open answers and model-proposed hypotheses. |
| M7 — Complete UX and sample course | **Done** (two items left as known gaps) | Done: every one of the eight sample concepts has a lesson with scenes, questions tagged with the mistakes their wrong options point at, and practice questions; every lesson is played from start to finish and every scene is run in both themes by the E2E suite. Also done: Settings → Privacy & data can save a copy of everything as one file, restore from one (checked and upgraded before anything is replaced; what is replaced is kept; undoable), and delete everything (ADR-016). Also done: the session summary (ADR-017). Polish done: every outcome of the new screens checked with axe, focus kept after "That was a slip". Left as known gaps, by decision: narration and animation are synchronised per segment (Wanim's slides mode was not tried), and screenshots are saved for review rather than compared against baselines. |
| M8 — Release hardening | **Done** (unsigned, by decision), and released as 0.1.0-alpha.1 | Done: a crashed or hung page, an uncaught error in the main process, and a core that dies are each handled, with a local log and no reporting (ADR-018). Packaging (ADR-019): a folder that runs by itself, with a private Python for the core, fuses set; the whole end-to-end suite passes against the packaged app, and the release build passes a start-up check from outside. Licence inventory generated and checked in every gate; `npm audit` and `pip-audit` clean; `PERFORMANCE.md` and `RELEASE_CHECKLIST.md` written. Since 2026-11-21: a licence (ADR-033); installers for Windows, macOS and Linux, built by GitHub, tried out where they are built and again on machines that did not build them; a release published from a tag (ADR-034). **Not done:** signing (the owner's decision), anyone's eyes on it on macOS or Linux, a generated lesson sat by a person (the owner's key is the owner's to type in). |

## What works in the running app

- First launch → welcome with the local-first disclosure → library. Remembered across restarts.
- Navigation rail (collapses under 960 px), light/dark/system theme, and Pastel and Pastel dark
  in a color the learner picks (ADR-074), applied before first paint.
- **The window has a title bar of its own** on Windows (and, untried, macOS): the app's
  canvas runs to the top edge, the system's buttons sit on it in the theme's colours, and the
  window is moved by the strip along its top. Linux keeps the frame it is given.
- **Library:** courses listed most recently used first; create a course from a topic or from
  materials; delete a course (with its files) after confirmation.
- **Course → Materials:** import PDF, Word, Markdown, and text files with the file dialog or by
  dropping them; progress while importing; per-file outcome (imported, already imported,
  rejected with a reason); extraction warnings; remove a source; search with file and page or
  section for every hit.
- **Course → Learn** (the tab a course with concepts opens on): one suggested next step with
  the reason for it, the alternatives ("Other options"), a note that stopping is fine when things
  are going badly, and each concept in learning order with its state in words, what is still
  missing, when it is next reviewed, and what Adle has noticed about it.
- **Hypotheses:** two answers pointing the same way show as "Seen more than once" with a
  sentence; one answer shows as "Suspected". "That was a slip" sets one aside.
  A slip of sign shows as a slip and is counted as partly right.
- **Practice and review:** a few questions on one concept, with why these questions, answered
  and explained as in a lesson, then a summary and what to do next. Nothing answered in the
  last twelve hours is asked again; if nothing can be asked, the screen says when it can.
- **Reviews:** scheduled by the core after answers; due ones are suggested first among routine
  steps and marked on the concept. Doing one moves the next further away.
- **The session summary** (Learn tab, under the suggested step): "This session" while the
  learner may still be in it, "Last time, yesterday" and the like afterwards. Lessons finished
  and questions answered; for each concept worked on, how many answers were right (with any
  that were given "with help" named, and one sentence saying what that means), what is still
  needed in the concept's own words, and when its review comes. No score, and wrong answers
  are not listed.
- **"This didn't help"** in a lesson: skip to the next question, have the concept explained
  another way (a chosen way of teaching; needs a key), or go to the course. The suggestion on
  the Learn tab changes accordingly and says why.
- **Course → Curriculum** (where a course without concepts opens, once it has a topic or materials): the
  concepts as a list in teaching order or as a map; add, edit, reorder, and remove concepts;
  learning objectives; what each concept needs first and why, with loops refused and explained;
  "Start from your materials" offers the headings of imported files as concepts; link a concept
  to passages in the materials; say how well you already know a concept and read back the record
  of everything noted about it.
- **Library → sample course:** "Try the sample course" adds "Introduction to neural networks"
  (eight concepts with objectives and reasons for every prerequisite) without a key. Every
  concept has a lesson of seven or eight parts: nine animated scenes and two things to try (the
  input of an activation function; the learning rate of gradient descent), questions in at
  least two forms with a question that asks to apply the idea somewhere new, and four or five
  further questions for practice and review. The whole loop can be walked without a key:
  lesson, evidence, the next concept, a prerequisite to revisit, practice, reviews.
- **Lessons:** a concept lists its lessons with how long they take and how far the learner has
  got. The lesson player shows parts one at a time with captions at the learner's reading pace,
  a board that fills in, a transcript, scenes that follow the narration (held until Start,
  paused with it), an interaction with keyboard-operable controls, and a description in words of
  every picture. Nothing plays until Start; Previous, Continue, and the numbered parts move
  around what has been reached.
- **Questions:** multiple choice, true or false, numeric, short answer, ordering, and
  self-assessed explanation. Hint, "I am not sure", and Skip. The core scores, explains, records
  the attempt and the evidence, and says in words what changed. After checking, options read
  "Your answer" / "Correct answer".
- **Resume and review:** a lesson reopens at the part where it was left; a finished one reopens
  from the start with every part open and no question blocking. A finished lesson ends with
  what to do next.
- **When a scene cannot run:** if it fails in the player, or the core withholds it, the part
  shows its description in words and the lesson goes on.
- **A picture is drawn at a size that suits the space it is shown in** (ADR-032), so that a
  small picture keeps its thinnest strokes on a display with one pixel to the point.
- **Suggested concepts:** "Suggest concepts with AI" on the curriculum says what will be sent,
  runs as a job with progress and Cancel, and ends in a review dialog where the learner picks
  what to add. Suggestions that finish while the learner is elsewhere wait to be reviewed or
  discarded. Nothing is added without the learner choosing it.
- **Generated lessons:** "Create a lesson with AI" on a concept (and "Create lesson" on
  the Learn tab) says what is sent, where, and about how long until the lesson can be
  started, shows progress and Cancel, and adds a lesson that plays like any other.
  **The lesson is there as soon as its text is written** (ADR-031): listed with "Pictures on
  their way", announced once, and ready to start while its pictures are drawn. A part whose
  picture has not arrived says so and gives the same idea in words; a picture that arrives
  takes its place in a part that has not begun, and is offered ("The picture is ready. Show
  picture") in one that has. "Stop" then stops the pictures and keeps the lesson; removing
  the lesson, or its course, stops the work. For another lesson on the same concept
  the learner can choose how it should explain; left alone, Adle uses a way not used yet. A
  concept has at most four lessons. No key, a rate-limit wait, a used-up day, a provider failure, and a cancelled job each
  have their own words and their own way forward. While a model is at work the job says
  what it is doing ("Writing the lesson: Kimi K3.1 Pro is thinking it through", then "is
  writing"): the models that work today take minutes over one answer.
- **Which model wrote it:** if a provider's first model is not available, its next one is
  asked, and that is said while it happens ("Kimi K3.1 Pro is not available at the moment.
  Asking Mistral Large 4 instead") and afterwards: in the notice that a lesson is ready, and
  in the review of suggested concepts, which names its author ("Suggested by Mistral Large 4
  on NVIDIA NIM"). A lesson a model wrote says so under its title, in one line ("Written by
  Kimi K3.1 Pro on NVIDIA NIM. AI can make mistakes."): who wrote it is kept with the
  lesson.
- **Narration aloud:** the lesson is read by a voice installed on the computer (never an online
  one), with "Read aloud" and "Transcript" switches in the lesson. Without a voice, or if the
  voice fails, the narration is shown as text at the learner's reading pace.
- Settings → AI provider: **"Provider": Automatic, AIHubMix only, or NVIDIA NIM only.**
  Automatic uses every provider that has a key, each for what it is best at: what is waited
  for (a question, a list of concepts) goes to the quick one, long work (a lesson) to the
  roomy one once the quick one is half used for the day, and the other is asked when one
  cannot answer. "Current routing" shows the plan for each kind of request and the reason.
  The choice is changed only there, and not while something is being written. Below it, a
  card for each provider: its address, its models in the order they are asked, its key
  (save, replace, remove; OS-encrypted; kept for one provider at one address and never sent
  anywhere else), **"Test key"** (one word from that provider, nothing of the learner's
  sent), and "Usage today", with a sentence saying whether the limits are the provider's
  or Adle's own.
- **Asking a question during a lesson:** "Ask a question" in the lesson's bar pauses the
  lesson and opens a dialog: the learner's own words or a ready-made question, what will
  be sent and where, and "Ask". The answer is kept beside that part under "Your questions
  about this part", says who wrote it, and can be removed. The learner can carry on with
  the lesson while it is written. On a question the lesson is asking, Adle helps without
  giving the answer, and the answer that follows counts as an aided one.
- **Waiting:** where something is being written, the app says about how long it usually
  takes, that the learner need not watch, and offers **a break**: one clock sized to the
  wait, a small idea of what to do away from the screen, and what is being written
  meanwhile. The rail shows "Now": what is being written (or "Drawing pictures") and a
  running break. When it is ready, which for a lesson is when it can be started, the app
  says so once, and so does the operating system (fixed words, only while Adle is in the
  background; can be turned off in Settings → Appearance). A break is also offered
  at the end of a lesson. Nothing about breaks is counted or kept.
- "Cancel" and "Stop" take effect at once, however silent the provider is.
- **Library:** opens with "Continue learning": the suggested next step of the
  course last opened, with its reason. A lesson a model wrote can be removed from its
  concept (after a confirmation that says what goes and what stays); a lesson that draws on
  the learner's materials names the passages under its title.
- Settings → Learning: pace, explanation depth, narration, voice, volume (with a sample),
  captions, goal (stored by the core).
- Settings → Privacy & data: what is stored and exactly what each kind of request sends.
  **Save a copy** writes everything to one `.adle` file wherever the learner chooses.
  **Restore from a copy** checks the file, brings it up to date, keeps what it replaces as a
  safety copy, and restarts the local service on it; a file that is not a copy, or cannot be
  used, changes nothing and says why. **Show safety copies** opens their folder; one of them
  can be restored the same way, which is how a restore is undone. **Delete everything** asks
  in the operating system's own window, then removes every course, material, answer, and
  safety copy; the key and the appearance settings stay. Each works when the local service
  has failed to start, except saving.
- Settings → About: whether Adle's background service is running, and "Restart"; an
  animation check with a mirrored, keyboard-operable slider; "Open log folder" opens the
  folder of local logs.
- **Words** (ADR-028): short and plain everywhere, with nothing about the app's own workings
  unless the learner must act on it. The rail says nothing about the background service
  while it runs. Progress is Not started, Learning, Nearly there, Understood.
- **When the app itself fails** (ADR-018): a page that crashes or hangs, and an error nobody
  caught in the main process, each bring a plain message from the operating system with a way
  on (reload, wait, restart, quit); a core that dies is started again, at most twice in five
  minutes. Each is noted in `logs/app.log` on this computer. Nothing is reported anywhere.
- Python core starts as a supervised child, authenticates with a per-launch token, migrates its
  database (with a backup first), and exits with the app.
- **As a packaged app** (`npm run package`): a folder with `Adle.exe`, the app in an archive,
  and a private Python for the core that takes nothing from the computer it is on. Everything
  above works in it; the end-to-end suite says so.

- **Installed like any other program** (ADR-034): a setup program on Windows (for one person,
  no administrator), a disk image on macOS for Apple's and for Intel's processors, a `.deb`
  and a tarball on Linux. Installing and uninstalling leave the learner's courses and
  settings alone. Settings → About says under what licence Adle is and leads to it and to
  the source. Adle never looks for a newer version of itself.

Not present yet (do not assume): a generated lesson sat by a person (one was gone through
by a script; see "The real providers"), exporting a single course to share (not planned;
ADR-016), a signed build (the owner's decision, ADR-034), anyone's eyes on Adle on a Mac or
on Linux (GitHub's machines build it, install it and start it there; nobody has looked).

## Test results

Windows 11, Node 24.3.0, Python 3.12.11, Electron 45.4.1. The latest: every gate and every
journey on the tree of ADR-070 to ADR-074, for 0.2.0, 2026-11-25 (the rows below). Every gate, the whole
end-to-end suite included, on the tree of ADR-050 and ADR-051 (the case first; a lesson made
with its voice), 2026-11-22: 202 journeys of 202 in 35.3 minutes, none retried, among them
every slide example stepped through in both themes (a formula made of the picture, a
sentence and an equation rewritten out of the ones before, points written inline) and
four journeys of a natural voice (a lesson ready once its first part can be heard, and one
waited for at its first line until the other voice is chosen); and again on the release
commit `2f3c894`, with the fix of a race in stopping a recording (`36bf34b`), which only
sets the version besides: 202 of 202 in 35.2 minutes, none retried. Before: on the tree of
ADR-049 (a lesson as a slideshow), 2026-11-22: 190 journeys of 190 in 32.9 minutes, none retried, among them every slide example stepped
through in both themes and a generated lesson whose slide steps on as its words are read;
and again on the release commit `fd2c524`, which only sets the version: 190 of 190 in 32.7
minutes, none retried. Before: on `13e5f99` (ADR-048, a lesson begun at its first part, with
the review's fixes and the last mends), on 2026-11-22; the release commit `3eddd4a` only
sets the version, and GitHub checked everything again for it. Before: the figures' commits
(ADR-045 to ADR-047), and `f3a75e6`. The release folder was not
built again on this computer, because the owner had Adle open from it; the build for tests
was, and passed its start-up check. What GitHub's machines ran is in the rows that name
them.

| Gate | Status | Detail |
|---|---|---|
| Contracts up to date (API and Lesson IR schema) | PASS | `npm run contracts:check` |
| Scene name allowlist up to date | PASS | `npm run wanim-names:check` |
| Packaged scene guide up to date | PASS | `npm run scene-guide:check` |
| Nothing secret about to be committed | PASS | `npm run secrets:check` |
| Prettier | PASS | |
| ESLint (type-aware, a11y, hooks) | PASS | 0 warnings |
| TypeScript (`tsc`, 6 projects) | PASS | |
| Vitest | PASS | 1024 tests, on the tree of ADR-077 and ADR-078 (2026-11-26); among them an answer almost right said "Almost", kept open, and reported only once answered again (ADR-078), and a film's chapters each saying what they are doing (ADR-076). Before: 1020 tests, 58 files; among them Pastel and Pastel dark (ADR-074): every tinted token inside sRGB and every pair at its ratio in all 360 hues, Pastel dark setting again all Pastel sets, the window's canvas and ink the tokens' own, the color a whole hue from 0 to 359, kept while another theme is chosen and carried in a settings file, and the swatches a radio group beside a slider along every hue; the teacher made of parts or in the learner's words, and named in what a lesson and a question send (ADR-071); what a slide said of its layout handed back with its trial's verdict, each once (ADR-073); among them the limits said as each provider's own, a day with no limit counted and how many requests go at once, a small allowance said only of a provider with a daily limit, and chapters being written several at a time (ADR-068); among them which parts of a lesson offer to change their picture, the words suggested for it, what a request to change it sends, and a picture put into a lesson the learner is in, or put back, taking the place of the old one where it stood (ADR-067); among them where each chapter's pictures go to be checked, and the bound with that look, said before a film is begun, and a film's time counting the look (ADR-066); where a course's film stands, its chapters, the line said at a moment, its subtitles with nothing in them read as markup or timing, a film saved only by its id to a place chosen in the system's window, and what setting the film maker up downloads said before anything is (ADR-065); among them a settings file's keys locked with a password and nothing else (scrypt, then AES-256-GCM), a wrong password or a changed byte refused before anything is applied, the costs a file names for unlocking bounded, and its parts checked one by one (ADR-064) |
| ruff (lint + format) | PASS | |
| mypy (strict) | PASS | 142 source files |
| pytest | PASS | 2263 tests on the tree of ADR-077 and ADR-078 (2026-11-26), among them a slip of the keys said and answered again with nothing kept, and none in a short answer or a number (ADR-078); five of six chapters of a film written at once at NVIDIA while a check of the key still goes (ADR-077); each chapter's own line (ADR-076). Before: 2242 tests, among them the teacher a lesson is written by (ADR-071): put together from parts in any order, Adle's own when none is chosen, the learner's words kept short, the Expressive voice's person while it reads and the learner lets it, chosen by parts or in words and never both, and given to the writer of a lesson and of an answer as a quoted description; a lesson of up to 20 parts (ADR-072; the first run found a test still expecting 14, which now follows `MAX_SEGMENTS`); a crowded slide sent back once, told which of its elements lay over which, tried again and kept under its own name, and nothing sent back where the provider takes one request at a time (ADR-073); among them a soft shadow under a word over something (ADR-069): in the stage's color, a little below and to the right, rims wider and fainter one after another, strongest under the letters and not full there, under every letter, with round corners, and the two slides that cannot be laid out clear drawn whole and passing the policy, now bounded at 8,000 nodes; among them each provider's own limits and several requests at once (ADR-068): AIHubMix's five a minute and hundred a day, a day with no limit never used up, as many in flight as a provider takes and no more, requests let in together never overrunning the minute, work stopped while it waited sending nothing; pieces of a job side by side, the first failure or Stop stopping the rest; three chapters of a film written at once while the film maker checks one at a time, in order where the provider takes one, a chapter that fails stopping the other; two pages read at once; and an original held open as its file is removed let go of in a moment, or at the next start; among them a part's picture drawn again at a question (ADR-067): one request that says what the part says and shows, a picture kept with its note and put into the lesson only at the learner's press, through `parse_bundle`, its own put back when the note is removed, never for a part with no picture to change, and a slide's script kept in its scene in base64 so that no word of a model's is in a scene but as a quoted literal; and the film maker's home taken away even while Windows holds it a moment; among them a chapter's pictures looked over (ADR-066): the engine's sheets read in order and bounded, what is said beside each picture, what the model saw read into lines of the writer's file, the look had once when a version runs clean or before the last mend, passed over when it fails, and sent only where a model sees pictures; a line given a run time mended; and a film of a whole course (ADR-065): a chapter checked by a policy of its own before any of it runs (72 hostile files refused, none of them run), what can be mended in one mended and the mended file checked whole (an engine name used bare, numpy or math not imported, brackets beyond a line's animations), what the real engine printed read by the chapter's own line, a film made, sent back three times at most, stopped, continued, removed and saved with a stand-in engine and provider, a chapter not blamed for an engine that starts cold, and the film maker set up only from what is pinned, with nothing of this computer's in its environment; among them the core's part of a settings file: the voice a file names planned for this computer (that one, set up only at the learner's word; else the nearest lighter one that runs here; else the computer's own) and each preference brought in only as a value it may have, the rest left as it was (ADR-064); among them a course file read as one from anywhere (member names that are paths, sizes that lie, parts that claim a state: each refused, nothing ever extracted) and a course saved and brought in whole: a template with nothing of the learner and no name of a document, a transfer with its materials, citations, progress worked out again from the answers, and notes; a hostile lesson left out and counted; half a course removed (ADR-063); among them the Expressive voice put together from parts: one sentence written from them by the core, the same whatever order they were chosen in, never longer than a learner may write, the parts kept beside it and let go once they no longer make it, a voice of parts heard before it is chosen (ADR-062); among them the rules of a lesson and what each of thirteen subjects needs, a course placed by its name (and left general when two subjects are as likely), by the AI with its plan, and by the learner, whose choice stands; a writer given one subject's needs and its example, every example obeying the rules it is an example of; a timeline, a vessel, a molecule and code drawn from data; and what six real lessons asked of a slide and did not get, each mended with a test (ADR-061); among them a page with no text kept as a picture and a PDF of nothing but pictures imported, a file's pictures read page by page into its text in their place, a picture sent only to a model seen to read one (AIHubMix alone sends nothing), removing the file stopping its reading, and a page drawn in a child process (ADR-060); among them a page drawn past pypdf's budget read on a second try, the time for second tries shared, and the counts said (`587fb31`); among them every slide and figure finding an axis as a line, reading a line's path once, and a moving label looking again only once its point has moved (ADR-058); among them typed mathematics said, Rich taken off a computer that has it, the learner's description with each lesson's delivery, samples made once, a new voice recording the lessons opened last, a lesson opened going first, a recording following the voice, and switching back saying nothing again (ADR-057); among them the figures of a lesson offered for their trials in one step however slow the gate (`89f6b40`); among them a line through a word counted and one beside it not (ADR-056); among them every slide pinning its labels, tidying them and saying how it is laid out as each step ends, every figure saying so as each page ends, and a step's animations fitted to its words; and which reports of "this did not help" still count, taking one back through the API, and revision 0012 up and down with the learner's rows. Before: `test_only_the_newest_copies_of_replaced_data_are_kept` failed now and then (three whole runs) because two restores in one step of Windows' clock (about 15 ms) named their safety copies the same, and the second replaced the first: a copy is now named a microsecond later when its name is taken (`_new_copy`), tested with a clock that stands still |
| Playwright + Electron (E2E) | PASS | 197 of 197 in 23.9 minutes on the tree of ADR-077 and ADR-078 (2026-11-26, `node scripts/check.mjs --all --e2e`), none retried. Before: 197 journeys in 39.9 minutes on the tree of ADR-076 (2026-11-26, `node scripts/check.mjs --e2e`, all of them, the API having changed): 187 at the first try, 2 at their second, and 8 at neither, all ten the scene player's own (`scene-player.spec.ts`), untouched by that change, whose scenes ran slow while the owner's own Adle, started anew during the run, was busy on the same computer; that file again with retries off, 53 of 53 in 3.3 minutes. Among them two chapters of a film written at once, each saying what it is doing in its own row. Before: the scanned-pages journey, mended to answer each page by its number (`1aff6dc`), three times over with retries off: 3 of 3. Before: 196 journeys in 32.2 minutes on the tree of ADR-075 (2026-11-25, `node scripts/check.mjs --e2e`, all of them): 189 at the first try, 5 at their second, and 2 at neither: slides untouched by that change whose steps took 17 to 22 s while the owner's own Adle was open and busy on the same computer (`example_experiment.py` and `example_timeline.py`, dark); those seven again with retries off, 7 of 7 in 1.3 minutes. Before it, the slides alone twice, 50 of 50 and 51 of 51, among them the two slides of the real lessons (`two_groups_beside.py`, `moved_beside.py`) with nothing over anything at any step. Before: 194 journeys in 23.5 minutes on the tree of ADR-070 to ADR-074 (2026-11-25, `node scripts/check.mjs --all --e2e`): 193 at the first try, none of them retried; and 1 that failed twice because it still expected the old "what is sent" of a question, which now names the teacher (`ask.spec.ts`): mended, and its file again with retries off, 5 of 5. Among them both Pastel themes with axe on every primary screen, a color picked by swatch and by the slider's keys, kept when another theme is chosen, and the window drawn in it; Pastel dark in mint carried in a settings file to another profile; a lesson written by the teacher the learner chose; and the crowded slides naming what lies over what. Before: 191 of 191 in 22.5 minutes on the tree of ADR-069 (2026-11-25, `node scripts/check.mjs --e2e`, all of them, the scene policy having changed), none retried: among them every slide and figure example with no word over another at any step, as before, and the two slides that cannot be laid out clear in both themes, each such word with a shadow that can be seen. Before: 186 journeys in 24.3 minutes on the tree of ADR-068 (2026-11-25, `node scripts/check.mjs --e2e`, all of them, the API having changed): 183 at the first try; 1 at its second, a slide untouched by that work (`distance.py`, light) whose steps took 22 s while the unit tests ran beside the journeys, and 6.4 s again; and 2 that still expected the old limits (a fifth request in a minute waiting at AIHubMix, and NVIDIA's note under the name the journey gives it), mended, with the sentence that called NVIDIA's allowance small. Then the files of those, and the slides, again: 62 in 16.8 minutes, the two mended passing; while the computer was busy two slides stalled (`example_meter.py` light twice, `list_sorted.py` dark once) and the lesson seen taking shape was written before its five parts were counted (twice); those three again with retries off, 3 of 3 in 37 seconds. Among them NVIDIA's day counted and not capped, with how many requests go at once, and a file's two pages read at once. Before: 186 of 186 in 24.9 minutes on the tree of ADR-067 (2026-11-25, `node scripts/check.mjs --e2e`, all of them, the API having changed), none retried: among them a part's picture drawn again at a question, used, put back and used again, and the hydrogen bond, a new slide example, stepped through. Before: 184 of 184 in 22.7 minutes on the tree of ADR-066 (2026-11-25, `node scripts/check.mjs --e2e`, all of them, the API having changed), none retried: among them a film whose chapter's storyboard goes to NVIDIA's stand-in and what it saw is told in the mend; then the three of a film again after the look was given its effort, 3 of 3. Before: 183 of 183 in 22.8 minutes on the tree of the release commit `d8e2778` (2026-11-25, `node scripts/check.mjs --all --e2e`), none retried. Before: 183 of 183 in 22.7 minutes on the tree of ADR-065 (2026-11-25, `node scripts/check.mjs --e2e`, all of them, the API having changed), none retried: among them a film of a course made with a stand-in engine and provider, stopped, continued, said to be ready by the operating system, played with its subtitles, saved and removed; the film maker's download said and nothing fetched; the page unable to name a place to save a film; and Settings saying where films are written. Before: 180 of 180 in 22.6 minutes on the tree of ADR-064 (2026-11-24, `node scripts/check.mjs --e2e`, all of them, the API having changed), none retried: among them settings saved with their keys and brought in on a new profile with the password, a wrong password changing nothing, settings saved without the keys, a file that is not settings, and the page unable to name a place or to see a key. Before: 177 of 177 in 22.1 minutes on the tree of ADR-063 (2026-11-24, `node scripts/check.mjs --e2e`, all of them, the API having changed), none retried: among them a course saved as a template and brought in as a new one that says “Imported”, everything saved to move a course and brought in with and without its progress, backing out of either window, a zip that is not a course, and the page unable to name a place to save or a file to open. Before: 173 of 173 in 21.7 minutes on the tree of ADR-062 (2026-11-24, `node scripts/check.mjs --e2e`, which chose them all because the API changed), none retried: among them the Expressive voice put together from parts, heard, saved, started from a ready-made voice, and written in the learner's own words; then, after one sentence was added to its note, the five voice journeys again. Before: 172 of 172 in 26.9 minutes on the tree of ADR-061 (2026-11-24, `node scripts/check.mjs --all --e2e`), none retried: among them a course saying what it is taught as and the learner saying otherwise, and each of the 42 slide examples stepped through with nothing over anything (25 more than before: a timeline, vessels, molecules, code, and each subject's own example). Before: 151 of 151 in 18.2 minutes on the tree of the release commit `76565a4` (2026-11-24), none retried. Before: 151 of 151 in 18.4 minutes on the tree of ADR-059 and ADR-060 (2026-11-24), none retried: each slide, figure and scene example once, the themes taking turns, figures and scenes as rehearsals (ADR-059); among them scanned and handwritten notes read at the learner's word, nothing sent before, one picture a request to NVIDIA alone, and what was read found at its page; a scan kept rather than refused, and with no key nothing to press. Before: 204 of 204 in 33.7 minutes on the tree of the release commit `2c01ef2` (2026-11-24) but for what a step that does not come says, none retried, among them every slide and figure example with no axis through a word either; then the two slides that had stalled once each, `machine.py` and `tangents_inline.py`, ten times each in both themes with retries off: 40 of 40 in 6.2 minutes, each between 8.3 and 10.2 s. Before: 204 journeys in 34.7 minutes on the tree of ADR-057 (2026-11-24), 203 at the first try and 1 at its second: a slide untouched by that work (`machine.py`, light) that did not say its step was done within 30 s, and stepped through in 10.2 s again; among them a Natural speaker heard before it is chosen, then chosen. Before: 204 of 204 in 33.7 minutes on the tree of the release commit `9b7a633`, none retried. Before: 204 of 204 in 33.8 minutes on the tree of the release of 0.1.0-alpha.7 with ADR-056 (2026-11-23), none retried, among them every slide and figure example with no word over another or under a line, and nothing past the edge, at any step. Before: 204 of 204 in 46.1 minutes on the tree of ADR-055 (2026-11-23), none retried, among them every slide example stepped through and every figure example run in both themes with no word over another and nothing past the edge at any step. Before: 204 journeys in 39.7 minutes on the tree of ADR-054 (2026-11-23), 203 at the first try and 1 at its second: a sample scene untouched by that work (`forward_pass.py`, dark) that did not finish within its time, and ran in 17 s again; among them "This didn't help" said, undone in its dialog, left standing across a lesson opened again, and taken back from the bar. Before: 203 of 203 in 35.3 minutes on the tree of the release commit `015506d`, and in 37.4 minutes on the tree of ADR-052 and ADR-053 (2026-11-23), none retried, among them a course made from its files, named by the AI and set up through to its first lesson. Before: 202 of 202 in 35.3 minutes on the tree of ADR-050 and ADR-051, none retried. Before: 190 of 190 in 32.7 minutes on the release commit `fd2c524`, and in 32.9 minutes on the tree of `449dcf3`, none retried; among them the seventeen slide examples stepped through cue by cue in both themes, and a generated lesson whose slide steps on as its words are read. Before: 154 of 154 in 26.7 minutes on `13e5f99`, none retried; among them a lesson seen taking shape and begun at its first part, one begun there that waits at the end of what is written and goes on by itself, and the seventeen figure examples (two rises; tanh and erf) in both themes. The tree before the review's fixes: 152 of 152 in 26.3 minutes, none retried. Before: 149 in 26.8 minutes on the tree of ADR-045 to ADR-047, 148 at the first try and 1 at its second: a sample scene untouched by that work (`backprop_chain.py`, dark) that did not finish within its minute, and ran in 16 s again. 30 of them run the fifteen figure examples in both themes, and one writes a lesson with four figures and goes through it to its slider. Before: 116 journeys in 19.5 minutes on `f3a75e6`, 115 at the first try and 1 at its second: a sample scene (untouched by that work) that did not finish within its minute while other checks ran beside it, and ran in its usual 17 s again. The voice's two journeys passed three times each with retries off. 22 journeys run the sample course's scenes in both themes. Wherever a journey checks a screen for accessibility it also checks that nothing pressable lies where the window is moved |
| Third-party licences (`npm run licenses:check`) | PASS | Part of the gate; 412 npm and 41 Python packages, none refused, none unstated |
| `npm audit` (all dependencies) | PASS | 0 vulnerabilities, 2026-11-21 |
| `pip-audit` (everything in `uv.lock`) | PASS | No known vulnerabilities, 2026-11-21 |
| GitHub Actions CI | PASS | Run 45870619546 on `245850f` and run 45875847041 on the release commit `ba24189`, 2026-11-26: every job. Run 45860538985 on `1d9d71d` failed only in trying out the installer for Apple's processors: the disk image was "temporarily unavailable" to attach just after it was made; attaching and detaching are tried again a little later (`27d9af0`). Run 45866580999 on `27d9af0` failed only in building the release app for Intel Macs, the packager's download of Electron dropping ("fetch failed"); a dropped download is tried again (`245850f`), and that run was stopped by the push of it. Before: run 45747366488 on `1aff6dc` and run 45751413215 on the release commit `f451016`, 2026-11-25: every job; run 45745443421 on `0d959e8` was stopped by the push after it, which carries it. Run 45735882920 on `719405c` failed the scanned-pages journey on Linux, twice: a file's pages are read side by side (ADR-068), so the second page's request reached the stand-in first and took the answer queued for the first, and what was read was found on page 2. The app pairs every answer with its own page; the journey assumed an order. The stand-in now answers a kind of request by its words, and the journey each page by its number (`1aff6dc`). Before: run 45731432843 on `bd6398e` and run 45731435685 on the release commit `cb2f00c`, 2026-11-25: every job; run 45730665674 on `f3c500d` was stopped by the push after it, which carries it. Run 45713992682 on `e0f0fc1`, the same day: every job. Before: run 45504077810 on `57073d3`, run 45510572948 on `26b6511`, run 45516577918 on `522f80b` and run 45522707493 on `8463062`, 2026-11-24, and run 45568533254 on `580f4ea` and run 45572795869 on the release commit `d8e2778`, 2026-11-25: every job, the audit of the film maker's locks among them. Before: run 45360385030 on `d156030`, run 45373179609 on `58d888c` and run 45434303266 on the release commit `76565a4`, 2026-11-24: every job. Before: run 45332947505 on `89a7d26`, run 45353284069 on `9ea453f` and run 45353347434 on the release commit `2c01ef2`, 2026-11-24: every job. Before: run 45274982680 on `72fde79`, run 45289133928 on `beb8a66`, run 45306519850 on `30895f2` and run 45312162613 on the release commit `9b7a633`, 2026-11-23: every job. The first release commit of 0.1.0-alpha.7, `e2f1e22`, did not pass (run 45306561888): `test_the_figures_of_a_lesson_taken_whole_are_offered_for_their_trials_all_at_once` saw one figure offered where three should have been, because the figures were offered one by one as the gate looked at each, and the gate had grown slower with ADR-055; nothing was published. Fixed in `89f6b40` (all offered in one step, with a test that makes the gate slow on purpose), and released from the commit after it. Before: run 45214333848 on `0ca95e8`, run 45232844385 on `3bebf70` and run 45240157859 on the release commit `015506d`, 2026-11-23: every job. Run 45229054785 on `d81611c` passed its checks, unit tests and every installer, and its end-to-end suites were stopped by the push of `3bebf70`, which carries it. Before: run 45094360998 on `36bf34b` and run 45098914521 on the release commit `2f3c894`, 2026-11-22: every job. Run 45093539444 on `916eca3` failed one core test on Linux, which passed here: removing a lesson while its voice was recorded ended the recording as failed when the engine's end was noticed before the stop; fixed in `36bf34b`, with a test of both orders. Before: run 45060012402 on `449dcf3` and run 45077644773 on the release commit `fd2c524`, 2026-11-22: every job, both end-to-end suites and every installer where it was built and where it was not. Before: run 45015241700 on `13e5f99` and the run on the release commit `3eddd4a`, 2026-11-22, the Linux installer check among them again (it waits for the app's processes before removing its profile now). Before: runs on `f3a75e6` and on the release commit `622b396`, 2026-11-22: the gates, unit tests and three audits (npm, the core's Python, and the programs a natural voice is set up with) on Linux; every journey on Linux and on Windows (116 of 116 on each, none retried, on `f3a75e6`); and the four installers, each built, installed, started and removed on the machine that built it and again on a machine that did not, each check now also having the installed app's Python make an environment with pip in it |
| Packaged build: every journey (`npm run e2e:packaged`) | PASS | On this tree, 2026-11-21: 105 journeys in 13 minutes, of which 104 passed and 1 passed on its second try. That one told whether a scene was still from two pictures of the page (see Findings); it now compares the scene's own canvas. Its file and the player's, with one journey added, were then run again against the same build: 48 of 48 passed with no retry |
| Packaged build: release start-up check (`npm run package:check`) | PASS | The build for tests on this computer, 2026-11-21: fuses set, the core's Python makes an environment with pip in it (it did not before `python.exe` was kept beside `adle-core.exe`), starts on an empty profile with the core up after 6.8 s, nothing in the log of failures, no service left behind. The release build: on GitHub's machines, every push |
| Packaged build on a computer that never had the project | PASS | On GitHub's machines, `a812d34`: each installer was handed to a second machine of its system that has Node, the scripts that do the trying and nothing else of the project, and was installed, started (the core up within 1.7 to 3.0 s) and removed there. Such a machine still carries more than a new computer does, so on Windows the package's 73 programs and libraries were also read for a runtime library they ask for and do not bring (none). A person installing a release on their own computer: NOT RUN |
| Installers | PASS | Made, installed, started and removed on GitHub's machines (`a812d34`): `…-windows-x64-setup.exe`, 133 MB; `…-macos-arm64.dmg`, 151 MB, and `…-macos-x64.dmg`, 156 MB; `…-linux-x64.deb`, 126 MB, and `…-linux-x64.tar.gz`, 171 MB. Those of 0.1.0-alpha.4, in the same order: 142, 158, 165, 134 and 182 million bytes; of 0.1.0-alpha.5: 142, 161, 161, 134 and 182; of 0.1.0-alpha.6: 142, 161, 160, 134 and 182; of 0.1.0-alpha.7: 142, 162, 162, 134 and 182; of 0.1.0-alpha.8: 142, 157, 164, 134 and 182; of 0.1.0-alpha.9: 145, 164, 168, 138 and 187; of 0.1.0-alpha.10: 146, 160, 168, 138 and 187; of 0.2.0: 146, 159, 167, 138 and 187; of 0.2.1: 146, 166, 168, 138 and 187; of 0.2.2: 146, 162, 166, 138 and 187. Not on this computer, which has no Inno Setup. On Ubuntu the tarball is unpacked and not started, because Ubuntu keeps an unpacked app from building its sandbox; the folder it holds is started there by the check of the release build |
| The release itself | PASS | **0.2.2** from the release commit `ba24189` (ADR-043), 2026-11-26, in run 45875847041, after run 45870619546 had passed on the commits it carries: every check passed, and the installers made and tried in that run were published as the latest release, tagged `v0.2.2` at that commit, with five installers and `SHA256SUMS.txt`. On this computer, every gate on the release tree itself (1,024 Vitest tests, 2,263 core tests), and every journey on the tree of ADR-077 and ADR-078 before it, which differs in its version numbers and the two build scripts' retries. **0.2.1** from the release commit `f451016` (ADR-043), 2026-11-25, in run 45751413215, after run 45747366488 had passed on the commits it carries: every check passed, and the installers made and tried in that run were published as the latest release, tagged `v0.2.1` at that commit, with five installers and `SHA256SUMS.txt`. On this computer, every gate on the release tree itself (1,022 Vitest tests, 2,249 core tests), and every journey on the tree of ADR-075 before it, which differs only in its version numbers and the scanned-pages journey's mend. **0.2.0**, the first version that is not an alpha, from the release commit `cb2f00c` (ADR-043), 2026-11-25, in run 45731435685: every check passed, and the installers made and tried in that run were published as the latest release, tagged `v0.2.0` at that commit, with five installers and `SHA256SUMS.txt`. Its notes no longer call a version an alpha (`bd6398e`, with a test). On this computer, every gate on the release tree itself (1,022 Vitest tests, 2,242 core tests), and every journey on the tree just before it, which differs only in its version numbers and the notes script. **0.1.0-alpha.10** from the release commit `d8e2778` (ADR-043), 2026-11-25, in run 45572795869: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.10` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.9** from the release commit `76565a4` (ADR-043), 2026-11-24, in run 45434303266: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.9` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.8** from the release commit `2c01ef2` (ADR-043), 2026-11-24, in run 45353347434: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.8` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.7** from the release commit `9b7a633` (ADR-043), 2026-11-23, in run 45312162613: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.7` at that commit, with five installers and `SHA256SUMS.txt`. Its first release commit, `e2f1e22`, did not pass and published nothing (see the CI row). **0.1.0-alpha.6** from the release commit `015506d` (ADR-043), 2026-11-23, in run 45240157859: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.6` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.5** from the release commit `2f3c894` (ADR-043), 2026-11-22, in run 45098914521: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.5` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.4** from the release commit `fd2c524` (ADR-043), 2026-11-22, in run 45077644773: every check passed, and the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.4` at that commit, with five installers and `SHA256SUMS.txt`. **0.1.0-alpha.3** from the release commit `3eddd4a` (ADR-043), 2026-11-22, published as a pre-release with its installers and checksums. **0.1.0-alpha.2** from the release commit `622b396` (ADR-043), 2026-11-22: its notes job found the version in `package.json` and the changelog and not yet released; every check passed; the installers made and tried in that run were published as a pre-release, tagged `v0.1.0-alpha.2` at that commit by GitHub, with five installers and `SHA256SUMS.txt`. Before it, 0.1.0-alpha.1 by `release.yml` on the tag `v0.1.0-alpha.1` (`c320bd7`), 2026-11-21: the tag is the version and the changelog has it; the four builds made again from the tag, each installer installed, started and removed where it was built and on a machine that did not build it; published as a pre-release with five installers and `SHA256SUMS.txt`, whose sums are the ones GitHub computed for the files. Nobody has installed one by hand yet |
| Code signing | NOT RUN | Not done, by the owner's decision (ADR-034). Windows and macOS say so to whoever opens a build |
| macOS / Linux | PASS (machines); NOT RUN (a person) | Linux: every journey passes on GitHub's Ubuntu machine, and the `.deb` installs and starts on Ubuntu as it ships. macOS: built, signed ad hoc, installed from its disk image and started, on Apple's and on Intel's processors; no journey runs there. Nobody has looked at Adle on either. The window's own title bar (ADR-030) has been seen on Windows 11 only |
| Real AI providers | AIHubMix: BLOCKED. NVIDIA NIM: tried by hand, works | No test may call a real provider. 2026-11-25, after 0.2.0: three lessons and three questions in the real app, through a relay that adds the key, eleven requests, every one answered (see "The lessons of 0.2.0, tried by hand"). 2026-11-25, later: a chapter's pictures looked over by hand, eleven requests, every one answered, one look empty for thinking too long (see "A film's pictures, looked over"). 2026-11-25: two films by hand, about a dozen requests, every one answered (see "A film of a course"). 2026-11-22: the whole way through the owner's chapter seven times (three at "high", three at "medium" with a lesson begun at its first part, one at "none"), and two more lessons at "none", by hand, 31 requests in all; before that, three times, ten requests (see "A whole way through the owner's chapter"). AIHubMix: a relay error for one key; the other account must be topped up. NVIDIA: lessons, curricula and answers were written through Adle's own services on 2026-11-20; tried again after the way an answer is read was changed (ADR-029): a key check in 26 seconds and an answer to a question in 88, two requests. See "The real providers" |
| A lesson a real model wrote, in the app | PASS | By a script, 2026-11-21, twice: a lesson written by Kimi K3.1 Pro, opened from its profile with no key, gone through in both themes from its first part to "Lesson complete", no error in the console. The second was written with the lesson opening when its text was ready (usable after 298 s, its one picture after 541 s); its interactive picture ran, and its formula is whole since ADR-032. Not a person |

## Launch reliability (ADR-008)

While the window was created hidden and shown on `ready-to-show`, about 1 to 3 in 100 launches
driven by Playwright never produced a first frame: no `paint` entry, no animation frame,
`capturePage` timed out, and the window never appeared. Hiding and showing, resizing,
`invalidate()`, and reloading did not recover it. Measured with a launch loop:

| What the driver did (window created hidden) | Stalled |
|---|---|
| Called `show()` after the heading rendered, with early viewport emulation | 2 of 110 |
| Called `show()` after the heading rendered, no emulation | 3 of 50 |
| Waited for the app's own show, then focus only | 0 of 50 |
| Nothing at all | 0 of 40 |
| Early viewport emulation only | 0 of 60 |
| Waited for the app's own show, then emulation and focus | 1 of 80 |
| No driver attached (plain `electron -r` observer) | 0 of 40 |

No single test-side action explains it. The window is now created visible (`show: true`); with
that build the loop showed **0 stalls in 150 launches** and the E2E suite passed twice with no
flaky test. The E2E helper waits for the window, requests focus, and fails fast with a clear
message if the page is not painting. `retries: 1` stays on; a test reported as *flaky* is to be
investigated, not ignored.

## Findings worth knowing (all recorded in ADRs, nested AGENTS files, or the Wanim skill)

- **How long a model thinks varies tenfold between two requests at the same setting**
  (ADR-048): a lesson at "medium" thought 1,500 to 30,000 characters before writing, so
  the wait before its first part was 53 to 205 seconds. Measure more than once before
  deciding anything about speed, and say a wait as a range.
- **Without thinking, a model does its working out in its answer.** At "none" a lesson
  began in 5.5 seconds, but one of four had a question whose answer key contradicted its
  own explanation, which held the model's second thoughts. Lessons stay at "medium".
- **A reviewer who reads the change without the author's reasoning finds what tests do
  not.** Five real bugs in the part-by-part lesson (ADR-048), four of them confirmed by
  probes, were found that way after every test passed; each is now a test.
- **A value handed over by the page can carry functions of its own** (ADR-029). The preload
  once called `.map` on "the dropped files", and a page could have answered with any path.
  The preload calls no method of anything from the page.
- **"No network" is more than requests.** A peer connection reached listeners on this
  computer by UDP and TCP with every request refused. What stops it is no name lookups, a
  proxy that is nowhere and no UDP outside a proxy. A `webrtc` directive in the content
  security policy is not known to this Chromium: it stops nothing and logs an error on
  every page.
- **Anything that can be pressed and may lie along the top of the window must say
  `app-region: no-drag`** (ADR-030). A tall dialog reached under the strip the window is
  moved by; a test's clicks do not pass through the window's frame, so only a check of where
  things lie finds this.
- **`scrollbar-width` or `scrollbar-color` anywhere switches off the `::-webkit-scrollbar`
  parts**, and with them the look of every scroll bar.
- **`getByRole(..., { name: 'Answer' })` also finds "Answering your question".** A journey
  read the dialog before its answer was there. Short names take `exact: true`.
- **When many journeys fail for one reason** (a change of wording), run the files one at a
  time: the list reporter prints what failed only when a run ends. And look for the words a
  journey expects in the sources before running it: two small scripts did that in seconds
  where a run takes minutes.
- **`set_fill` and `set_color` take their arguments in order, without names, in Wanim
  0.1.3.** `set_fill(opacity=0.3)` stops a scene with "ManimColor only accepts ...", and
  `set_fill(colour, opacity=0.3)` runs and leaves the shape with no fill. A lesson a real
  model wrote lost its interactive picture to the first. The scene policy now refuses both
  (`unreliable_call`), which gives the model one more try with the reason; the guide says
  how to write them; `e2e/scene-player.spec.ts` reads the pixels. Found by sitting that
  lesson in the app, not by any test: the policy cannot see what a call does when it runs.
- **A test that waits longer than its stand-in holds out proves nothing.** The tests for
  "removing a lesson stops its pictures" passed with the stopping taken out: the held
  answer lets go by itself after twenty seconds and the tests waited thirty. They wait five
  and ten now. Take the fix out and watch the test fail before believing it.
- **A journey that misses once in a hundred is a race in the app as often as in the test.**
  One pressed "anything that says lesson" before a concept's lessons had loaded, and so
  pressed "Create a lesson with AI". The button no longer shows until the list is known.
- **A picture shrunk by more than two loses strokes, it does not thin them.** The runtime
  drew every scene 1280 wide; a lesson shows it 565 wide. A minus sign that fell on the
  wrong row of pixels was not there (ADR-032). It showed only in pictures of the page,
  which are taken at one pixel to the point: this computer's own display has one and a
  half, and there nothing was lost. Found by sitting a lesson a real model wrote.
- **The window's pixels and a picture of the page are different pictures.** A page under
  test is laid out at one pixel to the point whatever the display; the window is shown at
  the display's scale, and `capturePage` reads that. A journey that reads the window and
  depends on how many pixels there are fixes the scale (`displayScale`). The first
  version of the journey for the above passed for either drawing size for this reason.
- **A picture of the page is not a picture of the scene.** A journey that told whether a
  scene was still by comparing two pictures of the page where it is passed a hundred times,
  then missed once in the packaged run and twice in a row in a full run. Two things change
  there with the scene quite still: about forty pixels at the stage's rounded edge, by one
  level of 255, seconds after loading; and the mark that offers to start the lesson, which
  lies over the stage and answers to a pointer, the real one included when it rests on a
  test's window. The journey now compares the scene's own canvas, and keeps both pictures
  with the report if they ever differ.
- **A build machine is not a learner's computer, in both directions.** It lacks things a
  desktop has, and the first runs on GitHub's machines (2026-11-21) found three assumptions,
  none of them in the app: a Linux machine with no keyring, where Adle rightly refuses to
  keep a key and the journeys that save one stopped (the test session is now given one); a
  Windows machine that lists voices and has nowhere to play sound, where the app stands in
  for the voice as designed and the journey had taken a listed voice for one that can be
  held; and a virtual display that asks for a right to draw on it, which the start-up check
  had stripped from the environment along with everything else. And it has things a new
  computer lacks: everything the app was built from, and the runtime libraries of the tools
  that build software. So each installer is tried again on a machine that did not build it,
  and on Windows the import table of every program in the package is read for a part of the
  Visual C++ runtime the package does not bring (none: 71 programs, 2026-11-21).
- **The usual tool is not always the small one.** electron-builder, wrapped around a folder
  Adle already builds, was 290 packages, six advisories and an install script. Each
  system's own tool (Inno Setup, hdiutil, dpkg-deb) is a few dozen lines (ADR-034).
- **Copy only a Python you asked for, and copy it once.** The private Python is copied from
  wherever the core's environment says its Python is. On a machine with a Python of the
  right version that is `/usr`; the package script refuses anything uv does not manage.
  And a name that is a link in that installation is copied as the whole program: on Linux
  the interpreter went in three times and its library twice, until its other names were
  left out. The build now lists the largest files of the core, so that is seen at once.
- **A release folder cannot be rebuilt while the app is open from it** (Windows refuses,
  with `EPERM`, and removes nothing). Close Adle, or use the build for tests.
- **A screenshot of the page is not the window.** The system's buttons, and how a dimmed
  page looks around them, show only in a picture of the window itself (`PrintWindow`).
- **A shell string is no place for a backslash.** A regular expression or `\n` passed
  through `node -e` or a here-document arrived changed, more than once. Patches are files.

- **A provider's reference is not its endpoint** (ADR-021). Kimi K3.1 Pro's documented
  default for `reasoning_effort` is not what it does when the field is left out: without it
  the model thought for eight minutes over a lesson and wrote nothing. Mistral Large 4
  refuses the value its reference lists and needs one it does not list. What works, and
  the date it was seen to, is written beside each model in `generation/provider.py`. Try a
  new field against the real endpoint by hand before relying on it.
- **A model writes TeX in JSON with one backslash as often as with two.** `\sigma` is then
  not JSON, and `\frac` is: a form feed and "rac". `drafts.mend_backslashes` mends an
  answer before it is parsed; do not parse a model's JSON any other way.
- **`set_opacity` fills a plotted curve.** The first interactive scene a real model wrote
  showed a curve as a solid shape for that reason. The scene guide says to use
  `set_stroke(opacity=...)`, and `e2e/scene-player.spec.ts` reads the window's own pixels
  to check both.
- **Real models take minutes.** A lesson's text: about five minutes from Kimi, seven and a
  half from Mistral. A scene: two to four. "Stop" and the time limit are checked on every
  line a provider sends, because the first piece of an answer arrives minutes in.
- Wanim 0.1.3 evaluates scenes in a same-origin child frame: needs `unsafe-eval` and a real origin.
- A scene stuck in a loop blocks its process; a new frame on the same origin never starts. Hence a
  fresh `adle://<id>.player` origin per frame.
- `preload_fonts` is typed but not exported; use `preload_submodules('fonts')`.
- `new URL('adle://…').origin` is `"null"` in Node. Use `adleOriginOf()`.
- Playwright forces a light colour scheme unless `colorScheme: null` is passed to `electron.launch`.
- On Linux, `safeStorage` may silently use a plaintext-equivalent backend; Adle refuses it.
- TypeScript 7 and ESLint 10 are not usable yet with the lint plugins (ADR-001).
- **Python `multiprocessing` hangs under the service on Windows** (the service blocks a thread on
  stdin, which a `multiprocessing` child inherits). Children are started with `subprocess` and
  explicit pipes (ADR-007). Unit tests parse in-process and cannot see this class of bug; the
  integration test that runs the real service can.
- SQLAlchemy URLs are built with `URL.create`, and SQLite URIs are percent-encoded: a profile
  folder may contain `#`, `%`, or `?`.
- `getByRole(..., { name })` matches substrings, and two controls may share a name (the
  navigation rail and a course's back button are both "Library"). Use `exact: true` and scope
  to a region.
- A `BrowserWindow` created with `show: false` can fail to paint its first frame (ADR-008).
- Vite inlines assets under 4 KB as `data:` URIs. One KaTeX font is that small, and the CSP
  (rightly) refused it. Both builds set `assetsInlineLimit: 0`. Found by an E2E test that
  asserts an empty console.
- React's lint rules (`react-hooks/immutability`, `refs`) reject writing to a ref received as
  a prop and reading refs in a `useState` initialiser. Long-lived non-React state goes in a
  small class created once (`openSession`, `SceneCues`).
- **A copy of a SQLite database made with the backup API is still in write-ahead mode.**
  Merely opening it, even read-only, creates a `-shm` and a `-wal` file beside it and leaves
  them there. Every copy is therefore switched to single-file mode before it is closed
  (`backup_database`); a test looks at the folder afterwards.
- `PRAGMA trusted_schema = OFF` does not break the triggers that keep the search index in
  step: FTS5 is marked harmless by SQLite. Checked with a probe before it was switched on,
  and by the whole suite since.
- The first version of a test for a guarantee can pass without testing it. The seven
  guarantees of ADR-016 were each removed from the code in turn and a test was seen to fail
  (a throwaway script outside the repository does this in a minute).
- Several notices of what a lesson request sends had left out the learner's goal, pace, depth
  of explanation, and the few words about where they stand on the concept. All of them now
  come from one function (`lessonDisclosure`), which is to be kept in step with
  `lesson_request` in the core.
- A long shell heredoc that contains an apostrophe can fail to parse under Git Bash. Patch
  scripts are written to a file and run from there.
- **Playwright's handle on a page does not survive that page's process crashing**, even after
  the window has reloaded ("Target crashed"). `e2e/recovery.spec.ts` reads the reloaded
  window through the main process with `webContents.executeJavaScript`, which works under
  the app's Content Security Policy.
- A self-marked answer is recorded as "unsure". The session summary first left such right
  answers out of its count, which read as a miscount beside "3 of 3 answers right"; the
  end-to-end journey showed it. They are counted, and named as lighter evidence (ADR-017).
- Patch scripts written in Python on Windows turn LF into CRLF unless they write with
  `newline="\n"`. Git normalises on commit, but the working tree is left mixed. Node's
  `writeFileSync` does not do this.
- A course's sample lesson has three questions; without more, a review can only repeat them.
  Lessons now carry up to eight further questions (`Lesson.practice`) for practice and review.
- On a question that is hard to guess, a slip of sign moves the estimate more than a right
  answer after a hint that gave the method away. That is intended (ADR-014) and tested.
- **In Wanim 0.1.3 a `Dot` given its position as an argument (`Dot(point, color=...)`) loses
  its colour and is drawn white**, which is invisible on the light stage. The shipped example
  had this too. A dot is created with keywords and then placed
  (`Dot(color=..., radius=...).move_to(point)`); the scene policy refuses the other form
  (`unreliable_call`) so that a generated scene cannot have it either. Found by looking at the
  screenshots the E2E suite takes of every scene.
- Text inside a scene is drawn in `ink` or `muted` only. The accent colours are for shapes:
  as text on the stage they do not have enough contrast in one theme or the other.
- The sample lessons are written by hand as JSON. A mistyped formula would fail nowhere (the
  player shows what it cannot typeset as written), so a unit test typesets every formula of
  every sample lesson and checks that narration, which is read aloud, contains no notation.
- An animation-only scene starts blank and is over in a few seconds, while its narration takes
  half a minute. Scenes follow the narration only at segment level today (start, pause, and a
  cue to leave a live page). Finer synchronisation needs Wanim's slides mode
  (`self.next_slide()`), which is documented upstream and not yet tested here.

## The real providers

Two providers (ADR-021). No test calls either: what follows was done by hand, with scripts
kept outside the repository that drive the core's own services, and is described so that it
can be done again.

### NVIDIA NIM: it works

Tried on 2026-11-20 with the owner's key, against
`https://integrate.api.nvidia.com/v1/chat/completions`. Requests that day: about thirty,
most of them small.

| What was asked for | By | Requests | Time | Outcome |
|---|---|---|---|---|
| A lesson on activation functions (sample course) | Kimi K3.1 Pro | 4 | 17.5 min | Nine segments, three checkpoints, two scenes. The first draft was refused (TeX with one backslash; now read), the second accepted. Both scenes passed the static policy as first written |
| A curriculum for "Probability for data analysis" | Kimi K3.1 Pro | 1 | 2 min | Twelve concepts, three objectives each, prerequisites that form a valid order; added without an issue |
| A lesson on gradient descent, after the fixes | Kimi K3.1 Pro | 2 | 8.7 min | Nine segments, one interactive scene; draft and scene each accepted as first written |
| A curriculum, with a first model that does not exist | Mistral Large 4 | 2 | 5 min | NVIDIA's own HTTP 404 for the absent model; Adle said so, asked Mistral, and recorded "… was not available, so Mistral Large 4 wrote this in its place" |

- All three generated scenes were then run in the isolated player, in both themes, with a
  one-off Playwright spec that is not in the suite: each loads, draws, and either finishes or
  waits for the learner with its controls announced.
- What the runs changed in the product: `reasoning_effort` for both thinking models; the
  reader that mends TeX backslashes, and a line in the prompt; a rule in the scene guide
  about showing a curve; "stop" and the time limit on every line; a refused request moving
  on to the next model; the job saying what the model is doing.
- GLM 5.3 Flash, the third in line, has not answered once: no line in three minutes, in
  three attempts. If the first two are both away, a request waits three minutes and fails.
- **One of these lessons was sat in the app from start to finish on 2026-11-21, by a
  script**: the profile the lesson was written into was opened in the app (a copy of it,
  with no key, so nothing was asked of anyone) and gone through part by part in both
  themes: ten parts, two questions answered and one skipped, the lesson finished, the
  course's next step shown, no error in the console. Its first picture played. Its second,
  the one to try, did not run: see "Findings" for why, and what now catches it. A person
  has still not learnt from one: the key has to be typed into Settings by the owner.

To do it again, from the repository root (the scripts are in the session's scratch folder,
`tools/`; they are described here because that folder does not last):

```bash
uv run --directory services/core python <scratch>/tools/real_smoke_nim.py nvidia <key file> <output dir> probe "lesson:Loss" curriculum
uv run --directory services/core python <scratch>/tools/nvidia_stream_diag.py <key file> <model id> <saved prompt> <answer file> usage effort=low
```

The first builds the real services on an empty profile, chooses the provider, puts the key
in the in-memory vault, and saves every prompt and answer. The second sends one saved prompt
to one model and prints, every twenty seconds, how much thinking and how much answer has
arrived: it is how the `reasoning_effort` findings were made.

### AIHubMix: still blocked at the provider

On 2026-11-19 the owner's key was valid (`GET /v1/models` lists exactly
`coding-kimi-k3-free`) but all nine completion requests failed with HTTP 500
`do_request_failed` (`Post "https://***/coding/v1/messages": Bad Request`): on both the
OpenAI-compatible and Anthropic-compatible endpoints, with the smallest possible body.
Retried on 2026-11-20 with the request printed on the model's own page: the same answer. So
the relay between AIHubMix and the model is refusing, for this key or for everyone; nothing
in Adle can be changed to fix it, and Adle was not made to pretend to be another program to
find out.

A second key, the same day: HTTP 200, and the text was the provider's own: "Sorry, to
prevent abuse of free resources, accounts that have not been recharged can only try 10
times. You can increase the free quota after recharging; https://console.aihubmix.com/topup".
With that account the model is reachable in principle, and what stands in the way is topping
the account up, which is the owner's to do. Adle recognises such an answer (`provider_notice`,
ADR-020): one request, the provider's words shown, the settings offered.

Tried again on 2026-11-20 through the new "automatic" choice, with keys for both providers
(`scripts/dev/real_provider_check.py`, see "Trying the real providers again"): AIHubMix
answered a check of its key and a question with the same notice; NVIDIA's Kimi K3.1 Pro
answered the check in 14 seconds and then **the question, in AIHubMix's place, in 64
seconds**, and the answer's record says "AIHubMix could not answer, so NVIDIA NIM wrote
this." That run is also why an account that refuses is now left alone for six hours, not
ten minutes: each try at it can be one of the ten the account allows.

New installations start on "automatic", which with one key is simply that provider. The
owner's description of AIHubMix as the quick one is written into its definition (`quick`)
and has not been observed: its model has never answered Adle.

### Trying the real providers again

    uv run --directory services/core python ../../scripts/dev/real_provider_check.py \
        --out <a folder outside the repository> \
        --aihubmix <file holding that key> --nvidia <file holding that key> \
        --selection auto check ask curriculum lesson

Keys are read from files and never printed. Every prompt and answer is saved under
`--out`, with which provider and model each request went to and how long it took, and the
data it leaves can be opened in the app (`ADLE_USER_DATA_DIR=<out>/profile`). No test runs
this, and it spends real allowance.

The step `document:<file>` goes the whole way through a document and times each step:
import, a course plan, a lesson on its first concept (until it can be started, and with
every picture), and a question in that lesson.

### A whole way through the owner's chapter (2026-11-22)

Three runs of `document:testchap.pdf` through NVIDIA, each request at its measured model:
import 1 s; a course plan 18 to 52 s, every section in it; a lesson's words 116 to 232 s
for one request (the model's thinking varies); a question 10 to 16 s. Ten requests and
about 109,000 tokens in all, as Adle counted them. Each run found something that cost a
lesson a second request or its pictures, and each is now mended (ADR-045 to ADR-047): all
five answers the runs gave are usable lessons as they came, with twenty-seven figures of
twenty-seven. Then at "medium", and with the lesson begun at its first part (ADR-048, run
7): a plan 37 s, the lesson begun at 77 s and whole at 122 s, a question 19 s. Run 8, with
every fix in: begun at 205 s (the model thought 30,000 characters), whole at 245 s, a
question 10 s. At "none", measured and not kept: begun at 5.5 s, but one lesson of four
had an answer key that contradicted its explanation. With the figure shapes taken since
(counted with `scripts/dev/figure_census.py`), 74 figures of 75 in every answer the model
wrote that day. The tables are in `PERFORMANCE.md`. What the model wrote is kept outside
the repository, as the owner's chapter is.

### A lesson as a slideshow (2026-11-22)

Eight lessons by hand through NVIDIA (`PERFORMANCE.md`): asked as a slideshow (ADR-049) the
model thought 19,000 to 59,000 characters at "medium" and a lesson could be begun after 118
to 313 s; without thinking, after 11.5 to 13.5 s, whole at 63 to 97 s, every part kept, five
or six slides a lesson, every question right but one practice question with two equal
options (now caught in drafts). What the answers scripted is drawn as the model meant it;
their slides were stepped through in the player and looked at. What the model wrote is
kept outside the repository.

### Every voice, timed (2026-11-23)

Every voice timed on the development machine, line by line and making a lesson through
NVIDIA (`PERFORMANCE.md`): ready 13.6 s after the lesson was asked for in Natural, 29.7 s
in Rich (its pinned model fetched for this into a scratch folder, every file checked, not
into the owner's profile), 40 to 49 s in Expressive. Natural is 4.3 times faster than
speech on all of the processor and 1.5 times on one thread of it. Two requests: 2 of the 80
a day allowed by hand.

### The case first, and a lesson made with its voice (2026-11-22)

Three lessons by hand through NVIDIA with the prompt of ADR-050, each made with the
Expressive voice borrowed read-only from the owner's own setup into a profile of its own
(`PERFORMANCE.md`): ready (its first part heard) 40.2, 45.0 and 49.0 s after it was asked
for, every word at 64 to 75 s, the whole voice at 71 to 105 s. No slide shows a formula in
its first step; the lesson on sample spaces brings its numbers out of its pictures 14
times; what a model wrote that could not be drawn (a point written inline, a point moved by
{"x": ...}, a number following a point, a slider that moved nothing) is read as meant, and
every slide of the day's six lessons draws with nothing left out. Before, the voice was
loaded again for every part it caught up with: 25 s for its first line and 13 for its
second each time, against 2 to 3 s a line once loaded. Three requests: 51 of the 80 a day
allowed by hand.

### A film of a course (2026-11-25)

Two films by hand through NVIDIA (Kimi K3.1 Pro), the real engine and the Kokoro voice
(ADR-065, `PERFORMANCE.md`). The first, on photosynthesis, was stopped on purpose once it
had shown what was wrong (a bare engine name; an engine that never ended its first run in
a new home; a line with more brackets than animations). The second, two chapters of
history, was made whole: 34.5 minutes, 6 requests, 7 minutes of film at 1080p with sound
throughout, one chapter clean and one with two faults of layout left after three mends.
Every request answered; none was refused or cut short. About a dozen requests in all, of
the 80 a day allowed by hand.

### A film's pictures, looked over (2026-11-25)

By hand through NVIDIA (ADR-066, `PERFORMANCE.md`). Three looks at a chapter of the earlier
film tuned what the look is asked; then a film of one chapter on the fall of the monarchy
was made whole through Adle's own services: 34.5 minutes and 5 requests (written, mended
three times, looked over once), 3 minutes 16 seconds of film at 1080p with sound
throughout, the chapter clean at the end. It found two things, both fixed: a line given a
run time stopped the engine (now mended by Adle, `policy.with_timing_passed_on`), and the
look thought past its 24,000 tokens and said nothing (now sent at a `reasoning_effort` of
"medium", after the same look was tried at "medium", "low" and "none"). The film is in the
session's scratch folder (`look/real1/`). Eleven requests in all, about 240,000 tokens.

### The lessons of 0.2.0, tried by hand (2026-11-25)

At the owner's yes, after 0.2.0 was published (ADR-075). For the first time the whole app
was used with a real model: the test build on a fresh profile, NVIDIA's endpoint moved to a
relay on this computer (`scripts/dev/provider_relay.mjs`, with
`ADLE_PROVIDER_ENDPOINTS`) that put the real key on each request while the app held a
stand-in one; a driver in the ignored `var/real-trial/` (a journey's helpers, never part of
the suite) chose the teacher "Curious scientist", made a course and the concept "Why ice
floats" with three objectives, asked for its lesson from the concept's panel, stepped
through every slide in the player, and asked a question about a part. Three runs, eleven
requests, every one answered: each lesson by Nemotron 3 Ultra in 85, 123 and 93 s (begun
at its first part after 6 to 12 s), each question by Nemotron 3.5 Super in 10 to 12 s.
Every lesson had 13 parts, four questions, a summary partway and one at the end, and a part
on what holds beyond the example. **The crowded slide was drawn again beside the writing
each time** (ADR-073): two requests in the first run, while the lesson was still being
written, the better kept but still crowded; two in the second and one in the third, each
kept with nothing in the way. What the first two runs showed, each fixed and tried again
(ADR-075): the teacher was not heard (a textbook's voice, no light moment: told now as a
voice to take on, with two or three light moments a lesson); molecules put beside each
other piled up where there was no room on the side asked for, and a stone moved below its
pond landed on a box shown later (what is put or moved beside another now keeps clear of
what shares the stage); a slash escaped twice showed its backslash. The third lesson was
heard as its teacher (feathers and books in a suitcase, molecules holding hands in a
crowded dance, "What if ice sank?"), and its answer said the molecules "haven't gone on a
diet; they just need more personal space". Still seen: the first summary comes after five
or six parts of new material, not three or four. The lessons, requests and answers are in
the session's scratch folder (`real/run1/` to `real/run3/`).

## Next actions

**Asked for by the owner on 2026-11-26, after 0.2.1: done, and released in 0.2.2.**

- **Asked and set aside the same day:** a way for a chapter of a film to say that an
  overlap is meant (a Venn diagram), so that it is not sent back to be mended. The owner,
  on reflection: "there will be never that text overlaps with anything for a reason —
  leave it". Nothing was built; the film maker still counts every overlap of text as a
  fault.

- **Done (ADR-078): "sometimes the user can make a mistake for filling answer — like i did
  CH3CHWCH3 instead of CH3CH2CH3 — so for very minor or close mistakes, it allows for a
  retry".** A typed answer within a slip of the keys of an accepted one
  (`scoring.near_miss`: a character put in, left out, changed or two swapped, in an answer
  of four characters or more; two in one of ten or more; never in a shorter one or a
  number) is told "Almost: check what you typed, and try again" (`outcome: "near"`),
  with nothing of the answer and nothing kept, and the question stays open; once a sitting
  a question, after which an answer is scored as it is.
- **Done (ADR-077): "if there are 6 concurrencies available, why just using 3 for film
  mode? use 5 and retain one in case he wants to study lessons till then".** A film writes
  as many chapters at once as the provider takes requests but one (`chapters_at_once`):
  five at NVIDIA, never more; one at a time at AIHubMix. Tested with six chapters, five
  asked for together and a check of the key going at once meanwhile.
- **Done (ADR-076): "for the film if multiple tasks are being done at once — why just one
  progress text? i want to see progress on all of them".** Each chapter being made works
  through its own view of the film's job (`_ChapterContext`), and what it says is its own
  line in the job's progress (`progress_detail.chapters`: number, what it is doing,
  stage), shown in that chapter's row of the Film tab (`chaptersAtWork`); the job's own
  line counts the chapters written ("Writing chapters: 2 of 8 done"). A chapter waiting
  for its turn at the film maker says so. Found on the way, and repaired:
  `services/core/AGENTS.md` had its first 450 lines doubled into its middle by `0d959e8`
  (a paragraph added with JavaScript's `replace` held `` $` ``, which stands for
  everything before the match); rebuilt from `f3c500d` with what was meant. Patch text
  that may hold a `$` with Python's `str.replace`, or a function given to `replace`.

**Asked for by the owner on 2026-11-25, after 0.2.0: done, and released in 0.2.1.**

- **Done (ADR-075): "Yes, try them" (the teacher, the deeper lessons, and crowded slides
  drawn again, with NVIDIA by hand).** Three real lessons in the real app through a relay
  (above, "The lessons of 0.2.0, tried by hand"). Fixed from what they showed: the teacher
  heard (a voice to take on, in the writer's role; two or three light moments a lesson; a
  teacher of parts saying what they never do), the lesson's outline naming its summaries,
  what is put or moved beside another keeping clear of what shares the stage (two new
  slide examples), and a slash escaped twice. Left: the first summary still comes late;
  slides whose arrows end in empty space are not looked for (a film's are, ADR-066).

**Asked for by the owner on 2026-11-25, for 0.2.0: done, and released in 0.2.0.**

- **Done (ADR-071): "make the ai a bit character-ful, allow random witty moments rarely
  ... fun facts", and "the lesson should adapt the character of [the Expressive voice] ...
  or allow building the character just like voice ... the character info should be given
  to that ai too".** Settings → Learning → Teacher: a teacher of parts (manner, kind of
  teacher, humor, fun facts, words), from six to start from, or in the learner's own words
  (300 characters); while the Expressive voice reads, a switch (on unless turned off)
  makes the teacher that voice's person (`lessons/character.py`,
  `GenerationService.teacher`). Given to the writer of every lesson and answer as a quoted
  description (`prompts._teacher`), and named in what those requests say they send.
  Light moments and fun facts are an axiom (`light_touch`): one part in four at most.
  Left: not tried with a real model.
- **Done (ADR-072): "not hurry stuff ... explain the concept clearly to even a child:
  examples, intuition, animations, summaries, generalisations".** A lesson is asked for in
  10 to 16 parts (up to 20), 2 to 5 beats, 3 or 4 questions; three new rules: a child
  could follow, summed up along the way and at the end, from the examples to the general
  idea. Left: not tried with a real model; a longer lesson's time to write not measured.
- **Done (ADR-073): "ai can draw the next picture and fix the last one parallelly".** A
  slide names what is in whose way as it is tried; a crowded one is sent back twice at most,
  beside the writing, where the provider takes several requests at once, and kept only
  when it is better, under its own name, through the gate; a lesson's model-written
  pictures are drawn up to three at once. Left: not tried with a real model.
- **Decided (ADR-070): "switch to manimgx for film look if it can act the same way as
  wanim".** Not for lesson slides yet: its browser player needs WebGPU, loads about 26 MB
  in every frame, and makes a video before playing it. Looked at again when that changes.
- **Done (ADR-074): "2 more themes: pastel (user can pick the color), and pastel dark".**
  Ten named colors and a slider along every hue, every contrast kept in all 360 hues, the
  window drawn in the color, the color kept in a settings file.

**Asked for by the owner on 2026-11-25, after 0.1.0-alpha.10: done, and released in 0.2.0.**

- **Done (ADR-069): "if text overlaps anything ... use a shadow underneath the top
  (latest) element", then "a gradual fade shadow and that too translucent", "the type
  like under mouse pointers in windows", "if background is light then shadow should be
  light too so to hide the stuff behind", and "increase the shadow opacity — still not
  full but more".** As each step ends, `audit` gives the later of two words on the stage
  that lie over each other, and a word a line runs through, a shadow (`layout.shade`,
  `shadow`): copies of the word at the front of its parts, a little below and to the
  right, each only a background stroke in the stage's color with round corners, wider and
  fainter one after another, about three quarters opaque under the letters; a word with a
  line through it is raised above the line, and a moving label with no clear place is
  shaded each frame. Two slides that cannot be laid out clear (`fixtures/slides/crowded/`)
  are stepped through in both themes. Tried on the way and left: one rim a letter, which
  ate into the next letter of tight serif text; shading before anything was shown, which
  shaded words for ones they never meet; a black shadow, which on the dark screen showed
  only over what was lighter. The scene policy's bound is 8,000 nodes (the busiest example
  came to 6,187). Nothing is sent back to be drawn again, as the owner said.

- **Done (ADR-068): "nvidea nim has 40 requests per min limit, no cap for how many
  requests tho so we can go for concurrent requests ... and for aihubmix, 100, not 90".**
  The limits are the providers' own (`QuotaLimits`: a daily limit of `None` is none):
  AIHubMix 5 a minute, 100 a day, a million tokens; NVIDIA 40 a minute and no daily limit,
  its day counted and shown in Settings ("2 sent"). A provider says how many requests it
  takes at once (`ProviderConfig.at_once`: AIHubMix 1, NVIDIA 6); the gateway holds a
  semaphore a provider, lets each request in and counts it as one step (`_admitted`), and
  sends nothing for work stopped while it waited. `jobs.side_by_side` works on pieces of a
  job at once, the first failure or Stop stopping the rest: a film's chapters, three at
  most, the engine still checking one at a time (`_engine_turn`), a chapter being written
  saying so (`writing`); a file's pages, four at most, each still drawn in turn. Found on
  the way: on Windows a file removed while a page of it was being drawn could not be
  deleted, and the removal failed; its original is now tried again for five seconds, and
  one still held is deleted at the next start, which now always deletes the originals no
  source refers to. Left: not tried with the real providers; a film's time with chapters
  side by side is not measured.

- **Done (ADR-067): "allow answer a question to change the lecture slides if user wants
  something specific... like for example in my case it forgot to draw hydrogen bonds".**
  The Ask dialog of a part that teaches with a picture offers "Change the picture": one
  request, to where a lesson goes (`prompts.redraw_request`), with the part's words marked
  where its steps play and its picture's script (every slide's scene now keeps it, base64
  in its last comment) or what it shows; the slide that comes back is drawn by Adle and
  paced to the part's words, which never change (`drafts.compile_redraw`), and kept with
  the note. "Use this picture" puts it in the lesson through `parse_bundle`
  (`lessons.replace_picture`); "Put the original back", or removing the note, restores
  the part's own. Tried with the stand-ins only: a part with no picture given the hydrogen
  bond between two water molecules, stepped through in the player (it is a slide example
  now, `hydrogen_bond.py`). Drawing that example first side by side laid the dashed bond
  through the other molecule's hydrogen, which the layout check does not look for (Known
  gaps: a dashed line through a word). Left: no real model has redrawn a picture yet; a
  lesson made before this keeps no scripts, so its pictures are drawn again from words.

- **Done (ADR-066): "a picture-reading model looking at each chapter's storyboard images,
  one more request per chapter".** `film/storyboard.py` reads the sheets `inspect` draws
  (the screen at the end of every animation, six to a sheet), what is said while each
  animation plays, and what the model saw; `prompts.storyboard_request` (purpose
  `storyboard`, Nemotron 3.5 Super, only a model that sees pictures) sends them in one
  request; what it sees goes to the writer by its own line, in the same three mends. Said
  before a film is begun ("Sends pictures of each chapter to …", five requests a chapter
  at most) and in Settings ("Checking films"). Tried by hand: three requests on a chapter of
  the earlier film tuned what it is asked; a one-chapter film made whole (see "A film's
  pictures, looked over"), whose look thought too long and said nothing, so a look is now
  sent at a `reasoning_effort` of "medium", and the writer is told that what was seen is
  one viewer's. Found while building it, and fixed: a chapter sent back was shown back cut
  at 12,000 characters, and every chapter written by hand so far was longer; and a line
  given a run time, which stopped the engine, is mended by Adle. Left: about half of what
  a look says is so (the writer judges it), and it misses arrows too short to see; "medium"
  was tried on one look, not yet inside a whole film; no person has watched a film whose
  pictures were looked over.

**Asked for by the owner on 2026-11-24, after 0.1.0-alpha.9: five things, all done, and
released in 0.1.0-alpha.10.** In the owner's order:

1. **Done (ADR-061): "too focused on maths ... every lesson needs axiomatic rules as to
   how a lesson should be formed".** `lessons/axioms.py` holds the rules and the subjects;
   a course has a subject; the prompt carries one subject's needs and example
   (`generation/examples.py`); slides draw a timeline, a vessel, a molecule and code. Six
   real lessons through NVIDIA (chemistry, history, programming, Spanish, biology, physics)
   were written as their subjects ask, and what their 34 slides showed was mended (the
   numbers are in the ADR). Seen and left: a model's narration can ramble, "(aq)" is set
   in italics, and a model can still lay words over a drawing it meant them to lie over.
2. **Done (ADR-062): the Expressive voice made of parts** (who speaks, age, pitch, pace,
   tone, feeling, delivery, accent, style), with voices to start from as choices of parts
   and the learner's own words as the most exact way. `voice/design.py` writes the one
   sentence the parts make; Settings asks it (`voice.describe`). Measured with the real
   voice on this machine: who speaks, pitch, pace and delivery are followed (the numbers
   are in the ADR), and a part left as Any is not held still. **Nobody has listened to an
   accent yet**: the clips asked for as British, Indian and Australian English are in
   the session's scratch folder (`voice-parts/`) for the owner to hear, and until someone
   has, the note beside the choices says an accent is followed least of all.
3. **Done (ADR-063): a course saved as a file and brought in from one**, as a template
   (the plan and its lessons, nothing of the learner, no materials) or with everything, to
   move it, what either holds changed under "Advanced" (`Disclosure`, new in the design
   system). `application/course_file.py` is the file and reading one from anywhere;
   `application/course_sharing.py` saves and brings in, always as a new course, by the
   services everything else goes through; `window.adle.courses` is the bridge, and the
   page names no place. Left: bringing in is one call the learner waits for, not a job
   with a bar; recordings of a natural voice are not carried.
4. **Done (ADR-064): settings saved as a file and brought in from one**: the look, how
   lessons are taught, the voice, which provider is used, and the keys, each part chosen
   by the learner. Keys are in a file only locked with a password they choose (scrypt,
   then AES-256-GCM, in the main process; the page never sees one), and are saved for the
   address their provider has on the computer they arrive at. A voice the other computer
   does not have is set up only at the learner's word, else the nearest lighter one that
   runs there, else the computer's own; a provider not offered there leaves the choice as
   it was; each is said. Left: a key in a file is as safe as its password; recordings of
   a voice are not carried.
5. **Done (ADR-065): a film of a whole course.** A course's Film tab makes a narrated
   film, a chapter for each concept in learning order, each a ManimGX animation the AI
   writes (`film`, its own kind of request: Kimi K3.1 Pro first at NVIDIA). A chapter
   passes a policy of its own (`film/policy.py`, 72 hostile files refused in its tests)
   before any of it runs; then the engine runs it alone, with Adle's voice, no network in
   its process and nothing of the computer's in its environment, and what it finds is told
   to the model by line, three times at most. The lines are recorded in the natural
   voice; the chapters are put together and made into a 1080p video with subtitles, in a
   lane of its own, and an unfinished film is continued. The film maker (a pinned Python
   and hash-locked ManimGX, about 110 MB on Windows) is downloaded only at the learner's
   word. Made by hand twice through NVIDIA, the real engine and the Kokoro voice; the
   second, of two chapters, took 34.5 minutes and 6 requests for 7 minutes of film, with
   sound throughout (PERFORMANCE.md). What the two found is fixed, each with a test: an
   engine name used bare, numpy or math not imported, and brackets beyond a line's
   animations are mended rather than sent back; fewer brackets than animations is caught
   before anything runs; ManimGX's own cache of what a voice said would have kept the
   chapters quiet in the finished film; a chapter's request may take half an hour; and
   **a first run of the engine in a home never used never ends** (not in ten minutes, on
   this computer) while every run after it takes seconds, so the home is kept and readied
   by a small scene ended after twenty seconds. What the engine found most, words in a box
   of a guessed size and arrows across words, is now in the writer's guide. Left: no
   person has watched a film yet (the second is in the session's scratch folder,
   `film/hand2/`); the film maker is untried on Linux and macOS; no film of more than two
   chapters has been made with a real model.

**Asked for by the owner on 2026-11-21, after looking at 0.1.0-alpha.1: done, and released
in 0.1.0-alpha.2.** Each is on `main` with its decision: the theme's lists and the sections' spacing,
and far fewer sentences (ADR-036); a lesson watched on one screen (ADR-035); a lesson seen
taking shape (ADR-037); pictures tried before they are shown (ADR-038); each request to the
model measured best for it (ADR-039); pictures drawn happening (ADR-040); more of a Word
document read, and search by any form of a word (ADR-041); a natural voice on this computer,
from Kokoro to Qwen3-TTS 1.7B with a voice designed for each lesson (ADR-042); and one
branch, with a release made by a commit (ADR-043). Left of what was asked, with the reason
in its decision: PowerPoint, web pages, text in pictures (OCR) and search by meaning
(ADR-041: each needs a download or a migration of its own); a sample of a natural voice in
Settings before it is used, and the voices tried by hand on Linux and a Mac (ADR-042).

**Asked for by the owner on 2026-11-22, after watching real lessons: done, and released
in 0.1.0-alpha.4.** A lesson is a slideshow (ADR-049): every part that teaches has a slide the
model scripts and Adle draws, a step at each phrase of the narration the script marked;
lessons teach by intuition and example first; no picture is asked of a model as a program,
and the model does not think first, so a lesson can be begun about twelve seconds after it
is asked for;
the teaching style can be chosen for a first lesson; a table's bare TeX is set as a formula;
a board line is not repeated. Measured by hand through NVIDIA (see "The real providers").

**Asked for by the owner on 2026-11-24, after 0.1.0-alpha.8: done, and released in
0.1.0-alpha.9.** The owner's textbook chapter lost its page 4: its drawing of a molecule went past
pypdf's budget of work, and the whole page was skipped, words included ("1 pages ... were
skipped"). It is read again with five times the budget, second tries sharing 60 s a file;
the chapter's 21 pages read in 24 s; and the counts are said properly (`587fb31`). Then:
a page with no text to select (a scan, a photograph, handwriting, or a drawing that still
cannot be taken apart) is kept as a picture, and a PDF of nothing but pictures is imported;
"Read them" in Materials, at the learner's word and with what is sent one press away, has
each page drawn by PDFium in the parser worker and read by a model that sees pictures, a
page a request; what comes back is the page's text, in its place, found and quoted like
any other (ADR-060). Only Nemotron 3.5 Super is sent pictures: it read a typed page and a
handwritten one word for word by hand (PERFORMANCE.md); AIHubMix's free model could not be
tried (its account wants paying first), so with AIHubMix alone nothing is sent and the
learner is told what would let the pages be read. A fixture made for it
(`scanned-notes.pdf`: typed notes photographed, handwriting with a drawing, a page of text)
stands in for the owner's file, which is a textbook's and is not committed. And the tests:
a check runs the static checks whole and then only what a change can reach, the core's
tests chosen by the code each ran (pytest-testmon), the journeys by `scripts/affected.mjs`;
each slide, figure and scene example once, the themes taking turns, figures and scenes as
rehearsals; `--all`, and GitHub, run everything (ADR-059).

**Asked for by the owner on 2026-11-23, after 0.1.0-alpha.7: done, and released in
0.1.0-alpha.8.** A lesson's narration says "n factorial", "and so on, up to n", "is not equal to"
where a model typed "n!", "1, 2, ..., n", "!=" (`speech._typed`). Rich is gone, and a
computer that has it set up has it removed as the core starts, keeping what Expressive
shares. Settings → Voice: the Natural voice's speakers each with "Listen" and "Use"; the
Expressive voice in the learner's words, from a preset ("Warm teacher", "Calm and low",
"Bright and lively", "British narrator", "Gentle storyteller") or their own, heard before it
is saved; each lesson adds only how it is delivered. A new voice records the two lessons
opened last at once, Settings says which and how far, and a lesson opened or a sample asked
for goes first; a recording under way follows the voice chosen. Every voice's recordings
were already kept, and are tested to be: switching back says nothing again (ADR-057).
The real Expressive voice, borrowed read-only from the owner's set-up voice, designed a passage and said two lines as copies of it, by hand: every word placed, the first line 63.2 s from cold, the second 2.9 s for 7.4 s of speech (PERFORMANCE.md).
As that release was checked, two slides stalled once each, in different runs, and passed
when tried again; the stalled run's screen showed "f' = 0" with the y axis through it,
which ADR-056 had said could not happen. The player draws an axis as a number line, its
line made of the number line's own points, so only its ticks had been found as lines; and
a label that moves, where no side was clear, tried every side on every frame. Now a number
line counts as a line, a line's path is read once with the box round it, and a moving
label keeps the place it found and, where it found none, looks again only once its point
has moved 0.2 (ADR-058).

**Asked for by the owner on 2026-11-23, later: done, and released in 0.1.0-alpha.7.** A
picture's words are kept clear of each other and of the edge of the screen (ADR-055): a
label is pinned beside what it names and, before anything is shown, moved to the first side
where it covers no word; one that moves with a point steps aside when it would, and stays
there. Every slide and figure says as each step ends how many of its words overlap and how
many things lie past the edge, and the journeys fail on any: the one example that had one
(`tangents_inline`, "f' < 0" over the y axis's 4, the gap of 2026-11-22) no longer does. A
slide's step is made quicker when the words before the next cue take less time than its
animations, down to 0.45 of them; a step with time to spare is left alone. Then, asked to
do whatever was left before the release: no line, arrow, axis or curve runs through the
middle of a word either (ADR-056); "f' = 0", which the y axis ran through, is set clear
of it, and the journeys fail on a word under a line in any example.

**Asked for by the owner on 2026-11-23, after 0.1.0-alpha.6: done, and released in
0.1.0-alpha.7.** The bar under a lesson is one row (ADR-054): the lesson's own controls, a note in the
middle that wraps in its own room, and what to do about the part; Read aloud, Transcript and
"This didn't help" are icon toggles named by their old words. "This didn't help" stays
pressed while it stands; Undo in its dialog, or pressing it again, takes it back with a row
of its own (`explanation_unhelpful_withdrawn`, revision 0012), and what the course suggests
is as it was. Seen in the built app at 1280, 1100, 960 and 820 points wide: one row, with a
note and without.

**Asked for by the owner on 2026-11-23: done, and released in 0.1.0-alpha.6.** Every voice
timed where it runs, a slow one giving a lesson a head start (ADR-052). A course made from
its files in the new-course dialog, named by Adle (from its first file, then from the AI)
and, with "Set it up for me", given every concept suggested and its first lesson; "Start
from your materials" removed; a concept's page in the order the owner gave (ADR-053).

**Asked for by the owner on 2026-11-22, after watching 0.1.0-alpha.4: done, and released
in 0.1.0-alpha.5.** The case first, and the rule out of it (ADR-050): a part opens on its
case alone, works it out in the picture, and only then writes the formula, its numbers
flying out of the picture before they turn into the rule's symbols; a sentence or an
equation comes out of the one before it. A lesson in a natural voice is made with its voice
(ADR-051): loaded as the lesson is asked for, recorded part by part by one recording, ready
once its first part can be heard, counted in how long a lesson usually takes; a line not
recorded yet is waited for, and the learner may choose the computer's voice instead.

What remains needs the owner. In the order it matters:

0. **Try the five things of 0.1.0-alpha.10**, installed from its release
   (`github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.10`): on a small course's Film tab,
   set up the film maker (about 110 MB) and watch the film it makes (15 to 20 minutes a
   chapter through NVIDIA, ADR-065); put an Expressive voice together from parts and
   listen to the accents (clips asked for as British, Indian and Australian English are
   in the session's scratch folder, `voice-parts/`, ADR-062); save a course as a template
   and import it (ADR-063); save your settings with a password and import them on another
   profile (ADR-064); and see whether a course in history, chemistry or a language is
   taught the way its subject asks ("Taught as …", ADR-061).
0. **Read a scanned or handwritten file of your own** in 0.1.0-alpha.9, installed from its
   release (`github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.9`, ADR-060): with an NVIDIA
   key, import it, press "Read them" in Materials, and see whether what comes back reads as
   the page does. Top up AIHubMix to have its model tried for pictures by hand (one request).
0. **Listen to the voice of 0.1.0-alpha.8**, installed from its release
   (`github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.8`, ADR-057): the Expressive voice from "Calm
   and low" or your own words, a Natural speaker heard with "Listen" before it is chosen, a
   lesson with "n!" in it, and a voice changed in Settings with a lesson left half done (it
   should be recording before you open it). And **try 0.1.0-alpha.7**, installed from its
   release
   (`github.com/XelXen/Adle/releases/tag/v0.1.0-alpha.7`): the bar under a lesson on one
   row, "This didn't help" undone (ADR-054), and a slide's labels clear of other words, of
   lines and of the edge, its steps keeping up with the voice (ADR-055, ADR-056). Then, as
   for 0.1.0-alpha.6: make a course from your files
   with "Set it up for me" and the name left empty, and say whether its name, its concepts
   and its first lesson are what you would have chosen (ADR-053), and whether a concept's
   page now reads in the right order. Watch a lesson in the Expressive voice: whether each
   part opens on its case and makes its rule out of it (ADR-050), and whether it is ready
   when it says so and is never read in another voice by itself (ADR-051, ADR-052).
   Through NVIDIA with that voice it is ready about 45 s after you ask. Which subjects
   still come out as words on a stage.
1. **Try the rest of what 0.1.0-alpha.3 and 0.1.0-alpha.4 brought**: a lesson begun at its
   first part (ADR-048), a PDF's whole syllabus (ADR-046), lessons mended rather than
   written twice (ADR-047), American English (ADR-044), a lesson as a slideshow (ADR-049).
2. **Replace the keys that were pasted into the chat** (two for AIHubMix, two for NVIDIA).
   They are in a transcript; treat them as used. The owner will, later (said 2026-11-21).
3. **Sit a generated lesson from start to finish**, asking it a question on the way. Install
   Adle from the release (or `npm run dev`), type a key into Settings → AI provider, press
   "Test key", leave the choice on Automatic. Through NVIDIA, expect about twelve seconds
   until the lesson can be started and a minute or two until it is whole; its slides come
   with its words.
4. **AIHubMix** will be topped up by the owner (2026-11-22, they said). Until then Automatic
   finds out once that it refuses and uses NVIDIA.
5. **Look at Adle on a Mac.** GitHub's machines build it, install it from the disk image and
   start it, on Apple's and on Intel's processors; nobody has seen it there. See "On a Mac"
   below: it is written for whoever opens this repository on one.
6. **Turn on private vulnerability reporting** for the repository (Settings → Security on
   GitHub), which `SECURITY.md` points people to. Only the owner can.
7. Decide whether GLM 5.3 Flash should stay NVIDIA's third model while it does not answer.
8. **A lesson begun at its first part** (ADR-048) is built and measured; sit one through
   NVIDIA and say whether waiting at the end of what is written ever happens to you, and
   whether "Part 2 of 3 so far" reads well.
9. Smaller, by choice: exporting a
   single course; a screen-reader pass by a person; a flow figure of seven or eight steps
   (the one figure shape of 75 still told in words); a question during a lesson in less
   than 10 to 19 seconds (Nemotron 3.5 Super thinks 4,800 to 8,600 characters first: try
   whether its reference lists a lower setting, by hand, as ADR-048 did for lessons).
10. From the review of 2026-11-20, left by decision (ADR-029, "Not done, and why"): a release
   build can still be started with Chromium's remote debugging switch; the page can ask for
   the data dialogs again and again; `provider.usage` is a route the interface does not
   call (five tests read it).

## On a Mac (for whoever opens this repository on one)

Nothing below has been done by a person or an agent with a Mac in front of them. What is
known: on GitHub's Macs (Apple's processor and Intel's) the release build is made, signed
"ad hoc", wrapped in a disk image, copied out of it, checked file for file against its
signature, and started with an empty profile, on the machine that built it and on one that
did not; its core comes up within a few seconds and goes away with it. The end-to-end
journeys have never run on macOS.

In this order:

1. `npm run setup`, then `npm run check`. The unit tests pass on Linux; expect the same.
2. `npm run dev` and look at the app. The window has a title bar of its own (ADR-030) that
   has only ever been seen on Windows: check that the three buttons of the system sit on
   the strip without covering anything, that the window drags by the strip, and that a
   dialog can be pressed where it reaches the top. Light and dark.
3. `npm run e2e`. This is its first run on macOS: read failures as findings about macOS,
   as the first run on Linux was (it found that a build machine has no keyring). Journeys
   that save a key use the Keychain, which may ask for permission.
4. `npm run package`, `npm run package:check`, `npm run installer`, then open the disk image
   as a person would. An app signed "ad hoc" that came from the internet is refused once;
   `README.md` → Install says how to open it. One made on the same Mac opens.
5. Reading aloud: macOS has voices of its own. `e2e/narration.spec.ts` asks the machine
   what it can do and follows; listen to a lesson once with the sound on.
6. Write down what was found, here and in `TESTING.md`, and give the rows about macOS in
   the table of test results their real status. If the journeys pass, add `macos-latest`
   to the end-to-end job in `.github/workflows/ci.yml`.

## Known gaps (tracked, not forgotten)

- **A slide's step did not come, twice in about 400 journeys** (2026-11-24):
  `machine.py`, light, on the tree of ADR-057, and `tangents_inline.py`, dark, on the first
  tree of 0.1.0-alpha.8. Each ran two to three times slower than usual from its start and
  then waited 30 s for a step, while the journeys beside it kept their usual pace; each
  passed when tried again, and 40 repeats with retries off passed. ADR-058 bounded what a
  moving label costs a frame, which `tangents_inline.py` has and `machine.py` has not, so
  the cause is not known. A step that does not come now says where the slide stopped: its
  page and its last messages (`slide-player.spec.ts`). Read them before guessing.
- **What is kept clear is words** (ADR-055, ADR-056, ADR-058): of words, of lines (an
  axis among them), of the edge. A filled shape over a word, and a dashed line through
  one, are not looked for, and a scene a model writes is not checked at all (its own code
  places its words; it still has its trial).
- **How long a step's words take is worked out at 3 words a second**, not measured: a
  voice much slower than that leaves the picture holding a little sooner, one much faster
  can still leave a step's animation running past its next cue.
- **The Expressive voice of a learner's description has been heard by nobody yet**
  (ADR-057): the reference passage and the design were checked with the real engine by
  hand, for what it makes and how long it takes, not for how it sounds. Whether "Calm and
  low" sounds calm and low is the owner's to say.
- **No voice has been seen slower than speech on a real computer** (ADR-052): the head
  start is tested against a stand-in made slow, and by the rule checked second by second,
  but every voice on the development machine is faster than speech (Natural on one thread
  of its processor, 0.68). A computer weak enough to need it has not been tried.

| Gap | Planned |
|---|---|
| A request the learner stopped is given up at once and hung up as well as that can be done from another thread; where it cannot, its connection is let go when the provider next says something (or its time runs out), so for a moment two may be open at one provider | By decision (ADR-023, ADR-029): the provider's turn is not kept waiting for a request nobody wants |
| The window's own title bar has been seen on Windows 11 only | Needs a Mac (ADR-030); Linux keeps its usual frame |
| A lesson's text is one request and arrives whole; the wait before a learner can begin is that request | By decision (ADR-012, ADR-031); "Next actions" 7 |
| A picture that arrives while a lesson is open is found by looking every three seconds, not by being told | By decision (ADR-031): nothing new crosses the bridge for it |
| A picture keeps the size it was drawn at if the window is made much larger or smaller while it is on screen | By decision (ADR-032): the next picture is drawn to suit; loading it again would start it again |
| A question asked during a lesson does not remember earlier questions | By decision (ADR-024): it is a note, not a chat |
| AIHubMix being "the quick one" is the owner's report, not a measurement | Its model has never answered Adle; one word in its definition if it turns out otherwise |
| GLM 5.3 Flash, NVIDIA's third model, has never answered | The owner's choice of order (ADR-021) |
| The parser worker has no OS-level sandbox | Not built. It is a separate, short-lived, isolated process that returns only checked JSON (SECURITY.md) |
| No signature, and no automatic update | The owner's decision, and Adle's rule about what it sends (ADR-034, ADR-019). Each system asks before opening a build |
| The end-to-end journeys do not run on macOS | Not built: the app is built, installed and started there with every push. See "On a Mac" |
| On Linux a key can be kept only where the desktop has a keyring (GNOME Keyring, KWallet) | By decision: Adle does not keep a key where the system would store it as plain text, and says so |
| Windows on ARM and Linux on ARM have no build | Not asked for (ADR-034) |
| A single course cannot be exported to share with someone else; a copy holds everything | By decision (ADR-016) |
| A saved copy is not encrypted | By decision (ADR-016); the interface says so |
| Narration and animation are synchronised per segment, not per sentence | M7, after testing Wanim's slides mode |
| Working memory from the plan is not a stored thing: what a session needs is rebuilt from attempts, observations, and `learner_events` on every request | By decision (ADR-014) |
| Open answers are self-assessed against a rubric, not graded by the model | By decision (ADR-014); revisit if the provider's allowance grows |
| Extraction quality on complex PDFs (columns, tables, equations) is whatever `pypdf` gives | When retrieval quality is evaluated |

## Open questions for the owner

- **Commit signing.** Git is configured to GPG-sign commits. Signing needs the key's passphrase in
  the desktop session; agents cannot provide it. Settled on 2026-11-21: wait a few minutes for
  the prompt to be answered, then commit unsigned.
- **Vector search.** Not built: FTS5 covers the current need, and `sqlite-vec` plus a local
  embedding model adds packaging risk. Revisit with packaging in M8 unless retrieval quality
  proves insufficient earlier.
