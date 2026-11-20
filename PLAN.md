# Adle — Product & Engineering Plan

> **Product:** Adle (Adaptive Learning Environment)  
> **Document:** `PLAN.md`  
> **Status:** Implementation baseline  
> **Audience:** Coding agents, engineers, reviewers, and future maintainers  
> **North star:** Help a learner build durable understanding by adapting the teaching experience to the learner's demonstrated knowledge—not merely generate attractive lessons.

---

## 1. Product definition

Adle is a local-first, desktop adaptive learning environment. A learner supplies a topic, syllabus, notes, or course materials. Adle turns those materials into a traceable curriculum, teaches concepts through narrated explanations and interactive visualizations, observes learning behavior, estimates concept mastery, and adapts subsequent instruction.

Adle is not primarily a slide generator, video generator, chatbot, flashcard app, or LMS. Those can be supporting capabilities. Its defining product loop is:

1. **Understand the target:** identify learning objectives, source material, and prerequisite relationships.
2. **Understand the learner:** maintain an evidence-based model of prior knowledge, preferences, confidence, and misconceptions.
3. **Choose instruction:** decide what concept to teach next and which explanatory approach is most appropriate.
4. **Compile the experience:** create a lesson plan, narration, interactive visualization, and assessment from a validated intermediate representation.
5. **Observe evidence:** capture answers, hints, control manipulation, confidence, and learner feedback.
6. **Adapt:** update the learner model and generate a targeted next step.
7. **Revisit:** schedule retrieval practice so that apparent mastery is checked for retention.

### Product principles

- **Learning before spectacle.** Animation must clarify a concept, not merely decorate it.
- **Evidence before assumptions.** A single correct answer is not proof of mastery. Interaction telemetry is suggestive evidence, not a diagnosis.
- **Local-first by default.** Course files, learner history, generated assets, and application state stay on the device. The configured LLM endpoint is the deliberate network exception. Optional cloud TTS is separately disclosed and opt-in.
- **Source traceability.** Claims derived from uploaded material should be traceable to a document and page/section when available.
- **Progressive delivery.** Show useful content as soon as it is ready. Do not block the whole lesson on every asset.
- **Predictable software.** Use deterministic code for state, scheduling, scoring, and validation wherever possible. Use the LLM for bounded tasks that benefit from language reasoning.
- **Respect the learner.** No manipulative streak pressure, shame, arbitrary XP grind, or infantilizing UI. Playful visual language should still feel credible to university and adult learners.
- **Recoverability.** Interrupted lessons, failed generations, app restarts, and quota exhaustion must not destroy learner progress.

## 2. Product scope

### 2.1 MVP: one complete adaptive learning loop

The first release must deliver one coherent, testable experience across the following capabilities:

1. Create a course from a topic prompt or imported syllabus/material.
2. Import PDF, Markdown, TXT, and DOCX files. Unsupported formats must be clearly rejected with an actionable explanation. Scanned PDF OCR is optional and must not silently upload files to a service.
3. Extract and preserve source provenance: filename, page/section, text range where possible, and content hash.
4. Propose a curriculum graph containing concepts, learning objectives, prerequisite edges, and source references. Let the learner inspect and edit it before starting.
5. Build a bounded lesson plan for one concept or small concept group.
6. Generate a complete, validated lesson bundle with narration text, a complete Wanim Python scene file, interaction/checkpoint metadata, and assessment items.
7. Play the lesson in an accessible application shell with narration controls, transcript/captions, interactive Wanim scene, and checkpoints.
8. Record learner responses and interactions as events.
9. Update concept-level knowledge estimates and record possible misconceptions with evidence and uncertainty.
10. Choose the next teaching action based on prerequisites, learner state, and review schedule.
11. Persist all progress and resume after restart.
12. Provide a course overview showing covered objectives, estimated mastery, unresolved items, and upcoming reviews.

The MVP should prove the loop with a bundled sample course on **introductory neural networks**. Include concepts such as perceptrons, weights and biases, activation functions, forward propagation, loss, derivatives/chain rule, backpropagation, and gradient descent. The sample course is a product fixture and must clearly distinguish authored sample material from user-provided sources.

### 2.2 Explicitly out of scope for the first release

Do not expand the MVP into these areas before the core loop is stable:

- Multi-user accounts, social learning, cloud sync, classrooms, teacher dashboards, or collaborative editing.
- Mobile applications or browser-hosted SaaS.
- User-generated marketplace/content sharing.
- Automatic OCR for every document type.
- Arbitrary code execution, arbitrary Python packages, or unrestricted generated scripts.
- Full video rendering/export as a requirement. Wanim is a live interactive scene runtime, not a conventional video-rendering pipeline.
- Fine-tuning or training a custom knowledge-tracing model.
- Complex gamification, streak economy, leaderboards, or in-app currency.
- A general-purpose agent that can execute shell commands on behalf of learners.

Keep extension points clean, but do not build speculative infrastructure without an MVP use case.

## 3. User experience and information architecture

### 3.1 Primary user journey

1. **Welcome:** explain local-first behavior and the one required external dependency (LLM inference). State clearly when external services receive content.
2. **Configure AI:** enter an AIHubMix API key, verify the connection, select the configured model, and see quota/connection status. Never require a key merely to open the app or inspect sample content.
3. **Create course:** choose `Start with a topic` or `Import course materials`.
4. **Review sources:** show imported files, extraction status, source references, and any unsupported or low-confidence extraction.
5. **Review curriculum:** show concepts and dependencies visually; allow renaming, adding, removing, and reordering concepts. Explain why prerequisites exist.
6. **Set learning preferences:** offer concise controls for pace, narration, explanation density, and accessibility. Preferences can be changed later.
7. **Learn:** display a focused lesson with a persistent concept/objective context, scene, narration/transcript, pause/continue controls, and small interactions.
8. **Checkpoint:** ask a short question or request a prediction. Allow confidence reporting where useful. Never interrupt every sentence with a quiz.
9. **Adapt:** explain the next step in plain language, e.g. “We’re revisiting the chain rule because your last two answers suggest the composition step needs more practice.”
10. **Session summary:** show demonstrated concepts, areas that need more evidence, and planned review. Provide a clear “Continue” action.

### 3.2 Primary screens

- **Home / Library:** recent courses, continue learning, create course, local sample course.
- **Course setup:** file dropzone, topic prompt, source list, extraction status.
- **Curriculum map:** concept graph, objectives, prerequisites, source references, edit controls.
- **Lesson player:** Wanim surface, narration/transcript, segment navigation, checkpoint panel, “ask for another explanation” actions.
- **Course progress:** mastery evidence, completed objectives, weak prerequisites, review schedule.
- **Settings:** AI provider/key, privacy, TTS voice, accessibility, storage, export/import, diagnostics.

### 3.3 Lesson player requirements

- The learner can pause, resume, replay a segment, mute narration, change narration speed where supported, and read a synchronized transcript.
- Focus and keyboard navigation work without a mouse.
- Interactive scene controls are usable by keyboard where Wanim supports them; provide an accessible textual alternative for every learning-critical interaction.
- A learner can request a simpler explanation, mathematical derivation, example, slower pace, or a direct practice question.
- A learner can report “This explanation did not help” without being blamed or forced through the same content again.
- A checkpoint pauses narration and visual progression until the learner responds or explicitly skips.
- Persist progress at meaningful boundaries and after user answers; do not rely on an unload event.
- If Wanim fails, show an understandable fallback explanation and preserve the rest of the lesson.
- Reduced-motion settings must be respected by the application shell. Wanim scenes should avoid unnecessary flashing, rapid motion, and distracting movement.

## 4. Visual design system

### 4.1 Direction: “Sprout” — playful precision

Use a bright, friendly, encouraging visual language inspired by the clarity and approachability of modern learning apps such as Duolingo, but do **not** copy Duolingo's mascot, exact palette, illustrations, layout, sound effects, or proprietary assets. Adle should feel more like a polished creative learning tool for teens, university students, and adults than a children's game.

Design must be implemented as tokens and reusable components before screen-by-screen styling begins.

### 4.2 Initial design tokens

These are the starting values. Centralize them in theme variables and document any intentional change.

**Light theme**

| Token | Value | Use |
|---|---|---|
| `color.canvas` | `#F6F8F4` | App background |
| `color.surface` | `#FFFFFF` | Cards and panels |
| `color.surface.subtle` | `#EEF3ED` | Quiet secondary regions |
| `color.ink` | `#17251E` | Main text |
| `color.muted` | `#69786F` | Secondary text |
| `color.border` | `#DCE5DC` | Hairlines and outlines |
| `color.primary` | `#269B62` | Main actions and progress |
| `color.primary.hover` | `#1F8352` | Hover/active primary |
| `color.primary.soft` | `#E2F4E9` | Gentle success/selection background |
| `color.accent.sun` | `#F2C14E` | Highlight, not body text |
| `color.accent.coral` | `#EF806C` | Warm emphasis |
| `color.accent.blue` | `#5B8DE6` | Information and visualization |
| `color.accent.violet` | `#9178D7` | Secondary emphasis |
| `color.danger` | `#C84E4E` | Errors/destructive actions |

**Dark theme** must be designed intentionally, not produced by simple color inversion. Use dark forest/charcoal surfaces, readable contrast, and appropriately softened accent colors.

**Typography**

- Use a clean, highly legible sans-serif such as Inter or Geist Sans, subject to licensing and packaging review.
- Use a small type scale with clear hierarchy: display, page title, section title, body, supporting, caption.
- Avoid tiny text. Body text should normally be 14–16 px or larger; captions should remain readable and never carry essential instructions alone.
- Use tabular numerals for progress, timing, and quantitative learning data.
- Math should use a dedicated mathematical rendering path; do not force complex formulas into ordinary UI text.

**Layout and components**

- 8 px base spacing grid.
- Card radius: 16–20 px; controls: 10–14 px; pills: fully rounded.
- Use restrained borders and soft elevation. Avoid stacking multiple nested cards without a clear purpose.
- Buttons have explicit primary, secondary, tertiary, and destructive variants with hover, pressed, focus, disabled, and loading states.
- Progress indicators must not imply unjustified precision. Prefer “Needs more practice” or an evidence-based range when a precise percentage would mislead.
- Use motion for feedback and orientation, not decoration. Respect `prefers-reduced-motion`.
- Build reusable tokens and components for buttons, inputs, cards, dialogs, toasts, progress, badges, tabs, navigation, empty states, loading states, error states, and lesson controls.

### 4.3 Brand behavior

- Product name: **Adle**.
- Short descriptor: **Learn at your own pace. Understand for real.**
- Use a simple original geometric sprout/idea mark if a mark is needed; do not create an elaborate mascot dependency.
- Encourage curiosity and effort. Avoid guilt-based copy, “you failed” language, or childish reward sounds.
- The design system must include examples of good/bad usage and component states in `DESIGN_SYSTEM.md`.

## 5. Technical architecture

### 5.1 Architecture principles

- Desktop-first, local-first, offline-capable except model inference and explicitly selected cloud TTS.
- Modular monolith, not a distributed microservice system.
- Typed contracts between the Electron app, backend, lesson compiler, and player.
- Python is used for document processing, curriculum/adaptive logic, and model orchestration.
- TypeScript is used for Electron, React UI, design system, and player integration.
- SQLite is the source of truth for persistent state.
- Generated lesson content is data plus a controlled Wanim source artifact, never an unrestricted application plugin.

### 5.2 Proposed repository structure

Adjust only when an ADR explains why. Keep the following logical boundaries:

```text
adle/
├── AGENTS.md
├── PROMPT.md
├── PLAN.md
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── DESIGN_SYSTEM.md
├── TESTING.md
├── apps/
│   └── desktop/
│       ├── electron/             # Main process and preload bridge
│       ├── renderer/             # React application
│       ├── player/               # Lesson player and Wanim adapter
│       └── e2e/                  # Playwright end-to-end tests
├── packages/
│   ├── design-system/            # Tokens, components, stories/examples
│   ├── contracts/                # Shared JSON Schemas / generated TS types
│   ├── lesson-ir/                # IR schemas, validation, fixtures
│   └── event-protocol/           # Typed events and protocol versioning
├── services/
│   └── core/                     # FastAPI application and Python domain logic
│       ├── adle_core/
│       │   ├── api/
│       │   ├── application/
│       │   ├── domain/
│       │   ├── infrastructure/
│       │   ├── ingestion/
│       │   ├── curriculum/
│       │   ├── learner_model/
│       │   ├── orchestration/
│       │   ├── generation/
│       │   ├── evaluation/
│       │   └── audio/
│       ├── migrations/
│       └── tests/
├── skills/
│   └── wanim-scene-authoring/
│       ├── SKILL.md
│       ├── reference.md
│       └── examples/
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── product/
│   ├── engineering/
│   ├── security/
│   └── reference/
├── fixtures/
│   ├── sample-course/
│   ├── sample-documents/
│   └── sample-lessons/
├── scripts/
└── .github/
    └── workflows/
```

Use package managers and workspace tooling only where they solve an actual monorepo need. Do not introduce Docker as a runtime dependency for end users. Electron is the desktop application runtime; it is not a container system.

### 5.3 Desktop process boundaries

- **Electron main process:** window lifecycle, secure storage, app lifecycle, filesystem dialogs, updates/packaging, and a narrow allowlisted IPC bridge.
- **Preload:** expose only typed, minimal methods. Do not expose Node globals, generic filesystem access, shell execution, or arbitrary IPC to the renderer.
- **Renderer:** React UI and player shell. Enable context isolation, sandboxing, and restrictive Content Security Policy. Keep `nodeIntegration` disabled.
- **Python core:** managed child process for local APIs and background tasks. Bind only to loopback on an OS-assigned port, use an ephemeral per-launch authentication token, verify readiness, and shut down cleanly. Do not put provider secrets in command-line arguments or logs.
- **IPC/backend bridge:** Electron main should mediate calls or use an equivalently authenticated, documented local bridge. The renderer must not get unrestricted access to the backend process, filesystem, or model API key.
- **Worker tasks:** isolate CPU-heavy document parsing, embeddings, and audio work from UI-critical processes. Use bounded concurrency and cancellation.

### 5.4 Suggested stack

| Layer | Preferred starting point | Notes |
|---|---|---|
| Desktop | Electron | Secure main/preload/renderer separation |
| UI | React + TypeScript + Vite | Fast iteration and type checking |
| Styling | CSS variables + a disciplined component system | Avoid a collection of ad hoc styles |
| Backend | Python + FastAPI + Pydantic | Domain logic and structured generation |
| Persistence | SQLite + SQLAlchemy + Alembic | Single-user local database with migrations |
| Text retrieval | SQLite FTS5 | Required, durable keyword retrieval |
| Vector retrieval | `sqlite-vec` behind an adapter, after packaging tests | Must have a graceful FTS5-only fallback |
| Local embeddings | Provider adapter with a small downloadable local model | No external embedding dependency by default |
| Wanim | `@wanimjs/wanim` / official supported player integration | Pin version, verify the real API, isolate generated scene execution |
| Tests | pytest, Vitest, Playwright, axe-core | Unit through end-to-end and accessibility |
| Packaging | Electron Builder or Forge, selected after a packaging spike | Must bundle Python runtime/backend correctly |

The agent must verify the currently supported package versions and API signatures before implementation. Pin compatible versions in lockfiles. Do not install the latest version blindly during every build.

### 5.5 Database and storage model

Use normalized relational records for structured facts. Use vectors only for semantic retrieval. Suggested entities:

- `courses`, `course_settings`
- `sources`, `source_sections`, `source_chunks`
- `concepts`, `concept_edges`, `learning_objectives`
- `lesson_plans`, `lessons`, `lesson_segments`, `lesson_assets`
- `learner_preferences`, `learner_concept_states`
- `attempts`, `interaction_events`, `misconception_hypotheses`
- `review_schedule`, `generation_jobs`, `model_usage`
- `asset_cache`, `schema_migrations`

Every source-backed chunk must retain its source ID and page/section locator when available. Store original files under an app-controlled data directory using safe generated filenames, not raw user paths. Store hashes to avoid duplicate imports.

Structured mastery records belong in SQLite. Vector embeddings are supplementary indexes and must be rebuildable from source chunks. FTS5 must continue to work if the vector extension or embedding model is unavailable.

Implement database migrations from the beginning. Never silently replace a database on schema mismatch. Include backup/export and restore workflows before release.

## 6. AI inference and quota management

### 6.1 Initial provider configuration

Use AIHubMix as the initial LLM provider through its OpenAI-compatible API:

```text
Base URL: https://aihubmix.com/v1
Model:    coding-kimi-k3-free
```

Use an environment/configuration abstraction. The model ID and base URL must be editable in developer configuration and, where appropriate, user settings. Do not hard-code the provider into domain logic. Do not place API keys in source control, renderer bundles, logs, crash reports, fixtures, or command-line arguments.

AIHubMix currently documents these limits for `coding-kimi-k3-free`:

- 5 requests per minute
- 100 requests per day
- 1,000,000 tokens per day
- 1,048,576-token context window
- Streaming and structured output capabilities

These limits can change. Treat the provider dashboard and current official model page as authoritative at implementation and release time.

### 6.2 Agent-development quota policy

The coding agent itself must conserve the same limited model resource:

- Plan and batch related edits before invoking the model.
- Avoid repetitive “review this tiny change” calls. Use local tests, linters, static analysis, and repository search first.
- Keep model-call concurrency at one unless the provider explicitly supports more.
- Space requests conservatively (target no more than 4 per minute, roughly 15 seconds between calls) to avoid rate-limit bursts.
- Maintain a daily request/token estimate. Aim to use no more than 80 of the documented 100 daily requests and no more than 800,000 tokens, leaving headroom for unexpected work and runtime testing.
- Do not resend the entire repository or huge unchanged context. Supply only relevant files and a concise project-state summary.
- Do not spend multiple requests generating and repairing the same Wanim scene. Give the scene generator the complete scene brief and Wanim skill in one request, request one complete Python file, then validate locally.
- If the quota is exhausted, continue deterministic work using fixtures/mocks, record blockers and state, and do not hammer the endpoint. Resume only after the provider's quota window resets or the user explicitly configures another provider.

The limits are account-level/provider-enforced and may be shared with other clients using the same account. A local tracker cannot know about calls made elsewhere. UI wording must explain that the displayed local usage is an estimate, not an authoritative provider balance.

### 6.3 Runtime quota manager

Implement a provider adapter and quota-aware scheduler with:

- Per-minute sliding-window limiter.
- Daily request and token estimates.
- One in-flight request by default.
- Configurable safety margins (initial runtime defaults: 4 requests/minute, 90 requests/day, 900,000 tokens/day).
- `Retry-After` handling, exponential backoff with jitter, and a small bounded retry count.
- No retry storm and no automatic retry of non-idempotent generation without a job/idempotency key.
- Request cancellation and timeout handling.
- Streaming support where it materially improves perceived responsiveness.
- Clear states for `queued`, `running`, `rate_limited`, `quota_exhausted`, `failed`, and `cancelled`.
- User-visible estimate of local usage and clear messaging when the provider quota may be exhausted.

Never silently use another provider or send data to another service. Any provider change requires explicit user configuration and disclosure.

### 6.4 Model responsibilities

Use bounded model calls for:

- Extracting candidate concepts and learning objectives from source excerpts.
- Proposing prerequisite edges with evidence/source references and confidence.
- Creating a lesson plan from a known curriculum node and learner state.
- Generating one complete Wanim scene Python file from a scene brief.
- Generating narration and formative questions.
- Classifying possible misconceptions from a learner response, as a hypothesis rather than a fact.
- Evaluating open-ended responses against an explicit rubric when deterministic evaluation is insufficient.

Do not use the LLM for:

- Database writes without validation and application-level authorization.
- Arbitrary shell/file execution.
- Deterministic multiple-choice or numeric scoring.
- Updating mastery with unbounded free-form output.
- Inventing citations or pretending a source supports an unsupported claim.
- Deciding that the learner is permanently finished with a topic based on one answer.

All model outputs must be schema-validated, length-bounded, and treated as untrusted data. Invalid output should produce a recoverable state, not crash a lesson.

## 7. Curriculum intelligence and retrieval

### 7.1 Ingestion pipeline

1. Validate file type, size, and extension; never trust filename alone.
2. Copy to app-controlled storage and calculate a cryptographic content hash.
3. Extract text locally using an appropriate parser.
4. Preserve page/heading/section boundaries and metadata.
5. Detect extraction problems (empty pages, garbled text, scanned-only PDF) and explain them.
6. Chunk by semantic/structural boundaries, not arbitrary fixed character slicing alone.
7. Store chunks with provenance.
8. Generate embeddings locally when the model is installed; keep FTS5 retrieval available regardless.
9. Treat document contents as untrusted data. They must never override system instructions or authorize tools, network calls, or file access.

### 7.2 Curriculum graph

A course is represented as a directed concept graph. Each concept has:

- Stable ID and human-readable title.
- One or more observable learning objectives.
- Prerequisite concept IDs.
- Source references.
- Suggested assessment methods.
- Estimated complexity/lesson size.
- Optional tags (calculation, conceptual, visual, procedural, etc.).

Check for cycles and unresolved prerequisite references. Let the learner review/modify the proposed graph. Keep source references visible so that the course map does not become an ungrounded hallucination.

### 7.3 RAG policy

Retrieve only the context needed for the current planning/generation task. Use source-aware retrieval with a mix of FTS and local vector similarity where available. Re-rank only if the corpus justifies the cost. Return source IDs, page/section, and relevant excerpt with each retrieved item.

Prompt construction must clearly separate system instructions, task instructions, learner state, and untrusted source excerpts. Delimit source excerpts and explicitly state that their content is evidence, not instructions.

## 8. Learner model and adaptive teaching

### 8.1 Three memory layers

**Working memory (session/lesson):** current concept, objective, recent attempts, active misconceptions, current teaching strategy, segment position, and pending action. It is bounded and can be reconstructed from persisted events.

**Learner profile:** explicit preferences (pace, narration, explanation density, accessibility), user-stated goals, and observed preferences with confidence. Do not infer sensitive personal attributes.

**Knowledge state:** structured per-concept evidence, mastery estimate, confidence/uncertainty, number and type of observations, hint usage, misconception hypotheses, last practiced time, and review due date.

Do not use a vector database as the primary learner model. Vectors are for finding relevant content, not representing what a learner knows.

### 8.2 Initial knowledge-tracing approach

Start with a transparent, testable implementation of Bayesian Knowledge Tracing (BKT) or an equivalently explainable probabilistic model. Keep parameters in configuration and document assumptions. Track at least:

- Prior knowledge probability.
- Learning/transition probability.
- Guess probability.
- Slip probability.
- Evidence count and evidence diversity.
- Confidence/self-report where collected.
- Hint dependence and transfer-question performance.

Do not expose a misleading exact score to learners when evidence is sparse. Display qualitative states such as `Not assessed`, `Building understanding`, `Needs more evidence`, and `Demonstrated for now`.

A concept must not be marked mastered from one lucky response. Initial mastery criteria should require multiple correct observations across more than one question form, including at least one application/transfer item where appropriate, with no unresolved high-confidence misconception. These thresholds must be configurable and covered by tests.

### 8.3 Misconception engine

Maintain a small taxonomy of mistake patterns, e.g.:

- prerequisite gap
- definition confusion
- symbol/notation confusion
- procedural ordering error
- conceptual causal confusion
- arithmetic/algebra slip
- misread question
- likely guess
- overgeneralization

An LLM may propose a misconception hypothesis, evidence, and confidence. The application should seek a discriminating follow-up question before treating an ambiguous diagnosis as established. Store whether the hypothesis is tentative, supported, rejected, or resolved.

### 8.4 Adaptive next-step policy

Use deterministic policy logic to choose among:

1. Teach the next curriculum concept whose prerequisites are sufficiently supported.
2. Re-teach a weak prerequisite.
3. Switch explanatory strategy (visual, mathematical, computational, worked example, analogy, Socratic).
4. Give a targeted practice item.
5. Schedule a retrieval review.
6. Offer a learner-requested alternate explanation.

Every decision must have a concise, learner-readable reason. Bound lesson length and the number of adaptation cycles. Never get stuck repeating the same lesson indefinitely; after repeated difficulty, offer an alternative path, a prerequisite review, or a pause.

### 8.5 Retention

Add spaced retrieval practice to the MVP in a simple, explainable form. The review scheduler should depend on evidence and response quality, not only elapsed time. Store review events so they are reproducible. Do not claim long-term retention until the learner has returned and demonstrated it.

## 9. Lesson intermediate representation (Lesson IR)

The Lesson IR is the stable contract between AI generation, lesson compilation, audio, assessments, and the player. It must be versioned and validated with JSON Schema and Pydantic (or generated equivalents).

### 9.1 Required top-level shape

At minimum:

```json
{
  "schema_version": "1.0",
  "lesson_id": "stable-id",
  "course_id": "stable-course-id",
  "title": "A single perceptron",
  "concept_ids": ["nn.perceptron"],
  "objectives": ["Explain how inputs, weights, bias, and activation produce an output"],
  "source_refs": [],
  "estimated_minutes": 8,
  "segments": []
}
```

A segment should have a stable ID, type, title, estimated duration, narration text, optional audio asset/alignment metadata, optional visual scene reference, optional interaction/checkpoint, and completion criteria. Assessment items need a typed question format, expected answer or rubric, explanation, related concept IDs, difficulty, and source references when applicable.

### 9.2 Segment types

Support a small validated set first:

- `explanation`
- `visualization`
- `interaction`
- `checkpoint`
- `worked_example`
- `reflection`
- `summary`

Do not permit arbitrary component names or arbitrary frontend HTML from the model.

### 9.3 Scene artifact contract

Each generated Wanim scene must be a **complete, standalone Python file** stored as an asset with:

- Scene artifact ID and content hash.
- Wanim/Manim compatibility target.
- Selected scene class and presentation mode.
- Scene purpose and objective.
- The full Python source (not a partial patch).
- Allowed interaction inputs and expected output events.
- Deterministic test/validation metadata.

The scene-generation prompt must include the Wanim skill/reference, the scene brief, learner context needed for pedagogy, design constraints, supported APIs, and an explicit instruction to return one complete Python file. Do not split one scene into multiple model-generated code fragments. A generation request should produce the complete file in one call wherever possible.

### 9.4 IR validation

- Strict schema validation with unknown fields rejected or explicitly versioned.
- Validate stable IDs, references, durations, required text, and asset paths.
- Validate question types and answer formats.
- Validate that learning-critical interactions have a textual fallback.
- Reject arbitrary remote URLs, filesystem paths, shell instructions, and frontend script payloads.
- Preserve the original model response for diagnostics only when safe and useful; redact secrets and personal data.

## 10. Wanim integration

### 10.1 Official integration requirements

Use the official Wanim documentation as the source of truth:

- `https://wanim.org/`
- `https://wanim.org/docs/intro/`
- `https://wanim.org/docs/interactive/`
- `https://wanim.org/docs/usage/`
- `https://wanim.org/llms.txt`
- npm package: `@wanimjs/wanim`

At implementation time, inspect the official `llms.txt` and relevant package/API documentation. Create a maintained local skill at `skills/wanim-scene-authoring/SKILL.md`, with a concise API reference, supported subset, limitations, tested examples, generation instructions, and validation checklist. Record the official documentation retrieval date and package version. Update this skill when the pinned runtime changes.

### 10.2 Required early spike

Before building the complete lesson system, implement a small proof that:

1. Installs and pins the official Wanim package.
2. Renders a normal `Scene` from a complete Python file.
3. Renders an `InteractiveScene` with a slider/switch and a reactive visual.
4. Emits a host-readable event (where supported) from an interaction.
5. Handles pause, resume, teardown, theme, resize, and component unmount.
6. Runs inside the chosen Electron renderer/isolated player arrangement.
7. Works with the packaged build, not only the development server.

Record unsupported APIs and any packaging/security compromises as ADRs. Wanim is currently documented as an early preview, so pin the version and isolate it behind `WanimPlayerAdapter`.

### 10.3 Player architecture

- Build an Adle player shell around Wanim; Wanim is not the full lesson framework.
- Create a `WanimPlayerAdapter` boundary for load, play, pause, resume, reset, dispose, set theme, send host event, and receive scene event operations where the underlying library supports them.
- Keep narration, transcript, checkpoint UI, lesson progress, and accessibility controls outside the generated scene.
- Prefer Wanim's supported scene/player API or web component. Do not build against undocumented internals.
- Handle one scene/module at a time initially. Multi-scene bundling can be considered only after lifecycle reliability is proven.
- Provide a fallback visual/explanation when a Wanim scene fails, times out, or uses unsupported features.

### 10.4 Generated-code security

Wanim compiles/transpiles generated Python-compatible source into browser-executed JavaScript. Treat it as executable, untrusted content even if the intended Python subset has restrictions.

- Never run generated scene code in Electron's privileged main process.
- Renderer must have Node integration disabled, context isolation and sandbox enabled, a restrictive CSP, and no exposed filesystem/shell/API-key capabilities.
- Prefer a dedicated isolated player surface/origin or sandboxed frame with a narrow `postMessage` protocol. Validate message origin, schema, size, and allowed event names.
- Do not expose arbitrary host callbacks to scene code.
- Keep scene inputs declarative and bounded. Do not allow arbitrary remote imports, file access, network calls, OS calls, or external scripts.
- Perform static checks on generated source and validate output messages. Static checks are defense-in-depth, not a claim of complete sandboxing.
- Do not weaken Electron security settings merely to make Wanim load. If the runtime requires a dangerous relaxation, stop and document the risk and alternatives before proceeding.

### 10.5 Wanim design conventions

- 16:9 stage; preserve safe margins and responsive scaling.
- Use a consistent Adle-compatible visual palette while ensuring mathematical color semantics remain clear.
- Use `Text` for prose and `MathTex` for ordinary mathematical notation; avoid unsupported LaTeX packages.
- Keep interactive `blueprint()` reactions computationally cheap; create display objects once and update them rather than constructing text on every frame.
- Make interactions purposeful and explain what changing a control demonstrates.
- Prefer a concise number of visual elements and legible labels over dense scenes.
- Include a no-interaction narrative path so the concept remains understandable without a mouse.

## 11. Audio and synchronization

### 11.1 Provider architecture

Define a TTS provider interface. Initial implementations:

- **Local TTS:** default/preferred path. Evaluate a lightweight, distributable local engine/voice model (for example Piper or Kokoro) for OS support, latency, package size, quality, and license before selection. Do not assume a model can be redistributed without checking its license.
- **System speech fallback:** use OS/browser speech synthesis only when available and clearly label its limitations; voice availability differs by platform.
- **ElevenLabs:** optional cloud provider, explicit opt-in, separate API key, and clear disclosure that narration text is sent to the provider.

Do not require cloud TTS for the MVP to function.

### 11.2 Narration generation

- Generate narration in independently cacheable lesson segments, not one monolithic chapter audio file.
- Cache by normalized narration text, voice/model ID, language, speed, and relevant settings.
- Preserve text transcript even when audio is unavailable.
- Support regeneration of only the changed segment.
- Store generated audio in the app-controlled asset directory and link it to the lesson segment.

### 11.3 Timing model

Use a shared **lesson timeline**. Audio playback time is the authoritative clock for narration synchronization; do not coordinate with wall-clock `setTimeout` calls.

- Prefer word-level alignment metadata if the selected TTS provider provides it reliably.
- If not, use a local forced aligner where practical, or fall back to sentence/phrase-level timing. Never invent equal word durations and present them as accurate alignment.
- Visual events reference timeline timestamps or segment IDs.
- The player owns audio clock, pause/resume, seek, and checkpoint behavior.
- Wanim scene progression should be segment-based initially. Investigate accurate in-scene timestamp synchronization during the integration spike; do not pretend a scene is synchronized if only segment start/end are aligned.
- User interactions pause the timeline when appropriate and must not be overwritten by background prefetch.
- Test drift, pause/resume, seeking, slow playback, and audio-device interruption.

## 12. Performance and progressive generation

### 12.1 Progressive generation pipeline

1. Display course context and objectives immediately.
2. Generate a short plan for the current concept.
3. Generate/validate the first lesson segment bundle.
4. Start preparing the first scene and narration as soon as inputs are available.
5. Display the first ready segment while later segments are generated in the background.
6. Record learner input and update state before selecting the next segment.
7. Prefetch only a bounded likely-next segment. Cancel obsolete work after an adaptation decision.

Do not generate an entire course's detailed animations upfront. Generate at concept/lesson granularity.

### 12.2 Caching

- Document extraction by source hash and parser version.
- Embeddings by chunk hash and embedding model/version.
- Lesson plan by concept ID, objective set, relevant learner state version, strategy, and model version.
- Scene artifact by full generation input hash and Wanim skill/runtime version.
- TTS by text and voice/model configuration.
- Do not cache learner-specific outputs across learners without a privacy and correctness analysis.

### 12.3 Performance budgets

Measure first; do not claim arbitrary performance success. Establish baselines on a documented reference machine.

Initial targets for a normal local installation:

- App cold-start to usable home screen: target under 4 seconds on reference hardware.
- Home navigation and ordinary UI interactions: target 60 FPS and no blocking synchronous work.
- Course database queries: target under 150 ms for typical local course sizes.
- A cached lesson segment should appear without LLM inference.
- The first useful lesson content should appear before all later segments/assets are complete.
- Wanim player startup, scene compilation, and first-frame latency must be measured separately; optimize based on real results.
- All long-running tasks expose progress, cancellation where safe, and recoverable errors.

## 13. Reliability, privacy, and security

- Store all course data locally by default.
- Make all external calls visible through settings and contextual disclosure: LLM inference, optional cloud TTS, optional update checks.
- Never send source documents, learner state, or narration to external services except for the minimum data required by a user-triggered AI operation and the services the user enabled.
- Provide course export, app data backup, and permanent deletion controls.
- Encrypt API keys using an OS credential store or Electron `safeStorage` through a secure main-process bridge. Never use plaintext config files.
- Do not log API keys, full documents, sensitive learner responses, or raw auth headers.
- Use safe file naming, path validation, size limits, content-type checks, and parser timeouts.
- Treat uploaded documents and model output as untrusted input; mitigate prompt injection by separating instructions from source excerpts and withholding tool privileges from the model.
- Use parameterized SQL and validate all IPC/API payloads.
- Pin dependencies, audit licenses, and run dependency/security checks in CI.
- Provide graceful behavior when offline, when a model quota is exhausted, or when a TTS engine is unavailable.

## 14. Quality engineering and testing strategy

Testing is a first-class product feature. Do not stop at a successful build or a few unit tests.

### 14.1 Test pyramid

**Unit tests**

- Lesson IR schema and version migration.
- Curriculum graph cycle detection and prerequisite resolution.
- BKT updates, evidence handling, confidence, and mastery criteria.
- Mistake taxonomy and tentative misconception lifecycle.
- Review scheduler.
- Provider quota limiter and retry logic.
- Retrieval ranking/provenance.
- Audio timeline mapping and cache key generation.
- Input sanitization and path validation.

**Integration tests**

- SQLite schema migrations, rollback/backup/restore.
- Document parsers with real fixtures and malformed files.
- FTS5 retrieval and optional vector extension/fallback.
- Model provider using a deterministic fake server; tests must not consume real AIHubMix quota.
- Structured output validation and invalid-response recovery.
- TTS provider interfaces using fixture audio/alignments.
- Wanim adapter with known-good scenes and known-bad/unsupported scene fixtures.
- Electron main/preload/backend process lifecycle and authenticated bridge.

**End-to-end tests (Playwright)**

At minimum, automate a complete user journey:

1. First launch with no provider key.
2. Open sample course without configuring cloud inference.
3. Create a course from a sample syllabus.
4. Review and modify a generated curriculum fixture.
5. Start a lesson and play/pause narration.
6. Interact with a Wanim slider and observe the visual response.
7. Submit correct, incorrect, and hinted answers.
8. Verify learner state and next-step rationale change.
9. Close and reopen the app; verify course and lesson resume.
10. Simulate provider quota exhaustion and verify clear recovery behavior.
11. Simulate Wanim failure and verify fallback explanation.
12. Export, delete, and restore a test course.

**Visual and accessibility tests**

- Screenshot tests for home, course setup, curriculum map, lesson player, progress, and settings in light/dark themes.
- Run axe-core and keyboard-only flows.
- Verify focus visibility, contrast, reduced-motion behavior, text scaling, and screen-reader labels.
- Test common desktop window sizes and resizing.

**Performance tests**

- Cold start, lesson-player mount, database read/write, document extraction, embedding throughput, Wanim first frame, audio startup, and large syllabus import.
- Test cancellation and background work under load.

### 14.2 Quality gates

A phase cannot be marked complete unless:

- Its acceptance criteria are met.
- Relevant tests have been added and executed.
- Formatting, linting, type checking, and security checks pass.
- The actual application has been launched and exercised when UI is involved.
- Known limitations are recorded, not hidden.
- Documentation and `AGENTS.md` are updated if contracts, commands, structure, or workflows changed.
- A coherent, atomic Git commit exists for the finished phase.

Never report a test as passed if it was not run. Distinguish `passed`, `failed`, `not run`, and `blocked`.

## 15. Documentation and LLM maintainability

The codebase will be maintained by successive LLM agents. Documentation must therefore preserve operational context, not just describe product features.

Required maintained documents:

- `AGENTS.md`: entry point for every coding agent; current architecture, rules, commands, workflows, test requirements, security rules, context-compaction procedure, and links to deeper docs.
- `README.md`: user-facing product description, install/dev/build instructions, configuration, known limitations.
- `PROMPT.md`: canonical coding-agent instructions.
- `PLAN.md`: milestones and acceptance criteria, with completion status updated as work progresses.
- `DESIGN_SYSTEM.md`: brand/design tokens, components, usage rules, examples.
- `TESTING.md`: test commands, test layers, fixtures, end-to-end flows, and current gaps.
- `SECURITY.md`: threat model, data flows, generated-code boundary, secret handling, reporting process.
- `CONTRIBUTING.md`: branch/commit convention, local workflow, code standards, PR checklist.
- `CHANGELOG.md`: user-visible changes by release/version.
- `docs/architecture/`: current architecture and data-flow diagrams.
- `docs/decisions/`: Architecture Decision Records (ADRs), numbered and immutable after acceptance (supersede rather than silently rewrite).
- `docs/engineering/PROJECT_STATE.md`: concise current state, working branch, latest commit, active milestone, completed tasks, blockers, next exact actions, test status, and uncommitted changes.
- `docs/engineering/DECISIONS.md`: short index of important current decisions and ADR references.
- `skills/wanim-scene-authoring/`: complete local scene-generation knowledge and examples.

### 15.1 Context compaction / agent handoff

Before ending a work session or compacting context, the agent must:

1. Update `docs/engineering/PROJECT_STATE.md` with exact current state and next action.
2. Update the milestone checklist in `PLAN.md`.
3. Update root/subdirectory `AGENTS.md` with new durable rules, commands, or boundaries.
4. Record architectural decisions in ADRs.
5. Record test commands and actual results, including failures and skipped tests.
6. Record outstanding uncommitted files and why they remain uncommitted.
7. Avoid copying the full chat transcript. Preserve facts, commands, decisions, and blockers only.

A new agent should be able to resume from `AGENTS.md` and `PROJECT_STATE.md` without relying on prior chat history.

### 15.2 Commit history

- Use Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `docs(scope): ...`, `refactor(scope): ...`, `chore(scope): ...`.
- Make small, coherent, atomic commits after a quality gate passes.
- Do not create fake historical commits, empty commits, or commits claiming tests that were not run.
- Never amend, reset, or rewrite user commits unless explicitly requested.
- Never force-push.
- Keep generated build output, databases, API keys, local voice models, cache files, and user content out of Git.
- Ensure a clean working tree at handoff, or clearly document every remaining change.

## 16. Delivery milestones

The coding agent must work sequentially through these milestones. It may parallelize independent non-LLM work only when this does not increase complexity or violate the provider quota. Update the status in this plan as work proceeds.

### M0 — Repository reconnaissance and engineering foundation

**Tasks**
- Inspect the existing repository and environment before changing files.
- Preserve existing user work and Git history.
- Create the monorepo structure and select pinned toolchain versions.
- Establish `AGENTS.md`, README, CONTRIBUTING, TESTING, SECURITY, DESIGN_SYSTEM, CHANGELOG, project state, and ADR process.
- Add formatting, linting, type checks, tests, pre-commit hooks if useful, and CI.
- Record baseline commands and environment assumptions.

**Acceptance**
- A clean clone can install dependencies and run lint, type checks, unit tests, and a basic desktop dev build.
- Documentation provides a reliable onboarding path.
- No secrets or local data are committed.

### M1 — Desktop shell and Sprout design system

**Tasks**
- Implement Electron main/preload/renderer separation.
- Implement secure Python child-process startup and health checks, even if backend features are stubbed.
- Build theme tokens and reusable components.
- Build home, onboarding/provider settings, empty states, and navigation.
- Add light and dark themes, keyboard focus, reduced motion, and responsive desktop layouts.

**Acceptance**
- App launches without a model key.
- Provider key can be added/removed without exposing it to renderer JavaScript or logs.
- No generic filesystem/shell access is exposed through preload.
- Screens use the design system; no ad hoc inconsistent visual language.

### M2 — Persistence, document ingestion, and source library

**Tasks**
- SQLite schema and Alembic migrations.
- App data directory and safe asset store.
- PDF/MD/TXT/DOCX parsers with provenance.
- FTS5 search; add optional local embeddings/vector extension after packaging validation.
- Course/source library UI, error recovery, and import progress.

**Acceptance**
- Import fixtures, preserve page/section citations, avoid duplicates by content hash, and recover from malformed files.
- Database survives restart and migration; backup/restore test passes.
- Ingestion works offline.

### M3 — Curriculum graph and learner model foundation

**Tasks**
- Concept/objective/prerequisite domain models.
- Graph validation and curriculum editing UI.
- Local retrieval with provenance.
- Learner profile, working memory, concept knowledge state, event log.
- Initial transparent knowledge-tracing model and review scheduler.
- Unit/property tests for graph and state transitions.

**Acceptance**
- Curriculum graph has no unresolved cycles/references.
- Learner knowledge is stored structurally, not primarily in vectors.
- Every mastery transition can be explained from recorded evidence.
- User can inspect and edit the curriculum.

### M4 — Wanim integration spike and lesson IR

**Tasks**
- Read official Wanim documentation and `llms.txt`.
- Create local `wanim-scene-authoring` skill and golden scene fixtures.
- Pin `@wanimjs/wanim` and implement the smallest working renderer integration.
- Test normal and interactive scenes, host events, lifecycle, and packaging.
- Define/version Lesson IR and strict validation.
- Implement Wanim adapter, static validation, and fallback rendering.
- Complete threat-model review of generated scene execution.

**Acceptance**
- A known-good interactive Wanim scene runs inside the desktop app and packaged build.
- User input visibly changes a scene.
- Host receives only allowlisted, schema-validated events.
- Bad/unsupported scene fails safely with fallback content.
- No Node/process/filesystem/API-key access is exposed to generated scene code.
- Wanim limitations and tested version are documented.

### M5 — Lesson generation, audio, and timeline

**Tasks**
- Provider abstraction and AIHubMix client.
- Quota manager, structured output validation, streaming where useful.
- Planner/content generator and one-request complete Wanim-file generation path.
- Local TTS adapter and optional ElevenLabs adapter.
- Segment/word alignment, audio cache, shared timeline, transcript highlighting.
- Progressive segment preparation and cancellation.

**Acceptance**
- A fixture curriculum concept generates a valid lesson bundle.
- A full Wanim scene is generated as one standalone Python file per request.
- Local TTS works without a network dependency after model installation.
- Audio pause/resume and checkpoint behavior are correct.
- Missing word alignment falls back honestly to phrase/segment timing.
- Provider quota errors do not break the app or trigger retry loops.

### M6 — Assessment, misconceptions, and adaptation

**Tasks**
- Typed formative assessment items.
- Deterministic scoring for supported closed-form question types.
- Rubric-bounded evaluation for open responses.
- Evidence event capture and confidence input.
- Misconception hypothesis lifecycle and diagnostic follow-up selection.
- Adaptive next-step policy with human-readable rationale.
- Review scheduling and course progress state.

**Acceptance**
- Correct, incorrect, guessed, hinted, and arithmetic-slip scenarios produce distinct evidence paths where supported.
- The system can switch teaching strategy and revisit prerequisites.
- It does not declare mastery after one lucky answer.
- Learner can override/skip an explanation and request another format.

### M7 — Complete user experience and sample course

**Tasks**
- Finish course setup, curriculum map, lesson player, progress, settings, and session summary.
- Add bundled neural-network sample course and full lesson fixtures.
- Add export/delete/restore flows.
- Add onboarding, empty/loading/error states, keyboard and accessibility polish.
- Run complete end-to-end journey with fake inference and real local Wanim/TTS fixtures.

**Acceptance**
- A new user can complete the entire learning loop without developer tools.
- User can resume a lesson after app restart.
- Failure states are understandable and recoverable.
- UI is consistent with `DESIGN_SYSTEM.md` and passes accessibility gates.

### M8 — Release hardening

**Tasks**
- Packaging and clean-machine installation tests for supported OS targets.
- Dependency/license/security review.
- Performance profiling and optimization.
- Database migration, backup/restore, and app update safety checks.
- Crash/error reporting design that does not upload learner data by default.
- Final docs, release notes, known limitations, and reproducible build instructions.

**Acceptance**
- A clean installation starts and can run the sample course.
- No unhandled startup or shutdown failures in the test matrix.
- Critical end-to-end flows pass.
- No known critical/high security findings remain unresolved.
- Final test report and release checklist are complete.

## 17. Release acceptance checklist

Adle is not ready to call production-quality until all applicable items below are true:

Filled in on 2026-11-20. A ticked item ran and passed; the evidence for each, and the status
of the one that is not ticked, is in `docs/engineering/RELEASE_CHECKLIST.md`. **One item is
open, so by this list Adle is not yet production-quality.** It cannot be closed from this
machine: it waits for the repository to have a remote.

- [x] First launch is understandable without reading technical documentation.
- [x] App works without an AI provider configured using sample/local content.
- [x] Topic/syllabus import and source provenance work locally.
- [x] Curriculum graph is reviewable and editable.
- [x] Lesson IR is versioned and validated.
- [x] Complete Wanim Python scene files are generated and executed only in the isolated player boundary.
      *Executed only in the isolated player: in development and in the packaged app.
      Generated: by a real model on 2026-11-20 (Kimi K3.1 Pro through NVIDIA NIM, ADR-021),
      through Adle's own generation service: two lessons with three scenes between them,
      every one of which passed the static policy on the first try and ran in the
      isolated player in both themes. Those runs were driven from a script and looked at
      by hand; no person has yet sat a generated lesson, and AIHubMix's model has still
      not answered.*
- [x] Audio/transcript controls work, with honest alignment fallback.
- [x] Learner interactions produce persistent events.
- [x] Mastery is evidence-based and explainable.
- [x] Misconceptions are treated as hypotheses until supported.
- [x] Next-step adaptation is bounded, understandable, and user-controllable.
- [x] Retrieval practice exists and persists.
- [x] Quota exhaustion, network loss, TTS failure, Wanim failure, and malformed model output are recoverable.
- [x] Data export, deletion, backup, and restore are tested. *("Export" is a copy of everything.)*
- [x] Light/dark themes, accessibility, and reduced motion are tested. *(By tools. No person
      has used it with a screen reader.)*
- [ ] CI, unit, integration, E2E, security, and packaging checks pass.
      *Unit, integration, end-to-end, security, licence, and packaging checks pass on Windows,
      against the built files and against the packaged app. CI has never run: there is no
      remote. Nothing has run on macOS or Linux.*
- [x] `AGENTS.md`, `PROJECT_STATE.md`, ADRs, README, and all developer docs are current.
- [x] Git history is coherent, atomic, and honest.

## 18. Current implementation status

Status is updated as work proceeds. The detailed, current picture (test results, findings, next
actions) is in `docs/engineering/PROJECT_STATE.md`. A milestone is "Done" only when its acceptance
criteria were demonstrated by tests that were actually run.

_Last updated: 2026-11-20._

| Milestone | Status | Notes and acceptance evidence |
|---|---|---|
| M0 — Foundation | **Done** | npm workspaces + uv; pinned stack (ADR-001); `npm run check` runs format, lint, types, and unit tests for TypeScript and Python; docs, ADRs, nested `AGENTS.md`. CI workflow written but **not run** (no remote). |
| M1 — Desktop/design system | **Done** | Electron main/preload/renderer separation; supervised Python core with stdin token handshake (ADR-002); `adle://` protocol (ADR-003); Sprout tokens and 20 components with contrast tests (ADR-006); welcome, library, settings. Acceptance shown by `e2e/first-run`, `provider-key`, `security`, `appearance-a11y` specs. |
| M2 — Persistence/ingestion | **Done** | SQLite with transactional Alembic migrations, automatic backup before any upgrade, tested restore, refusal of newer or foreign databases; local PDF/DOCX/Markdown/text parsers in a killable worker process with type, size, and time limits; structural chunking with page/section provenance; duplicates by SHA-256; FTS5 search; course and materials screens with import by dialog or drop (ADR-007). Acceptance shown by `test_database`, `test_ingestion`, `test_courses_and_sources`, `test_isolated_extraction`, and `e2e/course-materials` (import, provenance, restart, removal, duplicates) with the session's network block proving it works offline. **Not built:** vector search (optional in this plan; deferred to packaging). |
| M3 — Curriculum/learner model | **Done** | Pure, property-tested rules for the concept graph (`curriculum/graph.py`) and for knowledge tracing, mastery, and review (`learner_model/`); every write validated, loops refused with the loop named; curriculum screen with list and map, objectives, prerequisites with reasons, links to materials, and an outline drafted from headings without AI; knowledge stored as an append-only record with a sentence for every change, the derived state rebuildable, and no score exposed (ADR-009). Acceptance shown by `test_curriculum_graph`, `test_knowledge_tracing`, `test_review_schedule`, `test_curriculum_api`, `test_learner_api`, and `e2e/curriculum`, `e2e/learning-preferences`. **Deferred:** working memory and the interaction event log arrive with lesson sessions; AI-proposed curricula arrive with the provider client (M5). |
| M4 — Wanim/IR | **Done** | Isolated player frame, `WanimPlayerAdapter`, validated host protocol, static scene policy, authoring skill with three tested examples, threat model (ADR-004). Lesson IR 1.0 as strict Pydantic models with a generated JSON Schema; one validating gateway for lessons; scenes re-checked on every read and withheld, not fatal, if they fail; answer keys kept in the core with deterministic scoring; a lesson player (narration beats, board, transcript, scene cues, questions, progress, finish) and the first lesson of the sample course (ADR-010). Acceptance shown by `test_lesson_ir`, `test_lessons_api`, `test_scoring`, `test_answers_api`, the renderer's `lesson/*.test.ts`, and `e2e/scene-player`, `security`, `lesson` (a full lesson, resume, a scene that breaks while playing, a scene the core withholds). The same journeys pass against the packaged build (M8). |
| M5 — Generation/audio | **Done** | Provider client, quota gateway with recorded usage, generation as jobs with a fixed number of requests, a draft format compiled into the Lesson IR (ADR-012); interface to propose a curriculum and to create a lesson, with progress, cancel, and every failure state; usage shown in Settings; narration read aloud by local system voices with honest word highlighting, a voice and volume setting, and silent captions as fallback (ADR-013). Acceptance shown by `test_quota`, `test_provider_client`, `test_model_gateway`, `test_drafts`, `test_generation_api`, the renderer's `speech.test.ts` and `generation.test.ts`, and `e2e/generation`, `e2e/narration`. A second provider, NVIDIA NIM, chosen by the learner, with a key of its own and a provider's next model standing in when its first is not available (ADR-021; `test_provider_choice`, `e2e/providers`). **A real model has written lessons:** on 2026-11-20 Kimi K3.1 Pro through NVIDIA NIM wrote two lessons with their scenes and a twelve-concept curriculum through Adle's generation service; what that showed (TeX written with one backslash, a curve filled by `set_opacity`) is fixed and tested. AIHubMix's free model has still not answered (a relay error for one account; the other must be topped up). |
| M6 — Assessment/adaptation | **Done** | Hypotheses about mistakes computed from the record, with the four statuses, discriminating follow-up questions, and a way for the learner to set one aside; slips counted as partly right; repeats counted in full only after a gap; questions kept for practice and review in the Lesson IR; a deterministic next-step policy with a reason for every step, alternatives, a bound on explanations per concept, and no return to a lesson that did not help; a Learn tab (next step, progress in words, hypotheses), a practice and review screen, "what next" at the end of a lesson, and "This did not help" with other ways forward; teaching strategy chosen by the learner or rotated (ADR-014). Acceptance shown by `test_misconceptions`, `test_misconception_wording`, `test_practice_and_next_step`, `test_tracing_slips_and_dismissals`, `test_learning_api` (distinct paths for right, hinted, unsure, slipped, wrong, and skipped answers; a review that comes due), `test_practice_questions_and_strategies`, the renderer's `learning.test.ts`, and `e2e/learning`. **Not built:** grading of open answers by the model, and hypotheses proposed by the model (see deviations). |
| M7 — Complete UX/sample course | **Done** (two items left open by decision) | The bundled sample course is complete, with a lesson for each of its eight concepts (nine animated scenes, two interactions, questions tagged with the mistakes their wrong options point at, practice questions). Acceptance so far shown by `test_lessons_api` (the course installs whole, every lesson passes the gateway), `test_scene_policy` (every sample scene passes), `sample-content-math.test.ts` (every formula typesets), `e2e/lesson` (every lesson played from start to finish) and `e2e/scene-player` (every scene run in both themes). Also done: saving a copy of everything, restoring from one, and deleting everything in Settings → Privacy & data (ADR-016), shown by `test_data_copy`, `test_process_lifecycle`, `data.test.ts`, and `e2e/data` (save, delete a course, restore, undo; delete everything). Also done: the session summary on the Learn tab, as the latest sitting read off the record: right answers per concept, what still needs evidence, planned reviews, with the suggested next step as its "Continue" (ADR-017), shown by `test_sitting`, `test_session_summary_api`, and `e2e/learning`. Polish: axe on every outcome of the new screens; focus kept after "That was a slip". **Left open:** narration and animation are synchronised per segment, not per sentence (Wanim's slides mode was not tried); screenshots are saved for review, not compared against baselines. |
| M8 — Release hardening | **Done as far as one Windows machine allows** | Done: a crashed or hung page, an uncaught error in the main process, and a core that dies are handled with a plain message, a way on, and a local log; nothing is reported anywhere (ADR-018), shown by `recovery.test.ts` and `e2e/recovery` (the page's process is killed for real). Packaging (ADR-019): `npm run package` builds a folder that runs by itself, with a private Python for the core started cut off from the computer it is on, and the binary's fuses set. The whole end-to-end suite passes against the packaged app (`npm run e2e:packaged`), which re-verifies player isolation there; the release build passes a start-up check from outside (`npm run package:check`). Licences are inventoried and checked in every gate (`THIRD_PARTY.md`); `npm audit` and `pip-audit` are clean; timings and sizes are in `PERFORMANCE.md`; `RELEASE_CHECKLIST.md` holds the build steps, the acceptance list with evidence, and the known limitations. **Not done:** an installer and code signing; macOS and Linux; a clean-machine installation; CI has never run (no remote); a generated lesson sat by a person. |

### Deviations from this plan (each has an ADR)

- **The design system is a second edition, and no longer "playful" in its chrome.** The owner
  asked for a professional-grade design. A serif sets what is read and a sans what is
  operated; radii are 6, 8, 12, and 16, not the 10–20 of section 4.2; badges are not pills;
  there are three grounds; a lesson has the whole window. The tokens, the contrast rules, and
  the brand's teal are as before (ADR-022).
- **Both providers can be used together.** Section 6.3 says a provider change needs explicit
  configuration and disclosure. "Automatic" is that configuration: a setting the learner can
  see, which only ever uses providers they gave a key to, and every request says where it
  may go before it is sent and who wrote the answer after. With one provider chosen, nothing
  moves a request to another (ADR-023).
- **One request in flight at each provider**, not one overall (section 6.3): two providers are
  two accounts, and a question to one does not wait for a lesson at the other (ADR-023).
- **A learner can ask a question during a lesson** (section 3.3's "request a simpler
  explanation, derivation, example"), as a note beside the part and not as a chat (ADR-024).
- **A break is offered while a lesson is written**, and the learner is told when it is ready
  by a notification with fixed words. Section 12's "display the first ready segment while
  later segments are generated" is still not done (ADR-026).
- **The typefaces are Geist** (sans, mono, serif), at the owner's request (ADR-025).
- **There are two AI providers, not one.** Section 6.1 names AIHubMix and one model. The
  owner asked for NVIDIA NIM beside it: Kimi K3.1 Pro, with Mistral Large 4 and then GLM 5.3
  Flash standing in while the one before is not available. The learner chooses the provider
  and nothing else does; each has its own key, sent only to it, and its own count; a
  stand-in is always said. NVIDIA publishes no daily limit, so Adle keeps to its own there
  (ADR-021).
- **Colour tokens** adjusted where the starting values missed WCAG AA: `muted`, a separate filled
  `action` colour, `border-strong`, and `*-text` companions for accents (ADR-006).
- **The brand is the owner's "ad" mark and its teal**, not the green of section 4.2. Success keeps
  the green (ADR-011).
- **Narration uses the operating system's voices**, not a bundled engine, and there is no cloud
  voice, audio file, or audio cache (ADR-013).
- **The packaged core is a private Python, not a frozen executable**, and the package is a
  folder, not an installer. Clean-machine installation tests on the supported systems were
  not possible; the release build is started from outside with a stripped environment
  instead (ADR-019).
- **Crash and error reporting is a local log and nothing else.** There is no reporting
  service, not even one that is off by default (ADR-018).
- **"Export" is a copy of everything, not of one course.** A single file holds all courses and
  can be restored here or on another computer; a restore is done while the core starts and can
  be undone. Exporting one course to share with someone else is not built (ADR-016).
- **A lesson is generated whole**, in one request plus one per scene, not progressively segment
  by segment: there is nothing to stream in parts (ADR-012).
- **Runtime quota defaults** are 4 requests a minute, 90 a day, and 900,000 tokens a day, as
  section 6.3 says; sampling parameters are never sent, as the provider advises for this model
  (ADR-012).
- **There is no `packages/lesson-ir`.** The Lesson IR is defined once, in the core, and its JSON
  Schema is generated into `packages/contracts/schemas/` with the API contract (ADR-010).
- **Questions are scored and recorded from M4**, not M6: a lesson without working questions is
  not a slice a learner can use. M6 keeps misconceptions, the next-step policy, review, and
  model-assisted grading of open answers (ADR-010).
- **Narration is silent captions at reading pace until M5**, behind the interface speech will
  use (ADR-010).
- **No Vite dev server:** development uses the same built files and protocol as production (ADR-003).
- **Player sandbox** uses a dedicated per-frame origin with `allow-same-origin`, not an opaque
  origin, because the pinned Wanim runtime cannot run in one (ADR-004).
- **TypeScript 6 / ESLint 9** instead of the newest majors, for lint-plugin compatibility; **httpx2**
  instead of httpx (ADR-001).
- **Migrations** live inside the Python package (`adle_core/migrations/`), not beside it, so they
  ship with a packaged build without extra data-file handling (ADR-007).
- **Failed imports are not stored as rows.** A rejected file leaves nothing behind; the reason is
  reported in the import summary (ADR-007).
- **The main window is created visible**, not hidden until `ready-to-show`, which occasionally
  never came (ADR-008).
- **A curriculum can be drafted from headings without AI**, and a learner can say how well they
  already know a concept; neither was in this plan. Working memory and the event log move from
  M3 to the lesson work, where their events come from (ADR-009).
- **Open answers are self-assessed against a rubric, and hypotheses come from how questions
  are written**, not from the model. Either would send the learner's own answers to the provider
  and spend requests the daily allowance does not have (ADR-014).
- **A course opens on a "Learn" tab** (what to do next, and progress) that this plan folds into
  "Course progress" and the lesson player. The interaction event log is `learner_events`; it
  holds only events something reads (ADR-014).
- **Work happens on the `dev` branch.** `main` keeps the original plan until the owner merges.

---

## 19. External technical references

These are starting references, not substitutes for verifying pinned versions during implementation.

- AIHubMix Coding Kimi K3 Free: <https://aihubmix.com/model/coding-kimi-k3-free>
- AIHubMix model catalog: <https://aihubmix.com/models>
- Wanim home: <https://wanim.org/>
- Wanim introduction: <https://wanim.org/docs/intro/>
- Wanim interactive controls: <https://wanim.org/docs/interactive/>
- Wanim usage/player integration: <https://wanim.org/docs/usage/>
- Wanim code-generation guide: <https://wanim.org/llms.txt>
- Electron security guidance: <https://www.electronjs.org/docs/latest/tutorial/security>
- SQLite: <https://sqlite.org/docs.html>
- FastAPI: <https://fastapi.tiangolo.com/>
- Playwright: <https://playwright.dev/docs/intro>
